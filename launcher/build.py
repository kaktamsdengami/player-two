"""Build the game fork (Linux: autotools) or fetch the Windows zip that the fork's CI builds."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from urllib.parse import quote

from launcher.config import IS_WINDOWS, LauncherConfig

GAME_REPO = "kaktamsdengami/chocolate-doom"
QA_BRANCH = "player-two-qa"
WINDOWS_ARTIFACT = "MSYS2 UCRT64"


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def build(cfg: LauncherConfig) -> Path:
    """Build `cfg.fork_dir` (incremental `make`) and return the executable.

    On Windows the stage laptop has no toolchain: `fetch_ci_build` downloads the CI zip instead."""
    if IS_WINDOWS:
        if cfg.exe.exists():
            return cfg.exe
        raise FileNotFoundError(f"{cfg.exe} missing: run `python -m launcher fetch` first")
    if not (cfg.fork_dir / "Makefile").exists():
        subprocess.run(["./autogen.sh"], cwd=cfg.fork_dir, check=True, capture_output=True)
    subprocess.run(
        ["make", f"-j{os.cpu_count() or 4}"], cwd=cfg.fork_dir, check=True, capture_output=True
    )
    return cfg.exe


def resolve_sha(ref: str, repo: str = GAME_REPO) -> str:
    """Branch, tag, sha or `pull/N/head` on GitHub -> full commit sha (needs `gh`)."""
    if ref.startswith("pull/"):
        return _run(["gh", "api", f"repos/{repo}/pulls/{ref.split('/')[1]}", "-q", ".head.sha"])
    return _run(["gh", "api", f"repos/{repo}/commits/{ref}", "-q", ".sha"])


def find_artifact(ref: str, repo: str = GAME_REPO) -> int:
    """Newest unexpired Windows artifact for a branch, sha or `pull/N/head` (a job can be green
    while another job of the same run, e.g. macOS, is still running or failed)."""
    is_branch = not ref.startswith("pull/") and not re.fullmatch(r"[0-9a-f]{7,40}", ref)
    sha = None if is_branch else resolve_sha(ref, repo)
    out = _run(
        ["gh", "api", f"repos/{repo}/actions/artifacts?name={quote(WINDOWS_ARTIFACT)}&per_page=100",
         "-q", ".artifacts[] | [.id, .expired, .workflow_run.head_branch, .workflow_run.head_sha]"
         " | @tsv"]
    )  # fmt: skip
    for line in out.splitlines():
        art_id, expired, branch, head = line.split("\t")
        if expired == "false" and (head == sha if sha else branch == ref):
            return int(art_id)
    raise RuntimeError(f"no Windows build for {ref} yet (fork CI still running?)")


def create_branch(name: str, from_ref: str = QA_BRANCH, repo: str = GAME_REPO) -> None:
    """Create `name` on GitHub at `from_ref` (no local clone needed; idempotent)."""
    sha = resolve_sha(from_ref, repo)
    r = subprocess.run(
        ["gh", "api", f"repos/{repo}/git/refs", "-f", f"ref=refs/heads/{name}", "-f", f"sha={sha}"],
        capture_output=True, text=True,
    )  # fmt: skip
    if r.returncode and "already exists" not in r.stdout + r.stderr:
        raise RuntimeError(f"cannot create {name}: {(r.stderr or r.stdout).strip()}")


def qa_script(
    cfg: LauncherConfig, rel: str, dest: Path, ref: str = QA_BRANCH, repo: str = GAME_REPO
) -> Path:
    """A QA script (`qa/*.txt`) from the local fork, or downloaded from GitHub when there is no
    clone (stage laptop)."""
    local = cfg.fork_dir / rel
    if local.exists():
        return local
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / Path(rel).name
    url = f"repos/{repo}/contents/{rel}?ref={quote(ref, safe='')}"
    out.write_text(_run(["gh", "api", url, "-H", "Accept: application/vnd.github.raw"]) + "\n")
    return out


def fetch_ci_build(
    dest: Path, ref: str = QA_BRANCH, repo: str = GAME_REPO, wait_s: float = 0, poll_s: float = 20
) -> Path:
    """Download the Windows zip that the fork's CI built for `ref` and unpack it into `dest`,
    waiting up to `wait_s` for CI to finish."""
    end = time.monotonic() + wait_s
    while True:
        try:
            art_id = find_artifact(ref, repo)
            break
        except RuntimeError:
            if time.monotonic() >= end:
                raise
            time.sleep(poll_s)
    tmp = dest / "_artifact"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    blob = tmp / "artifact.zip"
    with blob.open("wb") as f:
        subprocess.run(
            ["gh", "api", f"repos/{repo}/actions/artifacts/{art_id}/zip"], stdout=f, check=True
        )
    with zipfile.ZipFile(blob) as z:
        z.extractall(tmp)
    blob.unlink()
    for inner in tmp.rglob("*.zip"):
        with zipfile.ZipFile(inner) as z:
            z.extractall(dest)
    shutil.rmtree(tmp, ignore_errors=True)
    exe = next(dest.rglob("chocolate-doom.exe"), None)
    if exe is None:
        raise RuntimeError(f"chocolate-doom.exe not found in artifact {art_id}")
    return exe


def pull_and_rebuild(cfg: LauncherConfig, ref: str = QA_BRANCH, wait_s: float = 1200) -> Path:
    """After a fix: check out `ref` (e.g. `pull/1/head`) in the fork and rebuild it (Windows: wait
    for the fork's CI build of `ref` and unpack it next to `cfg.exe`)."""
    if IS_WINDOWS:
        return fetch_ci_build(cfg.exe.parent, ref, wait_s=wait_s)
    _run(["git", "fetch", "-q", "origin", ref], cwd=cfg.fork_dir)
    _run(["git", "checkout", "-q", "--detach", "FETCH_HEAD"], cwd=cfg.fork_dir)
    return build(cfg)
