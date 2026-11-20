"""
How big a piece of work is.

The number in the sentence is not the size. "5 connection requests"
is a small chore every day, not 5 points.
"""

import re

_SIZE_5 = (
    "customer paid",
    "they paid",
    "invoice",
    "payment received",
    "wired the",
    "wired us",
    "signed the contract",
    "signed a contract",
    "closed won",
    "term sheet",
)
_SIZE_4 = (
    "to production",
    "in production",
    "deployed",
    "deploy",
    "outage",
    "hotfix",
    "went live",
    "pilot is live",
    "pilot started",
)
_SIZE_3 = (
    "merged",
    "had the call",
    "had a call",
    "had a demo",
    "on the call",
    "demo call",
    "onboarding",
)
_SIZE_2 = (
    "[github pr",
    "[github commit",
    "pull request",
    "booked",
    "meeting set",
    "bug",
    "fixed",
    "shipped",
    "built",
    "finished",
)
_OUTREACH = (
    "linkedin",
    "whatsapp",
    "connection request",
    "connection requests",
    "connects",
    "inmail",
    "cold email",
    "cold dm",
    "follow-up",
    "follow up",
    "followup",
    "outreach",
    "requests",
)
# Past tense. "send the deck" is a plan. "sent the deck" is work that happened.
_FINISHED_VERBS = re.compile(
    r"\b(sent|booked|paid|shipped|finished|fixed|deployed|called|merged|built|did|closed)\b",
    re.IGNORECASE,
)
_REAL_CONVERSATION = (
    "booked",
    "had the call",
    "had a call",
    "had a demo",
    "demo call",
    "on the call",
)


def _has(blob: str, phrases: tuple) -> bool:
    return any(phrase in blob for phrase in phrases)


def is_outreach(text: str) -> bool:
    """Pokes: connection requests, cold emails, follow-ups. Not a booked call."""
    return _has((text or "").lower(), _OUTREACH)


def has_finished_verb(text: str) -> bool:
    """Past tense. 'sent' happened. 'send' is still a plan."""
    return bool(_FINISHED_VERBS.search(text or ""))


def reports_finished_work(text: str) -> bool:
    """True when the note says the work already happened.

    A plan ("send the deck", "tomorrow", "I will") stays false.
    A sales log ("sent 30 whatsapp messages", "40 linkedin connects") stays true.
    """
    blob = text or ""
    finished = bool(_FINISHED_VERBS.search(blob))
    if re.search(r"\b(will|going to|gonna|plan to|tomorrow)\b", blob, re.IGNORECASE) and not finished:
        return False
    if finished or is_outreach(blob):
        return True
    return work_size(blob) > 1


def work_size(text: str) -> int:
    """1 to 5. Same words always return the same size. Counts are ignored."""
    blob = (text or "").lower()
    size = 1
    if _has(blob, _SIZE_2):
        size = 2
    if _has(blob, _SIZE_3):
        size = 3
    if _has(blob, _SIZE_4):
        size = 4
    if _has(blob, _SIZE_5) or (re.search(r"\bpaid\b", blob) and "ads" not in blob):
        size = 5
    # A poke that also says "finished" or "shipped" is still a poke.
    # A booked call or a real conversation is not.
    if is_outreach(blob) and size <= 2 and not _has(blob, _REAL_CONVERSATION):
        return 1
    return size


_FILE_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".pdf", ".csv", ".md",
    ".mp4", ".mov",
)
_STRONG_MARKERS = (
    "screenshot",
    "attachment",
    "recording",
) + _FILE_EXTENSIONS

# Only a real github.com pull or commit. evil.com/pull/1 is not proof.
_GITHUB_ARTIFACT = re.compile(
    r"https?://(?:www\.)?github\.com/[^\s)>\"']+/(?:pull|commit)/[^\s)>\"']+",
    re.IGNORECASE,
)


def github_artifact(text: str) -> bool:
    """True when the text links a pull request or commit on github.com."""
    return bool(_GITHUB_ARTIFACT.search(text or ""))


def proof_grade(text: str) -> str:
    """strong, link, or none.

    A file, a screenshot, a recording, or a github.com pull request unlocks
    the real size. A bare link only confirms a poke. The words "GitHub PR"
    are not proof on their own.
    """
    blob = (text or "").lower()
    if github_artifact(text) or any(marker in blob for marker in _STRONG_MARKERS):
        return "strong"
    if "http://" in blob or "https://" in blob:
        return "link"
    return "none"


def is_strong_url(url: str) -> bool:
    blob = (url or "").lower().split("?", 1)[0]
    if github_artifact(url):
        return True
    return any(blob.endswith(ext) for ext in _FILE_EXTENSIONS)


def scored_size(text: str, completion: float) -> int:
    """Strong proof unlocks the real size. A sentence or a bare link stays size 1."""
    if completion >= 1.0 and proof_grade(text) == "strong":
        return work_size(text)
    return 1


def size_note(text: str, completion: float) -> str:
    """One plain sentence for the card, or empty when the size is obvious."""
    rubric = work_size(text)
    grade = proof_grade(text)
    if is_outreach(text) and grade != "strong":
        if grade == "link":
            return (
                "A link confirms this poke. It stays size 1. "
                "The count is not the size, and the link is not a sale."
            )
        return "Pokes are size 1 every day. The count is not the size."
    if grade == "link" and rubric > 1:
        return (
            f"A bare link is not proof. With a file, a screenshot, or a pull request this is size {rubric}."
        )
    if completion < 1.0 and rubric > 1:
        return f"With proof this is size {rubric}. A sentence stays size 1."
    return ""


def size_label(scored: int, rubric: int) -> str:
    """What the card prints. Both numbers show when proof is missing."""
    scored_n = int(scored)
    rubric_n = int(rubric)
    if rubric_n > scored_n:
        return f"{scored_n}/5 (would be {rubric_n}/5 with proof)"
    return f"{scored_n}/5"


def praise_for_scored_lines(tasks: list) -> str:
    """Praise may only name lines that scored. A zero line stays off this sentence."""
    names = [
        (task.get("task") or "Work").strip()
        for task in tasks or []
        if float(task.get("completion") or 0) > 0 and (task.get("task") or "").strip()
    ]
    if not names:
        return "Nothing here counted as finished work."
    if len(names) == 1:
        return f"Counted today: {names[0]}."
    return "Counted today: " + "; ".join(names) + "."
