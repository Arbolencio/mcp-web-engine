# Releasing to PyPI and npm

Versions in `pyproject.toml`, `package.json` and
`src/mcp_web_engine/__init__.py` must match. Update `uv.lock`, current installation
examples and the changelog together. Preserve historical demo recordings and
their stated package version. Use absolute README URLs for package-registry
pages; the architecture PNG is rendered from the SVG source.

## One-time trusted publisher setup

The `release.yml` workflow uses short-lived GitHub Actions OIDC credentials.
An npm CLI login, PyPI token or repository secret is not required once each
registry's package owner has configured the following relationship:

| Setting | PyPI | npm |
|---|---|---|
| Package | `mcp-web-engine` | `mcp-web-engine` |
| GitHub owner | `Arbolencio` | `Arbolencio` |
| Repository | `mcp-web-engine` | `mcp-web-engine` |
| Workflow filename | `release.yml` | `release.yml` |
| GitHub environment | `pypi` | `npm` |
| Allowed action | Package upload | Enable direct `npm publish` |

For PyPI, open the project's **Manage → Publishing** page and add a GitHub
trusted publisher. For npm, open the package's settings and add a GitHub Actions
trusted publisher; direct `npm publish` must be allowed, not only staged publishing.
The workflow file must first exist on the repository's default branch.
If adding protection rules to the GitHub environments, allow the reviewed release
tags and arrange for any required reviewer to approve deployment.

See the official [PyPI setup](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
and [npm setup](https://docs.npmjs.com/trusted-publishers/) instructions.

## Build and inspect a candidate

```bash
uv sync --locked --extra test
uv run --locked python -m pytest -q
uv lock --check
uv build --out-dir dist
uvx twine check --strict dist/*.whl dist/*.tar.gz
npm pack --ignore-scripts --pack-destination dist
```

Use a clean `dist` directory containing only the candidate version. Inspect the
wheel metadata and the npm/sdist file manifests. Check that README assets and
documentation links point at the intended tag. Preview the rendered PyPI Markdown
and confirm that the original 1.2.1 demo is still identified as historical.

Run `tests/artifact_smoke.py` against the installed wheel and npm archive outside
the checkout. The smoke checks initialization, silent notifications, ping, tool
listing, rejected loopback fetching, an untrusted working-directory `.env` and
JSON-only stdout. Dependency installation can access package indexes; the probe
does not query a live search engine.

## Tag and publish

Merge the candidate only after its tests and installed-artifact CI checks pass.
Tag that reviewed commit, using the actual version and commit SHA:

```bash
git tag -a v1.2.2 REVIEWED_COMMIT_SHA -m "Release 1.2.2"
git push origin refs/tags/v1.2.2
gh workflow run release.yml --repo Arbolencio/mcp-web-engine --ref v1.2.2 -f publish=false
```

The manual dry run builds and tests archives without publishing. Review its
artifacts and result. Once trusted publishers are configured, dispatch the same
tag with publishing enabled:

```bash
gh workflow run release.yml --repo Arbolencio/mcp-web-engine --ref v1.2.2 -f publish=true
```

The workflow checks stable `vX.Y.Z` tags, all three versions, tag/commit identity
and ancestry on `master`, runs the offline suite, builds Python/npm archives and
tests the installed archives. The two publishing jobs upload exactly those
archives; neither receives permanent registry credentials. npm publishing uses
a pinned CLI with OIDC support.

The PyPI and npm uploads are independent: one may succeed while the other fails.
If that happens, fix the registry configuration and rerun **only failed jobs**.
Alternatively, dispatch the same tag with `-f publish=true -f registry=pypi` or
`-f publish=true -f registry=npm` to finish only that registry. The default
`registry=both` publishes to both; the build and verification job always runs.
If the package is already published to npm, dispatch from `master` and provide
the existing tag explicitly so the build can skip npm's duplicate-version
check. For example:

```bash
gh workflow run release.yml --repo Arbolencio/mcp-web-engine --ref master \
  -f release_tag=v1.2.2 -f publish=true -f registry=pypi
```

Never move the release tag or overwrite/reuse a published version for changed
artifacts. A change to a released package requires another version.

## Verify the public release

- Download the PyPI wheel and sdist and compare their SHA-256 digests with the
  workflow's tested artifacts. Install the public wheel outside the checkout and
  rerun the offline smoke.
- Compare npm's published archive integrity with the tested `.tgz`; install and
  smoke-test the public version outside the checkout.
- Confirm the new version, description, diagram and documentation links on both
  package pages. A rendered README check does not establish that an external
  asset URL is reachable; verify it after the release tag exists.
- Create the GitHub release from the same tag with the changelog and verification
  evidence. Update integration pins separately through their normal review process.

GitHub CI success alone does not prove that both registries received the release.
