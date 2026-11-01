# Progress

## Done
- Stage 0: computer checked, journal created, one paper done by hand.
- Stage 1: repo, config, BIS, NBER and IMF readers, SQLite with no duplicates.
- Stage 2: sources, health report, duplicates, backfill from 1 September.
- Stage 3: Groq connected, papers scored into checked JSON, results saved, tag rules in the prompt.
- Stage 4: selection, newsletter template, email-ready HTML, commands.
- Stage 5: public site with paper explorer and archive, plus weekly, monthly and Pages workflows.
- Stage 6: README, sample issue, screenshots, tests, demo mode, fresh clone test.
- A second AI tagged 20 papers without seeing the first AI's tags, and they agreed on all 20. This is a consistency check, not a human accuracy figure.
- Live on 1 November 2026: the repo is public, GitHub Pages is on, and the Groq key is in GitHub Secrets.
- Improved on 1 November 2026: 56 sources (55 work, 1 not covered), full NBER abstracts, cleaner text, JPE abstracts from RePEc, an editor step and an opening note for each issue, a warning for cut abstracts, a catch-up job every 6 hours, a better site and newsletter, 105 tests.

## Current step
About 290 papers to score from full text. The catch-up job restarts itself every 2 hours until they are done, then it builds the September issue and chooses October again.

## Next
1. Tag 20 papers by hand in the guide (Task 25) for a real accuracy figure.
2. Open the site on a phone in a private window.
3. Email the issue to myself, then submit. A draft reply to Yasmine is in Gmail.

## Open problems
- No scheduled GitHub run had fired by noon on 1 November, though manual runs work. Check that Monday's weekly run happens.
- Eight series give only a year, so they could not join the backfilled issues.
- 21 recent JPE papers have no abstract until RePEc lists them. Each run tries again.
