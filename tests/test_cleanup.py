import multiprocessing as mp
import os
import signal
import sys

import pytest


def setup_module():
    mp.set_start_method('spawn')


class ProcessUnderTest(mp.Process):
    def __init__(self) -> None:
        self.setup_is_done = mp.Event()
        self.should_cleanup = mp.Event()

        self._n_calls = mp.Value("i", 0)

        self._pconn, self._cconn = mp.Pipe()

        super().__init__(
            target=self.run_program,
            args=(
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

    @staticmethod
    def run_program(value, should_cleanup, setup_is_done, cconn) -> None:
        import pyterminate

        @pyterminate.register(signals=(signal.SIGINT, signal.SIGTERM))
        def cleanup():
            assert should_cleanup.wait(timeout=5)
            value.value += 1

        setup_is_done.set()

        exc = cconn.recv()
        if exc is not None:
            raise exc

        sys.exit(0)


@pytest.fixture(scope='function')
def proc() -> ProcessUnderTest:
    return ProcessUnderTest()


def test_normal_exit(proc: ProcessUnderTest) -> None:
    proc.start()
    proc.setup_is_done.wait()

    proc.raise_exception(None)
    proc.should_cleanup.set()

    proc.join()

    assert proc.exitcode == 0, proc.exitcode
    assert proc.n_cleanup_calls == 1, proc.n_cleanup_calls


def test_exception(proc: ProcessUnderTest) -> None:
    proc.start()
    proc.setup_is_done.wait()

    proc.raise_exception(Exception("Something bad happened"))
    proc.should_cleanup.set()

    proc.join()

    assert proc.exitcode == 1, proc.exitcode
    assert proc.n_cleanup_calls == 1, proc.n_cleanup_calls


@pytest.mark.parametrize('sig', [signal.SIGINT, signal.SIGTERM])
def test_sigint(proc: ProcessUnderTest, sig: int) -> None:
    proc.start()
    proc.setup_is_done.wait()

    os.kill(proc.pid, sig)
    proc.should_cleanup.set()

    proc.join()

    assert proc.exitcode == sig, proc.exitcode
    assert proc.n_cleanup_calls == 1, proc.n_cleanup_calls
