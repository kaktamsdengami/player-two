def test_sync_ptt_follows_the_dashboard_and_mutes_when_it_is_down():
    import threading

    import httpx

    from voice.listen import sync_ptt

    talking = threading.Event()
    sync_ptt(lambda: True, talking)
    assert talking.is_set()

    def down() -> bool:
        raise httpx.ConnectError("refused")

    sync_ptt(down, talking)
    assert not talking.is_set()
