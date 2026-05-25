from hipda_cli.auth import default_cookie_path, default_user_agent_path, load_cookie, load_user_agent, save_cookie, save_user_agent
from hipda_cli.cli import build_parser, load_discovery_page, main, run


def test_build_parser_accepts_discovery_list_options():
    parser = build_parser()

    args = parser.parse_args(["--ca-file", "/tmp/root.pem", "--verify-tls", "discovery", "list", "--page", "2", "--limit", "5"])

    assert args.command == "discovery"
    assert args.discovery_command == "list"
    assert args.ca_file == "/tmp/root.pem"
    assert args.verify_tls is True
    assert args.page == 2
    assert args.limit == 5


def test_help_hides_legacy_commands(capsys):
    parser = build_parser()

    parser.print_help()

    out = capsys.readouterr().out
    assert "{login,list,read,sync,search}" in out
    assert "auth" not in out
    assert "discovery" not in out


def test_main_without_subcommand_prints_help(capsys):
    assert main([]) == 0

    out = capsys.readouterr().out
    assert "usage: hipda" in out
    assert "{login,list,read,sync,search}" in out


def test_main_without_subcommand_from_sys_argv_prints_help(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["hipda"])

    assert main() == 0

    out = capsys.readouterr().out
    assert "usage: hipda" in out
    assert "{login,list,read,sync,search}" in out


def test_build_parser_accepts_top_level_list_options():
    parser = build_parser()

    args = parser.parse_args(["list", "--page", "2", "--limit", "5", "--show-pinned"])

    assert args.command == "list"
    assert args.page == 2
    assert args.limit == 5
    assert args.show_pinned is True


def test_build_parser_accepts_discovery_read_tid():
    parser = build_parser()

    args = parser.parse_args(["discovery", "read", "3446553", "--page", "3"])

    assert args.discovery_command == "read"
    assert args.thread == "3446553"
    assert args.page == 3


def test_build_parser_accepts_top_level_read_tid():
    parser = build_parser()

    args = parser.parse_args(["read", "3446553", "--page", "3"])

    assert args.command == "read"
    assert args.thread == "3446553"
    assert args.page == 3


def test_build_parser_accepts_auth_save_cookie():
    parser = build_parser()

    args = parser.parse_args(["auth", "save-cookie", "foo=bar; baz=qux"])

    assert args.command == "auth"
    assert args.auth_command == "save-cookie"
    assert args.cookie == "foo=bar; baz=qux"


def test_build_parser_accepts_auth_save_user_agent():
    parser = build_parser()

    args = parser.parse_args(["auth", "save-user-agent", "Mozilla/5.0 Chrome/147.0.0.0"])

    assert args.command == "auth"
    assert args.auth_command == "save-user-agent"
    assert args.user_agent == "Mozilla/5.0 Chrome/147.0.0.0"


def test_build_parser_accepts_login():
    parser = build_parser()

    args = parser.parse_args(["login"])

    assert args.command == "login"


def test_build_parser_accepts_sync_options():
    parser = build_parser()

    args = parser.parse_args(["sync", "--max-pages", "3", "--no-early-stop"])

    assert args.command == "sync"
    assert args.max_pages == 3
    assert args.early_stop is False


def test_build_parser_sync_has_default_max_pages_and_early_stop_enabled():
    parser = build_parser()

    args = parser.parse_args(["sync"])

    assert args.command == "sync"
    assert args.max_pages == 5
    assert args.early_stop is True


def test_build_parser_accepts_search_with_query_and_options():
    parser = build_parser()

    args = parser.parse_args(["search", "半导体", "--limit", "5", "--scope", "posts", "--json"])

    assert args.command == "search"
    assert args.query == "半导体"
    assert args.limit == 5
    assert args.scope == "posts"
    assert args.json is True


def test_build_parser_search_defaults_to_all_scope_human_output_limit_20():
    parser = build_parser()

    args = parser.parse_args(["search", "半导体"])

    assert args.limit == 20
    assert args.scope == "all"
    assert args.json is False


