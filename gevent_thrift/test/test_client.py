# Copyright 2012 Edgeware AB.
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

"""Test cases for the circuit breaker."""

from gevent_thrift.client import _ConnectionPool
import gevent
from mockito import mock, when, any, verify
import unittest


class ConnectionPoolTestCase(unittest.TestCase):

    def setUp(self):
        self.factory = mock()
        self.conn = mock()
        self.pool = _ConnectionPool(self.factory, pool_size=1)
        when(self.factory).create().thenReturn(self.conn)

    def test_creates_new_connection_on_drained_pool(self):
        conn = self.pool.get(1)
        verify(self.factory).create()
        self.assertTrue(conn is self.conn)
        self.assertEquals(self.pool.size, 1)

    def test_timeouts_on_full_queue(self):
        conn1 = self.pool.get(1)
        def test():
            return self.pool.get(0.1)
        self.assertRaises(gevent.Timeout, test)
        self.assertEquals(self.pool.size, 1)

    def test_failing_to_create_connection_propages_error(self):
        when(self.factory).create().thenRaise(ValueError)
        self.assertRaises(ValueError, self.pool.get, 1)
        self.assertEquals(self.pool.size, 0)

    def test_dispose_connection_disposes_using_factory(self):
        conn = self.pool.get(0)
        self.pool.dispose(conn)
        self.assertEquals(self.pool.size, 0)
        verify(self.factory).dispose(conn)


class Clock(object):
    now = 0.0

    def time(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
