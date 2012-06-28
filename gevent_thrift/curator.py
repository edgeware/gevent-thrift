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

"""Functionality for consuming and publishing services in a Netflix
Curator [1] environment.

Currently we do not support SSL.  Patches are welcome.

[1] https://github.com/Netflix/curator
"""

import os.path
import random
import json
import logging

try:
    from gevent_zookeeper.monitor import MonitorListener
except ImportError:
    # So the user do not have gevent-zookeeper installed.  Bad for
    # them.
    pass

from .client import MultiThriftClient


# Logger object in 2.6 do not have getChild.
def _getChild(log, suffix):
    if hasattr(log, 'getChild'):
        return log.getChild(suffix)
    else:
        return logging.getLogger('%s.%s' % (log.name,
                                            suffix))


class ServiceInstance(object):
    """Representation of a service instance.

    See C{com.netflix.curator.x.discovery.ServiceInstance} for
    documentation on what fields should be available.
    """

    def __init__(self, name, id, address, port, payload,
                 registration_time, service_type):
        self.name = name
        self.id = id
        self.address = address
        self.port = port
        self.payload = payload
        self.registration_time = registration_time
        self.service_type = service_type

    @classmethod
    def from_data(cls, data):
        """Create a service instance for a piece of raw data."""
        data = json.loads(data)
        return cls(data['name'], data['id'], data['address'], data['port'],
            data['payload'], data['registrationTimeUTC'], data['serviceType'])

    def __repr__(self):
        """Return a string representation of this instance."""
        return "<ServiceInstance name=%s id=%s address=%s port=%d>" % (
            self.name, self.id, self.address, self.port)

    def __str__(self):
        return '%s at %s:%d' % (self.id, self.address, self.port)


class _CacheLogMonitor(MonitorListener):
    """Monitor that logs cache updates."""

    def __init__(self, log):
        self.log = log

    def created(self, path, data):
        self.log.info("discovered %s" % (data,))

    def deleted(self, path):
        self.log.info("lost %s" % (path,))


class _Cache(object):
    """In-memory list of instances.

    It uses a watcher to keep the list up to date. The C{_Cache}
    object must be started by calling C{start} and, when done, you
    should call C{close}.
    """

    def __init__(self, client, log, path, cls):
        self.client = client
        self.path = path
        self.cls = cls
        self.log = log
        self._instances = {}

    def start(self):
        self.monitor = self.client.monitor().children().store_into(
            self._instances, self.cls.from_data).using(_CacheLogMonitor(
                self.log)).for_path(self.path)
        return self

    def close(self):
        self.monitor.close()

    def instances(self):
        """Return the current list of instances.

        NOTE: there is no guarantee of freshness. This is merely the
        last known list of instances. However, the list is updated via
        a ZooKeeper watcher so it should be fresh within a window of a
        second or two.
        """
        return self._instances.values()


class _Discovery(object):
    """Raw access to a registry.

    @ivar cls: Factory for creating representations of instances.  The
        factory must have a method C{from_data} that takes a string
        and return an instance.
    """

    def __init__(self, client, log, base_path, cls):
        self.client = client
        self.base_path = base_path
        self.cls = cls
        self.log = log

    def cache_for_name(self, name):
        """Return an instance cache for C{name}."""
        return _Cache(self.client, _getChild(self.log, 'cache.' + name),
                      os.path.join(self.base_path, name), self.cls).start()

    def query_for_names(self):
        """Return names."""
        return self.client.get_children(self.base_path)

    def query_for_instances(self, name):
        """Return instance names."""
        return self.client.children().for_path(os.path.join(
                self.base_path, name))

    def query_for_instance(self, name, instance_id):
        """Return a specific instance."""
        data = self.client.get().for_path(os.path.join(
                self.base_path, name, instance_id))
        return self.cls.from_data(data)

    def register_instance(self, instance):
        """Register instance with registry."""
        zpath = os.path.join(self.base_path, instance.name, instance.id)
        return self.client.create().as_ephemeral(
            ).parents_if_needed().for_path(zpath)

    def unregister_instance(self, name, instance_id):
        """Unregister instance."""
        zpath = os.path.join(self.base_path, name, instance_id)
        return self.client.delete().for_path(zpath)


class ServiceDiscovery(_Discovery):
    """Discovery for services."""

    def __init__(self, client, log):
        _Discovery.__init__(self, client, log, '/service', ServiceInstance)


def service_client(clock, log, cache, client_class, **kwargs):
    """Create a service client using the given instance cache.

    @param cache: Service instance cache.

    @param client_class: The Thrift generated client class for
        the service.

    @return: a L{MultiThriftClient}.
    """
    def endpoints():
        instances = list(cache.instances())
        random.shuffle(instances)
        for instance in instances:
            yield instance.address, instance.port

    return MultiThriftClient(clock, log, endpoints, client_class,
                             **kwargs)
