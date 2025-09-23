import re, json
from pathlib import Path
from typing import Iterable, List, Dict, Any, Tuple, TypedDict, Optional
# from .scraper import Tweet
import bs4
import x_client_transaction

class Tweet(TypedDict):
    tweet_id: str
    views: str
    quotes: int
    replies: int
    retweets: int
    likes: int
    created_at: str
    text: str
    bookmarks: int
    lang: str
    
    user_id: str # technically user_rest_id
    user_name: str
    user_screen_name: str
    user_bio: str

    user_avatar: str
    user_created_at: str
    user_followers_count: int
    user_friends_count: int
    user_favourites_count: int
    user_is_blue_verified: bool

    post_image_description: Optional[str]
    post_video_description: Optional[str]
    replying_to: Optional[str] 
    quoted_tweet: Optional["Tweet"]
    retweeted_tweet: Optional["Tweet"]

def load_secrets():
    "Load Twitter headers and cookies"
    with open(Path(__file__).parent / "../secrets.json", "r") as f:
        secrets = json.load(f)
        cookies = secrets['cookies']
        headers = secrets['headers']
    return headers, cookies

def create_client_transaction(client, headers):
    "Create a client for generating a transaction-id"
    response = client.get(url="https://x.com", headers=headers)
    home_page_response = bs4.BeautifulSoup(response.text(), 'html.parser')
    ondemand_file_url = x_client_transaction.constants.ON_DEMAND_FILE_REGEX.search(str(home_page_response))
    if not ondemand_file_url:
        raise Exception("Could not find ondemand.s file")
    ondemand_file_url = f"https://abs.twimg.com/responsive-web/client-web/ondemand.s.{ondemand_file_url.group(1)}a.js"
    ondemand_file_response = client.get(url=ondemand_file_url, headers=headers)
    ondemand_file = bs4.BeautifulSoup(ondemand_file_response.text(), 'html.parser')
    return x_client_transaction.ClientTransaction(home_page_response=home_page_response, ondemand_file_response=ondemand_file)

def clean_tweet(t):
    if t[0] == '@':
        t = t[t.index(' ')+1:]
    t = re.sub(r"http\S+", "", t)      # remove URLs
    t = re.sub(r"\s+", " ", t).strip()
    return t

DELIM = "|"
PIPE_SAFE = "¦"  # replacement for '|' inside fields

def _sanitize(text: str | None) -> str:
    if not text: return ""
    s = str(text)
    s = re.sub(r"https://t.co/\S+", " ", s)
    s = re.sub(r"[\s\r]+", " ", s).strip()
    s = s.replace(DELIM, PIPE_SAFE)
    return s

def _infer_type(t: Tweet) -> str:
    if t["retweeted_tweet"] is not None:
        return "retweet"
    if t["quoted_tweet"] is not None:
        return "quote"
    if t["replying_to"]:
        return "reply"
    return "tweet"

def _media_cell(t: Tweet) -> str:
    parts: List[str] = []
    if t["post_image_description"]:
        parts.append("img:" + _sanitize(t["post_image_description"]))
    if t["post_video_description"]:
        parts.append("vid:" + _sanitize(t["post_video_description"]))
    return "; ".join(parts)

def _ref_cell(t: Tweet) -> str:
    if t["retweeted_tweet"] is not None:
        rt = t["retweeted_tweet"]
        return f"repost: @{rt["user_screen_name"]}"
    if t["quoted_tweet"] is not None:
        qt = t["quoted_tweet"]
        return f'quote:@{qt["user_screen_name"]} {_sanitize(qt["text"])}'
    if t["replying_to"]:
        return f"reply:@{t["replying_to"]}"
    return "-"

def tweets_to_json(
    tweets: Iterable[Tweet], 
    fields: List[str] = ["tweet_id", "type", "created_at", "views", "likes", "retweets", "quotes", "replies", "text", "media", "ref"],
    indent: int = None
) -> str:
    "Field = None for all fields"
    fields = fields or Tweet.__annotations__.keys()
    
    json_list = []
    for t in tweets:
        row = {}
        is_retweet = False
        if t["retweeted_tweet"]:
            t = t["retweeted_tweet"]
            is_retweet = True

        for field in fields:
            field_value = None
            if field == "type":
                field_value = _infer_type(t)
            elif field == "media":
                field_value = _media_cell(t)
            elif field == "ref":
                field_value = _ref_cell(t) if not is_retweet else "retweet:@" + t["user_screen_name"]
            else:
                field_value = _sanitize(t[field])
            row[field] = field_value

        json_list.append(row)
                
    return json.dumps(json_list, ensure_ascii=False, indent=indent)

def users_to_json(users: Iterable[Dict[str, Any]], indent: int = None) -> str:
    users = [ {'screen_name': user['screen_name'], 'bio': user['user_bio'], 'location': user['location'], 'followers_count': user['followers_count'], 'is_blue_verified': user['is_blue_verified']} for user in users]
    return json.dumps(users, ensure_ascii=False, indent=indent)

def users_to_table(users: Iterable[Dict[str, Any]], include_header: bool = True) -> str:
    """
    Serializes user dicts into a compact, LLM-friendly pipe-delimited table.
    """
    cols = [
        # "user_id",
        # "name",
        "screen_name",
        # "avatar",
        "location",
        "followers_count",
        # "friends_count",
        # "favourites_count",
        "is_blue_verified",
        "description",
    ]
    header = DELIM.join(cols)
    lines: List[str] = [header] if include_header else []

    for u in users:
        row = DELIM.join([
            # _sanitize(u.get("user_id")),
            # _sanitize(u.get("name")),
            u.get("screen_name"),
            # _sanitize(u.get("avatar")),
            u.get("location", "Unknown"),
            str(u.get("followers_count")),
            # _sanitize(u.get("friends_count")),
            # _sanitize(u.get("favourites_count")),
            str(u["is_blue_verified"]),
            re.sub(r"@\S+", " ", _sanitize(u["description"])),
        ])
        lines.append(row)

    return "\n".join(lines)

def tweets_to_table(tweets: Iterable[Tweet], fields: List[str] = ["tweet_id", "type", "created_at", "views", "likes", "retweets", "quotes", "replies", "text", "media", "ref"]) -> str:
    "Field = None for all fields"
    fields = fields or Tweet.__annotations__.keys()
    table_rows: List[str] = [DELIM.join(fields)]
    for t in tweets:
        row = []
        for field in fields:
            field_value = None
            if field == "type":
                field_value = _infer_type(t)
            elif field == "media":
                field_value = _media_cell(t)
            elif field == "ref":
                field_value = _ref_cell(t)
            elif field == "text":
                field_value = _sanitize(t["text"])
            else:
                field_value = _sanitize(getattr(t, field_map[field], ""))
            row.append(field_value)

        table_rows.append(DELIM.join(row))
    
    return "\n".join(table_rows)

def write_to_file(content): # For debugging
    with open(Path(__file__).parent / "twitter.txt", "w") as f:
        json.dump(content,f, indent=5)