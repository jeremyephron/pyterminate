"""
Module: pyterminate
-------------------
Defines decorators for registering and unregistering functions to be called
at program termination.

"""

from collections import defaultdict
import atexit
import functools
import os
import signal
import sys
from types import FrameType
from typing import Any, Callable, DefaultDict, Dict, List, Optional, Set, Tuple


_registered_funcs: Set[Callable] = set()
_func_to_wrapper: Dict[Callable, Callable] = {}
_signal_to_prev_handler: DefaultDict[Callable, DefaultDict[int, List[Callable]]] = (
    defaultdict(lambda: defaultdict(list))
)


def register(
    func: Optional[Callable] = None,
    *,
    args: tuple = tuple(),
    kwargs: Optional[Dict[str, Any]] = None,
    signals: Tuple[int] = (signal.SIGTERM,),
    successful_exit: bool = False,
    keyboard_interrupt_on_sigint: bool = False,
) -> Callable:
    """
    Registers a function to be called at program termination or creates a
    decorator to do so.

    Args:
        func: Function to register.
        args: Positional arguments to pass to the function when called.
        kwargs: Keyword arguments to pass to the function when called.
        signals: Signals to call the given function for when handled.
        successful_exit: Whether to always exit with a zero exit code.
            Otherwise, exits with the code of the signal.
        keyboard_interrupt_on_sigint: Whether to raise a KeyboardInterrupt on
            SIGINT. Otherwise, exits with code SIGINT.

    Returns:
        func: The given function if not None.
        decorator: A decorator that will apply the given settings to the
            decorated function.

    """

    def decorator(func: Callable) -> Callable:
        return _register_impl(
            func,
            args,
            kwargs or {},
            signals,
            successful_exit,
            keyboard_interrupt_on_sigint
        )

    return decorator(func) if func else decorator


def unregister(func: Callable) -> None:
    """
    Unregisters a previously registered function from being called at exit.

    Args:
        func: A previously registered function. The call is a no-op if not
            previously registered.

    """

    if func in _func_to_wrapper:
        atexit.unregister(_func_to_wrapper[func])

    _registered_funcs.remove(func)


def _register_impl(
    func: Callable,
    args: tuple,
    kwargs: Dict[str, Any],
    signals: Tuple[int, ...],
    successful_exit: bool,
    keyboard_interrupt_on_sigint: bool,
) -> Callable:
    """
    Registers a function to be called at program termination.

    This function is the internal implementation of registration, and should
    not be called by a user, who should called register() instead.

    Idempotent handlers are created for both atexit and signal handling. All
    requested signals are ignored while registered function is executing, and
    are restored afterward.

    Args:
        func: Function to register.
        args: Positional arguments to pass to the function when called.
        kwargs: Keyword arguments to pass to the function when called.
        signals: Signals to call the given function for when handled.
        successful_exit: Whether to always exit with a zero exit code.
            Otherwise, exits with the code of the signal.
        keyboard_interrupt_on_sigint: Whether to raise a KeyboardInterrupt on
            SIGINT. Otherwise, exits with code SIGINT.

    Returns:
        func: The given function.

    """

    def exit_handler(*args: Any, **kwargs: Any) -> None:
        if func not in _registered_funcs:
            return

        prev_handlers = {}
        for sig in signals:
            prev_handlers[sig] = signal.signal(sig, signal.SIG_IGN)

        _registered_funcs.remove(func)
        func(*args, **kwargs)

        for sig, handler in prev_handlers.items():
            signal.signal(sig, handler)

    def signal_handler(sig: int, frame: Optional[FrameType]) -> None:
        exit_handler(*args, **kwargs)

        if _signal_to_prev_handler[func][sig]:
            prev_handler = _signal_to_prev_handler[func][sig].pop()
            prev_handler(sig, frame)

        if keyboard_interrupt_on_sigint and sig == signal.SIGINT:
            raise KeyboardInterrupt

        sys.exit(0 if successful_exit else sig)

    for sig in signals:
        prev_handler = signal.signal(sig, signal_handler)

        if not callable(prev_handler):
            continue

        if prev_handler == signal.default_int_handler:
            continue

        _signal_to_prev_handler[func][sig].append(prev_handler)

    _registered_funcs.add(func)
    _func_to_wrapper[func] = exit_handler

    atexit.register(exit_handler, *args, **kwargs)

    return func


def exit_with_signal(signum: int) -> Callable:
    """
    Creates a decorator for raising a given signal on exit.

    Args:
        signum: The signal to raise on exit.

    Returns:
        decorator: Decorator that executes a function and raises a signal
            afterward.

    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> None:
            try:
                func(*args, **kwargs)
            finally:
                os.kill(os.getpid(), signum)

        return wrapper

    return decorator
