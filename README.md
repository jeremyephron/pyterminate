# pyterminate

Reliably run cleanup code upon program termination.

## Table of Contents

- [Why does this exist?](#why-does-this-exist?)
- [What can it do?](#what-can-it-do?)
- [Quickstart](#quickstart)

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

- Ignore multiple repeated signals to allow the registered functions to
  complete
  - However, it can be canceled upon receipt of another signal. Desired
    behavior could vary application to application, but this feels appropriate
    for the most common known use cases.

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
