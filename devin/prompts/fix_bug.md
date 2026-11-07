You are fixing a bug that PLAYER TWO, an automated QA tester, found and verified in the game
repository {repo} (branch {base_branch}).

## Bug: {title}
- Finding id: {finding_id}
- Severity: {severity}
- Where: {location}

### Steps to reproduce
{steps}

### Expected
{expected}

### Actual
{actual}

### QA event log excerpt (JSONL from the QA build's `-qa-log`)
```
{log_excerpt}
```

### File hints
{file_hints}

## What to do
Fix in source, add a regression test if the codebase allows it, open a PR.

1. Fix the bug in source. Keep the change minimal and in the style of the surrounding code.
2. Add a regression test if the codebase allows it; otherwise explain in the PR how to reproduce.
3. Do not touch the QA patches (frame-step, event log, reset) except to keep them compiling.
4. Open a PR against {base_branch} titled "Fix: {title} ({finding_id})" and put the root cause,
   the fix and how you checked it in the description.
