"""Unit tests for the shared VADER + Twitch-emote sentiment scorer (scripts/sentiment.py)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import sentiment  # noqa: E402


def test_positive_text():
    comp, label = sentiment.score("this is so good Pog")
    assert label == "pos"
    assert comp > 0.05


def test_negative_text():
    comp, label = sentiment.score("worst stream ever")
    assert label == "neg"
    assert comp < -0.05


def test_neutral_text():
    _, label = sentiment.score("hello chat")
    assert label == "neu"


def test_emote_pushes_positive():
    # "KEKW" at positions 0-3 is a positive Twitch emote; should lift the score above 0
    comp, label = sentiment.score("KEKW", "25:0-3")
    assert comp > 0
    assert label == "pos"


def test_compound_in_range():
    for text in ["amazing wonderful great", "terrible awful bad", ""]:
        comp, _ = sentiment.score(text)
        assert -1.0 <= comp <= 1.0


def test_extract_emotes_by_position():
    names = sentiment.extract_emotes("KEKW", "25:0-3")
    assert names == ["KEKW"]


def test_empty_is_neutral():
    assert sentiment.score("")[1] == "neu"
