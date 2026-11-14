"""
Decide who did the work before any score is added up.

Saying a thing is done is not the same as doing it. One piece of work
is scored once, for the person who did it.
"""

import json
import re
from typing import Any, Dict, List, Optional

from config import FOUNDERS
from engine.impact import is_outreach, is_strong_url, proof_grade, scored_size, size_note, work_size

# Talk about the work, with no file and no named teammate.
_TALK_COMPLETION = 0.3
# Someone named exactly one teammate, and nobody brought proof.
_NAMED_COMPLETION = 0.4
# A pull request, commit, link, file, or recording.
_PROOF_COMPLETION = 1.0

_EXTRA_ALIASES = {
    "yash": ["yy4sh"],
    "shivang": ["shivang2468"],
}

# Short role nicknames steal unrelated sentences. Real names only.
_SKIP_ALIASES = {"ceo", "coo", "cto"}

_STOPWORDS = frozenset({
    "a", "an", "the", "this", "that", "these", "those", "thing", "things",
    "now", "today", "tomorrow", "just", "really", "actually", "done",
    "shipped", "finished", "closed", "booked", "merged", "fixed", "built",
    "deployed", "called", "added", "wrote", "with", "from", "have", "has",
    "been", "was", "were", "are", "for", "and", "but", "not", "you", "your",
    "our", "they", "them", "their", "his", "her", "she", "him", "said",
    "says", "say", "about", "into", "over", "after", "before", "out", "off",
    "all", "any", "can", "some", "more", "only", "also", "very", "much",
    "here", "back", "than", "then", "because", "there", "what", "when",
    "where", "which", "while", "would", "could", "should", "please",
    "thanks", "thank", "yeah", "yep", "okay", "hey", "guys", "team",
    "update", "updates", "task", "tasks", "stuff", "something", "someone",
    "work", "working", "made", "make", "making", "does", "did", "get", "got",
    "will", "wont", "want", "wants", "next", "call", "note", "notes",
    "github", "author", "summary", "files", "changed", "pull", "request",
    "commit", "http", "https", "source", "branch", "opened", "open", "file",
    "link", "pasting", "pasted", "paste", "its",
    "sent", "send", "sends", "sending", "calls", "requests", "messages",
    "message", "email", "emails", "linkedin", "connection", "connections",
    "client", "clients", "customer", "customers", "people", "person",
})

_NOT_DONE = re.compile(
    r"\b("
    r"not done|isn'?t done|not finished|isn'?t finished|"
    r"have not|haven'?t|hasn'?t|won'?t|will not|not yet|"
    r"will do|going to|gonna|will ship|will finish|will close|will book"
    r")\b",
    re.IGNORECASE,
)
_SELF = re.compile(r"\b(i|me|my)\b", re.IGNORECASE)
_LEADING = re.compile(
    r"^\s*(shipped|booked|closed|fixed|built|merged|finished|deployed|called|added|wrote|sent|did|made)\b",
    re.IGNORECASE,
)
_URL = re.compile(r"https?://[^\s)>\]\"']+", re.IGNORECASE)
_CLAUSE_SPLIT = re.compile(
    r"\s*,\s*(?:and\s+|but\s+)?|\s+\band\s+|\s+\bbut\s+",
    re.IGNORECASE,
)
_JOB_VERB = re.compile(
    r"\b(sent|send|booked|paid|shipped|finished|fixed|deployed|called|merged|built|made|did|closed)\b",
    re.IGNORECASE,
)
_AUTHOR = re.compile(r"(?im)^[ \t]*Author:\s*(.+)$")
_GITHUB_TITLE = re.compile(r"\[GitHub [^\]]*:\s*([^\]]+)\]", re.IGNORECASE)


def _is_github_block(text: str) -> bool:
    lower = (text or "").lstrip().lower()
    return lower.startswith("[github") or lower.startswith("author:")


def _looks_like_job(part: str) -> bool:
    if _JOB_VERB.search(part or "") or _NOT_DONE.search(part or ""):
        return True
    return work_size(part or "") > 1


def _split_clauses(line: str) -> List[str]:
    rough = _CLAUSE_SPLIT.split(line)
    parts = []
    for part in rough:
        cleaned = re.sub(r"^(?:and|but)\s+", "", part.strip(" ."), flags=re.IGNORECASE).strip()
        if cleaned:
            parts.append(cleaned)
    if len(parts) < 2:
        return [line.strip()]
    job_like = sum(1 for part in parts if _looks_like_job(part))
    if job_like < 2:
        return [line.strip()]
    return parts


