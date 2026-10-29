# Stack conventions

This directory holds the conventions shared by the agents, skills, mods, and idstack repositories and an offline checker for them. The source of truth is [iuliandita/agents](https://github.com/iuliandita/agents/tree/develop/.github/stack); its README describes the format and the checks.

Do not edit `canon.json` or `stack-check.py` here. Re-vendor them from agents and regenerate `SOURCE`. The checker reports any file whose sha256 differs from `SOURCE`.

`repo.json` holds the settings for this repository and is edited here. Run the checker from the repository root:

```sh
python3 .github/stack/stack-check.py
```

The weekly `stack-sync` workflow opens an issue when agents has a newer canon.
