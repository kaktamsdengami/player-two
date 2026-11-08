"""Compare Devin's fix with the upstream fix commit: side-by-side diff + one-line verdict."""

from __future__ import annotations

import html
import os
import re

import httpx

from app.contracts import FixComparison, FixVerdict

GITHUB_API = "https://api.github.com"
SAME_APPROACH_MIN = 0.6  # token overlap of the added lines
MODELS_URL = "https://api.hcompany.ai/v1/chat/completions"
JUDGE_MODEL = "holo4-27b"


def _github(path: str) -> str:
    headers = {"Accept": "application/vnd.github.diff"}
    if tok := os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {tok}"
    r = httpx.get(GITHUB_API + path, headers=headers, timeout=30, follow_redirects=True)
    r.raise_for_status()
    return r.text


def upstream_diff(ref: str) -> str:
    """`owner/repo@sha` (KnownBug.upstream_fix_ref) -> unified diff of that commit."""
    repo, sha = ref.split("@", 1)
    return _github(f"/repos/{repo}/commits/{sha}")


def pr_diff(pr_url: str) -> str:
    m = re.match(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", pr_url)
    if not m:
        raise ValueError(f"not a GitHub PR URL: {pr_url}")
    return _github(f"/repos/{m[1]}/pulls/{m[2]}")


def split_files(diff: str) -> dict[str, str]:
    """Unified diff -> {path: that file's section}."""
    out: dict[str, str] = {}
    for part in re.split(r"(?m)^(?=diff --git )", diff):
        m = re.match(r"diff --git a/(\S+) b/(\S+)", part)
        if m:
            out[m[2]] = part
    return out


def is_test_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return path.startswith(("qa/", "tests/", "test/")) or name.startswith("test_")


def code_part(diff: str, paths: set[str] | None = None) -> str:
    """Non-test files only; with `paths`, only those files (if any of them are present)."""
    files = {p: s for p, s in split_files(diff).items() if not is_test_path(p)}
    if paths and paths & files.keys():
        files = {p: s for p, s in files.items() if p in paths}
    return "".join(files.values())


def changed_lines(diff: str) -> list[str]:
    return [
        ln
        for ln in diff.splitlines()
        if ln[:1] in "+-" and not ln.startswith(("+++", "---")) and ln[1:].strip()
    ]


def _tokens(lines: list[str]) -> set[str]:
    return {t for ln in lines for t in re.findall(r"\w+|[<>=!]=?|[-+*/&|]", ln[0] + ln[1:])}


def overlap(a: str, b: str) -> float:
    """Token overlap of the added lines (removed lines are the shared bug, not the fix)."""
    ta = _tokens([ln for ln in changed_lines(a) if ln[0] == "+"])
    tb = _tokens([ln for ln in changed_lines(b) if ln[0] == "+"])
    return len(ta & tb) / len(ta | tb) if ta | tb else 0.0


def llm_assess(devin: str, upstream: str) -> tuple[FixVerdict, str] | None:
    """One-line assessment by an H model (Models API); None when unavailable."""
    key = os.environ.get("HAI_API_KEY")
    if not key:
        return None
    prompt = (
        "Two patches fix the same bug in Chocolate Doom. Both pass the bug's replay test.\n"
        "Answer with exactly one line: `same_approach: <why>` if they change the same logic in "
        "the same way, or `different_but_valid: <how they differ>` otherwise. Max 25 words.\n\n"
        f"Devin patch:\n{devin[:6000]}\n\nUpstream patch:\n{upstream[:6000]}"
    )
    try:
        r = httpx.post(
            MODELS_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": JUDGE_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1500,
                "temperature": 0,
            },
            timeout=60,
        )
        r.raise_for_status()
        line = (r.json()["choices"][0]["message"]["content"] or "").strip().splitlines()[-1]
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError):
        return None
    m = re.match(r"`?(same_approach|different_but_valid)`?\s*:\s*(.+)", line.strip())
    return (FixVerdict(m[1]), m[2].strip().rstrip("`")) if m else None


def compare(
    devin: str, upstream: str, upstream_ref: str, fixed: bool, assess: bool = False
) -> FixComparison:
    """`fixed` is the replay verdict: a fix the replay still fails on is incomplete.

    `assess=True` asks an H model for the same/different call; the token overlap is the fallback.
    """
    devin_code = code_part(devin)
    up = code_part(upstream, set(split_files(devin_code)))
    score = overlap(devin_code, up)
    d_files = ", ".join(split_files(devin_code)) or "no code files"
    u_files = ", ".join(split_files(up)) or "no code files"
    nd, nu = len(changed_lines(devin_code)), len(changed_lines(up))
    if not fixed:
        verdict = FixVerdict.incomplete
        head = "Incomplete: the replay still shows the bug"
    elif score >= SAME_APPROACH_MIN:
        verdict = FixVerdict.same_approach
        head = "Same approach as upstream"
    else:
        verdict = FixVerdict.different_but_valid
        head = "Different but valid: the replay passes with a different change than upstream"
    judged = llm_assess(devin_code, up) if fixed and assess else None
    if judged:
        verdict, why = judged
        head = f"{verdict.value.replace('_', ' ').capitalize()}: {why.rstrip('.')}"
    summary = (
        f"{head}. Devin changed {nd} lines in {d_files}; upstream changed {nu} in {u_files} "
        f"({score:.0%} token overlap)."
    )
    return FixComparison(
        upstream_fix_ref=upstream_ref,
        upstream_diff=up,
        devin_diff=devin_code,
        verdict=verdict,
        summary=summary,
    )


def _pane(diff: str) -> str:
    rows = []
    for ln in diff.splitlines():
        cls = "add" if ln.startswith("+") else "del" if ln.startswith("-") else "ctx"
        if ln.startswith(("diff --git", "index ", "+++", "---")):
            cls = "meta"
        rows.append(f'<div class="{cls}">{html.escape(ln) or "&nbsp;"}</div>')
    return "".join(rows)


def render_html(c: FixComparison, title: str = "Devin fix vs upstream fix") -> str:
    """Standalone side-by-side page (dashboard iframe or PR attachment)."""
    verdict = FixVerdict(c.verdict).value.replace("_", " ")
    return f"""<!doctype html><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body{{font:14px system-ui;margin:1rem;background:#111;color:#ddd}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:1rem}}
pre{{font:12px ui-monospace,monospace;background:#1b1b1b;padding:.5rem;overflow:auto;margin:0}}
.add{{background:#12361d;color:#9be9a8}}.del{{background:#3d1515;color:#ff9a9a}}
.meta{{color:#888}}.verdict{{font-size:1.1rem;margin:.5rem 0 1rem}}
</style>
<h1>{html.escape(title)}</h1>
<div class="verdict"><b>{verdict}</b>: {html.escape(c.summary)}</div>
<div class="grid">
<div><h2>Devin</h2><pre>{_pane(c.devin_diff)}</pre></div>
<div><h2>Upstream <small>{html.escape(c.upstream_fix_ref)}</small></h2>
<pre>{_pane(c.upstream_diff)}</pre></div>
</div>
"""
