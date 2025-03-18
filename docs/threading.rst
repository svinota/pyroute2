.. _threading:

Using library in threaded environments
======================================

Network namespaces
------------------

In order to run a separate socket in network namespace `A` while keeping
the Python process in namespace `B`, the library performs these steps:

1. spawn a child process
2. execute `netns.setns()` in the child
3. create a socket
4. send the file descriptor using `socket.send_fds()` back to the parent
5. terminate the child process
6. create a socket with `socket(fileno=...)`

As a result, in the parent process we get a socket that belongs to another
network namespace, but we can use it natively like any other socket, both in
sync and async way.

Start a child: os.fork()
------------------------

By default, pyroute2 uses `os.fork()` to create the child. When using it
in multithreaded processes, no threads will be recreated, and the child
will only continue the thread where `os.fork()` was called in. This leaves
the GC in a corrupted state.

This should not be an issue since the socket creation routine stops the GC,
and doesn't rely on any shared data. But still there is some risk.

That's why pyroute2 provides a configuration option
`config.child_process_mode`. By default it is `"fork"`, but you can change
the option to `"mp"`, and then pyroute2 will use `multiprocessing` to
create and control the child process.

Start a child: multiprocessing
------------------------------

Using `multiprocessing` may or may not rely on `os.fork()`, it depends on
`multiprocessing.set_start_method()`. In Python version < 3.14 the default
is `"fork"`, but starting with 3.14, the default is `"spawn"`.

Using `"spawn"` is safer, but significantly slower. Beside of that, `"spawn"`
implies additional limitations by pickling the target method and its
arguments. This prevents passing lambdas as the target, and make impossible
to pass the `libc` instance to the child process.

The `multiprocessing` start method is out of scope for pyroute2, thus no
way to set it using `config.child_process_mode`, where you can specify
only `"mp"`. You have to run `multiprocessing.set_start_method()` by
yourself somewhere else in your program then.
