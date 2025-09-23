from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from typing import TypedDict, Annotated, List, Dict, Any, Sequence, Set
from langchain_core.messages import BaseMessage, SystemMessage, AIMessage, ToolMessage, HumanMessage
from langchain_core.runnables.graph import CurveStyle
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional, Literal, Tuple
from colorama import Fore, Style
import time
import operator
import os
import random
from twitter import *
import json
import pandas as pd

os.system('cls')

class ContextSettingResult(BaseModel):
    """Result of entity extraction from user input"""
    target_entity_found: bool = Field(description="Whether a clear target was found in the user input")
    target_entity_name: Optional[str] = Field(description="The name of the target stock/company/person if found", default="")
    target_entity_requirements: Optional[str] = Field(description="Any specific requirements mentioned by the user when researching the target stock/company/person", default="")
    minimum_accounts_to_analyse: int = Field(description="The minimum number of accounts to analyse. If user does not specify, default to 5", default=5)
    minimum_tweets_to_collect: int = Field(description="The minimum number of tweets to collect. If user does not specify, default to 50", default=50)
    research_period: str = Field(description="The past period of time to research the target. If user does not specify, default to 1 month", default="month=1")
    follow_up_question: Optional[str] = Field(description="Follow-up question to ask if the user has not provided a clear target stock/company/person to research", default="")


class OverallState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    llms: List[ChatOpenAI]      
    node_before_timeout: str
    timeout_duration: int

    target_name: Optional[str] # target name to analyse
    research_requirements: Optional[str] # research requirements for the target
    research_period: Optional[str] # research period for the target

    minimum_accounts_to_analyse: int # minimum number of accounts to analyse
    minimum_tweets_to_collect: int # minimum number of tweets to analyse
    user_reports: Dict[str, str] # reports of the users analysed


    query_queue: List[Tuple[str,str]]                     # e.g., [("Tesla", "some cursor"), ("Elon Musk", "some cursor"), ...]
    queried: Annotated[Set[str], operator.or_]      # track queries already tried
    search_results: List[Dict[str, Any]]            # users collected

    tweets_to_analyse: Annotated[Set[str], operator.or_]          # list of tweet ids collected and filtered and pending analysis
    tweets_collected: Annotated[Set[str], operator.or_]           # list of tweet ids collected and pending filtering
    tweets_filtered_out: Annotated[Set[str], operator.or_]        # list of tweet ids filtered out
    accounts_to_analyse: Set[Tuple[int, str]]       # list of account ids collected and pending analysis
    
    
    


class InputState(TypedDict):
    target_name: Optional[str]
    research_requirements: Optional[str]
    research_period: Optional[str]
    minimum_accounts_to_analyse: int
    minimum_tweets_to_collect: int
    llms: Optional[List[ChatOpenAI]]


