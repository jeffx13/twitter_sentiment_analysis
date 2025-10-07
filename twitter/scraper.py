

from typing import Optional, Union, List, Dict, Any, Tuple
from urllib.parse import urlencode 
from urllib.parse import urlparse
import datetime
import rnet
from .utils import *
import os, json

def parse_tweet(result: dict) -> Optional[Tweet]:
    if '__typename' in result and result['__typename'] == "TweetTombstone":
        return None
    legacy = result['legacy']
    user_results = result['core']['user_results']['result']
    tweet: Tweet = {
        "text": legacy['full_text'],
        "quotes": legacy['bookmark_count'],
        "replies": legacy['reply_count'], 
        "retweets": legacy['retweet_count'],
        "likes": legacy['favorite_count'],
        "created_at": legacy['created_at'],
        "bookmarks": legacy['bookmark_count'],
        "lang": legacy['lang'],
        "tweet_id": result['rest_id'],
        "views": result['views']['count'] if 'count' in result['views'] else "?",
        
        # User Information
        "user_rest_id": user_results['rest_id'],
        "user_name": user_results['core']['name'],
        "user_screen_name": user_results['core']['screen_name'],
        "user_bio": user_results['legacy']['description'],  
        # "user_id": user_results['id']

        "retweeted_tweet": None,
        "quoted_tweet": None,
        "replying_to": None,
        "post_image_description": None,
        "post_video_description": None,
    }
    
    if 'post_image_description' in result:
        tweet["post_image_description"] = result['post_image_description']
    if 'post_video_description' in result:
        tweet["post_video_description"] = result['post_video_description']
    if 'in_reply_to_screen_name' in legacy:
        tweet["replying_to"] = legacy['in_reply_to_screen_name']
    
    if 'quoted_status_result' in result and result['quoted_status_result']:
        quoted_result = result['quoted_status_result']['result']
        if quoted_result['__typename'] == 'TweetWithVisibilityResults': quoted_result = quoted_result['tweet']
        quoted_tweet = parse_tweet(quoted_result)
        if not quoted_tweet:
            tweet["quoted_tweet"] = quoted_tweet
    if 'retweeted_status_result' in legacy and legacy['retweeted_status_result']:
        retweeted_result = legacy['retweeted_status_result']['result']
        if retweeted_result['__typename'] == 'TweetWithVisibilityResults': retweeted_result = retweeted_result['tweet']
        retweeted_tweet = parse_tweet(retweeted_result)
        if not retweeted_tweet:
            tweet["retweeted_tweet"] = retweeted_tweet

    return tweet

def parse_entries(entries: list[dict], filter_retweets: bool = True) -> Tuple[List[Tweet], str]:
    if len(entries) == 2 and (entries[0]['entryId'].startswith('cursor') and entries[-1]['entryId'].startswith('cursor')):
        return [], ""
    elif not entries[-1]['entryId'].startswith('cursor'): # cursor-showmorethreads or cursor-bottom 
        return [], ""
    
    cursor_bottom = entries[-1]['content']['value']
    tweets = []
    
    for entry in entries[:-1]:
        entry_id = entry['entryId']
        if entry_id.startswith('profile-conversation'):
            items = entry['content']['items']
            for item in items:
                result = item['item']['itemContent']['tweet_results']['result']
                if result['__typename'] == 'TweetWithVisibilityResults': 
                    result = result['tweet']
                elif result['__typename'] != 'Tweet': 
                    # print(result['__typename'])
                    continue
                tweet = parse_tweet(result)
                if not tweet: continue
                tweets.append(tweet)
            continue
        elif entry_id[:2] not in ['tw', 'co']:  # only consider tweet-1968010132945846663 or conversationthread-1968013218296762
            # tweet not promoted-tweet, who-to-follow, cursor-top, cursor-bottom
            continue
        
        content = entry['content']
        entry_type = content['entryType']
        if entry_type == 'TimelineTimelineModule':
            if 'promoted' in content['items'][0]['entryId']: continue
            content = content['items'][0]['item']
        elif entry_type != 'TimelineTimelineItem':
            # print("Invalid entry type: "+entry_type)
            continue

        tweet_results = content['itemContent']['tweet_results']
        if not tweet_results: continue
        result = tweet_results['result']
        if result['__typename'] == 'TweetWithVisibilityResults': 
            result = result['tweet']
        elif result['__typename'] != 'Tweet': 
            # print(result['__typename'])
            continue
        tweet = parse_tweet(result)
        if filter_retweets and tweet['retweeted_tweet']: continue
        if not tweet: continue
        tweets.append(tweet)   
    return tweets, cursor_bottom

