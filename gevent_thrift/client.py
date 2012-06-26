# Copyright 2012 Edgeware AB.
# Written by Johan Rydberg <johan.rydberg@gmail.com>.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Functionality for communicating with remote services."""

from gevent.queue import Queue, Empty, Full
from gevent import socket
import gevent

from circuit import CircuitBreaker, CircuitOpenError

from thrift.protocol import TBinaryProtocol
from thrift.transport import TTransport, TSocket


class UnavailableError(Exception):
    """The remote endpoint is currently not available."""


class _ConnectionPool(object):
    """A really simple connection pool."""

    def __init__(self, factory, pool_size=10):
        self.queue = Queue(pool_size)
        self.maxsize = pool_size
        self.factory = factory
        self.size = 0

    def close(self):
        """Close down the pool."""
        while True:
            try:
                conn = self.queue.get(False)
                self.factory.dispose(conn)
            except Empty:
                break

    def put(self, conn):
        """Put back a connection into the pool."""
        # This _should_ never raise Full since we have logic in get
        # that forbids us from creating more than C{maxsize}
        # connections. And all of those items fit in the queue.
        self.queue.put_nowait(conn)

    def dispose(self, conn):
        """Connection is considered broken and should be disposed from
        the pool.
        """
        self.size -= 1
        self.factory.dispose(conn)

    def get(self, timeout):
        """Try to get a connection from the pool.

        @param timeout: Time to wait for a connection.  Note that this
           is not the same as the connection timeout that will be
           triggered in the case of a connection timeout.

        @raise gevent.Timeout: If a connection could not be snatched
           from the pool within C{timeout} seconds.
        """
        try:
            block = self.size >= self.maxsize
            conn = self.queue.get(block, timeout)
        except Empty:
            if block:
                raise gevent.Timeout(timeout)
            conn = self.factory.create()
            self.size += 1
        return conn


class _ConnectionContextManager(object):
    """Context manager for a C{_ConnectionPool} that yields a connection
    and takes care of error handling.
    """

    def __init__(self, pool, timeout=10):
        self.pool = pool
        self.timeout = timeout
        self.dispose_errors = [socket.error, TTransport.TTransportException,
                               gevent.Timeout]

    def __enter__(self):
        self.conn = self.pool.get(timeout=self.timeout)
        return self.conn

    def __exit__(self, exctype, value, tb):
        if exctype in self.dispose_errors:
            self.pool.dispose(self.conn)
        else:
            self.pool.put(self.conn)


class GeventTSocket(TSocket.TSocket):
    """A simple variant of L{TSocket.TSocket} that use our version of
    the socket module rather than the stdlib one.
    """

    def _resolveAddr(self):
        if self._unix_socket is not None:
            return [(socket.AF_UNIX, socket.SOCK_STREAM,
                     None, None, self._unix_socket)]
        else:
            return socket.getaddrinfo(self.host, self.port,
                                      socket.AF_UNSPEC, socket.SOCK_STREAM, 0,
                                      socket.AI_PASSIVE | socket.AI_ADDRCONFIG)

    def open(self):
        res0 = self._resolveAddr()
        for res in res0:
            self.handle = socket.socket(res[0], res[1])
            self.handle.settimeout(self._timeout)
            try:
                self.handle.connect(res[4])
            except socket.error, e:
                if res is not res0[-1]:
                    continue
                else:
                    raise e
            break


class _ConnectionFactory(object):
    """Factory that creates connections for a C{_ConnectionPool}.

    @ivar timeout: connect_timeout.
    """

    def __init__(self, host, port, client_class, timeout):
        self.host = host
        self.port = port
        self.client_class = client_class
        self.timeout = timeout

    def create(self):
        stransport = GeventTSocket(self.host, self.port)
        stransport.setTimeout(self.timeout * 1000)
        ftransport = TTransport.TFramedTransport(stransport)
        ftransport.open()
        stransport.setTimeout(None)
        protocol = TBinaryProtocol.TBinaryProtocol(ftransport)
        return self.client_class(protocol)

    def dispose(self, client):
        """Close connection given a thrift client instance."""
        client._iprot.trans.close()


