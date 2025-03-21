.. _threading:

Using the library in threaded environments
==========================================

Network namespaces
------------------

To run a separate socket in one network namespace while keeping the
Python process in another namespace, the library follows these steps:

1. Spawn a child process.
2. Execute `netns.setns()` in the child.
3. Create a socket.
4. Send the file descriptor back to the parent using `socket.send_fds()`.
5. Terminate the child process.
6. Create a socket in the parent using `socket(fileno=...)`.

As a result, the parent process obtains a socket belonging to
another network namespace. However, it can be used natively like
any other socket, both synchronously and asynchronously.

Starting a child process: os.fork()
-----------------------------------

By default, pyroute2 uses `os.fork()` to create the child process.
In multithreaded environments, `os.fork()` does not recreate threads;
the child process continues only from the thread where `os.fork()`
was called. This can leave the garbage collector in a corrupted state.

While this is generally not an issue -- since the socket creation routine
stops the garbage collector, and does not rely on shared data -- there
is still some risk.

To address this, pyroute2 provides a configuration option:
`config.child_process_mode`. The default value is `"fork"`, but you
can change it to `"mp"` to use the `multiprocessing` module for creating
and managing the child process.

Starting a child process: multiprocessing
-----------------------------------------

The `multiprocessing` module may or may not rely on `os.fork()`, depending
on the method set via `multiprocessing.set_start_method()`. In Python
versions earlier than 3.14, the default method is `"fork"`, but starting
from Python 3.14, the default is `"spawn"`.

Using `"spawn"` is safer but significantly slower. Additionally, `"spawn"`
introduces limitations due to pickling:

* The target function and its arguments must be pickleable.
* Passing lambda functions as the target is not possible.
* The libc instance cannot be passed to the child process.

Since pyroute2 does not manage the `multiprocessing` start method, the
start method cannot be configured via `config.child_process_mode`. If you
set `config.child_process_mode` to `"mp"`, and need to explicitly specify
the start method, you must call `multiprocessing.set_start_method()`
manually elsewhere in your program.

Threading and asyncio
---------------------

An asyncio event loop can only run in the thread where it was started.
In a multithreaded environment, the library creates a local event loop
and a local netlink socket for each thread that accesses the object.
While this approach is safe, it complicates object termination.
Although an event loop can be stopped from another thread, it cannot
be closed.

The best solution is to call `close()` in every thread where you
call `bind()`.
