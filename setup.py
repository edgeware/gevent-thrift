#!/usr/bin/env python
from setuptools import setup

setup(name='gevent-thrift',
      version='0.4.0',
      description='Gevent bindings for Thrift',
      author='Edgeware AB',
      author_email='info@edgeware.tv',
      url='https://github.com/edgeware/gevent-thrift',
      packages=['gevent_thrift'],
      install_requires=[
          'gevent==1.0.1',
          'thrift==0.9.2'
      ])
