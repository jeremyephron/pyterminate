"""
Module: pyterminate
-------------------
Defines decorators for registering and unregistering functions to be called
at program termination.

"""

import atexit
import functools
import logging
import os
import signal
import sys
from types import FrameType
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Union
)
from weakref import WeakSet, WeakKeyDictionary

logger = logging.getLogger(__name__)

# The set of all functions currently registered.
_registered_funcs: 'WeakSet[Callable]' = WeakSet()

# A mapping from registered functions to their wrappers called on exit.
_func_to_wrapper_exit: 'WeakKeyDictionary[Callable, Callable]' = (
    WeakKeyDictionary()
)

# A mapping from registered functions to their wrappers called on signal.
_func_to_wrapper_sig: 'WeakKeyDictionary[Callable, Callable]' = (
    WeakKeyDictionary()
)

# { Registered function: { signal number: [ previous signal handler ] } }
# The innermost list is purely for reference management, and should always be
# of length <= 1.
_signal_to_prev_handler: 'WeakKeyDictionary[Callable, Dict[int, List[Callable]]]' = (
    WeakKeyDictionary()
)


def register(
    func: Optional[Callable] = None,
    *,
    args: tuple = tuple(),
    kwargs: Optional[Dict[str, Any]] = None,
    signals: Iterable[Union[signal.Signals, int]] = (signal.SIGTERM,),
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
    Unregisters a previously registered function from being called at exit or
    on signal.

    Args:
        func: A previously registered function. The call is a no-op if not
            previously registered.

    """

    # Unregister and remove exit handler.
    if func in _func_to_wrapper_exit:
        atexit.unregister(_func_to_wrapper_exit[func])
        del _func_to_wrapper_exit[func]

    # Remove signal handler.
    wrapper_sig = None
    if func in _func_to_wrapper_sig:
        wrapper_sig = _func_to_wrapper_sig[func]
        del _func_to_wrapper_sig[func]

    # Re-link chain of signal handlers around the unregistered function.
    # The length of collections to iterate through should be small, so
    # implementation is naive. If greater efficiency is needed, can add
    # more direct references for O(1) time to re-link.
    if func in _signal_to_prev_handler:

        # Register previous signal handlers if this is the most
        # recently registered one.
        for sig in _signal_to_prev_handler[func]:
            if signal.getsignal(sig) is not wrapper_sig:
                continue

            if _signal_to_prev_handler[func][sig]:
                handler = _signal_to_prev_handler[func][sig][0]
            else:
                handler = signal.SIG_DFL

            signal.signal(sig, handler)

        for fn, signals_to_prev in _signal_to_prev_handler.items():
            for sig in signals_to_prev:

                # Skip if fn wasn't registered for the relevant signals or not
                # pointing to func as the previous handler.
                if not (
                    sig in _signal_to_prev_handler[func]
                    and _signal_to_prev_handler[fn][sig]
                    and _signal_to_prev_handler[fn][sig][0] is wrapper_sig
                ):
                    continue

                _signal_to_prev_handler[fn][sig] = (
                    _signal_to_prev_handler[func][sig]
                )

        del _signal_to_prev_handler[func]

    _registered_funcs.discard(func)


def _register_impl(
    func: Callable,
    args: tuple,
    kwargs: Dict[str, Any],
    signals: Iterable[Union[signal.Signals, int]],
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

    if func in _registered_funcs:
        logger.warning(
            f"Attempted to register a function more than once ({func}). The "
            f"duplicate calls to register do nothing and this is usually a "
            f"mistake."
        )
        return func

    def exit_handler(*args: Any, **kwargs: Any) -> None:
        if func not in _registered_funcs:
            return

        prev_handlers = {}
        for sig in _signal_to_prev_handler[func]:
            prev_handlers[sig] = signal.signal(sig, signal.SIG_IGN)

        _registered_funcs.remove(func)
        func(*args, **kwargs)

        for sig, handler in prev_handlers.items():
            signal.signal(sig, handler)

        unregister(func)

    def signal_handler(sig: int, frame: Optional[FrameType]) -> None:
        exit_handler(*args, **kwargs)

        handler = signal.getsignal(sig)
        if callable(handler):
            handler(sig, frame)

        if keyboard_interrupt_on_sigint and sig == signal.SIGINT:
            raise KeyboardInterrupt

        sys.exit(0 if successful_exit else sig)

    _signal_to_prev_handler.setdefault(func, {})

    for sig in signals:
        prev_handler = signal.signal(sig, signal_handler)

        _signal_to_prev_handler[func].setdefault(sig, [])

        if not callable(prev_handler):
            continue

        if prev_handler == signal.default_int_handler:
            continue

        _signal_to_prev_handler[func][sig].append(prev_handler)

    _registered_funcs.add(func)
    _func_to_wrapper_exit[func] = exit_handler
    _func_to_wrapper_sig[func] = signal_handler

    atexit.register(exit_handler, *args, **kwargs)

    return func


def exit_with_signal(signum: Union[signal.Signals, int]) -> Callable:
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
