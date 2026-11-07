

def test_start_passes_plan_and_preset(tmp_path):
    from app.main import Runtime

    rt = Runtime(tmp_path)
    seen = {}

    def new(mode=None, plan=None, preset=None):
        seen.update(mode=mode, plan=plan, preset=preset)
        raise RuntimeError("stop here")

    rt.new = new
    try:
        rt.start("live", "power-ups", "stage-kb3")
    except Exception:  # noqa: BLE001
        pass
    assert seen == {"mode": "live", "plan": "power-ups", "preset": "stage-kb3"}
