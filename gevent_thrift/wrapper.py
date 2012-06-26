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

"""Wrapper around a L{ThriftClient} or L{MultiThriftClient} that
allows a user to simply call methods on the client without using the
C{call_remote} method.
"""

class _Invocation(object):
    """Help wrapper for C{ServiceWrapper}."""

    def __init__(self, client, name):
        self._client = client
        self._name = name

    def __call__(self, *args):
        """Invoke method."""
        return self._client.call_remote(self._name, *args)


class ClientInvocationWrapper(object):
    """Wrapper around a client that allows users to call methods
    directly on the agent rather than using C{call_remote}.
    """

    def __init__(self, thrift_client):
        self.client = thrift_client

    def __getattr__(self, name):
        return _Invocation(self.client, name)

    def close(self):
        """Internal method for closing the client.

        We're betting that an external service does not have a method
        called C{close}.
        """
        self.client.close()


def wrap(client):
    """Wrapper around a client that allows users to call methods
    directly on the agent rather than using C{call_remote}.
    """
    return ClientInvocationWrapper(client)
