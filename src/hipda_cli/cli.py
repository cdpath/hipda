from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone

from .auth import import_browser_auth, open_login_page, save_cookie, save_user_agent
from .client import BASE_URL, HipdaClient, HipdaClientError
from .db import connect, default_db_path
from .parser import is_login_required_page
from .queries import list_threads as list_threads_local
from .queries import read_thread as read_thread_local
from .queries import search as search_local
from .sync import sync_listing, sync_thread


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hipda", description="Read 4D4Y/HiPDA forum posts from the terminal.")
    parser.add_argument("--cookie", help="Logged-in Cookie header. Defaults to HIPDA_COOKIE.")
    parser.add_argument("--user-agent", help="User-Agent header. Defaults to HIPDA_USER_AGENT or Chrome-like UA.")
    parser.add_argument("--ca-file", help="PEM CA bundle to trust for HTTPS. Defaults to HIPDA_CA_FILE.")
    parser.add_argument(
        "--insecure-tls",
        action="store_true",
        help="Disable HTTPS certificate verification. This is the default for 4D4Y.",
    )
    parser.add_argument(
        "--verify-tls",
        action="store_true",
        help="Enable HTTPS certificate verification.",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="{login,list,read,sync,search}")

    subparsers.add_parser("login", help="Import 4D4Y login cookies from Chrome.")

    sync_parser = subparsers.add_parser(
        "sync", help="Refresh the local store from the Discovery listing."
    )
    sync_parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Maximum number of forum pages to walk.",
    )
    sync_parser.add_argument(
        "--no-early-stop",
        dest="early_stop",
        action="store_false",
        default=True,
        help="Walk every page even if a page brings no changes.",
    )

    search_parser = subparsers.add_parser(
        "search", help="Search the local store with full-text matching."
    )
    search_parser.add_argument("query", help="Search query (CJK supported via jieba).")
    search_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of matches to return.",
    )
    search_parser.add_argument(
        "--scope",
        choices=["all", "threads", "posts"],
        default="all",
        help="Restrict matches to thread titles, post bodies, or both (default).",
    )
    search_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit machine-readable JSON instead of human-friendly text.",
    )

    list_parser = subparsers.add_parser("list", help="List Discovery threads.")
    list_parser.add_argument("--page", type=int, default=1, help="Forum page number.")
    list_parser.add_argument("--limit", type=int, default=30, help="Maximum number of threads to print.")
    list_parser.add_argument("--show-pinned", action="store_true", help="Include pinned threads.")
    list_parser.add_argument(
        "--offline",
        action="store_true",
        help="Read from the local store only; never hit the network.",
    )
    list_parser.add_argument(
        "--refresh",
        action="store_true",
        help="Sync the listing from 4D4Y before printing.",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-friendly text.",
    )

    read_parser = subparsers.add_parser("read", help="Read a thread by tid or URL.")
    read_parser.add_argument("thread", help="Thread id, or a full viewthread.php URL.")
    read_parser.add_argument("--page", type=int, default=1, help="Thread page number.")
    read_parser.add_argument(
        "--offline",
        action="store_true",
        help="Read from the local store only; never hit the network.",
    )
    read_parser.add_argument(
        "--refresh",
        action="store_true",
        help="Sync the thread from 4D4Y before printing.",
    )
    read_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-friendly text.",
    )

    auth = subparsers.add_parser("auth", help=argparse.SUPPRESS)
    auth_subparsers = auth.add_subparsers(dest="auth_command", required=True)
    save_cookie_parser = auth_subparsers.add_parser("save-cookie", help="Save a pasted 4D4Y Cookie header.")
    save_cookie_parser.add_argument("cookie", nargs="?", help="Cookie header value. Reads stdin if omitted.")
    save_user_agent_parser = auth_subparsers.add_parser("save-user-agent", help="Save the Chrome User-Agent used with the cookie.")
    save_user_agent_parser.add_argument("user_agent", nargs="?", help="User-Agent value. Reads stdin if omitted.")

    discovery = subparsers.add_parser("discovery", help=argparse.SUPPRESS)
    discovery_subparsers = discovery.add_subparsers(dest="discovery_command", required=True)

    list_parser = discovery_subparsers.add_parser("list", help="List Discovery threads.")
    list_parser.add_argument("--page", type=int, default=1, help="Forum page number.")
    list_parser.add_argument("--limit", type=int, default=30, help="Maximum number of threads to print.")
    list_parser.add_argument("--show-pinned", action="store_true", help="Include pinned threads.")

    read_parser = discovery_subparsers.add_parser("read", help="Read a thread by tid or URL.")
    read_parser.add_argument("thread", help="Thread id, or a full viewthread.php URL.")
    read_parser.add_argument("--page", type=int, default=1, help="Thread page number.")

    subparsers._choices_actions = [
        action for action in subparsers._choices_actions if action.dest not in {"auth", "discovery"}
    ]

    return parser


