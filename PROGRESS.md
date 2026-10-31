# Progress

## Done
- Stage 0: computer checked, journal created, one paper done by hand.
- Stage 1: repo, config, BIS, NBER and IMF readers, SQLite with no duplicates.
- Stage 2: 44 sources (43 work, 1 not covered), health report, duplicates, backfill from 1 September.
- Stage 3: Groq connected, papers scored into checked JSON, results saved, tag rules in the prompt.
- Stage 4: selection, newsletter template, email-ready HTML, commands.
- Stage 5: dashboard, weekly, monthly and Pages workflows. The weekly job ran on GitHub with 0 failed.
- Stage 6: README, sample issue, screenshots, 46 tests, demo mode, fresh clone test.
- October 2026: 291 papers scored, and the issue is built with 8 papers.

## Current step
September 2026: 301 papers still to score, plus 2 October papers found on the last run. Groq's daily allowance refills after about 24 hours.

## Next
1. Run `python -m src.main analyse`, then `python -m src.main build-issue --month 2026-09`.
2. Make the repo public, turn on GitHub Pages and deploy on Streamlit. Only the owner can do these.
3. Add `GROQ_API_KEY` to GitHub Secrets. Only the owner can do this.
4. Tag 20 papers by hand and add the accuracy figure to the README.
5. Put the live links in the README, email the issue to myself, and submit.

## Open problems
- Seven series give only a year, so they could not join the backfilled issues.
- Tag accuracy has not been measured yet.