def get_user_tweets(user_id: Union[str, int], minimum_tweets: int = -1, period: str = "all", cursor: Optional[str] = "", filter_retweets: bool = True) -> tuple[list[Tweet], str]:
    """
    Fetch tweets from a user with pagination support. Minimum tweets takes precedence over period.
    """
    print("Getting tweets for user_id: ", user_id)
    cutoff_date = None
    user_tweets_url = "https://x.com/i/api/graphql/VfoNveT-zJPGVZMPydZUfQ/UserTweets"
    user_tweets_path = urlparse(url=user_tweets_url).path
    headers['x-client-transaction-id'] = ct.generate_transaction_id(method="GET", path=user_tweets_path)
    tweets = []

    if period != "all":
        for p in period.split(' '):
            metric, value = p.split('=')
            days = 0
            if metric == 'day':
                days += int(value)
            elif metric == 'week':
                days += int(value) * 7
            elif metric == 'month':
                days+= int(value) * 31
            elif metric == 'year':
                days += int(value) * 365
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
    
    while True:
        params = {
            'variables': '{"userId":"' + str(user_id) + '","count":20,"cursor":"' + cursor + '","includePromotedContent":false,"withQuickPromoteEligibilityTweetFields":false,"withVoice":true}',
            'features': '{"rweb_video_screen_enabled":false,"payments_enabled":false,"profile_label_improvements_pcf_label_in_post_enabled":true,"rweb_tipjar_consumption_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"premium_content_api_read_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"c9s_tweet_anatomy_moderator_badge_enabled":true,"responsive_web_grok_analyze_button_fetch_trends_enabled":false,"responsive_web_grok_analyze_post_followups_enabled":true,"responsive_web_jetfuel_frame":true,"responsive_web_grok_share_attachment_enabled":true,"articles_preview_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":true,"tweet_awards_web_tipping_enabled":false,"responsive_web_grok_show_grok_translated_post":true,"responsive_web_grok_analysis_button_from_backend":true,"creator_subscriptions_quote_tweet_preview_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_grok_image_annotation_enabled":true,"responsive_web_grok_imagine_annotation_enabled":true,"responsive_web_grok_community_note_auto_translation_is_enabled":false,"responsive_web_enhance_cards_enabled":false}',
            'fieldToggles': '{"withArticlePlainText":false}',
        }
        response = client.get(
            user_tweets_url + "?" + urlencode(params),
            cookies=cookies,
            headers=headers,
        )
        if response.status != 200:
            raise Exception(f"{response.status_code} : {response.text()}")
        
        entries = [instruction['entries'] for instruction in response.json()['data']['user']['result']['timeline']['timeline']['instructions'] if instruction['type'] == 'TimelineAddEntries'][0]
        
        if not entries:
            # print(f"No entries found for {user_id} {cursor}")
            break
        
        parsed_tweets, cursor = parse_entries(entries, filter_retweets=filter_retweets)
        tweets.extend(parsed_tweets)
        
        if minimum_tweets != -1 and len(tweets) >= minimum_tweets: break
        if cutoff_date and len(parsed_tweets) != 0:
            # e.g. "Sat Dec 21 15:23:55 +0000 2024"
            date_of_last_tweet = datetime.datetime.strptime(parsed_tweets[-1]["created_at"], "%a %b %d %H:%M:%S %z %Y").replace(tzinfo=None)
            if date_of_last_tweet < cutoff_date:
                cursor = ''

        if cursor == "": break

    return tweets, cursor

