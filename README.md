# The Research Roundup

A Python agent that keeps up with new economics research and turns it into a monthly newsletter for a markets research team.

Every week it collects new papers from the top journals, central banks and research bodies. It summarises each one, scores how useful it is to a markets team, and tags it EM, DM or Transversal. Once a month it picks the 5 to 8 best papers and builds a responsive HTML newsletter. There's also a public site where you can read each issue, browse everything collected so far, and search the papers. The search box on the site doesn't call an AI model: it searches the summaries already saved, right in your browser.

## Review in 5 minutes

1. **The newsletter:** the [October 2026 issue](https://ouailabed.github.io/research-roundup/issues/2026-10.html) and the [September 2026 issue](https://ouailabed.github.io/research-roundup/issues/2026-09.html).
2. **The dashboard:** [the live site](https://ouailabed.github.io/research-roundup/). Explore papers lists every paper with filters, plus its tag, the reason for the tag and its metadata. Archive has every issue and the latest source report.
3. **Sources:** 55 of 56 sources work. The one gap is the Reserve Bank of New Zealand, which blocks scripts and whose RePEc series stops in 2024. [Sources](#sources) shows how each one is read.
4. **Quality:** in a blind check of all 626 papers saved by 2 November, Codex agreed with the project's tags 91.4% of the time. A manual read-through of the tags agreed with most of them too, and every new write-up is fact-checked before an issue goes out. More in [How the tags and summaries were checked](#how-the-tags-and-summaries-were-checked).
5. **Run it yourself:** the dashboard runs locally without any API key. See [Run it locally](#run-it-locally).

| The home page | The newsletter | Exploring the papers |
|---|---|---|
| <img src="docs/overview.png" alt="The home page, with the search box and the 3D map of papers" width="360"> | <img src="docs/newsletter.png" alt="The October 2026 newsletter" width="300"> | <img src="docs/explore.png" alt="The Explore papers page" width="480"> |

## How it works

```
Feeds and APIs (56 sources)
      |
   collect       saves new papers to SQLite, skipping anything already saved
      |
   analyse       a small model writes a summary, a tag and a score for each paper
      |
 build-issue     a bigger model ranks the best papers, simple rules pick 5 to 8, then it writes them up
      |
   publish       builds the public site: latest issue, paper explorer and archive

GitHub Actions runs this every Monday and builds a new issue on the 1st of each month.
If a run stops at Groq's daily limit, a small catch-up job finishes the work later.
```

| Folder | What's in it |
|---|---|
| `src` | The Python code |
| `config` | `sources.yaml` lists every source, `settings.yaml` holds the model names |
| `data` | The SQLite database |
| `templates` | The newsletter layout and the site's page |
| `site` | The public site and the finished newsletters |
| `tests` | The tests |
| `docs` | Screenshots, and the full record of the quality checks |
| `app.py` | A Streamlit version of the dashboard, for running locally |

## Sources

There are 56 source entries: the five journals, NBER, BPEA, the IMF, the BIS, all the G10 central banks, the ECB, the 12 regional Feds and 20 other European central banks. 55 of them work, and 1 isn't covered.

| Source | Route | Status | Papers with no abstract |
|---|---|---|---|
| NBER | Own feed, dates from Crossref | Working | 0 |
| IMF | Crossref | Working | 0 |
| BIS | Own feed | Working | 0 |
| BPEA | Crossref | Working | 0 |
| Federal Reserve Board | Crossref | Working | 0 |
| Bank of England | RePEc IDEAS | Fallback | 0 |
| European Central Bank | RePEc IDEAS | Fallback | 0 |
| Bank of Canada | DataCite | Working | 0 |
| Bank of Japan | RePEc IDEAS | Fallback | 0 |
| Banque de France | RePEc IDEAS | Fallback | 0 |
| Deutsche Bundesbank | RePEc IDEAS | Fallback | 0 |
| Banca d'Italia | RePEc IDEAS | Fallback | 0 |
| De Nederlandsche Bank | RePEc IDEAS | Fallback | 0 |
| National Bank of Belgium | RePEc IDEAS | Fallback | 0 |
| Sveriges Riksbank | RePEc IDEAS | Fallback | 0 |
| Swiss National Bank | RePEc IDEAS | Fallback | 0 |
| Reserve Bank of Australia | Crossref | Working | 0 |
| Reserve Bank of New Zealand | None | Not covered | 0 |
| Boston Fed | RePEc IDEAS | Fallback | 0 |
| New York Fed | Crossref | Working | 0 |
| Philadelphia Fed | RePEc IDEAS | Fallback | 0 |
| Cleveland Fed | Crossref | Working | 0 |
| Richmond Fed | RePEc IDEAS | Fallback | 0 |
| Atlanta Fed | RePEc IDEAS | Fallback | 0 |
| Chicago Fed | RePEc IDEAS | Fallback | 0 |
| St. Louis Fed | RePEc IDEAS | Fallback | 0 |
| Minneapolis Fed Staff Reports | RePEc IDEAS | Fallback | 0 |
| Minneapolis Fed Working Papers | RePEc IDEAS | Fallback | 0 |
| Kansas City Fed | RePEc IDEAS | Fallback | 0 |
| Dallas Fed | RePEc IDEAS | Fallback | 0 |
| San Francisco Fed | Crossref | Working | 0 |
| Banco de Espana | RePEc IDEAS | Fallback | 0 |
| Banco de Portugal | RePEc IDEAS | Fallback | 0 |
| Bank of Finland | RePEc IDEAS | Fallback | 0 |
| Central Bank of Ireland | RePEc IDEAS | Fallback | 0 |
| Oesterreichische Nationalbank | RePEc IDEAS | Fallback | 1 |
| Norges Bank | Own feed | Working | 0 |
| Danmarks Nationalbank | EconStor feed | Fallback | 0 |
| Narodowy Bank Polski | RePEc IDEAS | Fallback | 0 |
| Czech National Bank | RePEc IDEAS | Fallback | 0 |
| Magyar Nemzeti Bank | RePEc IDEAS | Fallback | 0 |
| Bank of Greece | RePEc IDEAS | Fallback | 0 |
| Latvijas Banka | RePEc IDEAS | Fallback | 0 |
| Bank of Lithuania | RePEc IDEAS | Fallback | 0 |
| Eesti Pank | RePEc IDEAS | Fallback | 2 |
| National Bank of Slovakia | RePEc IDEAS | Fallback | 0 |
| Croatian National Bank | RePEc IDEAS | Fallback | 0 |
| Central Bank of Iceland | RePEc IDEAS | Fallback | 0 |
| Banque centrale du Luxembourg | RePEc IDEAS | Fallback | 0 |
| Central Bank of Cyprus | RePEc IDEAS | Fallback | 0 |
| National Bank of Ukraine | RePEc IDEAS | Fallback | 0 |
| American Economic Review | OpenAlex | Working | 3 |
| Econometrica | Crossref | Working | 3 |
| Journal of Political Economy | OpenAlex, abstracts from RePEc IDEAS | Working | 21 |
| Quarterly Journal of Economics | OpenAlex | Working | 0 |
| Review of Economic Studies | OpenAlex | Working | 0 |

**Working** means the publisher's own feed or an official registry (Crossref, DataCite or OpenAlex).

**Fallback** means RePEc IDEAS or EconStor. These are open catalogues that give the same fields for every series, so they're used when a bank's own feed has no abstracts or authors, or when Crossref has the DOIs but not the abstracts. Each entry in `config/sources.yaml` has a note explaining its choice.

**Not covered:** the Reserve Bank of New Zealand. Its site returns 403 to scripts and its RePEc series stops in 2024, and the agent never pretends to be a browser. A few smaller European central banks are missing too: Malta's RePEc series stops in 2023, and no RePEc series turned up for Slovenia, Bulgaria, Romania or Serbia.

Every source follows the same rules: feeds and official APIs first, respect `robots.txt`, about one request a second, a clear User-Agent, and no getting around paywalls. A paper with no abstract stays in the database but is skipped in the analysis for that cycle. This mostly hits the Journal of Political Economy, because OpenAlex has few of its abstracts and RePEc lists new papers late, so every run tries RePEc again. Journal housekeeping like Front Matter and Recent Referees is dropped, so it doesn't count as missing.

## How the analysis and tags work

The model only sees each paper's title, abstract and metadata, and the prompt tells it never to add findings or numbers of its own. Its answer has to fit a fixed JSON shape, which `pydantic` checks. A bad answer is retried once and logged, and a paper that fails on 3 separate runs is skipped.

The tags follow one set of rules, based on the IMF's list of 43 advanced economies:

- **DM:** mainly about advanced economies.
- **EM:** mainly about emerging or developing economies.
- **Transversal:** global, several regions, or theory and methods not tied to one group.

Two models keep everything inside Groq's free limits. `openai/gpt-oss-20b` scores every paper, and `openai/gpt-oss-120b` takes over if it runs out for the day. `openai/gpt-oss-120b` also writes the full write-ups, but only for the papers chosen for an issue. Every result is saved with the model name and date, so the same paper is never sent twice, and a run that hits the daily limit picks up where it stopped.

### How the tags and summaries were checked

- **A manual check:** a read-through of the tags agreed with most of them. It wasn't a blind test, so it doesn't count as an accuracy figure.
- **A blind check of every tag:** Codex tagged all 626 papers saved at the time without seeing the project's tags. It agreed on 572 of them: 91.4%, with a 95% range of 88.9% to 93.3%. Each disagreement was then checked against the abstract, and 23 tags were changed.
- **The write-ups:** a review of the first 16 found 8 with a claim the abstract didn't support, such as an effect in the wrong direction. All 8 were fixed, and that's why every new write-up now goes through a fact-check step before an issue is built.
- **The short summaries:** all 610 saved at the time were checked against their abstracts. 27 real problems were fixed, and 58 that were a bit loose were left as they are.
- **The numbers:** `python -m src.main check` compares every number in a summary with its abstract. It flagged 6 of 624 summaries, and all 6 were just rounding or simple sums.

Apart from the manual read-through, these are AI checks of AI work. They show the tags follow the rules consistently, not that every tag is right, so someone should still read each issue before it goes out. The full record, with every figure and how to reproduce it, is in [docs/quality-checks.md](docs/quality-checks.md).

## How papers are chosen

A score on its own can't pick the issue. In October, 145 of 295 papers scored 9 or 10, and the two models use the scale a little differently. So it works like an editor's desk: `openai/gpt-oss-120b` reads every paper scoring 9 or 10, in groups of 40, and ranks the ones most useful to a markets team. The issue takes the top of that ranking, with at most 2 papers per source and a mix of EM, DM and Transversal where possible. The same model also writes a short opening note on what the papers say together.

A paper belongs to the month it was first seen, because published dates are often unreliable. The backfilled September and October issues are the exception, since they use the best date each source gives. Once an issue's list is chosen it's saved, so rebuilding a month always gives the same issue.

## Run it locally

You'll need Python 3.13 or newer, and Git. It's tested on 3.13 and 3.14.

```powershell
git clone https://github.com/Ouailabed/research-roundup.git
cd research-roundup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

On Mac or Linux, use `source .venv/bin/activate` and `cp .env.example .env` instead.

The repo comes with saved data, so the dashboard works straight away without any keys:

```powershell
python -m streamlit run app.py
```

To run the agent itself, open `.env` and fill in the values. The only one you need is `GROQ_API_KEY`, which is free at console.groq.com and also runs the fact-check. `OPENALEX_API_KEY` is optional. `CONTACT_EMAIL` goes in the User-Agent, so sources can reach you if they need to. Then:

```powershell
python -m src.main collect
python -m src.main analyse
python -m src.main build-issue --month 2026-10
python -m src.main run
```

`run` does everything in one go: it collects, analyses, builds any missing issue and writes the site. `python -m src.main catch-up` does the same but only collects if nothing has run for a week, and `python -m src.main left` shows how many papers and issues are still waiting. Without a key, `analyse` tells you so and the saved results are used.

To run the tests:

```powershell
python -m pytest
```

## Deploy it

1. Fork or push this repo to GitHub as a public repo.
2. Add `GROQ_API_KEY` under Settings, Secrets and variables, Actions. `OPENALEX_API_KEY` and `CONTACT_EMAIL` are optional. To measure the fact-check, run "Measure the fact-checker" from the Actions tab.
3. Under Settings, Pages, set the source to GitHub Actions.
4. On a fork, turn on workflows in the Actions tab first, because GitHub leaves them off.
5. Start "Weekly run" by hand with Run workflow on the Actions tab. After that the workflows in `.github/workflows` run on their own schedules. GitHub doesn't promise exactly when a scheduled run starts (see Limits), so any job can also be started by hand.

The public site is a static page with no server, so there's no account to manage and it never goes to sleep. You can also deploy `app.py` on Streamlit Community Cloud if you like: pick this repo, set the main file to `app.py`, and choose Python 3.13 or newer under Advanced settings.

## Monthly cost

Nothing. On 31 October 2026, Groq's free tier gave each model 1,000 requests a day, 8,000 tokens a minute and 200,000 tokens a day, and GitHub Actions and Streamlit Community Cloud are free at this size. A normal month brings about 300 new papers, and scoring one takes about 850 tokens. That's about 255,000 tokens a month, but spread over weekly runs it comes to about 60,000 a week, well inside the daily allowance. The editor's ranking and the write-ups add about 50,000 tokens per issue on the bigger model.

The fact-check is free too. On the day an issue is built it adds at most 16 calls to `openai/gpt-oss-120b`, two for each of 8 write-ups, sharing that model's daily allowance with the editor and the write-ups. If the allowance runs out, the issue waits and the catch-up job finishes it later.

## Limits and next steps

- It only reads abstracts, never full papers, so it can only be as good as the abstract.
- RePEc can lag a bank's own site by a few weeks.
- Eight series only give a year, so their papers couldn't go into the backfilled September and October issues. New papers from them are dated by the day the agent first sees them.
- The free tier is slow: about 10 papers a minute, and the daily allowance refills gradually rather than all at once. A big backlog takes a few days, and the catch-up job handles that on its own.
- GitHub doesn't guarantee when a scheduled run starts, and it can skip one. On 1 November the 06:30 and 07:00 runs never came, and the first scheduled run fired at 17:56, about 5 hours late, even though every manual run worked. So the catch-up job restarts itself while there's work left, and collects if nothing has run for a week. Any job can also be started by hand. `timer.yml` can stand in for cron if it keeps failing: it waits 7 days on a deployment environment, using no runner, then starts the weekly run and itself again. It stays off until someone starts it.
- Scores bunch at 5 and 9, because the prompt names those values. The editor step works around it, but a better scale would mean scoring every paper again.
- The fact-check only covers the 5 to 8 write-ups in each issue, not the short summaries of every other paper.
- With more time: direct routes for the banks now read through RePEc, a way to read the Reserve Bank of New Zealand if it opens an API, a blind human check of the tags, and a person reading each issue before it goes out.

## How I built it

Built with AI coding assistants: Claude Code for development and Codex for code review.
