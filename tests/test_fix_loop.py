from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from agents.fix_loop import FixLoop, Replay, add_comparison
from app.contracts import Finding, FixAttempt, FixResult, FixVerdict, KnownBug
from insights import fix_compare
from insights.fix_compare import code_part, compare, overlap, render_html, split_files

DEVIN = """diff --git a/qa/test_medikit_message.sh b/qa/test_medikit_message.sh
+++ b/qa/test_medikit_message.sh
+echo test
diff --git a/src/doom/p_inter.c b/src/doom/p_inter.c
--- a/src/doom/p_inter.c
+++ b/src/doom/p_inter.c
@@ -339,6 +339,7 @@
+    int        oldhealth;
@@ -477,10 +478,11 @@
+    oldhealth = player->health;
     if (!P_GiveBody (player, 25))
-    if (player->health < 25)
+    if (oldhealth < 25)
"""
UPSTREAM = """diff --git a/src/doom/p_inter.c b/src/doom/p_inter.c
--- a/src/doom/p_inter.c
+++ b/src/doom/p_inter.c
@@ -481,7 +481,7 @@
-    if (player->health < 25)
+    if (player->health < 50)
diff --git a/src/doom/st_stuff.c b/src/doom/st_stuff.c
--- a/src/doom/st_stuff.c
+++ b/src/doom/st_stuff.c
-        if (plyr->health - st_oldhealth > ST_MUCHPAIN)
+        if (st_oldhealth - plyr->health > ST_MUCHPAIN)
"""
REF = "fabiangreffrath/crispy-doom@984fff1dce2bc7db076d8356208b9d0b3fbbbf0a"


def _finding() -> Finding:
    return Finding(
        id="F-1",
        session_id="s",
        title="Medikit message",
        location="E1M1",
        steps=["pick up a medikit at 20 health"],
        expected="never give up",
        actual="plain message",
        known_bug_ref="KB1",
        reported_at=datetime(2026, 11, 7, tzinfo=UTC),
    )


def _attempt(**kw) -> FixAttempt:
    return FixAttempt(
        id="fix-F-1",
        finding_id="F-1",
        devin_session_id="d",
        started_at=datetime(2026, 11, 7, tzinfo=UTC),
        **kw,
    )


class FakeDevin:
    """Serves a scripted sequence of results for `follow`."""

    base_branch = "qa-run/test"

    def __init__(self, results: list[FixResult]):
        self.results = list(results)
        self.calls: list[str] = []

    def create_fix_session(self, finding):
        self.calls.append("create")
        return _attempt()

    def follow(self, a, on_update=None, *, until, poll_s, timeout_s):
        r = self.results.pop(0)
        assert r in until
        self.calls.append(f"follow:{r}")
        return a.model_copy(
            update={"result": r, "pr_url": a.pr_url or "https://github.com/o/r/pull/1"}
        )

    def approve_merge(self, a):
        self.calls.append("merge")
        return a

    def send_feedback(self, a, note):
        assert a.result == FixResult.merged  # so the client drops the merged PR as stale
        self.calls.append("feedback")
        return a.model_copy(update={"round": 2, "result": FixResult.working, "pr_url": None})


def _loop(devin, outcomes, approve=True):
    rebuilt, replays = [], list(outcomes)

    def replay(f, tag):
        still = replays.pop(0)
        return Replay(still, f"{tag}: {'still' if still else 'gone'}", Path(f"/tmp/{tag}.mp4"), 3.0)

    loop = FixLoop(devin, replay, lambda ref: rebuilt.append(ref) or Path("x"), lambda a: approve)
    return loop, rebuilt


def test_fixed_first_round():
    d = FakeDevin([FixResult.pr_open, FixResult.merged])
    loop, rebuilt = _loop(d, [False])
    a, rep = loop.run(_finding())
    assert a.result == FixResult.fixed and a.round == 1 and a.finished_at
    assert d.calls == ["create", "follow:pr_open", "merge", "follow:merged"]
    assert rebuilt == ["qa-run/test"] and rep.clip.name == "round1.mp4"


def test_one_feedback_round_then_fixed():
    d = FakeDevin([FixResult.pr_open, FixResult.merged, FixResult.pr_open, FixResult.merged])
    loop, rebuilt = _loop(d, [True, False])
    a, _ = loop.run(_finding())
    assert a.result == FixResult.fixed and a.round == 2
    assert d.calls.count("feedback") == 1 and len(rebuilt) == 2


def test_stops_honestly_after_the_single_feedback_round():
    d = FakeDevin([FixResult.merged, FixResult.merged])
    loop, rebuilt = _loop(d, [True, True])
    a, rep = loop.run(_finding())
    assert a.result == FixResult.not_fixed and a.round == 2
    assert d.calls.count("feedback") == 1 and "still" in rep.note


