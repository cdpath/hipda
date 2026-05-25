from __future__ import annotations

import sqlite3

from .models import Post, SearchResult, ThreadSummary
from .text import segment_text


def list_threads(
    conn: sqlite3.Connection,
    *,
    limit: int = 30,
    show_pinned: bool = False,
) -> list[ThreadSummary]:
    where = "" if show_pinned else "where is_pinned = 0"
    rows = conn.execute(
        f"""
        select tid, title, url, author, created_at, replies, views,
               last_author, last_at, is_pinned
        from threads
        {where}
        order by last_at desc
        limit ?
        """,
        (limit,),
    ).fetchall()
    return [
        ThreadSummary(
            tid=row[0],
            title=row[1],
            url=row[2],
            author=row[3],
            created_at=row[4],
            replies=row[5],
            views=row[6],
            last_author=row[7],
            last_at=row[8],
            is_pinned=bool(row[9]),
        )
        for row in rows
    ]


def search(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 20,
    scope: str = "all",
) -> list[SearchResult]:
    segmented = segment_text(query).strip()
    if not segmented:
        return []

    results: list[SearchResult] = []
    if scope in ("all", "threads"):
        rows = conn.execute(
            """
            select threads_fts.tid,
                   threads.title,
                   threads.url,
                   threads.author,
                   threads.created_at,
                   snippet(threads_fts, 1, '[', ']', '...', 8)
            from threads_fts
            join threads on threads.tid = threads_fts.tid
            where threads_fts match ?
            order by rank
            limit ?
            """,
            (segmented, limit),
        ).fetchall()
        for tid, title, url, author, created_at, snippet in rows:
            results.append(
                SearchResult(
                    kind="thread",
                    tid=tid,
                    title=title,
                    snippet=snippet,
                    author=author,
                    published_at=created_at,
                    url=url,
                )
            )

    if scope in ("all", "posts"):
        rows = conn.execute(
            """
            select posts_fts.pid,
                   posts.tid,
                   posts.author,
                   posts.published_at,
                   posts.content,
                   threads.title,
                   threads.url,
                   snippet(posts_fts, 2, '[', ']', '...', 8)
            from posts_fts
            join posts on posts.pid = posts_fts.pid
            left join threads on threads.tid = posts.tid
            where posts_fts match ?
            order by rank
            limit ?
            """,
            (segmented, limit),
        ).fetchall()
        for pid, tid, author, published_at, _content, title, thread_url, snippet in rows:
            url = (thread_url or "") + (f"#post_{pid}" if thread_url else "")
            results.append(
                SearchResult(
                    kind="post",
                    tid=tid,
                    pid=pid,
                    title=title or "",
                    snippet=snippet,
                    author=author,
                    published_at=published_at,
                    url=url,
                )
            )

    return results[:limit]


def read_thread(conn: sqlite3.Connection, *, tid: str) -> list[Post]:
    rows = conn.execute(
        "select pid, author, published_at, content "
        "from posts where tid = ? order by position asc",
        (tid,),
    ).fetchall()
    return [
        Post(pid=row[0], author=row[1], published_at=row[2], content=row[3])
        for row in rows
    ]
