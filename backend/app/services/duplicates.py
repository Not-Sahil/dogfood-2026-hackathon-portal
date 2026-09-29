import re
from collections import defaultdict
from urllib.parse import urlsplit, urlunsplit

def fingerprint_url(url: str | None) -> str:
    if not url:
        return ""
    raw = url.strip().lower()
    try:
        parts = urlsplit(raw)
        host = parts.netloc
        path = re.sub(r"/+", "/", parts.path).rstrip("/")
        return urlunsplit((parts.scheme or "https", host, path, "", ""))
    except Exception:
        return raw

def fingerprint_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())

def find_duplicate_groups(projects) -> list[dict]:
    by_repo = defaultdict(list)
    by_title = defaultdict(list)
    for project in projects:
        repo = fingerprint_url(project.repo_url)
        title = fingerprint_text(project.title)
        if repo:
            by_repo[repo].append(project.id)
        if title:
            by_title[title].append(project.id)
    groups = []
    for kind, mapping in (("repository", by_repo), ("title", by_title)):
        for key, ids in mapping.items():
            if len(ids) > 1:
                groups.append({"type": kind, "fingerprint": key, "project_ids": ids})
    return groups