def get_comments(tweet_id: Union[str, int], minimum_comments: int = 1, ranking_mode: str = "Relevance", cursor: Optional[str] = "") -> tuple[list["Tweet"], str]:
    """Get the comments for a tweet
    Args:
        tweet_id: The ID of the tweet to get the comments for
        cursor: The cursor to get the next page of comments or empty string if it is the last page
    Returns:
        a json string of the comments and the cursor to get the next page of comments
    """
    tweet_id = str(tweet_id)
    comments = []
    while True:
        params = {
        'variables': '{"focalTweetId":"' + tweet_id + '","with_rux_injections":false,"rankingMode":"' + ranking_mode + '","includePromotedContent":false,"withCommunity":true,"withQuickPromoteEligibilityTweetFields":false,"withBirdwatchNotes":true,"withVoice":true,"cursor":"' + cursor + '"}',
        'features': '{"rweb_video_screen_enabled":false,"payments_enabled":false,"profile_label_improvements_pcf_label_in_post_enabled":true,"rweb_tipjar_consumption_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"premium_content_api_read_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"c9s_tweet_anatomy_moderator_badge_enabled":true,"responsive_web_grok_analyze_button_fetch_trends_enabled":false,"responsive_web_grok_analyze_post_followups_enabled":true,"responsive_web_jetfuel_frame":true,"responsive_web_grok_share_attachment_enabled":true,"articles_preview_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":true,"tweet_awards_web_tipping_enabled":false,"responsive_web_grok_show_grok_translated_post":true,"responsive_web_grok_analysis_button_from_backend":true,"creator_subscriptions_quote_tweet_preview_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_grok_image_annotation_enabled":true,"responsive_web_grok_imagine_annotation_enabled":true,"responsive_web_grok_community_note_auto_translation_is_enabled":false,"responsive_web_enhance_cards_enabled":false}',
        'fieldToggles': '{"withArticleRichContentState":true,"withArticlePlainText":false,"withGrokAnalyze":false,"withDisallowedReplyControls":false}',
        }

        tweet_detail_url = "https://x.com/i/api/graphql/ebRcCTtibrqIeEL92E34eg/TweetDetail"
        tweet_detail_path = urlparse(url=tweet_detail_url).path
        
        headers['x-client-transaction-id'] = ct.generate_transaction_id(method="GET", path=tweet_detail_path)
        response = client.get(
            tweet_detail_url + "?" + urlencode(params),
            cookies=cookies,
            headers=headers,
        )
        if response.status != 200: 
            raise Exception(f"{response.status_code} : {response.text}")
        instructions = response.json()['data']['threaded_conversation_with_injections_v2']['instructions']
        entries = []
        for instruction in instructions:
            if instruction['type'] == 'TimelineAddEntries':
                entries = instruction['entries']
                break

        if len(comments) >= minimum_comments: break
        parsed_comments, cursor = parse_entries(entries)
        comments.extend(parsed_comments)
        if cursor == "": break
    return comments, cursor
    
