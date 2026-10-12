"""
Attachment & Link Reader Engine for Peter Thiel Review Agent.
Extracts contents from:
- Plaintext & Markdown (.md, .txt, .csv, .json, etc.)
- Screenshots (.png, .jpg) via Gemini Multimodal Vision
- GitHub PRs & Commit URLs
- Discord cross-channel message jump links
"""

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