def _split_jobs(text: str) -> List[str]:
    """One bullet or one clause is one job. A GitHub block stays whole."""
    raw = (text or "").strip()
    if not raw:
        return []
    if _is_github_block(raw):
        return [raw]
    jobs = []
    for line in re.split(r"[\n\r]+", raw):
        cleaned = re.sub(r"^\s*(?:[-*•]+|\d+[.)])\s*", "", line).strip()
        if not cleaned or cleaned.lower().startswith(("author:", "url:", "summary of work")):
            continue
        # A link on the next line belongs to the job above it.
        if jobs and _urls(cleaned) and not _JOB_VERB.search(cleaned):
            jobs[-1] = jobs[-1] + "\n" + cleaned
            continue
        jobs.extend(_split_clauses(cleaned))
    return jobs or [raw]


def _display_name(founder_key: str) -> str:
    info = FOUNDERS.get(founder_key) or {}
    return info.get("display_name") or founder_key


def _roster_names() -> Dict[str, List[str]]:
    roster: Dict[str, List[str]] = {}
    for key, info in FOUNDERS.items():
        aliases = [info.get("display_name") or "", key]
        aliases.extend(info.get("usernames") or [])
        aliases.extend(info.get("github_usernames") or [])
        aliases.extend(_EXTRA_ALIASES.get(key) or [])
        cleaned = []
        seen = set()
        for alias in aliases:
            text = (alias or "").strip().lower()
            if len(text) < 3 or text in _SKIP_ALIASES or text in seen:
                continue
            seen.add(text)
            cleaned.append(text)
        roster[key] = cleaned
    return roster


def _names_in(text: str, roster_names: Dict[str, List[str]]) -> List[str]:
    lower = (text or "").lower()
    pairs = []
    for key, aliases in roster_names.items():
        for alias in aliases:
            pairs.append((len(alias), key, alias))
    pairs.sort(reverse=True)

    keys: List[str] = []
    spans: List[tuple] = []
    for _, key, alias in pairs:
        pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
        for match in re.finditer(pattern, lower):
            span = match.span()
            if any(not (span[1] <= start or span[0] >= end) for start, end in spans):
                continue
            spans.append(span)
            if key not in keys:
                keys.append(key)
    return keys


def _topic_text(text: str) -> str:
    lines = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith(("author:", "url:", "summary of work")):
            continue
        lines.append(stripped)
    blob = "\n".join(lines) if lines else (text or "")
    return _URL.sub(" ", blob)


def _topics(text: str, roster_names: Dict[str, List[str]]) -> set:
    words = re.findall(r"[a-z0-9]{4,}", _topic_text(text).lower())
    alias_words = {alias for aliases in roster_names.values() for alias in aliases}
    return {word for word in words if word not in _STOPWORDS and word not in alias_words}


def _urls(text: str) -> List[str]:
    found = []
    for match in _URL.findall(text or ""):
        url = match.rstrip(".,")
        url = url.split("?", 1)[0].split("#", 1)[0].rstrip("/").lower()
        if url and url not in found:
            found.append(url)
    return found


def _is_github(text: str) -> bool:
    lower = (text or "").lower()
    return any(tag in lower for tag in ("[github pr", "[github commit", "[github branch", "[github update"))


def _proof_kind(text: str) -> Optional[str]:
    """Strong proof only. A bare link, or the word commit, is not a file."""
    if proof_grade(text) != "strong":
        return None
    lower = (text or "").lower()
    if "[github commit" in lower or "/commit/" in lower:
        return "commit"
    if "[github pr" in lower or "/pull/" in lower:
        return "pr"
    return "file"


def _proof_word(kind: Optional[str]) -> str:
    if kind == "commit":
        return "commit"
    if kind == "pr":
        return "pull request"
    return "file"


def _author_name(text: str, roster_names: Dict[str, List[str]]) -> Optional[str]:
    match = _AUTHOR.search(text or "")
    if not match:
        return None
    keys = _names_in(match.group(1), roster_names)
    if len(keys) == 1:
        return keys[0]
    return None


def _label(text: str) -> str:
    match = _GITHUB_TITLE.search(text or "")
    if match:
        title = re.sub(r"\s*\([^)]*\)\s*$", "", match.group(1)).strip()
        return (title or "GitHub work")[:80]
    for line in (text or "").splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if not stripped or lower.startswith(("author:", "url:", "summary of work")):
            continue
        return stripped[:80]
    return (text or "Work")[:80]


