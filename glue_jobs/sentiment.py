#!/usr/bin/env python3
"""
sentiment.py — rule-based sentiment scoring (VADER + a Twitch emote dictionary).
Shared by both the realtime (realtime.py) and offline (batch) paths to keep the algorithm
consistent on both sides.
No ML: VADER handles the text, and the emote dictionary supplies the sentiment for
Twitch-specific emotes (which VADER does not recognize).
"""
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()

# Sentiment weights (-1 to +1) for high-frequency Twitch emotes, maintained by hand
EMOTE_SENTIMENT = {
    # Positive / hyped
    'PogChamp': 0.6, 'POGGERS': 0.6, 'Pog': 0.6, 'PogU': 0.6, 'Poggers': 0.6,
    'KEKW': 0.4, 'LULW': 0.4, 'LUL': 0.4, 'OMEGALUL': 0.4, 'LOL': 0.4,
    'EZ': 0.3, 'EZClap': 0.4, 'catJAM': 0.5, 'GIGACHAD': 0.4, 'Kreygasm': 0.6,
    'PepeLaugh': 0.3, 'forsenInsane': 0.3, '5Head': 0.2, 'PauseChamp': 0.1,
    'Clap': 0.3, 'POG': 0.6, 'peepoHappy': 0.5, 'BASED': 0.3,
    # Negative / down
    'Sadge': -0.5, 'PepeHands': -0.5, 'monkaS': -0.3, 'monkaW': -0.4,
    'FeelsBadMan': -0.5, 'NotLikeThis': -0.4, 'ResidentSleeper': -0.4,
    'WutFace': -0.2, 'Aware': -0.2, 'forsenPossessed': -0.1, 'Sadeg': -0.5,
}


def extract_emotes(text, emotes_field):
    """Extract emote names from text using the position indices in the emotes field."""
    names = []
    if not emotes_field:
        return names
    for chunk in emotes_field.split("/"):
        if ":" not in chunk:
            continue
        _, positions = chunk.split(":", 1)
        for pos in positions.split(","):
            if "-" not in pos:
                continue
            try:
                s, e = pos.split("-")
                names.append(text[int(s):int(e) + 1])
            except (ValueError, IndexError):
                continue
    return names


def score(text, emotes_field=""):
    """Return (compound score -1 to +1, label pos/neu/neg)."""
    text = text or ""
    v = _analyzer.polarity_scores(text)["compound"]
    emote_scores = [EMOTE_SENTIMENT[n] for n in extract_emotes(text, emotes_field)
                    if n in EMOTE_SENTIMENT]
    if emote_scores:
        e = sum(emote_scores) / len(emote_scores)
        comp = 0.5 * v + 0.5 * e          # text and emotes each weigh half
    else:
        comp = v
    label = 'pos' if comp > 0.05 else ('neg' if comp < -0.05 else 'neu')
    return comp, label


if __name__ == "__main__":
    for t, e in [("this is so good Pog", ""), ("worst stream ever", ""),
                 ("KEKW", "25:0-3"), ("hello chat", "")]:
        print(f"{score(t, e)}  <- {t!r}")
