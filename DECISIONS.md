# Decisions

One line for every choice: what we chose and why.

- AI provider: Groq, because it has a free tier and this project is a trial.
- Models: `openai/gpt-oss-20b` scores every paper and `openai/gpt-oss-120b` writes up the chosen papers, because the free limits are tight.
- Python 3.14 on the laptop, in GitHub Actions and on Streamlit Community Cloud, so all three behave the same.
- Feeds and official APIs come first, because they are stable and allowed. Scraping is a last resort.
- G10 can mean the G10 countries or the G10 currencies, so we cover both. That adds the Reserve Bank of Australia, the Reserve Bank of New Zealand and Norges Bank.
- IMF Working Papers come through Crossref (ISSN 1018-5941), because the IMF feed answered 403 to a script on 31 October 2026.
