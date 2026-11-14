"""
Discord message size limits.

Bots count characters, not words. A normal message body is 2,000 characters.
Nitro's 4,000-character bump is only for a person typing in the app. Bot
messages stay at 2,000.

Rich cards (embeds) have a second cap: every card in one message, added
together, must stay at or under 6,000 characters. That sum includes the
title, description, author name, footer, and every field name and value.
"""

from typing import List, Sequence, Tuple

import discord

MESSAGE_CONTENT_LIMIT = 2000
EMBED_TITLE_LIMIT = 256
EMBED_DESCRIPTION_LIMIT = 4096
EMBED_FIELD_NAME_LIMIT = 256
EMBED_FIELD_VALUE_LIMIT = 1024
EMBED_FOOTER_LIMIT = 2048
EMBED_AUTHOR_LIMIT = 256
EMBEDS_PER_MESSAGE = 10
EMBED_TOTAL_LIMIT = 6000
FIELDS_PER_EMBED = 25


def clip(text: str, limit: int) -> str:
    """Shorten text so Discord will accept it."""
    text = text or ""
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    if limit == 1:
        return "…"
    return text[: limit - 1].rstrip() + "…"


def embed_text_length(embed: discord.Embed) -> int:
    """Count the characters Discord charges against the 6,000 limit."""
    total = len(embed.title or "") + len(embed.description or "")
    footer = getattr(embed, "footer", None)
    if footer is not None and getattr(footer, "text", None):
        total += len(footer.text)
    author = getattr(embed, "author", None)
    if author is not None and getattr(author, "name", None):
        total += len(author.name)
    for field in embed.fields:
        total += len(field.name or "") + len(field.value or "")
    return total


def pack_embeds(
    embeds: Sequence[discord.Embed],
    limit: int = EMBED_TOTAL_LIMIT,
    max_count: int = EMBEDS_PER_MESSAGE,
) -> List[List[discord.Embed]]:
    """
    Group cards into messages that stay under Discord's combined limit.
    One card that is already over the limit is left on its own.
    """
    batches: List[List[discord.Embed]] = []
    current: List[discord.Embed] = []
    used = 0
    for embed in embeds:
        size = embed_text_length(embed)
        overflows = current and (len(current) >= max_count or used + size > limit)
        if overflows:
            batches.append(current)
            current = []
            used = 0
        current.append(embed)
        used += size
    if current:
        batches.append(current)
    return batches


def fit_embed(title: str, description: str, color: int, footer: str = "") -> discord.Embed:
    """Build one card that fits in a message by itself."""
    footer = clip(footer, EMBED_FOOTER_LIMIT)
    title = clip(title, EMBED_TITLE_LIMIT)
    room = EMBED_TOTAL_LIMIT - len(title) - len(footer)
    description = clip(description, min(EMBED_DESCRIPTION_LIMIT, max(0, room)))
    embed = discord.Embed(title=title, description=description, color=color)
    if footer:
        embed.set_footer(text=footer)
    return embed


def pack_field_embeds(
    title: str,
    description: str,
    fields: Sequence[Tuple[str, str, bool]],
    color: int,
    footer: str = "",
) -> List[discord.Embed]:
    """
    Turn a list of fields into as many cards as needed.
    Each field value is capped at 1,024. Each card stays under 6,000.
    """
    footer = clip(footer, EMBED_FOOTER_LIMIT)
    title = clip(title, EMBED_TITLE_LIMIT)
    description = clip(description, EMBED_DESCRIPTION_LIMIT)
    footer_len = len(footer)

    def fresh(continued: bool) -> discord.Embed:
        body = "More from the same report." if continued else description
        embed = discord.Embed(title=title, description=clip(body, EMBED_DESCRIPTION_LIMIT), color=color)
        return embed

    embeds: List[discord.Embed] = []
    current = fresh(False)
    used = embed_text_length(current) + footer_len

    for name, value, inline in fields:
        name = clip(name, EMBED_FIELD_NAME_LIMIT)
        value = clip(value, EMBED_FIELD_VALUE_LIMIT)
        extra = len(name) + len(value)
        needs_new = current.fields and (
            len(current.fields) >= FIELDS_PER_EMBED or used + extra > EMBED_TOTAL_LIMIT
        )
        if needs_new:
            if footer and not embeds:
                current.set_footer(text=footer)
            embeds.append(current)
            current = fresh(True)
            used = embed_text_length(current) + footer_len
        current.add_field(name=name, value=value or "—", inline=inline)
        used += extra

    if footer:
        current.set_footer(text=footer)
    embeds.append(current)
    return embeds
