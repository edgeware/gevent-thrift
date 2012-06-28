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

from gevent_thrift import ThriftClient, ThriftServer, ThriftClient, wrap_client
from gen.tutorial.Calculator import (Client as CalculatorClient,
                                     Processor as CalculatorProcessor)
import time
import logging


class CalculatorImpl(object):
    """Implementation of the calculator."""

    def ping():
        pass

    def add(self, num1, num2):
        return num1 + num2


def test():
    impl = CalculatorImpl()
    server = ThriftServer(('', 9090), logging.getLogger('server'),
        CalculatorProcessor(impl))
    server.start()

    client = wrap_client(ThriftClient(time.time, logging.getLogger('calc'),
        'localhost', 9090, CalculatorClient))
    z = client.add(1, 2)
    print "result of 1+2 is", z
    client.close()
    server.stop()

if __name__ == '__main__':
    test()
