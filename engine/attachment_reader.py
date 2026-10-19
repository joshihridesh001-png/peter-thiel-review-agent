"""
Attachment & Link Reader Engine for Peter Thiel Review Agent.
Extracts contents from:
- Plaintext & Markdown (.md, .txt, .csv, .json, etc.)
- Screenshots (.png, .jpg) via Gemini Multimodal Vision
- GitHub PRs & Commit URLs
- Discord cross-channel message jump links
"""

import os
import aiohttp
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".csv", ".json", ".py", ".sql", ".sh", ".yaml", ".yml"}

async def extract_text_attachment(url: str, filename: str, max_bytes: int = 256000) -> str:
    """Download text/markdown attachment and return formatted snippet."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10.0)) as resp:
                if resp.status != 200:
                    return f"[File Attachment: {filename} (HTTP {resp.status} download error)]"
                raw_bytes = await resp.read()
                size_kb = round(len(raw_bytes) / 1024, 1)
                
                truncated_note = ""
                if len(raw_bytes) > max_bytes:
                    raw_bytes = raw_bytes[:max_bytes]
                    truncated_note = f"\n[Truncated after {round(max_bytes/1024, 1)} KB]"
                
                text_content = raw_bytes.decode("utf-8", errors="replace")
                return (
                    f"\n[File Attachment: {filename} (Size: {size_kb} KB)]\n"
                    f"────────────────────────────────────────\n"
                    f"{text_content.strip()}{truncated_note}\n"
                    f"────────────────────────────────────────"
                )
    except asyncio.TimeoutError:
        return f"[File Attachment: {filename} (Download timed out)]"
    except Exception as e:
        logger.warning(f"Failed to read attachment {filename}: {e}")
        return f"[File Attachment: {filename} (Error: {str(e)[:60]})]"

from engine.evaluator import _get_client

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

async def extract_image_summary(url: str, filename: str) -> str:
    """Download screenshot and generate concise technical description using Gemini Vision."""
    client = _get_client()
    if not client:
        return f"[Image Attachment: {filename} (Gemini API key not configured for vision)]"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10.0)) as resp:
                if resp.status != 200:
                    return f"[Image Attachment: {filename} (HTTP {resp.status} download error)]"
                image_bytes = await resp.read()

        prompt = (
            "Analyze this technical startup screenshot. In 1 to 2 simple plain English sentences "
            "that a 10-year-old can understand, explain what technical work, code, terminal error, "
            "dashboard metric, or conversation is displayed."
        )

        candidate_models = [
            'gemini-3.8-flash',
            'gemini-3.5-flash',
            'gemini-3.5-flash-lite',
            'gemini-flash-latest',
        ]

        def _call_gemini():
            from google.genai import types
            for model_name in candidate_models:
                try:
                    return client.models.generate_content(
                        model=model_name,
                        contents=[
                            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                            prompt
                        ]
                    )
                except Exception as e:
                    logger.warning(f"Vision model {model_name} failed: {e}")
            return None

        response = await asyncio.to_thread(_call_gemini)
        if response and response.text:
            summary = response.text.strip().replace("\n", " ")
            return f"\n[Screenshot Analysis: {filename}]\nVisual Summary: {summary}"
        return f"[Image Attachment: {filename} (Vision analysis skipped)]"

    except asyncio.TimeoutError:
        return f"[Image Attachment: {filename} (Download timed out)]"
    except Exception as e:
        logger.warning(f"Failed vision analysis on {filename}: {e}")
        return f"[Image Attachment: {filename} (Vision analysis skipped)]"

import re

GH_PR_PATTERN = re.compile(r'https?://github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)')
GH_COMMIT_PATTERN = re.compile(r'https?://github\.com/([^/\s]+)/([^/\s]+)/commit/([a-f0-9]{7,40})')
DISCORD_MSG_PATTERN = re.compile(r'https?://(?:ptb\.|canary\.)?discord\.com/channels/(\d+)/(\d+)/(\d+)')

async def enrich_message_links(content: str, bot_client=None) -> str:
    """Enrich URLs like GitHub PRs, commits, or Discord message references with title/summary."""
    extra_snippets = []
    gh_headers = {"User-Agent": "Peter-Thiel-Review-Bot"}
    gh_token = os.getenv("GITHUB_TOKEN", "").strip()
    if gh_token:
        gh_headers["Authorization"] = f"token {gh_token}"

    # 1. GitHub PRs
    for owner, repo, pr_num in GH_PR_PATTERN.findall(content):
        api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=gh_headers, timeout=aiohttp.ClientTimeout(total=5.0)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        title = data.get("title", "")
                        state = data.get("state", "open")
                        files = data.get("changed_files", 0)
                        body = (data.get("body", "") or "").strip()
                        body_snippet = f"\nSummary of work:\n{body[:300]}..." if body else ""
                        extra_snippets.append(
                            f"[GitHub PR #{pr_num}: {title} ({state}, {files} files changed)]{body_snippet}"
                        )
        except Exception as e:
            logger.debug(f"GitHub PR fetch skipped: {e}")

    # 2. GitHub Commits
    for owner, repo, sha in GH_COMMIT_PATTERN.findall(content):
        api_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=gh_headers, timeout=aiohttp.ClientTimeout(total=5.0)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        msg = data.get("commit", {}).get("message", "").split("\n")[0]
                        extra_snippets.append(
                            f"[GitHub Commit {sha[:7]}: {msg}]"
                        )
        except Exception as e:
            logger.debug(f"GitHub commit fetch skipped: {e}")

    # 3. Discord Jump Links
    if bot_client:
        for gid, cid, mid in DISCORD_MSG_PATTERN.findall(content):
            try:
                channel = bot_client.get_channel(int(cid))
                if channel:
                    msg = await channel.fetch_message(int(mid))
                    if msg:
                        clean_text = msg.clean_content.strip().replace("\n", " ")[:150]
                        extra_snippets.append(
                            f"[Discord Reference from #{channel.name}: \"{clean_text}\"]"
                        )
            except Exception as e:
                logger.debug(f"Discord jump link fetch skipped: {e}")

    if extra_snippets:
        return content + "\n" + "\n".join(extra_snippets)
    return content

from pathlib import Path

async def enrich_discord_message(message, bot_client=None) -> str:
    """Master helper to merge message text, embed contents, attachment contents, and links."""
    content = (getattr(message, "content", "") or "").strip()

    # Append embed descriptions, titles, authors, and URLs
    for e in getattr(message, "embeds", []):
        raw_title = getattr(e, "title", None)
        title = str(raw_title).strip() if isinstance(raw_title, str) else ""

        raw_desc = getattr(e, "description", None)
        desc = str(raw_desc).strip() if isinstance(raw_desc, str) else ""

        raw_url = getattr(e, "url", None)
        url = str(raw_url).strip() if isinstance(raw_url, str) else ""

        author_name = ""
        author_obj = getattr(e, "author", None)
        if author_obj:
            raw_author_name = getattr(author_obj, "name", None)
            if isinstance(raw_author_name, str):
                author_name = raw_author_name.strip()

        parts = []
        if author_name:
            parts.append(f"Author: {author_name}")
        if url:
            parts.append(f"URL: {url}")
        if desc:
            parts.append(desc)
        for field in getattr(e, "fields", []):
            fname = getattr(field, "name", "")
            fval = getattr(field, "value", "")
            if isinstance(fname, str) and isinstance(fval, str) and (fname or fval):
                parts.append(f"{fname}: {fval}")

        embed_body = "\n".join(parts)
        if title and embed_body:
            content += f"\n[Embed: {title}] {embed_body}".strip()
        elif title:
            content += f"\n[Embed: {title}]".strip()
        elif embed_body:
            content += f"\n{embed_body}".strip()

    # Extract attachments
    for att in getattr(message, "attachments", []):
        filename = getattr(att, "filename", "")
        url = getattr(att, "url", "")
        ext = Path(filename).suffix.lower()
        if ext in TEXT_EXTENSIONS:
            snippet = await extract_text_attachment(url, filename)
            content += f"\n{snippet}"
        elif ext in IMAGE_EXTENSIONS:
            snippet = await extract_image_summary(url, filename)
            content += f"\n{snippet}"

    # Enrich links
    client = bot_client or getattr(message, "_state", None)
    content = await enrich_message_links(content, client)
    return content.strip()
