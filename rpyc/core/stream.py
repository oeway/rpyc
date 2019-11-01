"""
An abstraction layer over OS-dependent file-like objects, that provides a
consistent view of a *duplex byte stream*.
"""
import sys
from rpyc.external import socket, errno
from rpyc.external.timeout import Timeout
from rpyc.lib import socket_backoff_connect
from rpyc.lib.compat import poll, select_error, BYTES_LITERAL, get_exc_errno, maxint  # noqa: F401


retry_errnos = (errno.EAGAIN, errno.EWOULDBLOCK)


class Stream(object):
    """Base Stream"""

    __slots__ = ()

    def close(self):
        """closes the stream, releasing any system resources associated with it"""
        raise NotImplementedError()

    @property
    def closed(self):
        """tests whether the stream is closed or not"""
        raise NotImplementedError()

    def fileno(self):
        """returns the stream's file descriptor"""
        raise NotImplementedError()

    def poll(self, timeout):
        """indicates whether the stream has data to read (within *timeout*
        seconds)"""
        timeout = Timeout(timeout)
        try:
            p = poll()   # from lib.compat, it may be a select object on non-Unix platforms
            p.register(self.fileno(), "r")
            while True:
                try:
                    rl = p.poll(timeout.timeleft())
                except select_error:
                    ex = sys.exc_info()[1]
                    if ex.args[0] == errno.EINTR:
                        continue
                    else:
                        raise
                else:
                    break
        except ValueError:
            # if the underlying call is a select(), then the following errors may happen:
            # - "ValueError: filedescriptor cannot be a negative integer (-1)"
            # - "ValueError: filedescriptor out of range in select()"
            # let's translate them to select.error
            ex = sys.exc_info()[1]
            raise select_error(str(ex))
        return bool(rl)

    def read(self, count):
        """reads **exactly** *count* bytes, or raise EOFError

        :param count: the number of bytes to read

        :returns: read data
        """
        raise NotImplementedError()

    def write(self, data):
        """writes the entire *data*, or raise EOFError

        :param data: a string of binary data
        """
        raise NotImplementedError()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


class ClosedFile(object):
    """Represents a closed file object (singleton)"""
    __slots__ = ()

    def __getattr__(self, name):
        if name.startswith("__"):  # issue 71
            raise AttributeError("stream has been closed")
        raise EOFError("stream has been closed")

    def close(self):
        pass

    @property
    def closed(self):
        return True

    def fileno(self):
        raise EOFError("stream has been closed")


ClosedFile = ClosedFile()


class SocketStream(Stream):
    """A stream over a socket"""

    __slots__ = ("sock",)
    MAX_IO_CHUNK = 64000  # read/write chunk is 64KB, too large of a value will degrade response for other clients

    def __init__(self, sock):
        self.sock = sock

    @classmethod
    def _connect(cls, host, port, family=socket.AF_INET, socktype=socket.SOCK_STREAM,
                 proto=0, timeout=3, nodelay=False, keepalive=False, attempts=6):
        family, socktype, proto, _, sockaddr = socket.getaddrinfo(host, port, family,
                                                                  socktype, proto)[0]
        s = socket_backoff_connect(family, socktype, proto, sockaddr, timeout, attempts)
        try:
            if nodelay:
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            if keepalive:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                # Linux specific: after <keepalive> idle seconds, start sending keepalives every <keepalive> seconds.
                is_linux_socket = hasattr(socket, "TCP_KEEPIDLE")
                is_linux_socket &= hasattr(socket, "TCP_KEEPINTVL")
                is_linux_socket &= hasattr(socket, "TCP_KEEPCNT")
                if is_linux_socket:
                    # Drop connection after 5 failed keepalives
                    # `keepalive` may be a bool or an integer
                    if keepalive is True:
                        keepalive = 60
                    if keepalive < 1:
                        raise ValueError("Keepalive minimal value is 1 second")

                    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)
                    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, keepalive)
                    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, keepalive)
            return s
        except BaseException:
            s.close()
            raise

    @classmethod
    def connect(cls, host, port, **kwargs):
        """factory method that creates a ``SocketStream`` over a socket connected
        to *host* and *port*

        :param host: the host name
        :param port: the TCP port
        :param family: specify a custom socket family
        :param socktype: specify a custom socket type
        :param proto: specify a custom socket protocol
        :param timeout: connection timeout (default is 3 seconds)
        :param nodelay: set the TCP_NODELAY socket option
        :param keepalive: enable TCP keepalives. The value should be a boolean,
                          but on Linux, it can also be an integer specifying the
                          keepalive interval (in seconds)
        :param ipv6: if True, creates an IPv6 socket (``AF_INET6``); otherwise
                     an IPv4 (``AF_INET``) socket is created

        :returns: a :class:`SocketStream`
        """
        if kwargs.pop("ipv6", False):
            kwargs["family"] = socket.AF_INET6
        return cls(cls._connect(host, port, **kwargs))

    @classmethod
    def unix_connect(cls, path, timeout=3):
        """factory method that creates a ``SocketStream`` over a unix domain socket
        located in *path*

        :param path: the path to the unix domain socket
        :param timeout: socket timeout
        """
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.settimeout(timeout)
            s.connect(path)
            return cls(s)
        except BaseException:
            s.close()
            raise

    @classmethod
    def ssl_connect(cls, host, port, ssl_kwargs, **kwargs):
        """factory method that creates a ``SocketStream`` over an SSL-wrapped
        socket, connected to *host* and *port* with the given credentials.

        :param host: the host name
        :param port: the TCP port
        :param ssl_kwargs: a dictionary of keyword arguments to be passed
                           directly to ``ssl.wrap_socket``
        :param kwargs: additional keyword arguments: ``family``, ``socktype``,
                       ``proto``, ``timeout``, ``nodelay``, passed directly to
                       the ``socket`` constructor, or ``ipv6``.
        :param ipv6: if True, creates an IPv6 socket (``AF_INET6``); otherwise
                     an IPv4 (``AF_INET``) socket is created

        :returns: a :class:`SocketStream`
        """
        pass

    @property
    def closed(self):
        return self.sock is ClosedFile

    def close(self):
        if not self.closed:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
        self.sock.close()
        self.sock = ClosedFile

    def fileno(self):
        try:
            return self.sock.fileno()
        except socket.error:
            self.close()
            ex = sys.exc_info()[1]
            if get_exc_errno(ex) == errno.EBADF:
                raise EOFError()
            else:
                raise

    def read(self, count):
        data = []
        while count > 0:
            try:
                buf = self.sock.recv(min(self.MAX_IO_CHUNK, count))
            except socket.timeout:
                continue
            except socket.error:
                ex = sys.exc_info()[1]
                if get_exc_errno(ex) in retry_errnos:
                    # windows just has to be a bitch
                    continue
                self.close()
                raise EOFError(ex)
            if not buf:
                self.close()
                raise EOFError("connection closed by peer")
            data.append(buf)
            count -= len(buf)
        return BYTES_LITERAL("").join(data)

    def write(self, data):
        try:
            while data:
                count = self.sock.send(data[:self.MAX_IO_CHUNK])
                data = data[count:]
        except socket.error:
            ex = sys.exc_info()[1]
            self.close()
            raise EOFError(ex)