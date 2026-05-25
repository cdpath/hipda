from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThreadSummary:
    tid: str
    title: str
    url: str
    author: str = ""
    created_at: str = ""
    replies: int | None = None
    views: int | None = None
    last_author: str = ""
    last_at: str = ""
    is_pinned: bool = False


@dataclass(frozen=True)
class Post:
    author: str
    published_at: str
    content: str
