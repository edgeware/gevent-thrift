#!/usr/bin/env python

from distutils.core import setup
import os.path

import versioneer
versioneer.versionfile_source = "gevent_thrift/_version.py"
versioneer.versionfile_build = "gevent_thrift/_version.py"
versioneer.tag_prefix = ""
versioneer.parentdir_prefix = ""
commands = versioneer.get_cmdclass().copy()

## Get long_description from index.txt:
here = os.path.dirname(os.path.abspath(__file__))
f = open(os.path.join(here, 'README.md'))
long_description = f.read().strip()
f.close()

setup(name='gevent-thrift',
      version=versioneer.get_version(),
      description='gevent bindings for Thrift',
      author='Johan Rydberg',
      author_email='johan.rydberg@gmail.com',
      url='https://github.com/edgeware/gevent-thrift',
      packages=['gevent_thrift'],
      require_install=['python-circuit'],
      cmdclass=commands)