def _is_voice_only(text: str) -> bool:
    return bool(re.fullmatch(
        r"\s*\[voice note with no transcript\]\s*",
        text or "",
        flags=re.IGNORECASE,
    ))


def _task(title: str, completion: float, reason: str, evidence: str) -> Dict[str, Any]:
    body = evidence or title or ""
    if _is_voice_only(body):
        return {
            "task": "Voice note",
            "completion": 0.0,
            "complexity": 1,
            "rubric_size": 1,
            "dharma_multiplier": 1.0,
            "score_reason": "A voice note with no transcript scores 0. Type what was said.",
            "evidence_snippet": body.strip()[:120],
            "seen_urls": [],
        }
    grade = proof_grade(body)
    # A LinkedIn link confirms the poke. It must not unlock a sale or a ship.
    if grade == "link" and is_outreach(body) and completion > 0:
        completion = 1.0
        reason = (
            "A link confirms this poke. It stays size 1. "
            "The count is not the size, and the link is not a sale."
        )
    else:
        note = size_note(body, completion)
        if note:
            reason = f"{reason.rstrip()} {note}"
    return {
        "task": (title or "Work")[:80],
        "completion": completion,
        "complexity": scored_size(body, completion),
        "rubric_size": work_size(body),
        "dharma_multiplier": 1.0,
        "score_reason": reason,
        "evidence_snippet": body[:120],
        "seen_urls": _urls(body),
    }


