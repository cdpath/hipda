# PyPI Release

This project publishes with GitHub Actions trusted publishing. No PyPI token is stored in GitHub secrets.

## One-time PyPI setup

Create trusted publishers for repository `cdpath/hipda`.

If the project already exists on the index, add the publisher from that project's publishing settings. If the project does not exist yet, create a pending trusted publisher from the account publishing page; the first successful workflow run will create the project.

PyPI:

- Project: `hipda`
- Owner: `cdpath`
- Repository name: `hipda`
- Workflow name: `python-publish.yml`
- Environment name: `pypi`

The workflow uses a GitHub environment named `pypi`. Configure environment protection rules in GitHub if releases should require manual approval.

## PyPI release

1. Bump `version` in `pyproject.toml`.
2. Push the branch to GitHub.
3. Create and publish a GitHub release.
4. The release event publishes the package version to PyPI.
5. Verify the package:

```bash
uvx --refresh --from hipda==<version> hipda --help
```

Package versions are immutable on PyPI. If a publish partially succeeds, bump the version before retrying.