class ThriftClient(object):
    """Simple Thrift client that works against a remote service
    endpoint available at (HOST, PORT).

    @ivar client_class: The thrift-generated client class for the service
        interface.

    @ivar connect_timeout: The remote service must respond to our
        connection attempt within this time.  A C{gevent.Timeout}
        exception will be raised when this timeout is triggered.

    @ivar read_timeout: The remote service must present a response to
        the send request within this time.  A C{gevent.Timeout}
        exception will be raised when this timeout is triggered.

    @ivar psize: The number of open connections that are allowed to
        the remote service.

    @ivar pool_timeout: The connection pool must yield a client
        connection within this time.  A C{gevent.Timeout} exception
        will be raised when this timeout is triggered.
    """

    def __init__(self, clock, log, host, port, client_class,
                 pool_timeout=0.100, connect_timeout=0.100, read_timeout=0.250,
                 psize=10, maxfail=3, reset_timeout=10,
                 time_unit=60, error_types=None):
        self.client_class = client_class
        self.read_timeout = read_timeout
        self.pool_timeout = pool_timeout
        self.pool = _ConnectionPool(_ConnectionFactory(host, port,
            self.client_class, connect_timeout), psize)
        if error_types is None:
            error_types = [gevent.Timeout, socket.error,
                           TTransport.TTransportException]
        self.error_types = error_types
        self.breaker = CircuitBreaker(clock, log, self.error_types,
            maxfail, reset_timeout, time_unit)

    def handle_errors(self, error_types):
        """Tell the client that the exception types listen in
        C{error_types} should be considered errors.
        """
        self.error_types.extend(error_types)

    def close(self):
        """Shut down the client."""
        self.pool.close()

    def call_remote(self, fn, *args):
        """Call remote function."""
        # The order of these nested 'with' statements give the
        # following semantics:
        #
        # * The circuit breaker will see timeout errors triggered
        #   because the pool was full.
        # * The circuit breaker will see errors triggered by
        #   connection errors.
        # * The circuit breaker will see timeout errors triggered by
        #   the read timeout.
        # * The circuit breaker will see any errors raised from the
        #   Thrift client class.
        #
        with self.breaker:
            with _ConnectionContextManager(self.pool, self.pool_timeout) \
                   as client:
                with gevent.Timeout(self.read_timeout):
                    return getattr(client, fn)(*args)


class MultiThriftClient(object):
    """A Thrift client that can talk to multiple endpoints that
    implement the same service.

    The client is given a function C{endpoints} that should yield a
    list of C{(host, port)} tuples for available endpoints.  The
    endpoints will be used in the order they are given.

    This client has a build in retry mechanism that will try resend
    the request up to C{retries} times.  The retry mechanism only
    kicks in if the client yields an error that is listed in
    C{retryable_errors}.  Extend the list to include whatever custom
    exception seen to fit.
    """

    def __init__(self, clock, log, endpoints, client_class,
                 pool_timeout=0.100, connect_timeout=0.100, read_timeout=0.250,
                 psize=10, maxfail=3, reset_timeout=10,
                 time_unit=60, retries=1, idle_timeout=60):
        self.clock = clock
        self.endpoints = endpoints
        self.clients = {}
        self.error_types = [gevent.Timeout, socket.error,
                            TTransport.TTransportException]
        self.retryable_errors = self.error_types + [CircuitOpenError]
        self.client_factory = lambda (host, port): ThriftClient(clock,
            log.getChild('%s:%d' % (host, port)), host, port, client_class,
            pool_timeout=pool_timeout, connect_timeout=connect_timeout,
            read_timeout=read_timeout, psize=psize, maxfail=maxfail,
            reset_timeout=reset_timeout, time_unit=time_unit,
            error_types=self.error_types)
        self.retries = retries
        self.idle_timeout = idle_timeout
        self.timestamps = {}
        self.reaper = gevent.spawn(self.reap)

    def handle_errors(self, error_types):
        """Tell the client that the exception types listen in
        C{error_types} should be considered errors.
        """
        self.error_types.extend(error_types)

    def handle_retryable_errors(self, error_types):
        """Tell the client that the exception types listen in
        C{error_types} should be considered retryable errors.
        """
        self.retryable_errors.extend(error_types)

    def reap(self):
        """Go through and reap clients that are no longer used."""
        now = self.clock()
        for key, timestamp in self.timestamps.items()[:]:
            if (timestamp + self.idle_timeout) < now:
                client = self.clients.pop(key)
                del self.timestamps[key]
                client.close()

    def close(self):
        """Shut down the client."""
        gevent.kill(self.reaper)
        for client in self.clients.values()[:]:
            client.close()

    def call_remote(self, fn, *args):
        """Call remote function.

        @raise UnavailableError: if the remote service could not, for
            any reason, handle the request.
        """
        retries = 0
        for host, port in self.endpoints():
            client = self.clients.get((host, port), None)
            if client is None:
                self.clients[(host, port)] = client = self.client_factory(
                    host, port)

            try:
                self.timestamps[(host, port)] = self.clock()
                return client.call_remote(fn, *args)
            except Exception, e:
                if e not in self.retryable_errors:
                    raise
                self.log.debug('%s: caught retryable error: %r' % (fn, e))

            retries = retries + 1
            if retries > self.retries:
                break

        self.log.error('%s: gave up after %d tries' % (fn, retries))
        raise UnavailableError()
