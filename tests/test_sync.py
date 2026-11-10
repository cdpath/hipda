from hipda_cli.db import connect
from hipda_cli.sync import sync_listing, sync_listing_page, sync_thread


LISTING_HTML = """
<html><body>
<tbody id="normalthread_3057651">
<tr>
  <th class="subject"><a href="viewthread.php?tid=3057651">hipda已迁移到新域名4d4y</a></th>
  <td class="author"><cite>4d4y</cite><em>2022-6-13</em></td>
  <td class="nums"><strong>0</strong>/<em>90106</em></td>
  <td class="lastpost"><cite>4d4y</cite><em>2022-6-13 22:57</em></td>
</tr>
</tbody>
<tbody>
<tr><td class="folder"></td><td>&nbsp;</td><th class="subject">版块主题</th><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
</tbody>
<tbody id="normalthread_3449572">
<tr>
  <th class="subject"><a href="viewthread.php?tid=3449572">半导体依然疯了.....</a></th>
  <td class="author"><cite>yasool</cite><em>2026-5-25</em></td>
  <td class="nums"><strong>15</strong>/<em>517</em></td>
  <td class="lastpost"><cite>yasool</cite><em>2026-5-25 13:58</em></td>
</tr>
</tbody>
</body></html>
"""


class FakeClient:
    def __init__(self, responses: dict[tuple[str, tuple[tuple[str, object], ...]], str]):
        self._responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get(self, path: str, params: dict[str, object] | None = None) -> str:
        self.calls.append((path, dict(params or {})))
        key = (path, tuple(sorted((params or {}).items())))
        return self._responses[key]


def test_sync_listing_page_fetches_parses_and_upserts(tmp_path):
    client = FakeClient(
        {("forumdisplay.php", (("fid", 2), ("page", 1))): LISTING_HTML}
    )
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        inserted, updated = sync_listing_page(
            client, conn, page=1, now="2026-05-26T00:00:00Z"
        )
        rows = conn.execute(
            "select tid, title, author, last_at, fetched_at "
            "from threads order by tid"
        ).fetchall()
    finally:
        conn.close()

    assert (inserted, updated) == (2, 0)
    assert rows == [
        ("3057651", "hipda已迁移到新域名4d4y", "4d4y", "2022-06-13 22:57", "2026-05-26T00:00:00Z"),
        ("3449572", "半导体依然疯了.....", "yasool", "2026-05-25 13:58", "2026-05-26T00:00:00Z"),
    ]
    assert client.calls == [("forumdisplay.php", {"fid": 2, "page": 1})]


def _page_html(tid: str, title: str, last_at: str) -> str:
    return f"""
    <html><body>
    <tbody id="normalthread_{tid}">
    <tr>
      <th class="subject"><a href="viewthread.php?tid={tid}">{title}</a></th>
      <td class="author"><cite>user</cite><em>2026-5-25</em></td>
      <td class="nums"><strong>1</strong>/<em>10</em></td>
      <td class="lastpost"><cite>user</cite><em>{last_at}</em></td>
    </tr>
    </tbody>
    </body></html>
    """


def test_sync_listing_walks_multiple_pages(tmp_path):
    client = FakeClient(
        {
            ("forumdisplay.php", (("fid", 2), ("page", 1))): _page_html(
                "100", "page1", "2026-5-25 12:00"
            ),
            ("forumdisplay.php", (("fid", 2), ("page", 1))): _page_html(
                "100", "page1", "2026-5-25 12:00"
            ),
            ("forumdisplay.php", (("fid", 2), ("page", 2))): _page_html(
                "200", "page2", "2026-5-25 11:00"
            ),
        }
    )
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        inserted, updated, pages_fetched = sync_listing(
            client, conn, max_pages=2, early_stop=False, now="2026-05-26T00:00:00Z"
        )
        tids = [row[0] for row in conn.execute("select tid from threads order by tid")]
    finally:
        conn.close()

    assert (inserted, updated, pages_fetched) == (2, 0, 2)
    assert tids == ["100", "200"]
    assert client.calls == [
        ("forumdisplay.php", {"fid": 2, "page": 1}),
        ("forumdisplay.php", {"fid": 2, "page": 2}),
    ]


