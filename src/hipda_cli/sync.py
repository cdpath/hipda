from __future__ import annotations

import sqlite3
from typing import Protocol

from .client import BASE_URL
from .db import upsert_posts, upsert_threads
from .parser import parse_forum_listing, parse_thread


class _Fetcher(Protocol):
    def get(self, path: str, params: dict[str, object] | None = None) -> str: ...


def sync_listing_page(
    client: _Fetcher,
    conn: sqlite3.Connection,
    *,
    page: int = 1,
    fid: int = 2,
    now: str,
) -> tuple[int, int]:
    html = client.get("forumdisplay.php", {"fid": fid, "page": page})
    threads = parse_forum_listing(html, base_url=BASE_URL)
    return upsert_threads(conn, threads, now=now)


def sync_thread(
    client: _Fetcher,
    conn: sqlite3.Connection,
    *,
    tid: str,
    max_pages: int = 50,
    now: str,
) -> tuple[int, int, int]:
    total_inserted = 0
    total_updated = 0
    pages_fetched = 0
    position = 1
    for page in range(1, max_pages + 1):
        html = client.get("viewthread.php", {"tid": tid, "page": page})
        posts = parse_thread(html)
        pages_fetched += 1
        if not posts:
            break

        # Discuz wraps to the last existing page when the requested page is
        # out of range. If every pid on this page is already in the DB AND we
        # are past page 1, stop without re-upserting so we don't churn
        # positions.
        if page > 1:
            placeholders = ",".join("?" * len(posts))
            existing_pids = {
                row[0]
                for row in conn.execute(
                    f"select pid from posts where pid in ({placeholders})",
                    [post.pid for post in posts],
                )
            }
            if all(post.pid in existing_pids for post in posts):
                break

        inserted, updated = upsert_posts(
            conn, tid=tid, posts=posts, now=now, start_position=position
        )
        position += len(posts)
        total_inserted += inserted
        total_updated += updated
        if inserted == 0 and updated == 0:
            break
    return total_inserted, total_updated, pages_fetched


def sync_listing(
    client: _Fetcher,
    conn: sqlite3.Connection,
    *,
    fid: int = 2,
    max_pages: int = 5,
    early_stop: bool = True,
    now: str,
) -> tuple[int, int, int]:
    total_inserted = 0
    total_updated = 0
    pages_fetched = 0
    for page in range(1, max_pages + 1):
        inserted, updated = sync_listing_page(
            client, conn, page=page, fid=fid, now=now
        )
        pages_fetched += 1
        total_inserted += inserted
        total_updated += updated
        if early_stop and inserted == 0 and updated == 0:
            break
    return total_inserted, total_updated, pages_fetched
