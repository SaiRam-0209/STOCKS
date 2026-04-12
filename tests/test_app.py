"""Smoke test for main app module imports."""


def test_imports():
    from project.app import scan, backtest
    assert callable(scan)
    assert callable(backtest)
