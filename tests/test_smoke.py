import pytest
from config import FOUNDERS, CHANNELS

def test_config_smoke():
    assert "hridesh" in FOUNDERS
    assert "swarit" in FOUNDERS
    assert "rahul" in FOUNDERS
    assert "scores" in CHANNELS
