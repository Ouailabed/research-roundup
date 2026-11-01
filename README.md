# The Research Roundup

An automated Python agent that watches economics research and builds a monthly newsletter for a markets research team.

Every week it collects new papers from journals, central banks and research bodies, and uses AI to summarise, score and tag each one as EM, DM or Transversal. Every month it picks 5 to 8 papers and builds a responsive HTML newsletter. A public site shows each issue and lets you explore the papers.

- Live site, with the newsletter, paper explorer and archive: https://ouailabed.github.io/research-roundup/
- Latest newsletter on its own: https://ouailabed.github.io/research-roundup/issues/2026-10.html
- Sample issue in this repo: [site/issues/2026-10.html](site/issues/2026-10.html)

| The newsletter | Exploring the papers |
|---|---|
| <img src="docs/newsletter.png" alt="The October 2026 newsletter" width="360"> | <img src="docs/explore.png" alt="The Explore papers page" width="480"> |

## How it works

```
Feeds and APIs (44 sources)
      |
   collect       saves new papers to SQLite, no duplicates
      |
   analyse       cheap AI model: summary, tag and score for each paper
      |
 build-issue     picks 5 to 8 papers, stronger model writes them up, builds the HTML
      |
   publish       writes the public site: latest issue, paper explorer and archive

GitHub Actions runs everything every Monday and builds the new issue on the 1st of each month.
```

| Folder | What is in it |
|---|---|
| `src` | The Python code |
| `config` | `sources.yaml` lists every source and `settings.yaml` holds the model names |
| `data` | The SQLite database |
| `templates` | The newsletter layout and the public site's page |
| `site` | The public site and the finished newsletters |
| `tests` | The automatic tests |
| `app.py` | A Streamlit version of the dashboard, for running locally |

## Sources

44 source entries cover the five journals, NBER, BPEA, the IMF, the BIS, all G10 central banks, the ECB, the 12 regional Feds and 8 other European central banks. 43 work and 1 is not covered.

| Source | Route | Status | Papers with no abstract |
|---|---|---|---|
| NBER | Own feed, dates from Crossref | Working | 0 |
| IMF | Crossref | Working | 0 |
| BIS | Own feed | Working | 0 |
| BPEA | Crossref | Working | 21 |
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
| Oesterreichische Nationalbank | RePEc IDEAS | Fallback | 0 |
| Norges Bank | Own feed | Working | 0 |
| Danmarks Nationalbank | EconStor feed | Fallback | 0 |
| Narodowy Bank Polski | RePEc IDEAS | Fallback | 0 |
| American Economic Review | OpenAlex | Working | 9 |
| Econometrica | Crossref | Working | 10 |
| Journal of Political Economy | OpenAlex | Working | 38 |
| Quarterly Journal of Economics | OpenAlex | Working | 1 |
| Review of Economic Studies | OpenAlex | Working | 0 |

**Working** means the publisher's own feed or an official registry (Crossref, DataCite, OpenAlex).

**Fallback** means RePEc IDEAS or EconStor, open catalogues that give the same fields for each series. These are used when a bank's own feed has no abstracts or authors, or when Crossref has the DOIs but no abstracts. Each entry in `config/sources.yaml` has a note saying why.

**Not covered:** the Reserve Bank of New Zealand. Its site answered 403 to a script, RePEc stops in 2024, and the agent never disguises itself as a browser.

The rules for every source: feeds and official APIs first, respect `robots.txt`, about 1 request per second, a clear User-Agent, and no attempts to get around a paywall. Papers with no abstract are kept in the database but left out of the analysis for that cycle, which mainly affects the Journal of Political Economy.

## How the analysis and tags work

The AI reads only each paper's title, abstract and metadata. The prompt tells it never to add findings or numbers. Its answer must match a fixed JSON shape, which `pydantic` checks. A bad answer is retried once, then skipped and logged.

Tags follow one rule set, based on the IMF's list of advanced economies:

- **DM:** mainly about advanced economies.
- **EM:** mainly about emerging or developing economies.
- **Transversal:** global, many regions, or theory and methods not tied to one group.

Two models keep the work inside Groq's free limits. `openai/gpt-oss-20b` scores every paper at low effort, and `openai/gpt-oss-120b` takes over if it runs out for the day. `openai/gpt-oss-120b` also writes the full analysis, only for the papers chosen for an issue. Every result is saved with its model name and date, so the same model never reads the same paper twice, and a run that stops at the daily limit carries on from where it stopped.

No person has measured the tag accuracy yet. As a first check, a second AI (Claude) tagged 20 papers using the same written rules, without seeing the first AI's tags, and the two agreed on all 20. The tags are in `data/second_reader_tags.csv`. That is a consistency check on a small sample, not an accuracy figure, because both readers are AIs following the same rules. For a human check, `python -m src.compare sheet` makes a sheet of 20 papers to tag by hand, and `python -m src.compare score` compares those tags with the AI's.

Each month's selection takes the highest scores, at most 2 papers per source, with a mix of EM, DM and Transversal where possible. A paper belongs to the month it was first seen, because published dates are unreliable. The same month always gives the same issue.

## Run it locally

You need Python 3.14 and Git.

```powershell
git clone https://github.com/Ouailabed/research-roundup.git
cd research-roundup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

On Mac or Linux, use `source .venv/bin/activate` and `cp .env.example .env`.

The repo comes with saved data, so the dashboard works straight away with no keys:

```powershell
python -m streamlit run app.py
```

To run the agent, open `.env` and fill in the values. You only need `GROQ_API_KEY`, which you can get for free at console.groq.com. `OPENALEX_API_KEY` is optional. `CONTACT_EMAIL` is sent to sources in the User-Agent, so they can reach you. Then:

```powershell
python -m src.main collect
python -m src.main analyse
python -m src.main build-issue --month 2026-10
python -m src.main run
```

`run` collects, analyses, builds any missing issue and writes the public site. With no key, `analyse` says so and the saved results are used.

To run the tests:

```powershell
python -m pytest
```

## Deploy it

1. Fork or push this repo to GitHub, as a public repo.
2. Add `GROQ_API_KEY` under Settings, Secrets and variables, Actions. `OPENALEX_API_KEY` and `CONTACT_EMAIL` are optional.
3. Under Settings, Pages, set the source to GitHub Actions.
4. The workflows in `.github/workflows` then run by themselves. You can also start them by hand from the Actions tab.

The public site is a static page with no server, so it needs no account and never goes to sleep. `app.py` can also be deployed on Streamlit Community Cloud if you prefer: choose this repo, set the main file to `app.py`, and pick Python 3.14 under Advanced settings.

## Monthly cost

Nothing. Groq's free tier gave each model 1,000 requests a day, 8,000 tokens a minute and 200,000 tokens a day on 31 October 2026. GitHub Actions and Streamlit Community Cloud are free for this size of project. A normal month has about 300 new papers, and scoring one paper uses about 850 tokens, so a month's work fits well inside one day's allowance.

## Limits and next steps

- Abstracts only. The agent never reads full papers, so it can only be as good as the abstract.
- RePEc can lag a bank's own site by a few weeks.
- Seven series give only a year, so they could not join the backfilled September and October issues. New papers from them are dated by the day the agent first sees them.
- The free tier is slow: about 10 papers a minute.
- With more time: direct routes for the banks now on RePEc, a way to read the Reserve Bank of New Zealand if it opens an API, and a human check before each issue goes out.

## About AI help

Claude Code built this project from my plan. My guide and learning notes record each step.
