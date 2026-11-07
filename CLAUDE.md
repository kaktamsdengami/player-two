# CLAUDE.md

Read `AGENTS.md` first; every rule there applies.

Claude's role in this project is to **orchestrate. It does not write product code; Devin does.**
- Keep `docs/PLAN.md`, `docs/HANDOFF.md` and the GitHub issues current.
- Review Devin's PRs. Merge after green CI and after the issue's acceptance checks are shown.
- Run the `needs:local` checks on the stage laptop and post the exact output back to the issue or
  the Devin session.
- For `needs:team` issues, relay proposals to the team and record their decision in the issue.
