from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .models import Post, ThreadSummary
from .parser import normalize_date
from .text import segment_text


def default_db_path() -> Path:
    override = os.environ.get("HIPDA_DB")
    if override:
        return Path(override)
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / "hipda" / "hipda.sqlite"
    return Path.home() / ".local" / "share" / "hipda" / "hipda.sqlite"


SCHEMA_SQL = """
create table if not exists threads (
    tid text primary key,
    title text not null default '',
    author text not null default '',
    created_at text not null default '',
    last_at text not null default '',
    last_author text not null default '',
    replies integer,
    views integer,
    is_pinned integer not null default 0,
    url text not null default '',
    first_seen_at text not null,
    last_seen_at text not null,
    fetched_at text not null
);

create table if not exists posts (
    pid text primary key,
    tid text not null,
    position integer not null,
    author text not null default '',
    published_at text not null default '',
    content text not null default '',
    fetched_at text not null
);

create table if not exists sync_cache (
    cache_key text primary key,
    value_json text not null,
    updated_at text not null
);

create virtual table if not exists threads_fts using fts5(
    tid unindexed,
    title
);

create virtual table if not exists posts_fts using fts5(
    pid unindexed,
    author,
    content
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA_SQL)
    _migrate(conn)
    return conn


SCHEMA_VERSION = 1


def _migrate(conn: sqlite3.Connection) -> None:
    """One-shot migrations keyed off ``PRAGMA user_version``."""
    version = conn.execute("pragma user_version").fetchone()[0]
    if version >= SCHEMA_VERSION:
        return
    # v1: zero-pad historical Discuz dates ("2026-9-9" -> "2026-09-09") so
    # lexicographic ordering in queries.py sorts correctly.
    if version < 1:
        _migrate_pad_dates(conn)
    conn.execute(f"pragma user_version = {SCHEMA_VERSION}")
    conn.commit()


def _migrate_pad_dates(conn: sqlite3.Connection) -> None:
    for table, column in (("threads", "created_at"), ("threads", "last_at"), ("posts", "published_at")):
        rows = conn.execute(f"select rowid, {column} from {table} where {column} != ''").fetchall()
        for rowid, value in rows:
            padded = normalize_date(value)
            if padded != value:
                conn.execute(
                    f"update {table} set {column} = ? where rowid = ?",
                    (padded, rowid),
                )


def upsert_threads(
    conn: sqlite3.Connection,
    threads: Iterable[ThreadSummary],
    *,
    now: str,
) -> tuple[int, int]:
    inserted = 0
    updated = 0
    for thread in threads:
        existing = conn.execute(
            "select title, author, created_at, last_at, last_author, "
            "replies, views, is_pinned, url from threads where tid = ?",
            (thread.tid,),
        ).fetchone()
        incoming = (
            thread.title,
            thread.author,
            thread.created_at,
            thread.last_at,
            thread.last_author,
            thread.replies,
            thread.views,
            1 if thread.is_pinned else 0,
            thread.url,
        )
        is_insert = existing is None
        is_change = is_insert or existing != incoming

        if is_change:
            if not is_insert:
                conn.execute("delete from threads_fts where tid = ?", (thread.tid,))
            conn.execute(
                "insert into threads_fts (tid, title) values (?, ?)",
                (thread.tid, segment_text(thread.title)),
            )

        conn.execute(
            """
            insert into threads (
                tid, title, author, created_at, last_at, last_author,
                replies, views, is_pinned, url,
                first_seen_at, last_seen_at, fetched_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(tid) do update set
                title = excluded.title,
                author = excluded.author,
                created_at = excluded.created_at,
                last_at = excluded.last_at,
                last_author = excluded.last_author,
                replies = excluded.replies,
                views = excluded.views,
                is_pinned = excluded.is_pinned,
                url = excluded.url,
                last_seen_at = excluded.last_seen_at,
                fetched_at = excluded.fetched_at
            """,
            (
                thread.tid,
                thread.title,
                thread.author,
                thread.created_at,
                thread.last_at,
                thread.last_author,
                thread.replies,
                thread.views,
                1 if thread.is_pinned else 0,
                thread.url,
                now,
                now,
                now,
            ),
        )
        if is_insert:
            inserted += 1
        elif is_change:
            updated += 1
    conn.commit()
    return inserted, updated


def upsert_posts(
    conn: sqlite3.Connection,
    *,
    tid: str,
    posts: Iterable[Post],
    now: str,
    start_position: int = 1,
) -> tuple[int, int]:
    inserted = 0
    updated = 0
    for offset, post in enumerate(posts):
        position = start_position + offset
        existing = conn.execute(
            "select author, published_at, content from posts where pid = ?",
            (post.pid,),
        ).fetchone()
        incoming = (post.author, post.published_at, post.content)
        is_insert = existing is None
        is_change = is_insert or existing != incoming

        if is_change:
            if not is_insert:
                conn.execute("delete from posts_fts where pid = ?", (post.pid,))
            conn.execute(
                "insert into posts_fts (pid, author, content) values (?, ?, ?)",
                (post.pid, post.author, segment_text(post.content)),
            )

        conn.execute(
            """
            insert into posts (
                pid, tid, position, author, published_at, content, fetched_at
            ) values (?, ?, ?, ?, ?, ?, ?)
            on conflict(pid) do update set
                tid = excluded.tid,
                position = excluded.position,
                author = excluded.author,
                published_at = excluded.published_at,
                content = excluded.content,
                fetched_at = excluded.fetched_at
            """,
            (
                post.pid,
                tid,
                position,
                post.author,
                post.published_at,
                post.content,
                now,
            ),
        )
        if is_insert:
            inserted += 1
        elif is_change:
            updated += 1
    conn.commit()
    return inserted, updated
