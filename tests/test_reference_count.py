import pyterminate
import gc
import weakref
import signal


class Canary():
    pass


def test_unregister_refcount():
    """Tests that unregistering cleans up all references."""

    weakref_c = None

    def func():
        nonlocal weakref_c

        c = Canary()
        weakref_c = weakref.ref(c)

        def cleanup():
            print(c)

        pyterminate.register(cleanup)
        pyterminate.unregister(cleanup)

    func()
    assert weakref_c() is None, gc.get_referrers(weakref_c())


def test_unregister_refcount_with_decorator():
    """
    Tests that unregistering cleans up all references when registered using the
    decorator.

    """

    weakref_c = None

    def func():
        nonlocal weakref_c

        c = Canary()
        weakref_c = weakref.ref(c)

        @pyterminate.register
        def cleanup():
            print(c)

        pyterminate.unregister(cleanup)

    func()
    assert weakref_c() is None, gc.get_referrers(weakref_c())


def test_unregister_refcount_duplicate_calls():
    """
    Tests that unregistering cleans up all references when duplicate register
    and unregister calls are made.

    """

    weakref_c = None

    def func():
        nonlocal weakref_c

        c = Canary()
        weakref_c = weakref.ref(c)

        @pyterminate.register
        def cleanup():
            print(c)

        pyterminate.register(cleanup)
        pyterminate.register(cleanup)
        pyterminate.register(cleanup)
        pyterminate.unregister(cleanup)
        pyterminate.unregister(cleanup)

    func()
    assert weakref_c() is None, gc.get_referrers(weakref_c())


def test_unregister_refcount_multiple_signals():
    """
    Tests that unregistering cleans up all references when multiple signals
    are used.

    """

    weakref_c = None

    def func():
        nonlocal weakref_c

        c = Canary()
        weakref_c = weakref.ref(c)

        @pyterminate.register(
            signals=(signal.SIGINT, signal.SIGSEGV, signal.SIGTERM)
        )
        def cleanup():
            print(c)

        pyterminate.unregister(cleanup)

    func()
    assert weakref_c() is None, gc.get_referrers(weakref_c())


def test_unregister_refcount_multiple_functions():
    """
    Tests that unregistering cleans up all references when multiple functions
    are registered.

    """

    weakref_c = None

    def func():
        nonlocal weakref_c

        c = Canary()
        weakref_c = weakref.ref(c)

        def cleanup_1():
            print(c)

        def cleanup_2():
            print(c)

        def cleanup_3():
            print(c)

        pyterminate.register(cleanup_1)
        pyterminate.register(cleanup_2)
        pyterminate.register(cleanup_3)
        pyterminate.unregister(cleanup_3)
        pyterminate.unregister(cleanup_2)
        pyterminate.unregister(cleanup_1)

    func()
    assert weakref_c() is None, gc.get_referrers(weakref_c())


def test_unregister_refcount_multiple_functions_out_of_order():
    """
    Tests that unregistering cleans up all references when multiple functions
    are registered and then unregistered not in reverse order.

    """

    weakref_c = None

    def func():
        nonlocal weakref_c

        c = Canary()
        weakref_c = weakref.ref(c)

        def cleanup_1():
            print(c)

        def cleanup_2():
            print(c)

        def cleanup_3():
            print(c)

        pyterminate.register(cleanup_1)
        pyterminate.register(cleanup_2)
        pyterminate.register(cleanup_3)
        pyterminate.unregister(cleanup_1)
        pyterminate.unregister(cleanup_3)
        pyterminate.unregister(cleanup_2)

    func()
    assert weakref_c() is None, gc.get_referrers(weakref_c())
