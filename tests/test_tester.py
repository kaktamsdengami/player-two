def test_shell_is_refused_on_the_local_desktop():
    from hai_drivers.desktop.local.driver import LocalDesktopDriver

    from agents.tester import SHELL_REFUSED, forbid_shell

    forbid_shell()
    r = LocalDesktopDriver.run_command(object(), ["cat", "events.jsonl"])
    assert r.returncode != 0 and r.stderr == SHELL_REFUSED and not r.stdout
