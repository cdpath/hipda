# hipda

Local-first CLI for the 4D4Y/HiPDA Discovery channel (`fid=2`). Threads and posts are mirrored into a local SQLite store with FTS5 + jieba so listing, reading, and searching all work offline once the cache is warm.

## Install + log in

The site uses browser/session checks, so direct unauthenticated requests may return a Cloudflare challenge. Log in once through Chrome:

```bash
uvx --from . hipda login
```

From PyPI:

```bash
uvx hipda login
```

That opens 4D4Y in Google Chrome. After you finish logging in, return to the terminal and press Enter.

The cookie is stored at `~/.config/hipda/cookie` and the user agent is stored at `~/.config/hipda/user-agent`, both with `0600` permissions. You can override them per command with `HIPDA_COOKIE` / `--cookie` and `HIPDA_USER_AGENT` / `--user-agent`.

## Sync the local store

```bash
uvx --from . hipda sync                  # walk recent Discovery pages, stop when a page brings no changes
uvx --from . hipda sync --max-pages 10   # walk up to 10 pages
uvx --from . hipda sync --no-early-stop  # always walk the full --max-pages range
```

Sync writes to the SQLite database at `$HIPDA_DB`, or `$XDG_DATA_HOME/hipda/hipda.sqlite`, falling back to `~/.local/share/hipda/hipda.sqlite`.

## List threads (local-first)

```bash
uvx --from . hipda list --limit 20            # reads local DB; auto-syncs when cold
uvx --from . hipda list --refresh             # sync first, then print
uvx --from . hipda list --offline             # never touch the network
uvx --from . hipda list --show-pinned         # include pinned threads
uvx --from . hipda list --json                # machine-readable output
```

## Read a thread (local-first)

```bash
uvx --from . hipda read 3446553               # reads local; auto-fetches the thread when cold
uvx --from . hipda read 3446553 --refresh     # re-sync the thread before printing
uvx --from . hipda read 3446553 --offline     # local only
uvx --from . hipda read 3446553 --json        # JSON array of posts
```

## Full-text search

Search runs entirely against the local SQLite FTS5 index. Queries are segmented with jieba so CJK input works without spaces.

```bash
uvx --from . hipda search "半导体"
uvx --from . hipda search "半导体" --scope threads     # only thread titles
uvx --from . hipda search "半导体" --scope posts       # only post bodies
uvx --from . hipda search "半导体" --json --limit 50   # machine-readable
```

Each hit returns the matching `tid` (and `pid` for post matches), the thread title, and a snippet with `[...]` brackets around the matched tokens.

## Exit codes

- `0` — success
- `1` — generic failure (e.g. parse error, thread not found upstream)
- `2` — auth required (run `hipda login`)
- `4` — `--offline` requested but the local store is missing the needed data

## TLS

The CLI disables HTTPS certificate verification by default because 4D4Y often fails from Python environments where Chrome still works. To verify certificates, pass a trusted root certificate and `--verify-tls`:

```bash
uvx --from . hipda --verify-tls --ca-file /path/to/root-ca.pem sync
```

## Legacy

`hipda list` previously fetched directly from the forum on every call. The behaviour is now local-first; the old `hipda discovery list` and `hipda discovery read` subcommands still resolve through the same local-first path.
