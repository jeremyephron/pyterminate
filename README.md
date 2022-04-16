# pyterminate
[![CI](https://github.com/jeremyephron/pyterminate/actions/workflows/ci.yml/badge.svg)](https://github.com/jeremyephron/pyterminate/actions/workflows/ci.yml)
[![PyPI Downloads](https://img.shields.io/pypi/dm/pyterminate.svg?label=PyPI%20downloads)](
https://pypi.org/project/pyterminate/)

Reliably run cleanup code upon program termination.

## Table of Contents

- [Why does this exist?](#why-does-this-exist)
- [What can it do?](#what-can-it-do)
- [Quickstart](#quickstart)
- [Tips, tricks, and other notes](#tips-tricks-and-other-notes)
  - [Duplicate registration after forking](#duplicate-registration-after-forking)
  - [Multiprocessing start method](#multiprocessing-start-method)

## Why does this exist?

There are currently two builtin modules for handling termination behavior
in Python: [`atexit`](https://docs.python.org/3/library/atexit.html) and
[`signal`](https://docs.python.org/3/library/signal.html). However, using them
directly leads to a lot of repeated boilerplate code, and some non-obvious
behaviors that can be easy to accidentally get wrong, which is why I wrote this
package.

The `atexit` module is currently insufficient since it fails to handle signals.
The `signal` module is currently insufficient since it fails to handle normal
or exception-caused exits.

Typical approaches would include frequently repeated code registering a
function both with `atexit` and on desired signals. However, extra care
sometimes needs to be taken to ensure the function doesn't run twice (or is
idempotent), and that a previously registered signal handler gets called.

## What can it do?

This packages does or allows the following behavior:

- Register a function to be called on program termination
    - Always on normal or exception-caused termination: `@pyterminate.register`
    - Configurable for any desired signals:<br/>
      `@pyterminate.register(signals=(signal.SIGINT, signal.SIGABRT))`

- Allows multiple functions to be registered

- Will call previous registered signal handlers

- Allows zero or non-zero exit codes on captured signals:<br/>
  `@pyterminate.register(successful_exit=True)`

- Allows suppressing or throwing of `KeyboardInterrupt` on `SIGINT`:<br/>
  `@pyterminate.register(keyboard_interrupt_on_sigint=True)`
    - You may want to throw a `KeyboardInterrupt` if there is additional
      exception handling defined.

- Allows functions to be unregistered: `pyterminate.unregister(func)`

- Ignore requested signals while registered function is executing, ensuring
  that it is not interrupted.
  - It's important to note that `SIGKILL` and calls to `os._exit()` cannot be
    ignored.

## Quickstart

```bash
python3 -m pip install pyterminate
```

```python3
import signal

import pyterminate


@pyterminate.register(
    args=(None,),
    kwargs={"b": 42},
    signals=(signal.SIGINT, signal.SIGTERM),
    successful_exit=True,
    keyboard_interrupt_on_sigint=True
)
def cleanup(*args, **kwargs):
    ...

# or

pyterminate.register(cleanup, ...)
```

## Tips, tricks, and other notes

### Duplicate registration after forking

Since creating a new process through forking duplicates the entire process,
any previously registered functions will also be registered in the forked
process. This is an obvious consequence of forking, but important to 
consider if the registered functions are accessing shared resources. To 
avoid this behavior, you can unregister the function at the beginning of
the forked process, gate based on the process' ID, or use any other 
synchronization method that's appropriate.

### Multiprocessing start method

When starting processes with Python's
[`multiprocessing`](https://docs.python.org/3/library/multiprocessing.html)
module, the `fork` method will fail to call registered functions on exit, since
the process is ended with `os._exit()` internally, which bypasses all cleanup
and immediately kills the process.

One way of getting around this are using the `"spawn"` start method if that
is acceptable for your application. Another method is to register your function
to a user-defined signal, and wrap your process code in try-except block,
raising the user-defined signal at the end. `pyterminate` provides this
functionality in the form of the `exit_with_signal` decorator, which simply
wraps the decorated function in a try-finally block, and raises the given
signal. Example usage:

```python3
import multiprocessing as mp
import signal

import pyterminate


@pyterminate.exit_with_signal(signal.SIGUSR1)
def run_process():

    @pyterminate.register(signals=[signal.SIGUSR1, signal.SIGINT, signal.SIGTERM])
    def cleanup():
        ...

    ...


if __name__ == "__main__"
    mp.set_start_method("fork")

    proc = mp.Process(target=run_process)
    proc.start()

    try:
        proc.join(timeout=300)
    except TimeoutError:
        proc.terminate()
        proc.join()
```
