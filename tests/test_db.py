from pathlib import Path

from hipda_cli.db import connect, default_db_path, upsert_posts, upsert_threads
from hipda_cli.models import Post, ThreadSummary


def _user_tables(conn) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "select name from sqlite_master "
            "where type in ('table', 'view') and name not like 'sqlite_%'"
        )
    }


def _columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"pragma table_info({table})")}


def test_connect_creates_threads_table(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        tables = _user_tables(conn)
    finally:
        conn.close()

    assert "threads" in tables


def test_threads_table_holds_full_listing_row(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        columns = _columns(conn, "threads")
    finally:
        conn.close()

    assert {
        "tid",
        "title",
        "author",
        "created_at",
        "last_at",
        "last_author",
        "replies",
        "views",
        "is_pinned",
        "url",
        "first_seen_at",
        "last_seen_at",
        "fetched_at",
    } <= columns


def test_posts_table_holds_thread_replies(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        columns = _columns(conn, "posts")
    finally:
        conn.close()

    assert {
        "pid",
        "tid",
        "position",
        "author",
        "published_at",
        "content",
        "fetched_at",
    } <= columns


def test_sync_cache_table_records_per_key_freshness(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        columns = _columns(conn, "sync_cache")
    finally:
        conn.close()

    assert {"cache_key", "value_json", "updated_at"} <= columns


def test_threads_fts_indexes_titles_for_search(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        conn.execute(
            "insert into threads_fts (tid, title) values (?, ?)",
            ("3449572", "半导体 依然 疯了"),
        )
        rows = conn.execute(
            "select tid from threads_fts where threads_fts match ?",
            ("半导体",),
        ).fetchall()
    finally:
        conn.close()

    assert rows == [("3449572",)]


def _thread(tid: str = "3449572", **overrides) -> ThreadSummary:
    defaults = dict(
        tid=tid,
        title="半导体依然疯了.....",
        url=f"https://www.4d4y.com/forum/viewthread.php?tid={tid}",
        author="yasool",
        created_at="2026-5-25",
        replies=15,
        views=517,
        last_author="yasool",
        last_at="2026-5-25 13:58",
        is_pinned=False,
    )
    defaults.update(overrides)
    return ThreadSummary(**defaults)


def test_upsert_threads_inserts_new_rows_and_reports_inserted_count(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        inserted, updated = upsert_threads(conn, [_thread()], now="2026-05-26T00:00:00Z")
        row = conn.execute(
            "select tid, title, author, last_at, last_author, replies, views, "
            "is_pinned, url, first_seen_at, last_seen_at, fetched_at from threads"
        ).fetchone()
    finally:
        conn.close()

    assert (inserted, updated) == (1, 0)
    assert row == (
        "3449572",
        "半导体依然疯了.....",
        "yasool",
        "2026-5-25 13:58",
        "yasool",
        15,
        517,
        0,
        "https://www.4d4y.com/forum/viewthread.php?tid=3449572",
        "2026-05-26T00:00:00Z",
        "2026-05-26T00:00:00Z",
        "2026-05-26T00:00:00Z",
    )


def test_upsert_threads_updates_existing_row_and_preserves_first_seen_at(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        upsert_threads(conn, [_thread(replies=15, last_at="2026-5-25 13:58")], now="2026-05-25T05:58:00Z")
        inserted, updated = upsert_threads(
            conn,
            [_thread(replies=42, last_at="2026-5-25 18:30", last_author="zhangsan")],
            now="2026-05-25T10:30:00Z",
        )
        row = conn.execute(
            "select replies, last_at, last_author, first_seen_at, last_seen_at, fetched_at from threads"
        ).fetchone()
    finally:
        conn.close()

    assert (inserted, updated) == (0, 1)
    assert row == (
        42,
        "2026-5-25 18:30",
        "zhangsan",
        "2026-05-25T05:58:00Z",
        "2026-05-25T10:30:00Z",
        "2026-05-25T10:30:00Z",
    )


def test_upsert_threads_keeps_threads_fts_in_sync(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        upsert_threads(
            conn,
            [_thread(tid="1", title="半导体 依然 疯了")],
            now="2026-05-25T05:58:00Z",
        )
        rows_before = conn.execute(
            "select tid from threads_fts where threads_fts match ?", ("半导体",)
        ).fetchall()

        upsert_threads(
            conn,
            [_thread(tid="1", title="老登股 反弹 了")],
            now="2026-05-25T10:30:00Z",
        )
        rows_old = conn.execute(
            "select tid from threads_fts where threads_fts match ?", ("半导体",)
        ).fetchall()
        rows_new = conn.execute(
            "select tid from threads_fts where threads_fts match ?", ("老登股",)
        ).fetchall()
    finally:
        conn.close()

    assert rows_before == [("1",)]
    assert rows_old == []
    assert rows_new == [("1",)]


def test_default_db_path_prefers_hipda_db_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("HIPDA_DB", str(tmp_path / "custom.sqlite"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "should-not-use"))

    assert default_db_path() == tmp_path / "custom.sqlite"


def test_default_db_path_falls_back_to_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.delenv("HIPDA_DB", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    assert default_db_path() == tmp_path / "hipda" / "hipda.sqlite"


def test_default_db_path_falls_back_to_local_share(monkeypatch):
    monkeypatch.delenv("HIPDA_DB", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    assert default_db_path() == Path.home() / ".local" / "share" / "hipda" / "hipda.sqlite"


def test_upsert_posts_inserts_each_post_with_position(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    posts = [
        Post(pid="74283570", author="yasool", published_at="2026-5-25 13:08", content="老登股继续趴下"),
        Post(pid="74283580", author="lyztxcj", published_at="2026-5-25 13:10", content="要信早信"),
    ]
    try:
        inserted, updated = upsert_posts(conn, tid="3449572", posts=posts, now="2026-05-26T00:00:00Z")
        rows = conn.execute(
            "select pid, tid, position, author, published_at, content, fetched_at from posts order by position"
        ).fetchall()
    finally:
        conn.close()

    assert (inserted, updated) == (2, 0)
    assert rows == [
        ("74283570", "3449572", 1, "yasool", "2026-5-25 13:08", "老登股继续趴下", "2026-05-26T00:00:00Z"),
        ("74283580", "3449572", 2, "lyztxcj", "2026-5-25 13:10", "要信早信", "2026-05-26T00:00:00Z"),
    ]


def test_upsert_posts_updates_existing_row_and_keeps_posts_fts_in_sync(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        upsert_posts(
            conn,
            tid="3449572",
            posts=[Post(pid="74283570", author="yasool", published_at="13:08", content="老登 股 继续 趴下")],
            now="2026-05-26T00:00:00Z",
        )
        before_old = conn.execute(
            "select pid from posts_fts where posts_fts match ?", ("老登",)
        ).fetchall()

        inserted, updated = upsert_posts(
            conn,
            tid="3449572",
            posts=[Post(pid="74283570", author="yasool", published_at="13:08", content="老登 股 反弹 了")],
            now="2026-05-26T01:00:00Z",
        )
        after_old = conn.execute(
            "select pid from posts_fts where posts_fts match ?", ("继续",)
        ).fetchall()
        after_new = conn.execute(
            "select pid from posts_fts where posts_fts match ?", ("反弹",)
        ).fetchall()
        row = conn.execute(
            "select content, fetched_at from posts where pid = '74283570'"
        ).fetchone()
    finally:
        conn.close()

    assert before_old == [("74283570",)]
    assert (inserted, updated) == (0, 1)
    assert after_old == []
    assert after_new == [("74283570",)]
    assert row == ("老登 股 反弹 了", "2026-05-26T01:00:00Z")


def test_connect_is_idempotent_and_preserves_rows(tmp_path):
    db_path = tmp_path / "hipda.sqlite"

    first = connect(db_path)
    first.execute(
        "insert into threads (tid, first_seen_at, last_seen_at, fetched_at) "
        "values ('1', 'now', 'now', 'now')"
    )
    first.commit()
    first.close()

    second = connect(db_path)
    try:
        row = second.execute("select tid from threads where tid = '1'").fetchone()
    finally:
        second.close()

    assert row == ("1",)


def test_posts_fts_indexes_content_for_search(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        conn.execute(
            "insert into posts_fts (pid, author, content) values (?, ?, ?)",
            ("74283570", "yasool", "老登 股 继续 趴下"),
        )
        rows = conn.execute(
            "select pid from posts_fts where posts_fts match ?",
            ("老登",),
        ).fetchall()
    finally:
        conn.close()

    assert rows == [("74283570",)]
