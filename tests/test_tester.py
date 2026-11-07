def test_shell_is_refused_on_the_local_desktop():
    import pytest

    driver = pytest.importorskip("hai_drivers.desktop.local.driver")
    LocalDesktopDriver = driver.LocalDesktopDriver

    from agents.tester import SHELL_REFUSED, forbid_shell

    forbid_shell()
    r = LocalDesktopDriver.run_command(object(), ["cat", "events.jsonl"])
    assert r.returncode != 0 and r.stderr == SHELL_REFUSED and not r.stdout
