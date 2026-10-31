# Progress

## Done
- 0.1 Checked the computer.
- 0.2 Created the learning journal.
- 0.3 Did the job by hand once on one NBER paper.
- 1.1 Created the repo, folders and hello command.
- 1.2 Added the source config for NBER, IMF and BIS.
- 1.3 Read the BIS feed.
- 1.4 Added the Paper dataclass and read all three sources.
- 1.5 Saved papers in SQLite with no duplicates.
- 2.1 Added the five journals.
- 2.2 Added BPEA and reviewed NBER, the IMF and BIS.
- 2.3 Added the central banks: 33 of 34 give papers, and the Reserve Bank of New Zealand is not covered.

## Current step
2.4 Source health report.

## Next
2.5 Duplicates, 2.6 backfill, then 3.1 once the Groq key is in `.env`.

## Open problems
- `GROQ_API_KEY` is not in `.env` yet, so Stage 3 is waiting.
- Every paper has a first seen date of 31 October 2026, because that was the first run. The backfill in 2.6 will fix this.
