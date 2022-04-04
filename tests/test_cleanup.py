import multiprocessing as mp
import os
import signal
import sys
from typing import Any, Callable, Dict, Optional

import pytest

ProgramType = Callable[[Dict[str, Any], mp.Value, mp.Event, mp.Event, mp.Pipe], None]


def setup_module() -> None:
    mp.set_start_method('spawn')


class ProcessUnderTest(mp.Process):
    def __init__(self, program: ProgramType) -> None:
        self.setup_is_done = mp.Event()
        self.should_cleanup = mp.Event()
        self.register_kwargs = {"signals": (signal.SIGINT, signal.SIGTERM)}

        self._n_calls = mp.Value("i", 0)

        self._pconn, self._cconn = mp.Pipe()

        super().__init__(
            target=program,
            args=(
                self.register_kwargs,
                self._n_calls,
                self.should_cleanup,
                self.setup_is_done,
                self._cconn
            )
        )

    @property
    def n_cleanup_calls(self):
        return self._n_calls.value

    def raise_exception(self, exc):
        self._pconn.send(exc)


def simple_program(
    register_kwargs,
    value,
    should_cleanup,
    setup_is_done,
    cconn
) -> None:
    import pyterminate

    @pyterminate.register(**register_kwargs)
    def cleanup(a=1, b=0):
        assert should_cleanup.wait(timeout=5)
        value.value += (a + b)

    setup_is_done.set()

    exc = cconn.recv()
    if exc is not None:
        raise exc

    sys.exit(0)


def sig_handler_program(
    register_kwargs,
    value,
    should_cleanup,
    setup_is_done,
    cconn
) -> None:
    import pyterminate

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(66))

    @pyterminate.register(**register_kwargs)
    def cleanup(a=1, b=0):
        value.value += (a + b)

    setup_is_done.set()
    assert should_cleanup.wait(timeout=5)

    sys.exit(0)


def unregister_program(
    register_kwargs,
    value,
    should_cleanup,
    setup_is_done,
    cconn
) -> None:
    import pyterminate

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(66))

    @pyterminate.register(**register_kwargs)
    def cleanup(a=1, b=0):
        value.value += (a + b)

    setup_is_done.set()

    pyterminate.unregister(cleanup)

    assert should_cleanup.wait(timeout=5)

    sys.exit(0)


def multiple_register_program(
    register_kwargs,
    value,
    should_cleanup,
    setup_is_done,
    cconn
) -> None:
    import pyterminate

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(66))

    @pyterminate.register(**register_kwargs)
    def cleanup(a=1, b=0):
        value.value += (a + b)

    def cleanup2(a=1, b=0):
        value.value += (a + b)

    def cleanup3(a=1, b=0):
        value.value += (a + b)

    pyterminate.register(cleanup2, **register_kwargs)
    pyterminate.register(cleanup3, **register_kwargs)

    pyterminate.unregister(cleanup)

    setup_is_done.set()
    assert should_cleanup.wait(timeout=5)

    sys.exit(0)


@pytest.fixture(scope='function')
def proc(request) -> ProcessUnderTest:
    return ProcessUnderTest(getattr(request, "param", simple_program))


def test_normal_exit(proc: ProcessUnderTest) -> None:
    """Tests that registered function is called on normal exit."""

    proc.start()
    proc.setup_is_done.wait()

    proc.raise_exception(None)
    proc.should_cleanup.set()

    proc.join()

    assert proc.exitcode == 0, proc.exitcode
    assert proc.n_cleanup_calls == 1, proc.n_cleanup_calls


@pytest.mark.parametrize(
    ['args', 'kwargs'],
    [((1, 1), None), (tuple(), {'a': 1, 'b': 1}), ((1,), {'b': 1})]
)
def test_cleanup_args(
    proc: ProcessUnderTest,
    args: tuple,
    kwargs: Optional[Dict[str, Any]]
) -> None:
    """Tests that passing args and kwargs to registered function works."""

    proc.register_kwargs.update(args=args, kwargs=kwargs)

    proc.start()
    proc.setup_is_done.wait()

    proc.raise_exception(None)
    proc.should_cleanup.set()

    proc.join()

    assert proc.exitcode == 0
    assert proc.n_cleanup_calls == 2


def test_exception(proc: ProcessUnderTest) -> None:
    """Tests that registered function is called on exception."""

    proc.start()
    proc.setup_is_done.wait()

    proc.raise_exception(Exception("Something bad happened"))
    proc.should_cleanup.set()

    proc.join()

    assert proc.exitcode == 1
    assert proc.n_cleanup_calls == 1


@pytest.mark.parametrize('sig', [signal.SIGINT, signal.SIGTERM, signal.SIGABRT])
def test_signals(proc: ProcessUnderTest, sig: int) -> None:
    """Tests that registered function is called on specified signals."""

    proc.register_kwargs.update(signals=(sig,))

    proc.start()
    proc.setup_is_done.wait()

    os.kill(proc.pid, sig)
    proc.should_cleanup.set()

    proc.join()

    assert proc.exitcode == sig
    assert proc.n_cleanup_calls == 1


def test_raise_keyboard_interrupt(proc: ProcessUnderTest) -> None:
    """Tests that KeyboardInterrupt is raised on SIGINT when specified."""

    proc.register_kwargs.update(keyboard_interrupt_on_sigint=True)

    proc.start()
    proc.setup_is_done.wait()

    os.kill(proc.pid, signal.SIGINT)
    proc.should_cleanup.set()

    proc.join()

    assert proc.exitcode == 1
    assert proc.n_cleanup_calls == 1


def test_successful_exit(proc: ProcessUnderTest) -> None:
    """Tests that exit code 0 is returned on signal when specified."""

    proc.register_kwargs.update(successful_exit=True)

    proc.start()
    proc.setup_is_done.wait()

    os.kill(proc.pid, signal.SIGINT)
    proc.should_cleanup.set()

    proc.join()

    assert proc.exitcode == 0, proc.exitcode
    assert proc.n_cleanup_calls == 1, proc.n_cleanup_calls


@pytest.mark.parametrize('proc', [sig_handler_program], indirect=True)
def test_prev_sig_handler(proc: ProcessUnderTest) -> None:
    """Tests previously registered signal handler is called."""

    proc.start()
    proc.setup_is_done.wait()

    os.kill(proc.pid, signal.SIGTERM)

    proc.join()

    assert proc.exitcode == 66
    assert proc.n_cleanup_calls == 1


@pytest.mark.parametrize('proc', [unregister_program], indirect=True)
def test_unregister(proc: ProcessUnderTest) -> None:
    """
    Tests that unregistering a function doesn't call the function and doesn't
    mess up previously registered signal handler.

    """

    proc.start()
    proc.setup_is_done.wait()

    os.kill(proc.pid, signal.SIGTERM)

    proc.join()

    assert proc.exitcode == 66
    assert proc.n_cleanup_calls == 0


@pytest.mark.parametrize('proc', [multiple_register_program], indirect=True)
def test_multiple_register(proc: ProcessUnderTest) -> None:
    """Tests that multiple functions can be registered and unregistered."""

    proc.start()
    proc.setup_is_done.wait()

    os.kill(proc.pid, signal.SIGTERM)

    proc.join()

    assert proc.exitcode == 66
    assert proc.n_cleanup_calls == 2
