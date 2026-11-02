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
- Improved on 1 November 2026: 56 sources (55 work, 1 not covered), full NBER abstracts, cleaner text, JPE abstracts from RePEc, an editor step and an opening note for each issue, a warning for cut abstracts, a self-restarting catch-up job, a better site and newsletter, 111 tests.
- Redesigned on 1 November 2026: an Overview dashboard with filters and charts, cleaner Explore and Archive pages, dark mode, and new tag colours on the site and the newsletter. 144 tests.
- Added on 1 November 2026: an assistant you can ask questions on the home page, a 3D map of the papers, and motion across the dashboard, with a pause button. 146 tests.

- Reviewed on 2 November 2026: Claude and Codex audited the 16 write-ups, and 11 were corrected. Codex audited 40 short summaries, and 3 summaries and 2 tags were corrected. Three faults in the jobs were fixed. 151 tests.

- Added on 2 November 2026: a fact-check by OpenAI's gpt-6-luna on every write-up, off until its key is set, with a measure against the audited write-ups. 172 tests.

## Current step
Both issues are built and live, and their 16 write-ups have been audited against the abstracts. The next thing to watch is Monday's weekly run, the first scheduled weekly run this repo will have seen.

## Next
1. Open the site on a phone in a private window.
2. Email the issue to myself, then submit. A draft reply to Yasmine is in Gmail, and its three links need pasting in again first, because the connector turned them into Google redirects.
3. If there is time, tag 20 papers by hand in the guide (Task 25) for a real human figure. So far only AI readers have checked the tags.

## Open problems
- 548 short summaries haven't been audited. In a sample of 40, 3 stated something the abstract doesn't support.
- GitHub's schedule is late and unreliable here: the first scheduled run fired at 17:56 on 1 November, about 5 hours late. Check that Monday's weekly run happens.
- Eight series give only a year, so they could not join the backfilled issues.
- 21 recent JPE papers have no abstract until RePEc lists them. Each run tries again.