def load_discovery_page(
    *,
    page: int,
    path: str,
    params: dict[str, str | int],
    cookie: str | None,
    user_agent: str | None,
    ca_file: str | None,
    insecure_tls: bool,
    verify_tls: bool = False,
) -> tuple[str, HipdaClient]:
    client = HipdaClient.from_env(
        cookie=cookie,
        user_agent=user_agent,
        ca_file=ca_file,
        insecure_tls=insecure_tls or not verify_tls,
        verify_tls=verify_tls,
    )
    html = client.get(path, params)
    if not is_login_required_page(html):
        return html, client

    if cookie:
        return html, client

    try:
        imported_cookie, imported_user_agent = import_browser_auth()
    except Exception:
        return html, client

    client = HipdaClient.from_env(
        cookie=imported_cookie,
        user_agent=user_agent or imported_user_agent,
        ca_file=ca_file,
        insecure_tls=insecure_tls or not verify_tls,
        verify_tls=verify_tls,
    )
    return client.get(path, params), client


def wait_for_login_confirmation() -> None:
    if sys.stdin.isatty():
        input("Log in to 4D4Y in Chrome, then press Enter here...")


def _extract_tid(value: str) -> str:
    if "tid=" in value:
        return value.split("tid=", 1)[1].split("&", 1)[0]
    return value


def _run_read(client, args: argparse.Namespace) -> int:
    tid = _extract_tid(args.thread)
    offline = getattr(args, "offline", False)
    refresh = getattr(args, "refresh", False)
    conn = connect(default_db_path())
    try:
        has_posts = conn.execute(
            "select 1 from posts where tid = ? limit 1", (tid,)
        ).fetchone() is not None
        if not offline and (refresh or not has_posts):
            now = datetime.now(timezone.utc).isoformat()
            sync_thread(client, conn, tid=tid, now=now)
        posts = read_thread_local(conn, tid=tid)
    finally:
        conn.close()

    if not posts:
        if offline:
            print(
                f"hipda: no local posts for tid={tid}. Run `hipda read {tid}` "
                "without --offline, or `hipda sync` first.",
                file=sys.stderr,
            )
            return 4
        print(f"hipda: no posts found for tid={tid}.", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps([asdict(post) for post in posts], ensure_ascii=False))
        return 0

    for index, post in enumerate(posts, start=1):
        print(f"#{index} {post.author} {post.published_at}".rstrip())
        print(post.content)
        print()
    return 0


def _format_thread_line(thread) -> str:
    stats = ""
    if thread.replies is not None and thread.views is not None:
        stats = f" {thread.replies}/{thread.views}"
    last = f" last: {thread.last_author} {thread.last_at}".rstrip() if thread.last_author else ""
    return f"{thread.tid}\t{thread.title}\t{thread.author} {thread.created_at}{stats}{last}"


