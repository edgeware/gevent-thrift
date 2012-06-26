# gevent-thrift #

`gevent-thrift` is a small package that allows you to consume and
provide Thrift services.

## Using a Client ##

The client code in `gevent-thrift` is somewhat sophisticated and comes
with knobs for tuning.

* has a built-in circuit breaker to disable the servie for short
  periods if the remote service misbehaves.
* has a build-in connection pool
* has (tunable) timeouts for all parts of the interaction

Create a simple client using the `ThriftClient` class:

    from gevent_thrift import ThriftClient, wrap_client
    import time
    import logger

    up = UserProfile(uid=1, name='Test User', blurb='Thrift is great')
    service = wrap_client(ThriftClient(time.time, logger.getLogger(
        'userStorage'), 'localhost', 9090, UserStorage)
    service.store(up)
    up2 = service.retrieve(2)

The `ThriftClient` provides a method `call_remote(fn, *args)` to call
remote functions.  The `wrap_client` makes it so that we can call
methods directly on the client.

Remember to call the `close` method when you no longer use the client.
This will terminate any outgoing connections.

### Knobs ###

The client has tunable timeouts around pretty much every action.  This
allows you to get the exact behavior that you like and make it fit in
your environment.

The *connect timeout* (`connect_timeout`) specifies how quickly the
remote endpoint must accept our connection attempt.  This is default
set to 0.1 (100ms).

The *read timeout* (`read_timeout`) specifies the amount of time the
remote service has to produce a response.  Default is 0.25 (250ms).

The *pool timeout* (`pool_timeout`) gives the time to wait for a
connection when the pool is full.  Default is 0.1 (100ms).

It is also possible to specify the conneciton pool size using the
`psize` keyword argument.  Default size is 10.

We recommend that you set these timeouts to the 95th percentile
response time of your service, plus some headroom.  The default
settings are tuned for a service that has a response time of 200ms at
its 95th percentile, and that the client have a peak of of 30 sessions
per second.

### Circuit Breaker ###

*ThriftClient* use a circuit breaker from `python-circuit` to manage
error conditions.   The breaker is tunable with the following keyword
arguments to the client constructor:

* `maxfail` -- Number of allowed failures before the breaker is
  triggered.  Default value is 3.
* `time_unit` -- Over what time period the errors will have to happen
  before the breaker is triggered.  Default value is 60.
* `reset_timeout` -- The time to wait before probing to see if the
  remote service feels better gain.   Default value is 10.

The default settings will will allow 3 errors per minute with a reset
period of 10 seconds.

### Multi-Endpoint Client ###

If you have mutliple endpoints providing the same service you can use
the `MultiThriftClient` class instead.  The main different is that
instead of a host-port pair the MultiThriftClient-class takes a
function that should yield a sequence of host-port pairs.  To recreate
the example above:

    from gevent_thrift import ThriftClient, wrap_client
    import time
    import logger

    def endpoints():
        return [('localhost', 9090)]

    up = UserProfile(uid=1, name='Test User', blurb='Thrift is great')
    service = wrap_client(MultiThriftClient(time.time, logger.getLogger(
        'userStorage'), endpoints, UserStorage)
    service.store(up)
    up2 = service.retrieve(2)

Note that the pairs returned by end `endpoints` function will be tried
in the order they were returned, so if you want to spread the load you
will have to shuffle the list yourself.

#### Retry Mechanism ####

*MultiThriftClient* also provides a retry mechanism.  They `retries`
keyword argument to the constructor specifies how many *retries* are
allowed before the remote service is deemed unavailable.  The default
setting is 1.  The retry will *always* be made against the next
endpoint, so if you have a limited set of endpoints it might be useful
to cycle through them:

    def endpoints():
        return itertools.cycle([('localhost', 9090)])

Normally the client will only do a retry if it encounters a transport
related error.  If your service itself raises exceptions that signal
that the service is temporarly unvailable, you can tell the client
that these errors are "retryable":

    client = MultiThriftClient(time.time, logger.getLogger(),
        endpoints, RemoteService)
    client.handle_retryable_errors([ttypes.TemporaryUnavailable])

When the remote service raises `TemporaryUnavailable`, the error won't
be propagated to the caller, but another service endpoint will be
tried before a `UnavailabelError` exception is raised.

If you also want the build-on circuit breaker to be triggered on these
errors you will have to call `client.handle_errors` with the same
error list.

## Thrift Server ##

Starting a Thrift server is as simple as creating a `ThriftServer`
object and call `start` on it:

    impl = CalculatorImpl()
    server = ThriftServer(('', 9090), CalculatorProcessor(impl))
    server.start()

`CalculatorProcessor` is the Thrift generated processor class and
`impl` is our implementation of the service.  *ThriftServer* inherits
`gevent.StreamServer` which mean that you can pass in `spawn` and
the other keyword arguments to control the server.
