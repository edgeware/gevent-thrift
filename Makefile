all:

prepare:

check: frosted pep8

pep8:
	pep8 gevent_thrift

frosted:
	frosted -vb -r gevent_thrift

test:
	python setup.py test

build:

dist:

clean:
	git clean -fdx