def test_run_search_prints_matches_from_local_store(monkeypatch, tmp_path, capsys):
    db_path = tmp_path / "hipda.sqlite"
    monkeypatch.setenv("HIPDA_DB", str(db_path))

    from hipda_cli.db import connect, upsert_posts, upsert_threads
    from hipda_cli.models import Post, ThreadSummary

    conn = connect(db_path)
    upsert_threads(
        conn,
        [
            ThreadSummary(
                tid="100",
                title="半导体依然疯了",
                url="https://www.4d4y.com/forum/viewthread.php?tid=100",
                author="yasool",
                created_at="2026-5-25",
                replies=1,
                views=10,
                last_author="yasool",
                last_at="2026-5-25 13:58",
                is_pinned=False,
            )
        ],
        now="2026-05-26T00:00:00Z",
    )
    upsert_posts(
        conn,
        tid="100",
        posts=[Post(pid="111", author="yasool", published_at="13:08", content="半导体太热了")],
        now="2026-05-26T00:00:00Z",
    )
    conn.close()

    parser = build_parser()
    args = parser.parse_args(["search", "半导体", "--limit", "5"])

    assert run(args) == 0
    out = capsys.readouterr().out
    assert "100" in out
    assert "半导体" in out


def test_run_search_emits_json_when_requested(monkeypatch, tmp_path, capsys):
    import json

    db_path = tmp_path / "hipda.sqlite"
    monkeypatch.setenv("HIPDA_DB", str(db_path))

    from hipda_cli.db import connect, upsert_threads
    from hipda_cli.models import ThreadSummary

    conn = connect(db_path)
    upsert_threads(
        conn,
        [
            ThreadSummary(
                tid="100",
                title="半导体依然疯了",
                url="https://www.4d4y.com/forum/viewthread.php?tid=100",
                author="yasool",
                created_at="2026-5-25",
                replies=1,
                views=10,
                last_author="yasool",
                last_at="2026-5-25 13:58",
                is_pinned=False,
            )
        ],
        now="2026-05-26T00:00:00Z",
    )
    conn.close()

    parser = build_parser()
    args = parser.parse_args(["search", "半导体", "--json"])

    assert run(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert any(item["tid"] == "100" and item["kind"] == "thread" for item in payload)


def test_run_list_reads_from_local_db_without_network_when_warm(monkeypatch, tmp_path, capsys):
    db_path = tmp_path / "hipda.sqlite"
    monkeypatch.setenv("HIPDA_DB", str(db_path))

    from hipda_cli.db import connect, upsert_threads
    from hipda_cli.models import ThreadSummary

    conn = connect(db_path)
    upsert_threads(
        conn,
        [
            ThreadSummary(
                tid="100",
                title="local-only thread",
                url="https://www.4d4y.com/forum/viewthread.php?tid=100",
                author="yasool",
                created_at="2026-5-25",
                replies=1,
                views=10,
                last_author="yasool",
                last_at="2026-5-25 13:58",
                is_pinned=False,
            )
        ],
        now="2026-05-26T00:00:00Z",
    )
    conn.close()

    network_calls: list[object] = []

    def fail_if_called(**_kwargs):
        network_calls.append("touched")
        raise AssertionError("list must not hit the network when DB is warm")

    monkeypatch.setattr("hipda_cli.cli.load_discovery_page", fail_if_called)
    monkeypatch.setattr("hipda_cli.cli.sync_listing", fail_if_called)

    parser = build_parser()
    args = parser.parse_args(["list", "--limit", "5"])

    assert run(args) == 0
    assert network_calls == []
    out = capsys.readouterr().out
    assert "100" in out
    assert "local-only thread" in out


def test_list_offline_returns_error_when_db_empty(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HIPDA_DB", str(tmp_path / "hipda.sqlite"))

    def fail_if_called(**_kwargs):
        raise AssertionError("--offline must not hit the network")

    monkeypatch.setattr("hipda_cli.cli.sync_listing", fail_if_called)

    parser = build_parser()
    args = parser.parse_args(["list", "--offline"])

    assert run(args) == 4
    assert "local store is empty" in capsys.readouterr().err


def test_list_refresh_always_syncs_before_reading(monkeypatch, tmp_path, capsys):
    db_path = tmp_path / "hipda.sqlite"
    monkeypatch.setenv("HIPDA_DB", str(db_path))
    _seed_listing_db(db_path, pinned=False)

    sync_calls: list[object] = []

    def fake_sync_listing(client, conn, **kwargs):
        sync_calls.append(kwargs)
        return (0, 0, 1)

    monkeypatch.setattr("hipda_cli.cli.HipdaClient.from_env", lambda **_: object())
    monkeypatch.setattr("hipda_cli.cli.sync_listing", fake_sync_listing)

    parser = build_parser()
    args = parser.parse_args(["list", "--refresh"])

    assert run(args) == 0
    assert len(sync_calls) == 1


def test_build_parser_accepts_read_offline_and_refresh():
    parser = build_parser()

    args = parser.parse_args(["read", "3449572", "--offline"])
    assert args.offline is True
    assert args.refresh is False

    args = parser.parse_args(["read", "3449572", "--refresh"])
    assert args.refresh is True
    assert args.offline is False


def test_read_reads_from_local_db_when_warm(monkeypatch, tmp_path, capsys):
    db_path = tmp_path / "hipda.sqlite"
    monkeypatch.setenv("HIPDA_DB", str(db_path))

    from hipda_cli.db import connect, upsert_posts
    from hipda_cli.models import Post

    conn = connect(db_path)
    upsert_posts(
        conn,
        tid="999",
        posts=[
            Post(pid="111", author="yasool", published_at="13:08", content="第一帖"),
            Post(pid="112", author="lyztxcj", published_at="13:10", content="跟帖"),
        ],
        now="2026-05-26T00:00:00Z",
    )
    conn.close()

    def fail_if_called(**_kwargs):
        raise AssertionError("read should not touch the network when DB is warm")

    monkeypatch.setattr("hipda_cli.cli.sync_thread", fail_if_called)
    monkeypatch.setattr("hipda_cli.cli.HipdaClient.from_env", lambda **_: object())

    parser = build_parser()
    args = parser.parse_args(["read", "999"])

    assert run(args) == 0
    out = capsys.readouterr().out
    assert "第一帖" in out
    assert "跟帖" in out
    assert "yasool" in out


def test_read_cold_db_auto_syncs_the_thread(monkeypatch, tmp_path, capsys):
    db_path = tmp_path / "hipda.sqlite"
    monkeypatch.setenv("HIPDA_DB", str(db_path))

    from hipda_cli.db import upsert_posts
    from hipda_cli.models import Post

    captured: dict[str, object] = {}

    def fake_sync_thread(client, conn, *, tid, now, **_kwargs):
        captured["tid"] = tid
        captured["now"] = now
        upsert_posts(
            conn,
            tid=tid,
            posts=[Post(pid="111", author="yasool", published_at="13:08", content="synced body")],
            now=now,
        )
        return (1, 0, 1)

    monkeypatch.setattr("hipda_cli.cli.HipdaClient.from_env", lambda **_: object())
    monkeypatch.setattr("hipda_cli.cli.sync_thread", fake_sync_thread)

    parser = build_parser()
    args = parser.parse_args(["read", "999"])

    assert run(args) == 0
    out = capsys.readouterr().out
    assert "synced body" in out
    assert captured["tid"] == "999"


def test_read_offline_returns_error_when_thread_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HIPDA_DB", str(tmp_path / "hipda.sqlite"))

    def fail_if_called(**_kwargs):
        raise AssertionError("--offline must not hit the network")

    monkeypatch.setattr("hipda_cli.cli.sync_thread", fail_if_called)
    monkeypatch.setattr("hipda_cli.cli.HipdaClient.from_env", lambda **_: object())

    parser = build_parser()
    args = parser.parse_args(["read", "999", "--offline"])

    assert run(args) == 4
    assert "no local posts" in capsys.readouterr().err


def test_list_cold_db_auto_syncs(monkeypatch, tmp_path):
    db_path = tmp_path / "hipda.sqlite"
    monkeypatch.setenv("HIPDA_DB", str(db_path))

    sync_calls: list[object] = []

    def fake_sync_listing(client, conn, **kwargs):
        sync_calls.append(kwargs)
        return (0, 0, 1)

    monkeypatch.setattr("hipda_cli.cli.HipdaClient.from_env", lambda **_: object())
    monkeypatch.setattr("hipda_cli.cli.sync_listing", fake_sync_listing)

    parser = build_parser()
    args = parser.parse_args(["list"])

    assert run(args) == 0
    assert len(sync_calls) == 1


def test_list_json_emits_array_of_thread_objects(monkeypatch, tmp_path, capsys):
    import json

    db_path = tmp_path / "hipda.sqlite"
    monkeypatch.setenv("HIPDA_DB", str(db_path))
    _seed_listing_db(db_path, pinned=False)

    parser = build_parser()
    args = parser.parse_args(["list", "--json"])

    assert run(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert payload[0]["tid"] == "2"
    assert payload[0]["title"] == "Normal"
    assert payload[0]["is_pinned"] is False


def test_read_json_emits_array_of_post_objects(monkeypatch, tmp_path, capsys):
    import json

    db_path = tmp_path / "hipda.sqlite"
    monkeypatch.setenv("HIPDA_DB", str(db_path))

    from hipda_cli.db import connect, upsert_posts
    from hipda_cli.models import Post

    conn = connect(db_path)
    upsert_posts(
        conn,
        tid="999",
        posts=[
            Post(pid="111", author="yasool", published_at="13:08", content="第一帖"),
            Post(pid="112", author="lyztxcj", published_at="13:10", content="跟帖"),
        ],
        now="2026-05-26T00:00:00Z",
    )
    conn.close()

    monkeypatch.setattr("hipda_cli.cli.HipdaClient.from_env", lambda **_: object())

    parser = build_parser()
    args = parser.parse_args(["read", "999", "--json", "--offline"])

    assert run(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [item["pid"] for item in payload] == ["111", "112"]
    assert payload[0]["author"] == "yasool"
    assert payload[0]["content"] == "第一帖"


def test_run_sync_invokes_sync_listing_and_prints_stats(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HIPDA_DB", str(tmp_path / "hipda.sqlite"))
    captured: dict[str, object] = {}

    class StubClient:
        def get(self, path, params=None):
            return ""

    def fake_sync_listing(client, conn, *, fid, max_pages, early_stop, now):
        captured["client"] = client
        captured["fid"] = fid
        captured["max_pages"] = max_pages
        captured["early_stop"] = early_stop
        captured["now"] = now
        return (3, 2, 4)

    monkeypatch.setattr("hipda_cli.cli.HipdaClient.from_env", lambda **_: StubClient())
    monkeypatch.setattr("hipda_cli.cli.sync_listing", fake_sync_listing)

    parser = build_parser()
    args = parser.parse_args(["sync", "--max-pages", "4", "--no-early-stop"])

    assert run(args) == 0
    assert captured["max_pages"] == 4
    assert captured["early_stop"] is False
    assert captured["fid"] == 2
    assert isinstance(captured["client"], StubClient)

    out = capsys.readouterr().out
    assert "synced" in out
    assert "3 new" in out
    assert "2 updated" in out
    assert "4 pages" in out


def test_run_login_opens_chrome_then_imports(monkeypatch, capsys):
    events = []
    parser = build_parser()
    args = parser.parse_args(["login"])
    monkeypatch.setattr("hipda_cli.cli.open_login_page", lambda: events.append("open"))
    monkeypatch.setattr("hipda_cli.cli.wait_for_login_confirmation", lambda: events.append("wait"))
    monkeypatch.setattr("hipda_cli.cli.import_browser_auth", lambda: events.append("import") or ("cookie", "ua"))

    from hipda_cli.cli import run

    assert run(args) == 0
    assert events == ["open", "wait", "import"]
    assert "Imported 4D4Y login from Chrome." in capsys.readouterr().out


def test_save_cookie_strips_cookie_prefix_and_uses_private_permissions(tmp_path):
    cookie_path = tmp_path / "cookie"

    save_cookie("Cookie: foo=bar; baz=qux\n", cookie_path)

    assert load_cookie(cookie_path) == "foo=bar; baz=qux"
    assert oct(cookie_path.stat().st_mode & 0o777) == "0o600"


def test_default_cookie_path_uses_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert default_cookie_path() == tmp_path / "hipda" / "cookie"


def test_save_user_agent_round_trips(tmp_path):
    path = tmp_path / "user-agent"

    save_user_agent("Mozilla/5.0 Chrome/147.0.0.0\n", path)

    assert load_user_agent(path) == "Mozilla/5.0 Chrome/147.0.0.0"
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_default_user_agent_path_uses_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert default_user_agent_path() == tmp_path / "hipda" / "user-agent"


def test_load_discovery_page_imports_browser_auth_when_saved_auth_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    calls = []

    class FakeClient:
        def __init__(self, cookie=""):
            self.cookie = cookie

        def get(self, path, params):
            calls.append((self.cookie, path, params))
            return "<html><a href='viewthread.php?tid=1'>ok</a></html>" if self.cookie else "您还未登录"

    monkeypatch.setattr("hipda_cli.cli.HipdaClient.from_env", lambda **kwargs: FakeClient(kwargs.get("cookie") or load_cookie()))
    monkeypatch.setattr("hipda_cli.cli.import_browser_auth", lambda: ("cdb_auth=abc", "Mozilla/5.0 Chrome/147.0.0.0"))

    html, client = load_discovery_page(
        page=1,
        path="forumdisplay.php",
        params={"fid": 2, "page": 1},
        cookie=None,
        user_agent=None,
        ca_file=None,
        insecure_tls=False,
    )

    assert "viewthread.php" in html
    assert client.cookie == "cdb_auth=abc"
    assert calls == [
        ("", "forumdisplay.php", {"fid": 2, "page": 1}),
        ("cdb_auth=abc", "forumdisplay.php", {"fid": 2, "page": 1}),
    ]


def _seed_listing_db(db_path, *, pinned: bool = True, normal: bool = True):
    from hipda_cli.db import connect, upsert_threads
    from hipda_cli.models import ThreadSummary

    threads = []
    if pinned:
        threads.append(
            ThreadSummary(
                tid="1",
                title="Pinned",
                url="https://www.4d4y.com/forum/viewthread.php?tid=1",
                author="admin",
                created_at="2022-1-1",
                replies=0,
                views=10,
                last_author="admin",
                last_at="2099-1-1 00:00",
                is_pinned=True,
            )
        )
    if normal:
        threads.append(
            ThreadSummary(
                tid="2",
                title="Normal",
                url="https://www.4d4y.com/forum/viewthread.php?tid=2",
                author="user",
                created_at="2026-5-25",
                replies=1,
                views=20,
                last_author="user",
                last_at="2026-5-25 12:00",
                is_pinned=False,
            )
        )
    conn = connect(db_path)
    upsert_threads(conn, threads, now="2026-05-26T00:00:00Z")
    conn.close()


def test_list_hides_pinned_threads_by_default(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HIPDA_DB", str(tmp_path / "hipda.sqlite"))
    _seed_listing_db(tmp_path / "hipda.sqlite")

    parser = build_parser()
    args = parser.parse_args(["list"])

    assert run(args) == 0
    out = capsys.readouterr().out
    assert "Normal" in out
    assert "Pinned" not in out


def test_list_can_show_pinned_threads(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HIPDA_DB", str(tmp_path / "hipda.sqlite"))
    _seed_listing_db(tmp_path / "hipda.sqlite", normal=False)

    parser = build_parser()
    args = parser.parse_args(["list", "--show-pinned"])

    assert run(args) == 0
    assert "Pinned" in capsys.readouterr().out