def context_setting(input_state: InputState) -> OverallState:
    """
    Interactive context setting to identify target entity and analysis parameters.
    Ensures clear target identification before proceeding with analysis.
    """
    
    update = OverallState({
        "target_name": input_state.get("target_name", None),
        "research_requirements": input_state.get("research_requirements", None),
        "research_period": input_state.get("research_period", "month=1"),
        "minimum_accounts_to_analyse": input_state.get("minimum_accounts_to_analyse", 5),
        "minimum_tweets_to_collect": input_state.get("minimum_tweets_to_collect", 50),
        "llms": input_state.get("llms", {"fast": ChatOpenAI(model_name="gpt-4o-mini", temperature=0), "detailed": ChatOpenAI(model_name="gpt-4o", temperature=0)}),
        "messages": [],
        "search_results": [],
        "query_queue": [],
        "user_reports": {},
        "queried": set(),
        "accounts_to_analyse": set(),

        "tweets_to_analyse": set(),
        "tweets_collected": set(),
        "tweets_filtered_out": set(),
        "node_before_timeout": None,
        "timeout_duration": 30,
    })

    if update["target_name"]:  
        return update

    messages = [
        SystemMessage(content="""
        You are a professional investment research assistant specializing in Twitter sentiment analysis.
        OBJECTIVE: Help users identify a specific target company with a known ticker symbol for comprehensive social media sentiment analysis.

        REQUIRED INFORMATION TO EXTRACT:
        1. TARGET ENTITY: Exact company name
        2. ANALYSIS SCOPE: Number of accounts to analyze (default: 5 high-quality accounts)
        3. DATA DEPTH: Number of tweets to collect per account (default: 50-100 tweets)
        4. TIME FRAME: Analysis period (default: last month)
        5. SPECIFIC REQUIREMENTS: Any particular focus areas or constraints
        
        Be direct and professional and ask clarifying questions to ensure precision.
        Validate entity names against known companies/tickers when possible
        Suggest reasonable defaults for unspecified parameters
        Confirm all parameters before proceeding""".strip()),
        HumanMessage(content=""" I am ready. Ask away!""".strip())
    ]
    
    
    
    entity_extraction_result = ContextSettingResult(target_entity_found=False)
    while not entity_extraction_result.target_entity_found:
        entity_extraction_result = input_state["llms"]["fast"].with_structured_output(ContextSettingResult).invoke(messages)
        print(f"{Fore.MAGENTA}AI: {entity_extraction_result.follow_up_question}{Style.RESET_ALL}")
        user_response = input("You: ")
        messages.append(HumanMessage(content=user_response))

    print(f"{Fore.MAGENTA}AI: {entity_extraction_result.model_dump_json(indent=4)}{Style.RESET_ALL}")
    update.update({
        "target_name": entity_extraction_result.target_entity_name, 
        "research_requirements": entity_extraction_result.target_entity_requirements,
        "minimum_accounts_to_analyse": entity_extraction_result.minimum_accounts_to_analyse,
        "minimum_tweets_to_collect": entity_extraction_result.minimum_tweets_to_collect,
        "research_period": entity_extraction_result.research_period
    })
    return update
    
# User Reconnaissance
class QueryGeneration(BaseModel):
    """Result of query generation for user search"""
    queries: List[str] = Field(description="List of 3 distinct search queries")
    rationale: str = Field(description="1-2 sentences on query coverage")

def user_recon_query(state: OverallState) -> OverallState:
    """
    Generate search queries or determine next query+cursor combination to search
    """
    # If no queries in queue, generate 5 new ones
    query_queue = state["query_queue"]

    if not query_queue:
        sys = SystemMessage(content=f"""
        JSON ONLY. 
        Goal: Return EXACTLY 3 DISTINCT Twitter search queries for {state["target_name"]} in this order:
        1) Exact company name (no quotes): e.g., the company name
        2) One key person's name (CEO/founder or top exec)
        3) One key product/program (brand or generic), you may use "OR" to combine close variants.
        Rules:
        - No tickers, no hashtags, no duplicates.
        - Prefer entities likely to have official/verified accounts.
        - Use your knowledge to pick a real executive and a flagship product/program.
        - Output fields: "queries": [q1,q2,q3], "rationale": "2 short sentences"
        """.strip())

        query_gen: QueryGeneration = state["llms"]["fast"].with_structured_output(QueryGeneration).invoke([sys])
        print(f"{Fore.MAGENTA}Generated queries: {query_gen.queries}{Style.RESET_ALL}")
        print(f"{Fore.MAGENTA}Rationale: {query_gen.rationale}{Style.RESET_ALL}")
        query_queue = list(zip(query_gen.queries, [""] * len(query_gen.queries)))

    update = {
        "search_results": [],
        "queried": set(),
        "query_queue": query_queue
    }
    
    while update["query_queue"]:
        query, cursor = update["query_queue"][0]
        if query in state["queried"]: continue
        try:
            search_results = search_people(query=query, cursor=cursor)[0]
            time.sleep(random.random() * 2)
            update["search_results"].append(search_results)
            update["queried"].add(query)
            update["query_queue"].pop(0)
            print(f'{Fore.GREEN}Successfully fetched "{query}" {f"with cursor {cursor}" if cursor else ""}{Style.RESET_ALL}')
        except Exception as e:
            error_code = str(e)[:3]
            print(f'{Fore.RED}Error fetching "{query}" {f"with cursor {cursor}" if cursor else ""}: {e}{Style.RESET_ALL}')
            if error_code == '429':  # Rate limit
                update["node_before_timeout"] = "user_recon_query"
                update["timeout_duration"] = 60  # Longer timeout for rate limits
                print(f'{Fore.YELLOW}Rate limit detected. Waiting 60 seconds before retry...{Style.RESET_ALL}')
            else:  # Random errors
                update["node_before_timeout"] = "user_recon_query"
                update["timeout_duration"] = 5
                print(f'{Fore.YELLOW}Unknown error. Retrying in 10 seconds...{Style.RESET_ALL}')
            return update
    return update