def _run_list(client, args: argparse.Namespace) -> int:
    offline = getattr(args, "offline", False)
    refresh = getattr(args, "refresh", False)
    conn = connect(default_db_path())
    try:
        existing = conn.execute("select 1 from threads limit 1").fetchone()
        should_sync = refresh or (existing is None and not offline)
        if should_sync:
            now = datetime.now(timezone.utc).isoformat()
            sync_listing(
                client,
                conn,
                fid=2,
                max_pages=max(args.page, 1),
                early_stop=True,
                now=now,
            )
        if offline and conn.execute("select 1 from threads limit 1").fetchone() is None:
            print(
                "hipda: local store is empty. Run `hipda sync` or drop --offline.",
                file=sys.stderr,
            )
            return 4
        threads = list_threads_local(
            conn, limit=args.limit, show_pinned=args.show_pinned
        )
    finally:
        conn.close()
    if getattr(args, "json", False):
        print(json.dumps([asdict(thread) for thread in threads], ensure_ascii=False))
        return 0
    for thread in threads:
        print(_format_thread_line(thread))
    return 0


def run(args: argparse.Namespace) -> int:
    if args.command == "login":
        try:
            open_login_page()
            wait_for_login_confirmation()
            import_browser_auth()
        except Exception as exc:
            print(
                "hipda: could not import 4D4Y cookies from Chrome. "
                "Open Chrome, log in to https://www.4d4y.com/forum/forumdisplay.php?fid=2, then run `hipda login` again.",
                file=sys.stderr,
            )
            print(f"hipda: {exc}", file=sys.stderr)
            return 2
        print("Imported 4D4Y login from Chrome.")
        return 0

    if args.command == "auth" and args.auth_command == "save-cookie":
        cookie = args.cookie if args.cookie is not None else sys.stdin.read()
        try:
            path = save_cookie(cookie)
        except ValueError as exc:
            print(f"hipda: {exc}", file=sys.stderr)
            return 2
        print(f"Saved cookie to {path}")
        return 0

    if args.command == "auth" and args.auth_command == "save-user-agent":
        user_agent = args.user_agent if args.user_agent is not None else sys.stdin.read()
        try:
            path = save_user_agent(user_agent)
        except ValueError as exc:
            print(f"hipda: {exc}", file=sys.stderr)
            return 2
        print(f"Saved user-agent to {path}")
        return 0

    client = HipdaClient.from_env(
        cookie=args.cookie,
        user_agent=args.user_agent,
        ca_file=args.ca_file,
        insecure_tls=args.insecure_tls or not args.verify_tls,
        verify_tls=args.verify_tls,
    )

    if args.command == "search":
        conn = connect(default_db_path())
        try:
            results = search_local(conn, args.query, limit=args.limit, scope=args.scope)
        finally:
            conn.close()
        if args.json:
            print(json.dumps([asdict(result) for result in results], ensure_ascii=False))
        else:
            for result in results:
                tag = "thread" if result.kind == "thread" else f"post  in tid={result.tid}"
                head = result.tid if result.kind == "thread" else f"{result.tid}#{result.pid}"
                print(f"{head}\t{tag}\t{result.title}\t{result.snippet}")
        return 0

    if args.command == "sync":
        conn = connect(default_db_path())
        try:
            now = datetime.now(timezone.utc).isoformat()
            inserted, updated, pages_fetched = sync_listing(
                client,
                conn,
                fid=2,
                max_pages=args.max_pages,
                early_stop=args.early_stop,
                now=now,
            )
        finally:
            conn.close()
        print(
            f"synced {inserted + updated} threads: "
            f"{inserted} new, {updated} updated, {pages_fetched} pages fetched"
        )
        return 0

    try:
        command = args.discovery_command if args.command == "discovery" else args.command

        if command == "list":
            return _run_list(client, args)

        if command == "read":
            return _run_read(client, args)
    except HipdaClientError as exc:
        print(f"hipda: {exc}", file=sys.stderr)
        if not client.cookie:
            print("hipda: set HIPDA_COOKIE or pass --cookie with a logged-in 4D4Y Cookie header.", file=sys.stderr)
        return 2

    raise AssertionError(f"Unhandled command: {args}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        parser.print_help()
        return 0
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
