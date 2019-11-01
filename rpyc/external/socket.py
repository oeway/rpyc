error = Exception

timeout = Exception


AF_INET, AF_UNIX = 1, 2

SOCK_STREAM, SOCK_DGRAM, SOCK_RAW = 2, 4, 5

def gethostbyname_ex():
    return None


class socket():

    """A subclass of _socket.socket adding the makefile() method."""

    __slots__ = ["__weakref__", "_io_refs", "_closed"]

    def __init__(self, family=-1, type=-1, proto=-1, fileno=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if not self._closed:
            self.close()

    def __repr__(self):
        """Wrap __repr__() to reveal the real class name and socket
        address(es).
        """
        pass

    def __getstate__(self):
        raise TypeError("Cannot serialize socket object")

    def dup(self):
        pass

    def accept(self):
        pass

    def makefile(self, mode="r", buffering=None, *,
        pass

    

    def sendfile(self, file, offset=0, count=None):
        pass
   

    def close(self):
        pass
    def detach(self):
        """detach() -> file descriptor

        Close the socket object without closing the underlying file descriptor.
        The object cannot be used after this call, but the file descriptor
        can be reused for other purposes.  The file descriptor is returned.
        """
        pass

    @property
    def family(self):
        """Read-only access to the address family for this socket.
        """
        pass

    @property
    def type(self):
        """Read-only access to the socket type.
        """
        pass


    def get_inheritable(self):
        pass
    def set_inheritable(self, inheritable):
        pass



