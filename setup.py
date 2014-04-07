#!/usr/bin/env python
from setuptools import setup

kwargs = {
    'name': 'gevent-thrift',
    'version': '0.1',
    'description': 'gevent bindings for Thrift',
    'author': 'Edgeware AB',
    'author_email': 'info@edgeware.tv',
    'url': 'https://github.com/edgeware/gevent-thrift',
    'packages': ['gevent_thrift'],
    'install_requires': [
        'gevent==0.13.8',
        'thrift'
    ]
}

setup(**kwargs)
