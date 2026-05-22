# Get started

Your team shouldn't be copying AI skill files around by hand. agr gives you a
shared, versioned skill environment: one manifest, one sync command, the same
setup on every machine and every tool.

## Install

```bash
uv tool install agr
```

## Add a skill

```bash
agr add anthropics/skills/pdf
```

Handles follow `owner/repo/skill` — a directory inside a GitHub repo.
`anthropics/skills/pdf` is the `pdf/` directory in
[github.com/anthropics/skills](https://github.com/anthropics/skills).

Open Claude Code and type `/pdf` — the skill is there.

## Share with your team

Commit `agr.toml` and `agr.lock`. When a teammate clones the repo:

```bash
agr sync
```

Same skills. Every machine.

---

[Manage your skill environment →](managing.md)
