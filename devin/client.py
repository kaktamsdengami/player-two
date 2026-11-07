"""Devin API v3 client: one fix session per verified Finding (T10).

Flow: create_fix_session → follow (polls, reports every change) → approve_merge on the human's
"yes", or send_feedback once on "not fixed". The verifier (T11) decides fixed / not_fixed.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.contracts import Finding, FixAttempt, FixResult

API_BASE = "https://api.devin.ai"
PROMPT = Path(__file__).parent / "prompts" / "fix_bug.md"
DEFAULT_REPO = "kaktamsdengami/chocolate-doom"
DEFAULT_BRANCH = "player-two-qa"
TERMINAL = {FixResult.merged, FixResult.failed}
FAILED_STATUSES = {"error"}


class DevinError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def render_prompt(
    finding: Finding,
    repo: str = DEFAULT_REPO,
    base_branch: str = DEFAULT_BRANCH,
    file_hints: list[str] | None = None,
) -> str:
    log = "\n".join(e.model_dump_json(exclude_none=True) for e in finding.evidence.log_excerpt)
    return PROMPT.read_text().format(
        repo=repo,
        base_branch=base_branch,
        title=finding.title,
        finding_id=finding.id,
        severity=finding.severity,
        location=finding.location,
        steps="\n".join(f"{i}. {s}" for i, s in enumerate(finding.steps, 1)),
        expected=finding.expected,
        actual=finding.actual,
        log_excerpt=log or "(no log excerpt)",
        file_hints="\n".join(f"- {h}" for h in file_hints or []) or "- (none)",
    )


def result_from_session(
    session: dict, ignore: frozenset[str] | set[str] = frozenset()
) -> tuple[FixResult, str | None]:
    """Map a v3 SessionResponse to our FixResult and the PR URL (if any).

    `ignore`: PR URLs from an earlier round (a merged fix that failed re-verification).
    """
    prs = [p for p in session.get("pull_requests") or [] if p.get("pr_url") not in ignore]
    pr = prs[-1] if prs else None
    pr_url = pr.get("pr_url") if pr else None
    pr_state = (pr.get("pr_state") or "").lower() if pr else ""
    status = session.get("status")
    if pr_state == "merged":
        return FixResult.merged, pr_url
    if (
        status in FAILED_STATUSES
        or status == "suspended"
        and session.get("status_detail")
        not in (
            None,
            "inactivity",
            "user_request",
        )
    ):
        return FixResult.failed, pr_url
    if pr_url and pr_state != "closed":
        return FixResult.pr_open, pr_url
    if status == "exit" or session.get("status_detail") == "finished":
        return FixResult.failed, pr_url
    if status in ("new", "claimed"):
        return FixResult.queued, pr_url
    return FixResult.working, pr_url


def _is_active(session: dict) -> bool:
    status, detail = session.get("status"), session.get("status_detail")
    if status in ("new", "claimed", "resuming"):
        return True
    return status == "running" and detail not in ("finished", "waiting_for_user")


class DevinClient:
    def __init__(
        self,
        api_key: str,
        org_id: str,
        *,
        base_url: str = API_BASE,
        client: httpx.Client | None = None,
        repo: str = DEFAULT_REPO,
        base_branch: str = DEFAULT_BRANCH,
        max_acu_limit: int | None = 10,
        tags: tuple[str, ...] = ("player-two",),
    ):
        self.org_id = org_id
        self.repo = repo
        self.base_branch = base_branch
        self.max_acu_limit = max_acu_limit
        self.tags = list(tags)
        self.http = client or httpx.Client(timeout=30)
        self.base = f"{base_url.rstrip('/')}/v3/organizations/{org_id}/sessions"
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self._stale_prs: dict[str, set[str]] = {}
        # after feedback: devin_id -> whether Devin has been seen working on it again
        self._feedback: dict[str, bool] = {}

    @classmethod
    def from_env(cls, **kw) -> DevinClient:
        try:
            from dotenv import find_dotenv, load_dotenv

            load_dotenv(find_dotenv(usecwd=True))
        except ImportError:
            pass
        missing = [k for k in ("DEVIN_API_KEY", "DEVIN_ORG_ID") if not os.environ.get(k)]
        if missing:
            raise DevinError(f"missing env: {', '.join(missing)}")
        return cls(os.environ["DEVIN_API_KEY"], os.environ["DEVIN_ORG_ID"], **kw)

    def _req(self, method: str, path: str = "", **kw) -> dict:
        r = self.http.request(method, self.base + path, headers=self.headers, **kw)
        if r.status_code >= 400:
            raise DevinError(f"Devin API {method} {path or '/'}: HTTP {r.status_code}")
        return r.json() if r.content else {}

    # ---------------------------------------------------------------- sessions

    def create_fix_session(
        self, finding: Finding, file_hints: list[str] | None = None, attempt_id: str | None = None
    ) -> FixAttempt:
        body = {
            "prompt": render_prompt(finding, self.repo, self.base_branch, file_hints),
            "title": f"PLAYER TWO fix: {finding.title}"[:120],
            "repos": [self.repo],
            "tags": [*self.tags, f"finding:{finding.id}"],
        }
        if self.max_acu_limit:
            body["max_acu_limit"] = self.max_acu_limit
        s = self._req("POST", json=body)
        attempt = FixAttempt(
            id=attempt_id or f"fix-{finding.id}",
            finding_id=finding.id,
            devin_session_id=s["session_id"],
            devin_session_url=s.get("url"),
            started_at=_now(),
        )
        return self._apply(attempt, s)

    def get_session(self, devin_id: str) -> dict:
        return self._req("GET", f"/{devin_id}")

    def messages(self, devin_id: str) -> list[dict]:
        return self._req("GET", f"/{devin_id}/messages").get("items", [])

    def send_message(self, devin_id: str, message: str) -> None:
        self._req("POST", f"/{devin_id}/messages", json={"message": message})

    def _apply(self, attempt: FixAttempt, session: dict) -> FixAttempt:
        sid = attempt.devin_session_id
        result, pr_url = result_from_session(session, self._stale_prs.get(sid, set()))
        resumed = self._feedback.get(sid)
        if resumed is not None and session.get("status") not in FAILED_STATUSES:
            # The session still shows its old finished state until Devin picks the feedback up.
            if _is_active(session):
                self._feedback[sid] = True
                result = FixResult.working
            elif not resumed:
                result = FixResult.working
            else:
                del self._feedback[sid]
        update: dict = {"result": result, "pr_url": pr_url or attempt.pr_url}
        if session.get("url"):
            update["devin_session_url"] = session["url"]
        if session.get("acus_consumed") is not None:
            update["acus"] = session["acus_consumed"]
        if result in TERMINAL and attempt.finished_at is None:
            update["finished_at"] = _now()
        return attempt.model_copy(update=update)

    def refresh(self, attempt: FixAttempt) -> FixAttempt:
        return self._apply(attempt, self.get_session(attempt.devin_session_id))

    def follow(
        self,
        attempt: FixAttempt,
        on_update: Callable[[FixAttempt], None] | None = None,
        *,
        until: frozenset[FixResult] = frozenset({FixResult.pr_open, *TERMINAL}),
        poll_s: float = 15,
        timeout_s: float = 3600,
        sleep: Callable[[float], None] = time.sleep,
    ) -> FixAttempt:
        """Poll until the attempt reaches a state in `until`; call on_update on every change."""
        last = attempt.model_dump()
        waited = 0.0
        while True:
            attempt = self.refresh(attempt)
            if attempt.model_dump() != last:
                last = attempt.model_dump()
                if on_update:
                    on_update(attempt)
            if attempt.result in until:
                return attempt
            if waited >= timeout_s:
                raise DevinError(f"timeout following {attempt.devin_session_id}")
            sleep(poll_s)
            waited += poll_s

    # ---------------------------------------------------------------- human decisions

    def approve_merge(self, attempt: FixAttempt) -> FixAttempt:
        if not attempt.pr_url:
            raise DevinError("no PR to merge yet")
        self.send_message(
            attempt.devin_session_id,
            f"The developer approved the fix. Merge {attempt.pr_url} into {self.base_branch} "
            "now (squash), then reply 'merged'.",
        )
        return attempt

    def send_feedback(self, attempt: FixAttempt, verifier_note: str) -> FixAttempt:
        """The single feedback round after the re-verify says "not fixed"."""
        if attempt.round >= 2:
            raise DevinError("feedback round already used")
        merged = attempt.result == FixResult.merged
        where = "open a new PR" if merged else "fix it on the same PR and push"
        self.send_message(
            attempt.devin_session_id,
            "Not fixed: PLAYER TWO replayed the repro on your branch and the bug is still there.\n"
            f"{verifier_note}\nPlease {where}.",
        )
        update: dict = {"round": 2, "result": FixResult.working, "finished_at": None}
        self._feedback[attempt.devin_session_id] = False
        if merged and attempt.pr_url:
            self._stale_prs.setdefault(attempt.devin_session_id, set()).add(attempt.pr_url)
            update["pr_url"] = None
        return attempt.model_copy(update=update)


def _demo(argv: list[str] | None = None) -> int:
    """`python -m devin.client finding.json [hint ...]`: open one real fix session, follow it."""
    import sys

    args = sys.argv[1:] if argv is None else argv
    finding = Finding.model_validate_json(Path(args[0]).read_text())
    dc = DevinClient.from_env(repo=os.environ.get("GAME_REPO", DEFAULT_REPO))
    attempt = dc.create_fix_session(finding, file_hints=args[1:])
    print(json.dumps({"session": attempt.devin_session_url}))
    attempt = dc.follow(attempt, lambda a: print(a.model_dump_json(include={"result", "pr_url"})))
    print(attempt.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_demo())
