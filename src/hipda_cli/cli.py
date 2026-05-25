from __future__ import annotations

import argparse
import sys

from .auth import import_browser_auth, open_login_page, save_cookie, save_user_agent
from .client import BASE_URL, HipdaClient, HipdaClientError
from .parser import is_login_required_page, parse_forum_listing, parse_thread


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

    subparsers = parser.add_subparsers(dest="command", metavar="{login,list,read}")

    subparsers.add_parser("login", help="Import 4D4Y login cookies from Chrome.")

    list_parser = subparsers.add_parser("list", help="List Discovery threads.")
    list_parser.add_argument("--page", type=int, default=1, help="Forum page number.")
    list_parser.add_argument("--limit", type=int, default=30, help="Maximum number of threads to print.")
    list_parser.add_argument("--show-pinned", action="store_true", help="Include pinned threads.")

    read_parser = subparsers.add_parser("read", help="Read a thread by tid or URL.")
    read_parser.add_argument("thread", help="Thread id, or a full viewthread.php URL.")
    read_parser.add_argument("--page", type=int, default=1, help="Thread page number.")

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


def _thread_params(thread: str, page: int) -> dict[str, str | int]:
    if "tid=" in thread:
        tid = thread.split("tid=", 1)[1].split("&", 1)[0]
    else:
        tid = thread
    return {"tid": tid, "page": page}


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

    try:
        command = args.discovery_command if args.command == "discovery" else args.command

        if command == "list":
            html, client = load_discovery_page(
                page=args.page,
                path="forumdisplay.php",
                params={"fid": 2, "page": args.page},
                cookie=args.cookie,
                user_agent=args.user_agent,
                ca_file=args.ca_file,
                insecure_tls=args.insecure_tls or not args.verify_tls,
                verify_tls=args.verify_tls,
            )
            if is_login_required_page(html):
                print(
                    "hipda: 4D4Y says this request is not logged in. "
                    "Open Chrome, log in to 4D4Y, then run `hipda login`.",
                    file=sys.stderr,
                )
                return 2
            threads = parse_forum_listing(html, base_url=BASE_URL)
            if not args.show_pinned:
                threads = [thread for thread in threads if not thread.is_pinned]
            threads = threads[: args.limit]
            for thread in threads:
                stats = ""
                if thread.replies is not None and thread.views is not None:
                    stats = f" {thread.replies}/{thread.views}"
                last = f" last: {thread.last_author} {thread.last_at}".rstrip() if thread.last_author else ""
                print(f"{thread.tid}\t{thread.title}\t{thread.author} {thread.created_at}{stats}{last}")
            return 0

        if command == "read":
            html, client = load_discovery_page(
                page=args.page,
                path="viewthread.php",
                params=_thread_params(args.thread, args.page),
                cookie=args.cookie,
                user_agent=args.user_agent,
                ca_file=args.ca_file,
                insecure_tls=args.insecure_tls or not args.verify_tls,
                verify_tls=args.verify_tls,
            )
            if is_login_required_page(html):
                print(
                    "hipda: 4D4Y says this request is not logged in. "
                    "Open Chrome, log in to 4D4Y, then run `hipda login`.",
                    file=sys.stderr,
                )
                return 2
            posts = parse_thread(html)
            for index, post in enumerate(posts, start=1):
                print(f"#{index} {post.author} {post.published_at}".rstrip())
                print(post.content)
                print()
            return 0
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
