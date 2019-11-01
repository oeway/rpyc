from rpyc.lib.compat import BYTES_LITERAL
from rpyc.core.stream import PipeStream, NamedPipeStream
import rpyc
import sys
import time
import unittest

from nose import SkipTest
if sys.platform != "win32":
    raise SkipTest("Requires windows")


if __name__ == "__main__":
    unittest.main()