def route_after_user_recon_query(state: OverallState) -> str:
    if state["node_before_timeout"] == "user_recon_query":
        return "timeout_node"
    if len(state["search_results"]) > 0:
        return "user_recon_select"
    return "user_recon_query" # no search results from any of the queries, so we need to generate new queries # TODO could also due to rate limit
    
class UserSelection(BaseModel):
    chosen_handles: List[str] = Field(description="Twitter screen_names to analyze (e.g., elonmusk)")
    rationale: str = Field(description="Brief reasons for each; 1-2 lines total")
    
def user_recon_select(state: OverallState) -> OverallState:
    search_results = state.get("search_results") # [users collected]
    if not search_results: return {}
    sys = SystemMessage(content=f"""
    You select high-credibility accounts for {state["target_name"]}.
    RETURN FORMAT: JSON only, using the schema. 
    IMPORTANT: Return ONLY screen_names (without @) that appear in the table. 
    Do NOT invent or modify handles. Do NOT return numeric IDs.
    Pick the best 3-10 accounts that could move sentiment or price:
    - Official company & programs
    - C-suite & key execs
    - Major analysts/journalists (tier-1)
    - Regulators when relevant
    Disqualify:
    - Fan/meme/parody
    - Generic "stock/crypto guru"
    - Low-cred bios with no affiliation
    Be concise in rationale (single line).
    """.strip())
    handle_to_user_id = {}
    results_table = ""
    for i, batch in enumerate(search_results):
        batch = [user for user in batch if user["followers_count"] > 1000]
        batch_table = users_to_table(batch, include_header=i==0)
        results_table += f'{'' if i==0 else '\n'}{batch_table}'
        for user in batch:
            handle_to_user_id[user["screen_name"]] = user["user_id"]
        
    # print(f"{Fore.GREEN}{results_table}{Style.RESET_ALL}")    
    human = HumanMessage(content=results_table)
    state["llms"]["fast"].bind_tools([])
    sel: UserSelection = state["llms"]["fast"].with_structured_output(UserSelection).invoke([sys, human])

    update = {
        "search_results": [],
        "accounts_to_analyse": set(),
        "accounts_to_analyse": state["accounts_to_analyse"]
    }

    msg = f"Selected: "
    for i, handle in enumerate(sel.chosen_handles):
        msg += f"@{handle}" + (", " if i < len(sel.chosen_handles) - 1 else "")
        update["accounts_to_analyse"].add((handle_to_user_id[handle], handle))
    msg += f"\nRationale: {sel.rationale}"

    update["messages"] = [AIMessage(content=msg)]
        
    return update

def route_after_user_recon_select(state: OverallState) -> str:
    have = len(state.get("accounts_to_analyse", set()))
    need = state["minimum_accounts_to_analyse"]
    
    
    if have >= need:
        print(f"{Fore.CYAN}Selected ({have}/{need}) accounts: {Style.RESET_ALL}")
        return "analyse_users" 
    
    return "user_recon_query"

