"""
File:
-----

"""

from collections import defaultdict
import atexit
import signal
import sys
from types import FrameType
from typing import Any, Callable, Dict, Optional, Tuple


_registered_funcs = set()
_func_to_wrapper = {}
_signal_to_prev_handler = defaultdict(lambda: defaultdict(list))


def register(
    func: Optional[Callable] = None,
    *,
    args: tuple = tuple(),
    kwargs: Optional[Dict[str, Any]] = None,
    signals=(signal.SIGTERM,),
    successful_exit: bool = False
) -> Callable:
    kwargs = kwargs or {}

    def decorator(func: Callable) -> Callable:
        return _register_impl(func, args, kwargs, signals, successful_exit)

    return decorator(func) if func else decorator


def unregister(func: Callable) -> None:
    if func in _func_to_wrapper:
        atexit.unregister(_func_to_wrapper[func])

    _registered_funcs.remove(func)


def _register_impl(
    func: Callable,
    args: tuple,
    kwargs: Dict[str, Any],
    signals: Tuple[int, ...],
    successful_exit: bool,
) -> Callable:
    def exit_handler(*args: Any, **kwargs: Any) -> Any:
        if func not in _registered_funcs:
            return

        _registered_funcs.remove(func)
        return func(*args, **kwargs)

    def signal_handler(sig: int, frame: FrameType):
        signal.signal(sig, signal.SIG_IGN)

        exit_handler(*args, **kwargs)
        prev_handler = _signal_to_prev_handler[func][sig][-1]
        if callable(prev_handler) and prev_handler != signal.default_int_handler:
            prev_handler(sig, frame)

        sys.exit(0 if successful_exit else sig)

    for sig in signals:
        _signal_to_prev_handler[func][sig].append(signal.signal(sig, signal_handler))

    _registered_funcs.add(func)
    _func_to_wrapper[func] = exit_handler

    atexit.register(exit_handler, *args, **kwargs)

    return func
