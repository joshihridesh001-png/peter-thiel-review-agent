import discord

from cogs.tracker import TrackerCog
from engine.discord_budget import (
    EMBED_TOTAL_LIMIT,
    clip,
    embed_text_length,
    fit_embed,
    pack_embeds,
    pack_field_embeds,
)


def test_clip_keeps_short_text_and_marks_the_cut():
    assert clip("hello", 10) == "hello"
    assert clip("hello team", 6) == "hello…"
    assert len(clip("x" * 50, 6)) == 6


def test_pack_embeds_splits_before_the_6000_character_cap():
    small = discord.Embed(title="Day", description="Short standings.")
    huge_a = discord.Embed(title="A", description="a" * 4000)
    huge_b = discord.Embed(title="B", description="b" * 4000)

    batches = pack_embeds([small, huge_a, huge_b])

    assert len(batches) == 2
    assert batches[0] == [small, huge_a]
    assert batches[1] == [huge_b]
    for batch in batches:
        assert sum(embed_text_length(item) for item in batch) <= EMBED_TOTAL_LIMIT


def test_fit_embed_stays_inside_one_message():
    embed = fit_embed("Score", "word " * 5000, color=0x3498DB, footer="saved")
    assert embed_text_length(embed) <= EMBED_TOTAL_LIMIT
    assert len(embed.description) <= 4096


def test_field_report_splits_when_five_long_notes_do_not_fit():
    fields = [(f"Person {i}", "n" * 1024, False) for i in range(5)]
    embeds = pack_field_embeds("Week", "s" * 2000, fields, color=1, footer="end")
    assert len(embeds) >= 2
    for embed in embeds:
        assert embed_text_length(embed) <= EMBED_TOTAL_LIMIT
        for field in embed.fields:
            assert len(field.value) <= 1024


def test_tracker_matches_display_name_and_ignores_a_missing_id():
    cog = TrackerCog(bot=None)
    assert cog._resolve_founder_key(42, "unknown", display_name="Shivang") == "shivang"
    assert cog._resolve_founder_key(923595474454323281, "unknown") == "yash"
    assert cog._resolve_founder_key(665573807494529065, "unknown") == "shivang"
    assert cog._resolve_founder_key(42, "Yash Aggarwal") == "yash"
    assert cog._resolve_founder_key(0, "stranger") is None
    assert cog._resolve_founder_key(42, "stranger") is None
    assert cog._resolve_founder_key(42, "yy4sh") == "yash"
    assert cog._resolve_founder_key(42, "shivang2468") == "shivang"
