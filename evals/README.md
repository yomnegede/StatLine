# Answer-quality checks

Start the API, then run `venv/bin/python -m evals.run`. The nine questions in
`cases.json` include players outside the recommended list, comparisons, a
league-wide ranking, a historical player, and unsupported live or defensive
questions. Use `--ids unlisted_player season_ppg_leader` for a quick run.
Pass `--expected-season 2025-26` when you know which season should be active;
this catches accidental fallback to an older season during an NBA data outage.

The runner checks whether expected players reached retrieval, citation IDs
refer to returned sources, direct average questions state the sourced number,
and unsupported questions decline to guess. It saves full answers and source
texts to ignored `evals/runs/` JSON reports. This is deliberately local and
does not depend on a hosted evaluation service.

Review every answer in the report and score **factuality, relevance, scope
honesty, and citation support** from 0 (wrong) to 2 (fully correct). Check each
numeric claim against the cited game log, not just whether a citation exists.
Investigate failures by stage: player resolution, NBA data freshness,
retrieval, generation, or UI rendering. Add a new case for each real user
failure before changing prompts or retrieval.