def test_sync_listing_early_stops_when_page_brings_no_changes(tmp_path):
    page1 = _page_html("100", "page1", "2026-5-25 12:00")
    page2 = _page_html("200", "page2", "2026-5-25 11:00")
    cold_client = FakeClient(
        {
            ("forumdisplay.php", (("fid", 2), ("page", 1))): page1,
            ("forumdisplay.php", (("fid", 2), ("page", 2))): page2,
        }
    )
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        sync_listing(
            cold_client, conn, max_pages=2, early_stop=True, now="2026-05-26T00:00:00Z"
        )

        warm_client = FakeClient(
            {
                ("forumdisplay.php", (("fid", 2), ("page", 1))): page1,
                ("forumdisplay.php", (("fid", 2), ("page", 2))): page2,
            }
        )
        inserted, updated, pages_fetched = sync_listing(
            warm_client, conn, max_pages=2, early_stop=True, now="2026-05-26T01:00:00Z"
        )
    finally:
        conn.close()

    assert (inserted, updated, pages_fetched) == (0, 0, 1)
    assert warm_client.calls == [("forumdisplay.php", {"fid": 2, "page": 1})]


def _thread_page(*posts: tuple[str, str, str, str]) -> str:
    bodies = []
    for pid, author, published_at, content in posts:
        bodies.append(
            f"""
            <div id="post_{pid}">
              <table><tr>
                <td class="postauthor">
                  <div class="postinfo"><a href="space.php?uid=1">{author}</a></div>
                </td>
                <td class="postcontent">
                  <div class="postinfo">
                    <div class="authorinfo"><em id="authorposton{pid}">发表于 {published_at}</em></div>
                  </div>
                  <td class="t_msgfont" id="postmessage_{pid}">{content}</td>
                </td>
              </tr></table>
            </div>
            """
        )
    return f"<html><body>{''.join(bodies)}</body></html>"


THREAD_PAGE_1 = _thread_page(
    ("111", "yasool", "2026-5-25 13:08", "老登股继续趴下"),
    ("112", "lyztxcj", "2026-5-25 13:10", "要信早信"),
)


def test_sync_thread_fetches_single_page_and_upserts_posts(tmp_path):
    # Discuz serves the last existing page when you request a page beyond the
    # actual range, so sync_thread is expected to fetch page 2, see no new
    # posts, and stop.
    client = FakeClient(
        {
            ("viewthread.php", (("page", 1), ("tid", "999"))): THREAD_PAGE_1,
            ("viewthread.php", (("page", 2), ("tid", "999"))): THREAD_PAGE_1,
        }
    )
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        inserted, updated, pages_fetched = sync_thread(
            client, conn, tid="999", now="2026-05-26T00:00:00Z"
        )
        rows = conn.execute(
            "select pid, tid, position, author, content from posts order by position"
        ).fetchall()
    finally:
        conn.close()

    assert (inserted, updated, pages_fetched) == (2, 0, 2)
    assert rows == [
        ("111", "999", 1, "yasool", "老登股继续趴下"),
        ("112", "999", 2, "lyztxcj", "要信早信"),
    ]
    assert client.calls == [
        ("viewthread.php", {"tid": "999", "page": 1}),
        ("viewthread.php", {"tid": "999", "page": 2}),
    ]


def test_sync_thread_walks_multiple_real_pages_and_assigns_consecutive_positions(tmp_path):
    page1 = _thread_page(
        ("111", "yasool", "13:08", "post1"),
        ("112", "user2", "13:10", "post2"),
    )
    page2 = _thread_page(
        ("113", "user3", "13:11", "post3"),
        ("114", "user4", "13:12", "post4"),
    )
    page3_wraparound = page2
    client = FakeClient(
        {
            ("viewthread.php", (("page", 1), ("tid", "999"))): page1,
            ("viewthread.php", (("page", 2), ("tid", "999"))): page2,
            ("viewthread.php", (("page", 3), ("tid", "999"))): page3_wraparound,
        }
    )
    conn = connect(tmp_path / "hipda.sqlite")
    try:
        inserted, updated, pages_fetched = sync_thread(
            client, conn, tid="999", now="2026-05-26T00:00:00Z"
        )
        rows = conn.execute(
            "select pid, position, content from posts order by position"
        ).fetchall()
    finally:
        conn.close()

    assert (inserted, updated, pages_fetched) == (4, 0, 3)
    assert rows == [
        ("111", 1, "post1"),
        ("112", 2, "post2"),
        ("113", 3, "post3"),
        ("114", 4, "post4"),
    ]
