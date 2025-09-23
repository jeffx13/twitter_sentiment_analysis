from langchain_core.tools import tool
from typing import Optional
from .scraper import get_user_tweets, get_comments, search_people, search_tweets
from .utils import tweets_to_json, tweets_to_table, users_to_json, users_to_table

@tool
def get_user_tweets_str(user_id: str, minimum_tweets: int = 0, period: str = "month=1", cursor: Optional[str] = "") -> str:
    """Fetch a user's tweets with pagination.
    Input: user_id, minimum_tweets, period ("all"|"day"|"week"|"month"|"year"), cursor ("" first page; else prior).
    Output: first line "cursor: <next>" ("" if none); then pipe table:
    tweet_id|type|user|time|views|likes|retweets|quotes|replies|text|lang|user_bio|user_id|media|reply_to|ref
    """

    try:
        tweets_data, cursor = get_user_tweets(user_id, minimum_tweets=minimum_tweets, period=period, cursor=cursor)
        if not tweets_data:
            return f"No tweets found for user ID: {user_id}. You could probably be rate limited. Try again later."
        
        result = f"cursor: {cursor}\n{tweets_to_json(tweets_data)}"
        return result
    except Exception as e:
        return f"Error fetching tweets for user {user_id}: {str(e)}"


@tool  
def get_comments_str(tweet_id: str, minimum_comments: int = 0, cursor: Optional[str] = "") -> str:
    """Fetch replies for a tweet with pagination.
    Input: tweet_id, minimum_comments, cursor ("" first page; else prior).
    Output: first line "cursor: <next>" ("" if none); then pipe table.
    """
    try:
        comments, cursor = get_comments(tweet_id, cursor)
        result = f"cursor: {cursor}\n{tweets_to_json(comments)}"
    except Exception as e:
        result = f"Error fetching comments for tweet ID: {tweet_id}: {str(e)}. You could probably be rate limited. Try again later."
    return result


@tool
def search_people_str(query: str, cursor: Optional[str] = "") -> str:
    """Search Twitter users with pagination.
    Input: query, cursor ("" for first page; else use prior).
    Output: first line is next_cursor ("" if none); then pipe table:
    name|screen_name|rest_id|description|location|followers_count|friends_count|favourites_count|is_blue_verified
    """
    users, next_cursor = search_people(query, cursor)
    if not users:
        return f"No users found for query: {query}. You've probably been rate limited. Try again later."
    ret = f"{next_cursor}\n{users_to_json(users)}"
    return ret


@tool
def search_tweets_str(query: str, cursor: Optional[str] = "") -> str:
    """Search tweets with pagination.
    Input: query, cursor ("" first page; else prior).
    Output: first token is next_cursor ("" if none); then pipe table (same schema as get_user_tweets).
    """
    tweets, cursor_bottom = search_tweets(query, cursor)
    if not tweets:
        return f"No tweets found for query: {query}. You could probably be rate limited. Try again later."
    
    result = f"{cursor_bottom} {tweets_to_json(tweets)}"
    return result
