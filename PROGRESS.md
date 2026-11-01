# Progress

## Done
- Stage 0: computer checked, journal created, one paper done by hand.
- Stage 1: repo, config, BIS, NBER and IMF readers, SQLite with no duplicates.
- Stage 2: 44 sources (43 work, 1 not covered), health report, duplicates, backfill from 1 September.
- Stage 3: Groq connected, papers scored into checked JSON, results saved, tag rules in the prompt.
- Stage 4: selection, newsletter template, email-ready HTML, commands.
- Stage 5: public site with paper explorer and archive, plus weekly, monthly and Pages workflows. The weekly job ran on GitHub with 0 failed.
- Stage 6: README, sample issue, screenshots, 48 tests, demo mode, fresh clone test.
- October 2026: 291 papers scored, and the issue is built with 8 papers.
- A second AI tagged 20 papers without seeing the first AI's tags, and they agreed on all 20. This is a consistency check, not a human accuracy figure.

## Current step
Going live. The repo is still private. Only the owner can run `go-live.ps1`, which makes it public, turns on Pages and stores the Groq key.

## Next
1. Run `.\go-live.ps1`.
2. September 2026: 301 papers still to score. Groq's daily allowance refills after about 24 hours. Once the key is in GitHub, the Monday weekly job scores them and builds the issue. Before that, `python -m src.main run` does the same on the laptop.
3. Tag 20 papers by hand for a real accuracy figure, if there is time.
4. Email the issue to myself, then submit.

## Open problems
- Seven series give only a year, so they could not join the backfilled issues.