def test_no_merge_without_approval():
    d = FakeDevin([FixResult.pr_open])
    loop, rebuilt = _loop(d, [], approve=False)
    a, rep = loop.run(_finding(), _attempt())
    assert a.result == FixResult.pr_open and rep is None and not rebuilt
    assert "merge" not in d.calls


def test_failed_session_stops():
    d = FakeDevin([FixResult.failed])
    loop, rebuilt = _loop(d, [])
    a, _ = loop.run(_finding())
    assert a.result == FixResult.failed and not rebuilt


def test_code_part_drops_tests_and_limits_upstream_to_devins_files():
    assert list(split_files(code_part(DEVIN))) == ["src/doom/p_inter.c"]
    assert list(split_files(code_part(UPSTREAM, {"src/doom/p_inter.c"}))) == ["src/doom/p_inter.c"]
    assert len(split_files(code_part(UPSTREAM, {"src/other.c"}))) == 2


def test_compare_verdicts():
    c = compare(DEVIN, UPSTREAM, REF, fixed=True)
    assert c.verdict == FixVerdict.different_but_valid
    assert "st_stuff" not in c.upstream_diff and "qa/" not in c.devin_diff
    assert compare(UPSTREAM, UPSTREAM, REF, fixed=True).verdict == FixVerdict.same_approach
    assert compare(DEVIN, UPSTREAM, REF, fixed=False).verdict == FixVerdict.incomplete
    assert overlap(UPSTREAM, UPSTREAM) == 1.0


def test_llm_assessment_is_used_when_available(monkeypatch):
    monkeypatch.setenv("HAI_API_KEY", "k")

    def post(url, **kw):
        body = {"choices": [{"message": {"content": "\n\nsame_approach: both fix the check."}}]}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(fix_compare.httpx, "post", post)
    c = compare(DEVIN, UPSTREAM, REF, fixed=True, assess=True)
    assert c.verdict == FixVerdict.same_approach and "both fix the check" in c.summary


def test_llm_failure_falls_back_to_overlap(monkeypatch):
    monkeypatch.setenv("HAI_API_KEY", "k")

    def post(url, **kw):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(fix_compare.httpx, "post", post)
    assert (
        compare(DEVIN, UPSTREAM, REF, True, assess=True).verdict == FixVerdict.different_but_valid
    )


def test_render_html_side_by_side():
    page = render_html(compare(DEVIN, UPSTREAM, REF, fixed=True))
    assert page.count("<pre>") == 2 and 'class="add"' in page and "&lt; 25" in page


def test_add_comparison_needs_upstream_ref(monkeypatch):
    monkeypatch.setattr("agents.fix_loop.pr_diff", lambda url: DEVIN)
    monkeypatch.setattr("agents.fix_loop.upstream_diff", lambda ref: UPSTREAM)
    bug = KnownBug.model_validate(
        {
            "id": "KB1",
            "title": "t",
            "source_url": "u",
            "map": "E1M1",
            "steps": ["s"],
            "expected": "e",
            "actual": "a",
            "log_signature": {"description": "d", "all_of": [{"type": "pickup"}]},
            "upstream_fix_ref": REF,
        }  # fmt: skip
    )
    a = _attempt(result=FixResult.fixed, pr_url="https://github.com/o/r/pull/1")
    assert add_comparison(a, bug, assess=False).comparison.upstream_fix_ref == REF
    no_up = bug.model_copy(update={"upstream_fix_ref": None})
    assert add_comparison(a, no_up, assess=False).comparison is None


class _Proc:
    def __init__(self, rc):
        self.returncode = rc


class _Log:
    def __init__(self, events):
        self.events = events

    def since(self):
        return self.events


class _FakeGame:
    def __init__(self, rc, events, hang=False):
        self.proc, self.log, self.hang = _Proc(rc), _Log(events), hang
        self.run_dir = Path("/tmp/p2-test-script-replay")

    def start(self, *a):
        return object()

    @property
    def running(self):
        return self.hang

    def stop(self):
        pass


def _bug():
    from agents.oracles import load_known_bugs

    return next(b for b in load_known_bugs() if b.id == "KB1")


def _event():
    from app.contracts import GameEvent

    return GameEvent(tic=1, type="message", data={"text": "hi"})


@pytest.mark.parametrize("rc,events,hang", [(139, [1], False), (0, [], False), (None, [1], True)])
def test_incomplete_replay_is_not_fixed(rc, events, hang):
    from agents.fix_loop import ScriptReplay

    game = _FakeGame(rc, [_event() for _ in events], hang)
    r = ScriptReplay(game, _bug(), Path("qa/x.txt"), 1, 1, timeout_s=0.3, record=False)(
        _finding(), "round1"
    )
    assert r.still_there and r.note.startswith("replay incomplete")


def test_complete_replay_without_signature_is_fixed():
    from agents.fix_loop import ScriptReplay

    game = _FakeGame(0, [_event()])
    r = ScriptReplay(game, _bug(), Path("qa/x.txt"), 1, 1, record=False)(_finding(), "round1")
    assert not r.still_there
