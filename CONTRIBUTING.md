# Contributing

Open an issue before starting a bug fix or a substantial change, and reference it in the PR
(`Closes #NN` for a completed fix). Branch from `develop`, keep changes small, and use
conventional commit titles. PRs are squash-merged.
Report suspected vulnerabilities through [SECURITY.md](SECURITY.md), not a public issue.

## Sources

- `docs/plan.md` is the design. Change it in the same PR as any change that departs from it.
- The three manifests (`plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`)
  carry the same version. Bump all three for a release.
- `config/pstack-models.json` sets pstack's model per role. Run `python3 scripts/pstack_models.py --dry-run` after editing; it rejects unknown models.
- `PSTACK_MIRROR_REF` in `install.sh` pins the pstack mirror for Codex and OpenCode. Move it only
  after running the installer against the new commit.

## Checks

Run these before opening a PR:

```sh
python3 scripts/check.py
python3 -m unittest discover -s tests
python3 bin/idstack build --check
ruff check bin/idstack scripts tests
ruff format --check bin/idstack scripts tests
shellcheck install.sh
claude plugin validate .
```

`harness/**` and `skills/*/agents/openai.yaml` are generated. After editing `agents/*.md` or a
skill, run `python3 bin/idstack build` and commit the result; never edit the generated files.

`scripts/check.py` checks ASCII, JSON, manifest agreement, the mirror pin, the changelog, and
relative links. If `private-patterns.txt` exists (it is gitignored; copy
`private-patterns.example.txt`), it also fails on any listed literal in a tracked file.

For installer changes, run it against a throwaway directory so nothing touches your real config:

```sh
R=$(mktemp -d)
export CLAUDE_CONFIG_DIR=$R/claude CODEX_HOME=$R/codex AGENTS_SKILLS_DIR=$R/agents/skills \
  OPENCODE_SKILLS_DIR=$R/opencode/skills OPENCODE_AGENTS_DIR=$R/opencode/agents \
  IDSTACK_CACHE_DIR=$R/cache IDSTACK_BIN_DIR=$R/bin
mkdir -p "$CODEX_HOME"
./install.sh --harness claude,codex,opencode --source "$PWD"
./install.sh --harness claude,codex,opencode --source "$PWD" --check
```

Update [INSTALL.md](INSTALL.md) and [CHANGELOG.md](CHANGELOG.md) in the same PR when behavior
changes.