# Target Analysis
def analyse_users(state: OverallState) -> OverallState:
    """Analyses the tweets and comments of a user"""
    users_to_analyse = state.get("accounts_to_analyse", set())
    
    # Produce a comprehensive final report based on all user analyses
    items = [{
         'user_id':user[0],
         'user_screen_name':user[1],
         'llm':state["llms"]["detailed"], 
         'target_name':state["target_name"], 
         'research_period':state["research_period"], 
         'research_requirements':state["research_requirements"], 
         'minimum_tweets_to_collect':state["minimum_tweets_to_collect"],
         'minimum_accounts_to_analyse':state["minimum_accounts_to_analyse"]
         } for user in users_to_analyse]
    
    results = analyse_user_app.batch(items, config={'max_concurrency': 2}) # 2 is the max concurrency to prevent rate limit
    for result in results:
        print(f"{Fore.GREEN}{result['user_screen_name']}: {result['tweets_summary']}{Style.RESET_ALL}")
    user_reports = {result['user_screen_name']: result['tweets_summary'] for result in results} 
    
    # Generate an overall report based on the user reports
    system_prompt = f"""
    You are a senior investment research analyst conducting deep Twitter sentiment analysis for {state["target_name"]}.
    ANALYSIS PERIOD: Last {state["research_period"]}
    {f"SPECIFIC REQUIREMENTS: {state['research_requirements']}" if state["research_requirements"] else ""}
    You should have analysed at least {state["minimum_accounts_to_analyse"]} accounts.
    The following is the user reports for {state["target_name"]}:
    """
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"{json.dumps(user_reports)}")
    ]
    response = state["llms"]["detailed"].invoke(messages)

    with open(f"{state['target_name']}.md", "w") as f: # output as markdown file
        f.write(f"{state['target_name']}\n")
        f.write(f"ANALYSIS PERIOD: Last {state['research_period']}\n")
        f.write(f"{f'SPECIFIC REQUIREMENTS: {state['research_requirements']}' if state['research_requirements'] else ''}\n")
        f.write("# USER REPORTS\n")
        for user_screen_name, tweets_summary in user_reports.items():
            f.write(f"## {user_screen_name}\n")
            f.write(tweets_summary)
            f.write("\n")
        f.write("# FINAL EVALUATION\n")
        f.write(response.content)
    
    return {
        "messages": [response]
    }

def route_after_analyse_users(state: OverallState) -> str:
    return "end" # for now

def timeout_node(state: Any) -> OverallState:
    """timeout node"""
    node_before = state.get("node_before_timeout", "")
    if not node_before:
        return {}
    duration = state.get("timeout_duration", 30) # default to 30 seconds
    print(f"{Fore.RED}Rate limit/error detected. Implementing {duration}s backoff strategy for {node_before}...{Style.RESET_ALL}")
    
    # Progressive countdown with status updates
    for i in range(duration):
        remaining = duration - i
        if remaining % 10 == 0 or remaining <= 5:
            print(f"{Fore.YELLOW}Waiting... {remaining}s remaining{Style.RESET_ALL}")
        time.sleep(1)
    
    print(f"{Fore.GREEN}Timeout complete. Resuming operations...{Style.RESET_ALL}")
    
    return {}
    
def route_after_timeout_node(state: Any) -> str:
    node_before_timeout = state.get("node_before_timeout", "")
    if not node_before_timeout:
        raise Exception("No node before timeout")
    return node_before_timeout

# SUBGRAPH: Analyse user
class AnalyseUserState(TypedDict):
    target_name: str
    research_period: str
    research_requirements: str
    minimum_tweets_to_collect: int
    minimum_accounts_to_analyse: int

    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_id: int
    user_screen_name: str
    tweets_summary: str
    top_tweets: List[str]
    comments_summary: Dict[str, Tuple[float, str]] # tweet_id: (sentiment_score, summary)
    llm: ChatOpenAI
    node_before_timeout: str

class AnalyseTweetsResult(BaseModel):
    tweets_summary: str = Field(description="Summary of the tweets offering insights into the company and the market")
    top_tweets: List[str] = Field(description="List of the top 10 tweets by their tweet_id")

