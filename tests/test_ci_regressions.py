"""Additional offline regression tests for the existing PlayerPulse scripts.

These complement, rather than replace, your tests/test_transform_games.py.
Run from the repository root with: python -m pytest tests -v
"""
from pathlib import Path

import pytest

from scripts.fetch_player_games import fetch_archive_urls
from scripts.transform_games import flatten_game, unix_to_utc
from scripts.upload_to_s3 import build_s3_key


def test_epoch_timestamp():
    assert unix_to_utc(0) == "1970-01-01T00:00:00+00:00"


def test_none_timestamp():
    assert unix_to_utc(None) is None


def test_one_day_after_epoch():
    assert unix_to_utc(86400) == "1970-01-02T00:00:00+00:00"


def test_flatten_required_player_fields():
    source = {
        "uuid": "game-001",
        "white": {"username": "Ali", "rating": 1510},
        "black": {"username": "Bob", "rating": 1600},
        "accuracies": {"white": 87.5},
    }
    record = flatten_game(source)
    assert record["game_id"] == "game-001"
    assert record["white_username"] == "Ali"
    assert record["black_rating"] == 1600
    assert record["white_accuracy"] == 87.5
    assert record["black_accuracy"] is None


def test_flatten_missing_optional_fields():
    record = flatten_game({"uuid": "game-002"})
    assert record["game_id"] == "game-002"
    assert record["white_rating"] is None
    assert record["black_username"] is None


def test_archive_url_discovery_uses_mock(monkeypatch):
    """No actual Chess.com API call is made."""
    observed = []

    def fake_fetch_json(url):
        observed.append(url)
        return {"archives": ["https://example.invalid/2026/10"]}

    monkeypatch.setattr("scripts.fetch_player_games.fetch_json", fake_fetch_json)
    assert fetch_archive_urls("Ali") == ["https://example.invalid/2026/10"]
    assert observed == ["https://api.chess.com/pub/player/ali/games/archives"]


def test_s3_partition_key_format():
    key = build_s3_key(Path("ali_games_2026_10.json"))
    assert key == "chesscom/games/username=ali/year=2026/month=10/games.json"


def test_s3_partition_key_rejects_bad_filename():
    with pytest.raises(ValueError, match="Expected filename format"):
        build_s3_key(Path("not_an_archive.txt"))