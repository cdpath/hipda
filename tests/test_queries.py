from hipda_cli.db import connect, upsert_posts, upsert_threads
from hipda_cli.models import Post, ThreadSummary
from hipda_cli.queries import list_threads, read_thread, search


def _thread(tid: str, last_at: str, *, is_pinned: bool = False, title: str | None = None) -> ThreadSummary:
    return ThreadSummary(
        tid=tid,
        title=title or f"thread-{tid}",
        url=f"https://www.4d4y.com/forum/viewthread.php?tid={tid}",
        author="user",
        created_at="2026-5-25",
        replies=1,
        views=10,
        last_author="user",
        last_at=last_at,
        is_pinned=is_pinned,
    )


def test_list_threads_returns_thread_summaries_ordered_by_last_at_desc(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        upsert_threads(
            conn,
            [
                _thread("1", "2026-5-25 10:00"),
                _thread("2", "2026-5-25 12:00"),
                _thread("3", "2026-5-25 11:00"),
            ],
            now="2026-05-26T00:00:00Z",
        )
        threads = list_threads(conn, limit=10, show_pinned=True)
    finally:
        conn.close()

    assert [thread.tid for thread in threads] == ["2", "3", "1"]
    assert isinstance(threads[0], ThreadSummary)
    assert threads[0].title == "thread-2"
    assert threads[0].last_at == "2026-5-25 12:00"


def test_list_threads_hides_pinned_threads_by_default(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        upsert_threads(
            conn,
            [
                _thread("1", "2099-1-1 00:00", is_pinned=True),
                _thread("2", "2026-5-25 12:00", is_pinned=False),
            ],
            now="2026-05-26T00:00:00Z",
        )
        default_view = list_threads(conn, limit=10)
        full_view = list_threads(conn, limit=10, show_pinned=True)
    finally:
        conn.close()

    assert [thread.tid for thread in default_view] == ["2"]
    assert [thread.tid for thread in full_view] == ["1", "2"]


def test_read_thread_returns_posts_in_position_order(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        upsert_posts(
            conn,
            tid="999",
            posts=[
                Post(pid="b", author="u2", published_at="13:10", content="second"),
                Post(pid="a", author="u1", published_at="13:08", content="first"),
            ],
            now="2026-05-26T00:00:00Z",
            start_position=1,
        )
        # Sanity: position is 1 for "b", 2 for "a" — but read_thread orders
        # by position, so the result reflects insertion order.
        posts = read_thread(conn, tid="999")
    finally:
        conn.close()

    assert [post.pid for post in posts] == ["b", "a"]
    assert [post.content for post in posts] == ["second", "first"]
    assert isinstance(posts[0], Post)


def test_read_thread_only_returns_posts_for_given_tid(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        upsert_posts(
            conn,
            tid="111",
            posts=[Post(pid="a", author="u", published_at="t", content="from-111")],
            now="2026-05-26T00:00:00Z",
        )
        upsert_posts(
            conn,
            tid="222",
            posts=[Post(pid="b", author="u", published_at="t", content="from-222")],
            now="2026-05-26T00:00:00Z",
        )
        posts = read_thread(conn, tid="111")
    finally:
        conn.close()

    assert [post.content for post in posts] == ["from-111"]


def test_search_finds_thread_by_chinese_title(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        upsert_threads(
            conn,
            [
                _thread("100", "2026-5-25 12:00", title="半导体依然疯了"),
                _thread("200", "2026-5-25 11:00", title="iPhone电池更换"),
            ],
            now="2026-05-26T00:00:00Z",
        )
        results = search(conn, "半导体", limit=20)
    finally:
        conn.close()

    assert len(results) == 1
    assert results[0].kind == "thread"
    assert results[0].tid == "100"
    assert results[0].title == "半导体依然疯了"
    assert "半导体" in results[0].snippet


def test_search_finds_posts_by_chinese_content(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        upsert_threads(
            conn,
            [_thread("100", "2026-5-25 12:00", title="random")],
            now="2026-05-26T00:00:00Z",
        )
        upsert_posts(
            conn,
            tid="100",
            posts=[
                Post(pid="111", author="yasool", published_at="13:08", content="老登股继续趴下"),
                Post(pid="112", author="lyztxcj", published_at="13:10", content="要信早信"),
            ],
            now="2026-05-26T00:00:00Z",
        )
        results = search(conn, "老登股", limit=20)
    finally:
        conn.close()

    matching_pids = [result.pid for result in results if result.kind == "post"]
    assert matching_pids == ["111"]
    post_result = next(result for result in results if result.kind == "post")
    assert post_result.tid == "100"
    assert post_result.author == "yasool"
    assert "老登股" in post_result.snippet


def test_search_scope_can_restrict_to_threads_or_posts(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        upsert_threads(
            conn,
            [_thread("100", "2026-5-25 12:00", title="半导体疯了")],
            now="2026-05-26T00:00:00Z",
        )
        upsert_posts(
            conn,
            tid="100",
            posts=[Post(pid="111", author="u", published_at="13:08", content="半导体太热了")],
            now="2026-05-26T00:00:00Z",
        )

        all_kinds = {result.kind for result in search(conn, "半导体", scope="all")}
        threads_only = {result.kind for result in search(conn, "半导体", scope="threads")}
        posts_only = {result.kind for result in search(conn, "半导体", scope="posts")}
    finally:
        conn.close()

    assert all_kinds == {"thread", "post"}
    assert threads_only == {"thread"}
    assert posts_only == {"post"}


def test_search_returns_no_results_for_blank_or_empty_query(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        upsert_threads(
            conn,
            [_thread("100", "2026-5-25 12:00", title="半导体疯了")],
            now="2026-05-26T00:00:00Z",
        )

        assert search(conn, "") == []
        assert search(conn, "   ") == []
    finally:
        conn.close()


def test_list_threads_respects_limit(tmp_path):
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        upsert_threads(
            conn,
            [
                _thread("1", "2026-5-25 10:00"),
                _thread("2", "2026-5-25 11:00"),
                _thread("3", "2026-5-25 12:00"),
            ],
            now="2026-05-26T00:00:00Z",
        )
        threads = list_threads(conn, limit=2, show_pinned=True)
    finally:
        conn.close()

    assert [thread.tid for thread in threads] == ["3", "2"]