def judge_doer(
    text: str,
    roster_names: Dict[str, List[str]],
    other_notes: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Who did this sentence? A roster key, "speaker", or "unknown".

    The rule version is the stand-in for LAYA. Names, "I", and a matching
    note are all it is allowed to use.
    """
    names = _names_in(text, roster_names)
    if len(names) >= 2:
        return "unknown"
    if len(names) == 1:
        return names[0]
    if _SELF.search(text or "") or _LEADING.search(text or ""):
        return "speaker"

    topics = _topics(text, roster_names)
    owners: List[str] = []
    for note in other_notes or []:
        note_text = note.get("text") or ""
        # A sentence that names someone is an announcement, not their own note.
        if _names_in(note_text, roster_names):
            continue
        if topics and topics & _topics(note_text, roster_names):
            owner = note.get("founder_key") or ""
            if owner and owner not in owners:
                owners.append(owner)
    if len(owners) == 1:
        return owners[0]
    return "unknown"


def _parse(raw: Dict[str, Any], roster_names: Dict[str, List[str]]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    speaker = str(raw.get("founder_key") or "").strip().lower()
    if speaker not in roster_names:
        return None
    text = str(raw.get("content") or "").strip()
    if not text or (_NOT_DONE.search(text) and not _is_voice_only(text)):
        return None
    if _is_voice_only(text):
        return {
            "speaker": speaker,
            "text": text,
            "topics": set(),
            "names": [],
            "self_claim": False,
            "proof_kind": None,
            "github": False,
            "urls": [],
        }
    topics = _topics(text, roster_names)
    proof = _proof_kind(text)
    vague = bool(re.fullmatch(r"(done|shipped|finished|fixed|sent|booked)[.!]?", text.strip(), re.IGNORECASE))
    # A poke or a real clause can be all common words ("sent 5 requests", "booked two calls").
    if vague or (not topics and not proof and not is_outreach(text) and not _looks_like_job(text)):
        return None
    return {
        "speaker": speaker,
        "text": text,
        "topics": topics,
        "names": _names_in(text, roster_names),
        "self_claim": bool(_SELF.search(text) or _LEADING.search(text)),
        "proof_kind": proof,
        "github": _is_github(text),
        "urls": _urls(text),
    }


def _cluster(items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    parent = list(range(len(items)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            same_topic = items[i]["topics"] & items[j]["topics"]
            same_url = set(items[i]["urls"]) & set(items[j]["urls"])
            if same_topic or same_url:
                union(i, j)

    groups: Dict[int, List[Dict[str, Any]]] = {}
    for index, item in enumerate(items):
        groups.setdefault(find(index), []).append(item)
    return list(groups.values())


def _url_owners(items: List[Dict[str, Any]], roster_names: Dict[str, List[str]]) -> Dict[str, str]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        for url in item["urls"]:
            grouped.setdefault(url, []).append(item)

    owners: Dict[str, str] = {}
    for url, group in grouped.items():
        author = None
        for item in group:
            author = _author_name(item["text"], roster_names)
            if author:
                break
        if author:
            owners[url] = author
            continue
        tagged = [item for item in group if item["github"]]
        if tagged:
            owners[url] = tagged[0]["speaker"]
            continue
        owners[url] = group[0]["speaker"]
    return owners


def _artifact_owner(
    cluster: List[Dict[str, Any]],
    url_owners: Dict[str, str],
    roster_names: Dict[str, List[str]],
) -> Optional[str]:
    best: Optional[tuple] = None
    for item in cluster:
        for url in item["urls"]:
            if not is_strong_url(url):
                continue
            owner = url_owners.get(url)
            if owner:
                author = _author_name(item["text"], roster_names)
                priority = 3 if author or item["github"] else 1
                if best is None or priority > best[0]:
                    best = (priority, owner)
        if item["github"]:
            author = _author_name(item["text"], roster_names) or item["speaker"]
            if best is None or 2 > best[0]:
                best = (2, author)
        elif item["proof_kind"]:
            if best is None or 1 > best[0]:
                best = (1, item["speaker"])
    return best[1] if best else None


def _best_kind(cluster: List[Dict[str, Any]]) -> str:
    kinds = [item["proof_kind"] for item in cluster if item["proof_kind"]]
    if "commit" in kinds:
        return "commit"
    if "pr" in kinds:
        return "pr"
    return "file"


def _append(buckets: Dict[str, List[Dict[str, Any]]], founder_key: str, task: Dict[str, Any]) -> None:
    buckets.setdefault(founder_key, []).append(task)


def _decide_cluster(
    cluster: List[Dict[str, Any]],
    roster_names: Dict[str, List[str]],
    url_owners: Dict[str, str],
    buckets: Dict[str, List[Dict[str, Any]]],
) -> None:
    winner = _artifact_owner(cluster, url_owners, roster_names)
    if winner:
        kind = _proof_word(_best_kind(cluster))
        others = [item for item in cluster if item["speaker"] != winner]
        named_others = []
        for item in cluster:
            named_others.extend(name for name in item["names"] if name != winner)
        if others:
            reason = (
                f"{_display_name(others[0]['speaker'])} said this was done. "
                f"Counted for {_display_name(winner)} because the {kind} is his."
            )
        elif named_others:
            reason = (
                f"{_display_name(winner)} said {_display_name(named_others[0])} did this. "
                f"Counted for {_display_name(winner)} because the {kind} is his."
            )
        else:
            reason = f"The {kind} is yours."
        evidence = next((item["text"] for item in cluster if item["speaker"] == winner), cluster[0]["text"])
        _append(buckets, winner, _task(_label(evidence), _PROOF_COMPLETION, reason, evidence))
        seen = set()
        for item in cluster:
            if not item["self_claim"] or item["speaker"] == winner or item["speaker"] in seen:
                continue
            seen.add(item["speaker"])
            claim_reason = (
                f"{_display_name(item['speaker'])} said he did this. "
                f"It stays a claim because the {kind} is {_display_name(winner)}'s."
            )
            _append(buckets, item["speaker"], _task(_label(item["text"]), 0.0, claim_reason, item["text"]))
        return

    if any(len(item["names"]) >= 2 for item in cluster):
        item = next(item for item in cluster if len(item["names"]) >= 2)
        _append(buckets, item["speaker"], _task(
            _label(item["text"]),
            0.0,
            "This named two people, so it was unclear who did the work.",
            item["text"],
        ))
        return

    people: List[str] = []
    named_explicit = False
    evidence_for: Dict[str, str] = {}
    for item in cluster:
        others = [
            {"founder_key": other["speaker"], "text": other["text"]}
            for other in cluster
            if other is not item
        ]
        verdict = judge_doer(item["text"], roster_names, others)
        if verdict == "speaker":
            doer = item["speaker"]
        elif verdict in roster_names:
            doer = verdict
            if verdict in item["names"]:
                named_explicit = True
        elif not item["names"] and (_looks_like_job(item["text"]) or is_outreach(item["text"])):
            # "Gyro paid" has no "I", but the speaker wrote the clause.
            doer = item["speaker"]
        elif _is_voice_only(item["text"]):
            doer = item["speaker"]
        else:
            continue
        if doer not in people:
            people.append(doer)
        if doer == item["speaker"]:
            evidence_for[doer] = item["text"]
        else:
            evidence_for.setdefault(doer, item["text"])

    if len(people) >= 2:
        reason = "Two claims, no proof, so nobody gets the points."
        for person in people:
            evidence = evidence_for.get(person, cluster[0]["text"])
            _append(buckets, person, _task(_label(evidence), 0.0, reason, evidence))
        return

    if len(people) != 1:
        return

    doer = people[0]
    evidence = evidence_for.get(doer, cluster[0]["text"])
    speaker = next((item["speaker"] for item in cluster if item["speaker"] != doer), doer)
    if named_explicit and speaker != doer:
        reason = (
            f"{_display_name(speaker)} said this was done. "
            f"Counted for {_display_name(doer)} because he was named and there is no file or pull request."
        )
        completion = _NAMED_COMPLETION
    elif named_explicit:
        reason = (
            f"This is {_display_name(doer)}'s note. "
            "There is no file or pull request, so it stays a small score."
        )
        completion = _NAMED_COMPLETION
    else:
        reason = (
            f"This is {_display_name(doer)}'s note. "
            "There is no file or pull request, so it stays a small score."
        )
        completion = _TALK_COMPLETION
    _append(buckets, doer, _task(_label(evidence), completion, reason, evidence))


def assign_credit(
    updates: Optional[List[Dict[str, Any]]],
    prior: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Split the day's notes into one task list per person.

    The caller adds those lists up. This function does not talk to Discord
    or to a model. `prior` is work already scored in the last 7 days.
    """
    roster_names = _roster_names()
    items = []
    for raw in updates or []:
        if not isinstance(raw, dict):
            continue
        for piece in _split_jobs(str(raw.get("content") or "")):
            parsed = _parse({**raw, "content": piece}, roster_names)
            if parsed is not None:
                items.append(parsed)
    if not items:
        return {}

    url_owners = _url_owners(items, roster_names)
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for cluster in _cluster(items):
        _decide_cluster(cluster, roster_names, url_owners, buckets)
    collapsed = _collapse_outreach(buckets)
    collapsed = _collapse_booked_calls(collapsed)
    collapsed = _drop_recent_repeats(collapsed, prior)
    return _cap_booked_calls(collapsed)


_CALL_MARKERS = (
    "booked",
    "had a call",
    "had the call",
    "had a demo",
    "demo call",
    "on the call",
    "meeting set",
)
_WIN_VERBS = ("booked", "paid", "merged", "deployed", "shipped", "closed")
_CUSTOMER_SKIP = _STOPWORDS | frozenset({
    "call", "calls", "demo", "meeting", "meet", "booked", "booking",
    "pilot", "follow", "followup", "whatsapp", "linkedin", "inmail",
    "connects", "request", "requests", "outreach", "cold", "email",
    "emails", "message", "messages", "note", "notes",
})


def _task_blob(task: Dict[str, Any]) -> str:
    urls = " ".join(task.get("seen_urls") or [])
    return f"{task.get('task', '')} {task.get('evidence_snippet', '')} {urls}"


def _is_call(task: Dict[str, Any]) -> bool:
    blob = _task_blob(task).lower()
    return any(marker in blob for marker in _CALL_MARKERS)


def _win_verb(text: str) -> Optional[str]:
    blob = (text or "").lower()
    for verb in _WIN_VERBS:
        if re.search(r"\b" + re.escape(verb) + r"\b", blob):
            return verb
    return None


def _customer_tokens(text: str, roster_names: Dict[str, List[str]]) -> set:
    # The link is not the customer. example.com must not glue Gyro and Acme.
    words = re.findall(r"[a-z0-9]{3,}", _URL.sub(" ", text or "").lower())
    alias_words = {alias for aliases in roster_names.values() for alias in aliases}
    return {
        word for word in words
        if word not in _CUSTOMER_SKIP and word not in alias_words
    }


def _collapse_outreach(buckets: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    """Five poke notes are one chore. A booked call is not a poke."""
    collapsed: Dict[str, List[Dict[str, Any]]] = {}
    for founder_key, tasks in buckets.items():
        outreach = [
            task for task in tasks
            if is_outreach(_task_blob(task)) and not _is_call(task)
        ]
        if len(outreach) <= 1:
            collapsed[founder_key] = tasks
            continue
        rest = [task for task in tasks if task not in outreach]
        best = max(outreach, key=lambda task: task.get("completion", 0))
        merged = dict(best)
        merged["task"] = "Outreach messages"
        merged["completion"] = max(task.get("completion", 0) for task in outreach)
        merged["complexity"] = 1
        merged["score_reason"] = (
            f"{len(outreach)} outreach notes count as one size-1 chore. "
            "The number of requests does not raise the score."
        )
        collapsed[founder_key] = rest + [merged]
    return collapsed


def _merge_call_group(group: List[Dict[str, Any]], unnamed: bool) -> Dict[str, Any]:
    best = max(group, key=lambda task: (task.get("completion", 0), task.get("complexity", 1)))
    merged = dict(best)
    if len(group) == 1:
        return merged
    if unnamed:
        merged["task"] = "Booked calls"
        extra = "No customer name, so these bookings count as one call."
    else:
        extra = "Same customer, so these notes are one call."
    merged["score_reason"] = f"{str(merged.get('score_reason') or '').rstrip()} {extra}".strip()
    merged["completion"] = max(task.get("completion", 0) for task in group)
    urls = []
    for task in group:
        for url in task.get("seen_urls") or []:
            if url not in urls:
                urls.append(url)
    merged["seen_urls"] = urls
    return merged


def _collapse_booked_calls(buckets: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    """Gyro and Acme are two calls. Gyro twice is one call."""
    roster_names = _roster_names()
    collapsed: Dict[str, List[Dict[str, Any]]] = {}
    for founder_key, tasks in buckets.items():
        calls = [task for task in tasks if _is_call(task)]
        rest = [task for task in tasks if task not in calls]
        groups: List[List[Any]] = []
        unnamed: List[Dict[str, Any]] = []
        for task in calls:
            tokens = _customer_tokens(_task_blob(task), roster_names)
            if not tokens:
                unnamed.append(task)
                continue
            placed = False
            for group in groups:
                if group[0] & tokens:
                    group[0] |= tokens
                    group[1].append(task)
                    placed = True
                    break
            if not placed:
                groups.append([tokens, [task]])
        merged = [_merge_call_group(group[1], unnamed=False) for group in groups]
        if unnamed:
            merged.append(_merge_call_group(unnamed, unnamed=True))
        collapsed[founder_key] = rest + merged
    return collapsed


def _drop_recent_repeats(
    buckets: Dict[str, List[Dict[str, Any]]],
    prior: Optional[List[Dict[str, Any]]],
) -> Dict[str, List[Dict[str, Any]]]:
    """A link, or the same person and customer and verb, does not score again for 7 days."""
    if not prior:
        return buckets
    roster_names = _roster_names()
    prior_urls = set()
    prior_wins = set()
    for item in prior:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "")
        founder = str(item.get("founder_key") or "")
        for url in _urls(text):
            prior_urls.add(url)
        verb = _win_verb(text)
        if verb and founder:
            for token in _customer_tokens(text, roster_names):
                prior_wins.add((founder, verb, token))

    for founder, tasks in buckets.items():
        for task in tasks:
            if float(task.get("completion") or 0) <= 0:
                continue
            blob = _task_blob(task)
            if set(_urls(blob)) & prior_urls:
                task["completion"] = 0.0
                task["complexity"] = 1
                task["score_reason"] = "Already counted in the last 7 days."
                continue
            verb = _win_verb(blob)
            tokens = _customer_tokens(blob, roster_names)
            if verb and any((founder, verb, token) in prior_wins for token in tokens):
                task["completion"] = 0.0
                task["complexity"] = 1
                task["score_reason"] = "Already counted in the last 7 days."
    return buckets


def _cap_booked_calls(buckets: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    """The 4th booked call in one day counts at a quarter, same as a 4th tiny chore."""
    for tasks in buckets.values():
        seen = 0
        for task in tasks:
            if not _is_call(task) or float(task.get("completion") or 0) <= 0:
                continue
            seen += 1
            if seen > 3:
                task["stack_discount"] = 0.25
                reason = str(task.get("score_reason") or "").rstrip()
                task["score_reason"] = f"{reason} The 4th booked call in one day counts at a quarter.".strip()
    return buckets


def prior_from_scores(rows: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Pull last week's scored lines. A zero line does not block a new one."""
    prior = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        breakdown = row.get("breakdown_json") or {}
        if isinstance(breakdown, str):
            try:
                breakdown = json.loads(breakdown)
            except json.JSONDecodeError:
                breakdown = {}
        for task in breakdown.get("task_breakdown") or []:
            if float(task.get("completion") or 0) <= 0:
                continue
            prior.append({
                "founder_key": row.get("founder_key") or "",
                "text": " ".join([
                    str(task.get("task") or ""),
                    str(task.get("evidence") or ""),
                    " ".join(task.get("seen_urls") or []),
                ]),
            })
    return prior
