from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from typing import List
import numpy as np
from twitter.utils import stringify_tweet

analyzer = SentimentIntensityAnalyzer()
roberta_model_path = "cardiffnlp/twitter-roberta-base-sentiment-latest"
# sentiment_task = pipeline("sentiment-analysis", model=roberta_model_path, tokenizer=roberta_model_path)
tokenizer = AutoTokenizer.from_pretrained(roberta_model_path, use_fast=True)
model = AutoModelForSequenceClassification.from_pretrained(roberta_model_path)
model.to('cuda' if torch.cuda.is_available() else 'cpu')
model.eval()

def calculate_roberta_sentiment_scores(texts: List[str], batch_size: int = 32) -> List[float]:
    """
    Batch inference returning continuous scores in [-1, 1]:
    score = prob_pos - prob_neg
    For models with 3 labels arranged [negative, neutral, positive].
    """
    scores = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            enc = tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=256)
            enc = {k: v.to('cuda') for k, v in enc.items()}
            out = model(**enc)
            logits = out.logits.cpu()
            probs = torch.softmax(logits, dim=-1).numpy()  # shape (batch, num_labels)
            # mapping - assumes label order is neg, neu, pos
            # if model uses different label order, you must reorder accordingly
            for p in probs:
                if p.shape[0] == 3:
                    prob_neg, prob_neu, prob_pos = p
                    score = float(prob_pos - prob_neg)  # in (-1, 1)
                elif p.shape[0] == 2:
                    # binary model mapping (pos prob - neg prob)
                    prob_neg = p[0]
                    prob_pos = p[1]
                    score = float(prob_pos - prob_neg)
                else:
                    # fallback: compute (expected label index scaled)
                    labels = np.arange(len(p))
                    norm = (labels - labels.mean()) / (labels.max() - labels.min() + 1e-9)
                    score = float(np.dot(p, norm))
                    # then scale to -1..1
                    score = max(-1.0, min(1.0, score))
                scores.append(score)
    return scores

def calculate_vader_sentiment_scores(texts: List[str]) -> List[float]:
    return [analyzer.polarity_scores(sentence)["compound"] for sentence in texts]

def combine_scores(roberta_scores, vader_scores, roberta_weight=0.7, vader_weight=0.3):
    """
    Vectorized combination of RoBERTa and VADER sentiment scores (both in [-1, 1]).
    - If models strongly disagree (|diff|>0.6) or VADER is 0, trust RoBERTa.
    - When signs disagree, upweight RoBERTa (0.9/0.1) and apply disagreement damping.
    Returns a list of combined scores in [-1, 1].
    """
    sR = np.asarray(roberta_scores, dtype=float)
    sV = np.asarray(vader_scores, dtype=float)
    wR = np.full_like(sR, float(roberta_weight))
    wV = np.full_like(sR, float(vader_weight))

    diff = np.abs(sR - sV)
    strong_mask = (diff > 0.6) | (sV == 0.0) # strong disagreement or VADER is exactly neutral → trust RoBERTa
    
    # if disagree, upweight RoBERTa and dampen
    sign_disagree = (sR * sV) < 0.0 
    wR = np.where(sign_disagree, 0.9, wR)
    wV = np.where(sign_disagree, 0.1, wV)
    damp_factor = np.ones_like(sR, dtype=float)
    damp_factor = np.where(sign_disagree, 1.0 - 0.5 * np.minimum(diff, 1.0), damp_factor)

    combined = (wR * sR + wV * sV) / (wR + wV)
    combined = combined * damp_factor
    combined = np.where(strong_mask, sR, combined)

    combined = np.clip(combined, -1.0, 1.0)
    return combined

def calculate_overall_sentiment(comments, roberta_weight=0.8, vader_weight=0.2):
    """
    Calculate the overall sentiment of the comments.
    Return the overall sentiment score in [0, 1].
    """
    cleaned_comments = []
    cleaned_comments_str = []
    for comment in comments:
        cleaned_comment = stringify_tweet(comment)
        if not cleaned_comment: continue
        cleaned_comments.append(comment)
        cleaned_comments_str.append(cleaned_comment)

    roberta_sentiments = calculate_roberta_sentiment_scores(cleaned_comments_str)
    vader_sentiments = calculate_vader_sentiment_scores(cleaned_comments_str)
    combined_scores = combine_scores(roberta_sentiments, vader_sentiments, roberta_weight, vader_weight)
    combined_scores = (combined_scores + 1) / 2
    likes = [comment['likes'] for comment in cleaned_comments]
    weighted_likes = np.log1p(likes) + 1e-9
    weighted_normalised_likes = weighted_likes / np.linalg.norm(weighted_likes)
    return cleaned_comments, np.average(combined_scores, weights=weighted_normalised_likes)