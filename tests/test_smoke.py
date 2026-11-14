from config import FOUNDERS, CHANNELS, SYSTEM_EMBED_TITLES, TARGET_UNVESTED_WEIGHTS

def test_config_smoke():
    assert "hridesh" in FOUNDERS
    assert "swarit" in FOUNDERS
    assert "rahul" in FOUNDERS
    assert "yash" in FOUNDERS
    assert "shivang" in FOUNDERS
    assert "riya" not in FOUNDERS
    assert "scores" in CHANNELS
    assert "Weekly Team Report" in SYSTEM_EMBED_TITLES

def test_sales_reps_are_scored_but_not_on_the_cap_table():
    assert FOUNDERS["yash"]["on_cap_table"] is False
    assert FOUNDERS["shivang"]["on_cap_table"] is False
    assert FOUNDERS["yash"]["unvested_target"] == 0.0
    assert FOUNDERS["shivang"]["unvested_target"] == 0.0
    assert FOUNDERS["yash"]["discord_id"] == 923595474454323281
    assert FOUNDERS["shivang"]["discord_id"] == 665573807494529065
    assert set(TARGET_UNVESTED_WEIGHTS) == {"swarit", "rahul"}