def analyse_tweets(state: AnalyseUserState) -> AnalyseUserState:
    """Analyse users"""
    print(f"{Fore.RED}Analysing tweets for {state['user_screen_name']}{Style.RESET_ALL}")
    # Starting fresh analysis
    # TODO: Use bullet points for the summary and keep it concise
    system_prompt = f"""
    You are a senior investment research analyst conducting market impact assessment for {state["target_name"]}.
    ANALYSIS PERIOD: Last {state["research_period"]}
    {f"SPECIFIC REQUIREMENTS: {state['research_requirements']}" if state["research_requirements"] else ""}
    You are a senior investment research analyst. Task: Write a Market Impact Report (≥200 words but no more than 400 words) based on the provided tweets from the last month. Include 3 sections: Themes & Catalysts – Summarize tweet content (news, products, services, milestones). Explicitly name products/services. Identify market catalysts (events, announcements, trends that could move price). Engagement, Timing & Risks – Analyze which topics drove the most engagement/viral potential. Highlight timing indicators (urgency, near-term vs. long-term impact). Note risk factors (negative issues, governance, funding, delays). Top 10 Influential Tweets – List top 10 tweets by tweet_id with highest market-moving potential. For each: give sentiment (positive/negative/neutral, quantified if possible) + key engagement metrics. Focus on actionable insights affecting stock price, trading volume, investor behavior.""".strip()
    
    update = {
        "tweets_summary": "",
        "top_tweets": [],
        "node_before_timeout": ""
    }
    
    try:
        latest_tweets = get_user_tweets(state["user_id"], minimum_tweets=state["minimum_tweets_to_collect"], period=state["research_period"])[0]
    except Exception as e:
        return {
            "node_before_timeout": "analyse_tweets",
            "timeout_duration": 60
        }

    
    
    if not latest_tweets:
        return update
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"{tweets_to_json(latest_tweets)}"),
    ]
    response = state["llm"].with_structured_output(AnalyseTweetsResult).invoke(messages)
    update["tweets_summary"] = response.tweets_summary
    update["top_tweets"] = response.top_tweets
    return update

from transformers import pipeline
roberta_model_path = "cardiffnlp/twitter-roberta-base-sentiment-latest"
roberta_model = pipeline("sentiment-analysis", model=roberta_model_path, tokenizer=roberta_model_path)


def analyse_comments(state: AnalyseUserState) -> AnalyseUserState:
    """Analyse comments"""
    # system_prompt = f"""
    #     For each high-engagement tweet, use get_comments tool to extract top 100 comments. Input the tweet_id of the tweet.
    #     Analyze comment sentiment patterns, themes, and market-moving insights
    #     Identify bullish vs bearish sentiment ratios
    #     PHASE 4: INVESTMENT-GRADE ANALYSIS SYNTHESIS
    #     Synthesize findings into actionable investment insights
    #     Quantify sentiment trends with specific metrics
    #     Identify key themes, catalysts, and risk factors
    #     Provide concrete examples with engagement data
    #     Assess potential market impact and timing
    # """
    labels = {
        'negative': -1,
        'neutral': 0,
        'positive': 1
    }
    update = {
        "comments_summary": {}
    }
    for tweet_id in state["top_tweets"][:5]:
        comments = get_comments(tweet_id, minimum_comments=100)[0]
        cleaned_comments = []
        for comment in comments:
            cleaned_comment = stringify_tweet(comment)
            if not cleaned_comment: continue
            cleaned_comments.append(cleaned_comment)

        sentiments = roberta_model(cleaned_comments)
        sentiment_score = sum([sentiment["score"] * labels[sentiment["label"]] for sentiment in sentiments]) / len(sentiments)
        update["comments_summary"][tweet_id] = (sentiment_score, "") # TODO: Add summary here
        print(f"{Fore.CYAN}Tweet {tweet_id}: {sentiment_score}{Style.RESET_ALL}")

        
    return update

def user_analysis_tools(state: AnalyseUserState) -> AnalyseUserState:
    """Analyse one user tools"""
    ai_msg = next(m for m in reversed(state["messages"]) if isinstance(m, AIMessage))
    tool_msgs = []
    for tool_call in ai_msg.tool_calls:
        call = tool_call
        tool_name = tool_call["name"]
        args = tool_call["args"]
        print(f"{Fore.CYAN}Tool call: {tool_name} with args: {args}{Style.RESET_ALL}")
        content = ''
        if tool_name == "get_comments":
            content = get_comments_str.run(args)

        tool_msg = ToolMessage(
            content=content, name=tool_name, tool_call_id=call["id"]
        )
        tool_msgs.append(tool_msg)
    return {
        "messages": state["messages"] + tool_msgs
    }

def route_after_analyse_tweets(state: AnalyseUserState) -> str:
    if state["node_before_timeout"]:
        return "timeout_node"

    if state["top_tweets"]:
        return "analyse_comments"
    return "end"



