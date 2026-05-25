# hipda

CLI reader for the 4D4Y/HiPDA Discovery channel (`fid=2`).

The site uses browser/session checks, so direct unauthenticated requests may return a Cloudflare challenge. Log in once through Chrome:

```bash
uvx --from . hipda login
```

From PyPI:

```bash
uvx hipda login
```

That opens 4D4Y in Google Chrome. After you finish logging in, return to the terminal and press Enter. Then read Discovery:

```bash
uvx --from . hipda list --limit 20
uvx --from . hipda read 3446553
```

From PyPI:

```bash
uvx hipda list --limit 20
uvx hipda read 3446553
```

`hipda list` hides pinned threads by default; pass `--show-pinned` to include them. It also tries to import automatically if Chrome is already logged in, so most of the time you can skip straight to reading. The old `hipda discovery list` and `hipda discovery read` commands still work.

The cookie is stored at `~/.config/hipda/cookie` and the user agent is stored at `~/.config/hipda/user-agent`, both with `0600` permissions. You can override them per command with `HIPDA_COOKIE` / `--cookie` and `HIPDA_USER_AGENT` / `--user-agent`.

You can also pass a browser user agent:

```bash
HIPDA_USER_AGENT='Mozilla/5.0 ...' uvx --from . hipda list
```

The CLI disables HTTPS certificate verification by default because 4D4Y often fails from Python environments where Chrome still works. To verify certificates, pass a trusted root certificate and `--verify-tls`:

```bash
uvx --from . hipda --verify-tls --ca-file /path/to/root-ca.pem list
```