def search_people(query: str, cursor: Optional[str] = "") -> Tuple[Dict[str, Any], str]:
    query = query.replace('"', '')
    params = {
    'variables': '{"rawQuery":"' + query + '","count":100,"cursor":"' + cursor + '","querySource":"","product":"People","withGrokTranslatedBio":false}',
    'features': '{"rweb_video_screen_enabled":false,"payments_enabled":false,"profile_label_improvements_pcf_label_in_post_enabled":true,"rweb_tipjar_consumption_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"premium_content_api_read_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"c9s_tweet_anatomy_moderator_badge_enabled":true,"responsive_web_grok_analyze_button_fetch_trends_enabled":false,"responsive_web_grok_analyze_post_followups_enabled":true,"responsive_web_jetfuel_frame":true,"responsive_web_grok_share_attachment_enabled":true,"articles_preview_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":true,"tweet_awards_web_tipping_enabled":false,"responsive_web_grok_show_grok_translated_post":true,"responsive_web_grok_analysis_button_from_backend":true,"creator_subscriptions_quote_tweet_preview_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_grok_image_annotation_enabled":true,"responsive_web_grok_imagine_annotation_enabled":true,"responsive_web_grok_community_note_auto_translation_is_enabled":false,"responsive_web_enhance_cards_enabled":false}',
    }
    
    search_timeline_url = "https://x.com/i/api/graphql/7fWgap3nJOk9UpFV7UqcoQ/SearchTimeline"
    search_timeline_path = urlparse(url=search_timeline_url).path
    headers['x-client-transaction-id'] = ct.generate_transaction_id(method="GET", path=search_timeline_path)

    response = client.get(
        search_timeline_url + "?" + urlencode(params),
        cookies=cookies, headers=headers,
    )


    if response.status != 200: 
        raise Exception(f"{response.status_code} : {response.text}")
    entries = response.json()['data']['search_by_raw_query']['search_timeline']['timeline']['instructions'][-1]['entries']
    cursor_bottom = entries[-1]['content']['value']
    users = []
    for entry in entries:
        entry_id = entry['entryId'] #
        if entry_id[0] != 'u': # e.g. user-\d+
            continue
        result = entry['content']['itemContent']['user_results']['result']
        name = result['core']['name'] if 'name' in result['core'] else ""
        if not name: continue
        rest_id = result['rest_id']
        # avatar = result['avatar']['image_url'] if 'avatar' in result else ""
        is_blue_verified = result['is_blue_verified']
        
        screen_name = result['core']['screen_name']
        created_at = result['core']['created_at']
        
        legacy = result['legacy']
        description = legacy['description']
        location = result['location']['location']
        followers_count = legacy['followers_count']
        friends_count = legacy['friends_count']
        favourites_count = legacy['favourites_count']

        # listed_count = legacy['listed_count']
        # media_count = legacy['media_count']
        # profile_banner_url = legacy['profile_banner_url'] if 'profile_banner_url' in legacy else ""
        # statuses_count = legacy['statuses_count']
        users.append({
            'name': name,
            'screen_name': screen_name,
            'user_id': rest_id,
            # 'avatar': avatar,
            'description': description,
            'location': location,
            'followers_count': followers_count,
            'friends_count': friends_count,
            'favourites_count': favourites_count,
            'is_blue_verified': is_blue_verified,
        })
    return users, cursor_bottom

def search_tweets(query: str, latest: bool = True, cursor: Optional[str] = "") -> Tuple[List[Tweet], str]:
    params = {
    'variables': '{"rawQuery":"' + query + ' min_replies:10 -filter:replies","count":20,"querySource":"typed_query","product":"' + ("Latest" if latest else "Top") + '","withGrokTranslatedBio":false}',
    'features': '{"rweb_video_screen_enabled":false,"payments_enabled":false,"profile_label_improvements_pcf_label_in_post_enabled":true,"rweb_tipjar_consumption_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"premium_content_api_read_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"c9s_tweet_anatomy_moderator_badge_enabled":true,"responsive_web_grok_analyze_button_fetch_trends_enabled":false,"responsive_web_grok_analyze_post_followups_enabled":true,"responsive_web_jetfuel_frame":true,"responsive_web_grok_share_attachment_enabled":true,"articles_preview_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":true,"tweet_awards_web_tipping_enabled":false,"responsive_web_grok_show_grok_translated_post":true,"responsive_web_grok_analysis_button_from_backend":true,"creator_subscriptions_quote_tweet_preview_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_grok_image_annotation_enabled":true,"responsive_web_grok_imagine_annotation_enabled":true,"responsive_web_grok_community_note_auto_translation_is_enabled":false,"responsive_web_enhance_cards_enabled":false}',
    }
    
    search_timeline_url = "https://x.com/i/api/graphql/7fWgap3nJOk9UpFV7UqcoQ/SearchTimeline"
    search_timeline_path = urlparse(url=search_timeline_url).path
    headers['x-client-transaction-id'] = ct.generate_transaction_id(method="GET", path=search_timeline_path)

    response = client.get(
        search_timeline_url + "?" + urlencode(params),
        cookies=cookies,
        headers=headers,
    )
    if response.status != 200: 
        raise Exception(f"{response.status_code} : {response.text}")
    entries = response.json()['data']['search_by_raw_query']['search_timeline']['timeline']['instructions'][0]['entries']
    return parse_entries(entries)

client = rnet.BlockingClient(impersonate=rnet.Impersonate.Firefox139)
headers, cookies = load_secrets()
ct = create_client_transaction(client, headers)