analyse_user_workflow = StateGraph(AnalyseUserState)
analyse_user_workflow.add_node(timeout_node)
analyse_user_workflow.add_node(analyse_tweets)
analyse_user_workflow.add_node(analyse_comments)
analyse_user_workflow.add_node(user_analysis_tools)
analyse_user_workflow.add_edge(START, "analyse_tweets")
analyse_user_workflow.add_conditional_edges("analyse_tweets", route_after_analyse_tweets, {
    "analyse_comments": "analyse_comments",
    "timeout_node": "timeout_node",
    "end": END
})
analyse_user_workflow.add_conditional_edges("timeout_node", route_after_timeout_node, {
    "analyse_tweets": "analyse_tweets",
    "analyse_comments": "analyse_comments",
    "end": END
})
analyse_user_workflow.add_edge("analyse_comments", END)
analyse_user_app = analyse_user_workflow.compile()

main_workflow = StateGraph(OverallState, input_state=InputState)
main_workflow.add_node(timeout_node)
main_workflow.add_node(context_setting)
main_workflow.add_node(user_recon_query)
main_workflow.add_node(user_recon_select)
main_workflow.add_node(analyse_users)
main_workflow.add_node(analyse_user_app)

main_workflow.add_edge(START, "context_setting")
main_workflow.add_edge("context_setting", "user_recon_query")
# User Recon 
main_workflow.add_conditional_edges("user_recon_query", route_after_user_recon_query, {
    "timeout_node": "timeout_node",
    "user_recon_select": "user_recon_select",
})
main_workflow.add_conditional_edges("user_recon_select", route_after_user_recon_select, {
    "user_recon_query": "user_recon_query",
    "analyse_users": "analyse_users"
})
# User Analysis
main_workflow.add_conditional_edges("analyse_users", route_after_analyse_users, {
    "timeout_node": "timeout_node",
    "end": END
})

# Timeout
main_workflow.add_conditional_edges("timeout_node", route_after_timeout_node, {
    "user_recon_query": "user_recon_query",
    "user_recon_select": "user_recon_select",
    "analyse_users": "analyse_users"
})
app = main_workflow.compile()

# print(app.get_graph().draw_ascii())
import mermaid as md; from mermaid.graph import Graph;render = md.Mermaid(app.get_graph().draw_mermaid(curve_style=CurveStyle.NATURAL)).to_png("workflow.png")

# exit() 


load_dotenv()
llms = {
    "fast": ChatOpenAI(model_name="gpt-4o-mini", temperature=0),
    # "detailed": ChatOpenAI(model_name="gpt-4o", temperature=0),
    "detailed": ChatOpenAI(model_name="gpt-4o-mini", temperature=0), # 4o costs too much, im poor...
}

input_state = {
    "target_name": "Rocket Lab",
    "research_requirements": "",
    "minimum_tweets_to_collect": 200,
    "minimum_accounts_to_analyse": 3,
    "research_period": "month=1",
    "llms": llms,
}
    
for chunk in app.stream(input_state, stream_mode="updates", config={"recursion_limit": 100}, subgraphs=True):
    try:
        if isinstance(chunk, tuple):
            chunk = chunk[1]
        node_name = list(chunk.keys())[0]
        print(f'{Fore.YELLOW}Processed Node: {node_name}{Style.RESET_ALL}')
        if not chunk[node_name]: continue
        if 'messages' not in chunk[node_name]: continue

        messages = chunk[node_name]['messages']   
        if 'tool' in node_name:
            for message in messages:
                if message.status == 'error':
                    print(f"{Fore.RED}{message.tool_call_id} : {message.content} ❌{Style.RESET_ALL}")
                else:
                    print(f"{Fore.GREEN}{message.tool_call_id} ✅{Style.RESET_ALL}")
        elif len(messages) > 0:
            message = messages[0]
            if message.content:
                print(f"{Fore.CYAN}{message.content}{Style.RESET_ALL}")
            elif hasattr(message, 'tool_calls'):
                for tool_call in message.tool_calls:
                    args = [f"{key} = '{value}'" for key, value in tool_call['args'].items()]
                    print(f"{Fore.CYAN}{tool_call['id']}: {tool_call['name']}({", ".join(args)}) {Style.RESET_ALL}")
    except Exception as e:
        # pass
        print(type(chunk),chunk)
        import traceback
        traceback.print_exc()

    print("="*100)
