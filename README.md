# Twitter Sentiment Analysis for Investment Research

A powerful AI-driven tool that analyzes Twitter sentiment and social media engagement to provide investment insights for stocks and companies. This tool uses LangGraph workflows to systematically collect, analyze, and synthesize Twitter data from key influencers, company accounts, and market participants.

THIS PROJECT IS UNDER WORKING PROGRESS SO EXPECT BUGS AND OTHER UNFORESEEN PROBLEMS. RUN AT YOUR OWN RISK.

## Features

- **Intelligent Target Detection**: Automatically identifies and validates company targets for analysis
- **Multi-Account Analysis**: Discovers and analyzes relevant Twitter accounts including:
  - Official company accounts
  - C-suite executives and key personnel
  - Industry analysts and journalists
  - Regulatory bodies (when relevant)
- **Comprehensive Tweet Analysis**: Collects and analyzes tweets with configurable parameters:
  - Minimum number of accounts to analyze (default: 5)
  - Minimum tweets per account (default: 50-100)
  - Configurable time periods (default: last month)
- **Advanced Sentiment Analysis**: Uses GPT-4 models to provide:
  - Market impact assessment
  - Sentiment quantification
  - Risk factor identification
  - Engagement pattern analysis
- **Rate Limit Management**: Intelligent backoff strategies and error handling
- **Structured Reporting**: Generates comprehensive investment-grade reports

## Prerequisites

- Python 3.8+
- OpenAI API key
- Twitter headers and cookies
- Required Python packages (see Installation)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file in the root directory:
```env
OPENAI_API_KEY=your_openai_api_key_here
# Add Twitter API credentials as needed
```

4. Ensure you have the required `twitter.py` module with the following functions:
   - `search_people(query, cursor)`
   - `get_user_tweets(user_id, minimum_tweets, period, cursor)`
   - `get_comments(tweet_id, minimum)`
   - `users_to_table(users, include_header)`
   - `tweets_to_json(tweets)`

## Usage

### Basic Usage

Run the main script:
```bash
python main.py
```

The tool will interactively guide you through:
1. **Target Selection**: Specify the company/stock you want to analyze
2. **Parameter Configuration**: Set analysis scope and requirements
3. **Automated Analysis**: The system will automatically discover and analyze relevant accounts

### Programmatic Usage

You can also use the tool programmatically by providing an input state:

```python
from main import app

input_state = {
    "target_name": "Tesla",
    "research_requirements": "Focus on production updates and regulatory news",
    "minimum_tweets_to_collect": 100,
    "minimum_accounts_to_analyse": 5,
    "research_period": "month=1",
    "llms": {
        "fast": ChatOpenAI(model_name="gpt-4o-mini", temperature=0),
        "detailed": ChatOpenAI(model_name="gpt-4o", temperature=0)
    }
}

for chunk in app.stream(input_state, stream_mode="updates", config={"recursion_limit": 100}):
    # Process results
    pass
```

## Configuration Options

### Analysis Parameters

- **target_name**: Company or stock symbol to analyze
- **research_requirements**: Specific focus areas or constraints
- **minimum_accounts_to_analyse**: Number of accounts to analyze (default: 5)
- **minimum_tweets_to_collect**: Tweets per account (default: 50)
- **research_period**: Time frame for analysis (default: "month=1")

### LLM Configuration

The tool uses two LLM configurations:
- **fast**: GPT-4o-mini for quick operations (query generation, user selection)
- **detailed**: GPT-4o for comprehensive analysis (tweet analysis, report generation)

## Workflow Architecture

The tool uses a LangGraph-based workflow with the following nodes:

1. **Context Setting**: Interactive target identification and parameter configuration
2. **User Reconnaissance**: 
   - Query generation for finding relevant accounts
   - Account discovery and selection
3. **User Analysis**: 
   - Tweet collection and analysis
   - Comment analysis for high-engagement tweets
   - Report generation
4. **Timeout Management**: Intelligent rate limit handling

## Output

The tool generates comprehensive reports including:

- **Themes & Catalysts**: Summary of key topics, products, services, and market-moving events
- **Engagement & Timing Analysis**: Most engaging content and timing indicators
- **Risk Assessment**: Identified risk factors and negative sentiment
- **Top Influential Tweets**: Ranked list of high-impact tweets with sentiment analysis
- **Quantified Insights**: Actionable metrics for investment decisions

## Error Handling

- **Rate Limit Management**: Automatic backoff with progressive timeouts
- **API Error Recovery**: Intelligent retry mechanisms
- **Data Validation**: Robust input validation and error reporting

## Visualization

The tool automatically generates a workflow diagram (`workflow.png`) showing the complete analysis pipeline using Mermaid.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request


## Disclaimer

This tool is for research and educational purposes only. Investment decisions should not be made solely based on social media sentiment analysis. Always conduct thorough due diligence and consult with financial professionals before making investment decisions.
