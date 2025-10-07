# Social Market Sentiment (LangGraph + GPT-4)

AI agent that scrapes X/Twitter, analyzes sentiment with an ensemble of RoBERTa + VADER, and produces an investor-ready report on a target company’s latest activity and market sentiment.

Note: Work in progress. Use at your own risk.

## Highlights

- **LangGraph workflow**: multi-stage pipeline (discover → scrape → clean → infer → ensemble → weight → report)
- **Ensemble sentiment**: RoBERTa (CardiffNLP) + VADER with disagreement-aware weighting
- **Scale**: processes 1,000+ tweets/comments per run with rate-limit aware retries
- **Outputs**: concise report with themes, sentiment trends, risks, and high-impact posts

## Quick start

Prereqs: Python 3.8+, OpenAI API key, X/Twitter headers/cookies.

```bash
pip install -r requirements.txt
echo OPENAI_API_KEY=your_key_here > .env
python main.py
```

You’ll be prompted for a target (company/stock) and analysis scope; the agent discovers relevant accounts, collects recent tweets/comments, and generates a report.

## Programmatic usage

```python
from main import app

input_state = {
    "target_name": "Tesla",
    "research_requirements": "Focus on production updates and regulatory news",
    "minimum_tweets_to_collect": 100,
    "minimum_accounts_to_analyse": 5,
    "research_period": "month=1",
}

for chunk in app.stream(input_state, stream_mode="updates", config={"recursion_limit": 100}):
    pass
```

## Configuration

- **target_name**: company or ticker to analyze
- **research_requirements**: guidance for the report
- **minimum_accounts_to_analyse**: default 5
- **minimum_tweets_to_collect**: default 50 per account
- **research_period**: e.g., `month=1`, `days=14`

## What you get

- Themes and catalysts, sentiment trend, risks
- Ranked influential tweets with sentiment and engagement
- Weighted, quantitative sentiment summary

## Reliability notes

- Backoff and retry for scraping limits and transient errors
- Basic input validation; expect occasional edge cases while WIP

## Disclaimer

For research/education only; not investment advice.
