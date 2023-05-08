import sys

import pytest
from pytest_pyodide import run_in_pyodide


@run_in_pyodide()
def test_persistent_mock_pyodide(selenium_standalone_micropip):  #
    import sys
    from importlib.metadata import version as importlib_version
    from io import StringIO

    from micropip import add_mock_package

    capture_stdio = StringIO()

    sys.stdout = capture_stdio
    add_mock_package("test_1", "1.0.0", persistent=True)
    add_mock_package(
        "test_2",
        "1.2.0",
        modules={
            "t1": "print('hi from t1')",
            "t2": """
        def fn():
            print("Hello from fn")
        """,
        },
        persistent=True,
    )
    import test_1

    dir(test_1)

    import t1

    dir(t1)
    import t2

    dir(t2)

    t2.fn()
    assert capture_stdio.getvalue().find("Hello from fn") != -1
    assert capture_stdio.getvalue().find("hi from t1") != -1
    assert importlib_version("test_1") == "1.0.0"


def test_persistent_mock(monkeypatch, capsys, tmp_path):
    import site
    from importlib.metadata import version as importlib_version

    from micropip import add_mock_package

    def _getsitepackages():
        return [tmp_path]

    monkeypatch.setattr(site, "getsitepackages", _getsitepackages)
    monkeypatch.setattr(sys, "path", [tmp_path])
    add_mock_package("test_1", "1.0.0")
    add_mock_package(
        "test_2",
        "1.2.0",
        modules={
            "t1": "print('hi from t1')",
            "t2": """
        def fn():
            print("Hello from fn")
        """,
        },
    )
    import t1

    dir(t1)
    import t2

    dir(t2)
    import test_1

    dir(test_1)

    t2.fn()
    assert importlib_version("test_2") == "1.2.0"
    captured = capsys.readouterr()
    assert captured.out.find("hi from t1") != -1
    assert captured.out.find("Hello from fn") != -1


def test_memory_mock():
    import micropip

    def mod_init(module):
        module.__dict__["add2"] = lambda x: x + 2

    micropip.add_mock_package(
        "micropip_test_bob",
        "1.0.0",
        modules={
            "micropip_bob_mod": "print('hi from bob')",
            "micropip_bob_mod.fn": mod_init,
        },
        persistent=False,
    )
    import importlib

    import micropip_bob_mod

    dir(micropip_bob_mod)

    import micropip_bob_mod.fn

    assert micropip_bob_mod.fn.add2(5) == 7

    found_bob = False
    for d in importlib.metadata.distributions():
        if d.name == "micropip_test_bob":
            found_bob = True
    assert found_bob is True
    assert (
        importlib.metadata.distribution("micropip_test_bob").name == "micropip_test_bob"
    )
    # check package removes okay
    micropip.remove_mock_package("micropip_test_bob")
    del micropip_bob_mod
    with pytest.raises(ImportError):
        import micropip_bob_mod

        dir(micropip_bob_mod)


@run_in_pyodide()
def test_memory_mock_pyodide(selenium_standalone_micropip):
    import pytest

    import micropip

    def mod_init(module):
        module.__dict__["add2"] = lambda x: x + 2

    micropip.add_mock_package(
        "micropip_test_bob",
        "1.0.0",
        modules={
            "micropip_bob_mod": "print('hi from bob')",
            "micropip_bob_mod.fn": mod_init,
        },
        persistent=False,
    )
    import importlib

    import micropip_bob_mod

    dir(micropip_bob_mod)

    import micropip_bob_mod.fn

    assert micropip_bob_mod.fn.add2(5) == 7

    found_bob = False
    for d in importlib.metadata.distributions():
        if d.name == "micropip_test_bob":
            found_bob = True
    assert found_bob is True
    assert (
        importlib.metadata.distribution("micropip_test_bob").name == "micropip_test_bob"
    )
    # check package removes okay
    micropip.remove_mock_package("micropip_test_bob")
    del micropip_bob_mod
    with pytest.raises(ImportError):
        import micropip_bob_mod

        dir(micropip_bob_mod)
