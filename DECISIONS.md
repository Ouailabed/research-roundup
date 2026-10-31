# Decisions

One line for every choice: what we chose and why.

- AI provider: Groq, because it has a free tier and this project is a trial.
- Models: `openai/gpt-oss-20b` scores every paper and `openai/gpt-oss-120b` writes up the chosen papers, because the free limits are tight.
- Python 3.14 on the laptop, in GitHub Actions and on Streamlit Community Cloud, so all three behave the same.
- Feeds and official APIs come first, because they are stable and allowed. Scraping is a last resort.
- G10 can mean the G10 countries or the G10 currencies, so we cover both. That adds the Reserve Bank of Australia, the Reserve Bank of New Zealand and Norges Bank.
- IMF Working Papers come through Crossref (ISSN 1018-5941), because the IMF feed answered 403 to a script on 31 October 2026.
- Routes are tried in this order: the publisher's own feed, Crossref or DataCite, then RePEc IDEAS. Each source's notes in `config/sources.yaml` say why it uses its route.
- RePEc IDEAS is the fallback for most central banks, because it gives authors, abstracts and dates in the same fields for every bank, and its robots.txt allows scripts.
- BIS abstracts come from each paper's page, because the feed often gives only the first sentence.
- The Reserve Bank of New Zealand is not covered. Its site answers 403 to scripts, RePEc stops in 2024, and we never disguise the script as a browser.
- Papers with no abstract stay in the database but are not analysed, as Yasmine's note on paywalls allows.
