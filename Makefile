all:

prepare:

check: frosted pep8

pep8:
	pep8 gevent_thrift

frosted:
	frosted -vb -r gevent_thrift

test:
	# Currently doesn't contain any tests, so we skip it for now so we don't
	# waste time compiling Gevent for nothing.
	# python setup.py test

build:

dist:

clean:
	git clean -fdx
