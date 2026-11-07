def test_shell_is_refused_on_the_local_desktop():
    import pytest

    driver = pytest.importorskip("hai_drivers.desktop.local.driver")
    LocalDesktopDriver = driver.LocalDesktopDriver

    from agents.tester import SHELL_REFUSED, forbid_shell

    forbid_shell()
    r = LocalDesktopDriver.run_command(object(), ["cat", "events.jsonl"])
    assert r.returncode != 0 and r.stderr == SHELL_REFUSED and not r.stdout


def test_hai_regions_restricts_fallback(monkeypatch):
    import pytest

    from agents.tester import HBusyError, choose_region

    monkeypatch.setenv("HAI_BASE_URL", "https://agp.hcompany.ai")
    monkeypatch.setenv("HAI_REGIONS", "https://agp.hcompany.ai")
    seen = []

    def q(url):
        seen.append(url)
        return {"available": 0}

    with pytest.raises(HBusyError):
        choose_region(quota_fn=q)
    assert seen == ["https://agp.hcompany.ai"]
