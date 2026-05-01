# Handles, resources, and scopes

agr identifies every resource by a **handle**. Get the handle format wrong and
nothing else works, so this is the page to consult first when an `agr add`
fails with "not found".

## Handle formats

| Form | Resolves to | When to use |
|---|---|---|
| `user/skill` | `github.com/user/skills` repo, `skill/` subdirectory | When the publisher follows the convention of putting all skills in a repo named `skills` |
| `user/repo/skill` | `github.com/user/repo` repo, `skill/` subdirectory | When the repo has a different name |
| `skill` (1-part) | `<default_owner>/skills/skill` | When `default_owner` is configured (defaults to `computerlovetech`) |
| `./path/to/skill` | Local directory | In-repo or scratch skills |

**Examples:**

```bash
agr add anthropics/skills/pdf            # 3-part: anthropics, repo "skills", folder "pdf"
agr add anthropics/pdf                   # 2-part: same thing (assumes "skills" repo)
agr add vercel-labs/agent-browser/agent-browser  # 3-part: repo isn't called "skills"
agr add ./skills/my-skill                # local
```

When in doubt, ask the user for the GitHub URL and translate.

## Resource types

agr manages three resource types. Every dep entry in `agr.toml` carries a
`type` field that agr fills in automatically on `agr add`.

| Type | Marker file | Installed to | Notes |
|---|---|---|---|
| `skill` | `SKILL.md` | Each configured tool's skills dir | The common case |
| `ralph` | `RALPH.md` | `.agents/ralphs/<name>/` (per project) | Autonomous agent loop, executed by a runtime like ralphify. Ignores the `tools` list. Project-scoped only — `-g` is rejected. |
| `package` | `agr.toml` (no marker file at top) | N/A — expanded transitively | A folder whose `agr.toml` lists more deps. Adding a package installs all its skills/ralphs and records the parent relationship in `agr.lock`. |

`agr add` detects type automatically:

- For local paths, from the marker file inside the directory.
- For remote handles, by searching the repo for a matching skill first, then
  falling back to ralph.

There is no `--type` flag — the `type` is recorded after a successful install.

## Scopes

Every `add` / `remove` / `sync` / `list` accepts `-g` / `--global`:

| Scope | Manifest | Skills installed to |
|---|---|---|
| Project (default) | `./agr.toml` | `.claude/skills/`, `.cursor/skills/`, … in the repo |
| Global (`-g`) | `~/.agr/agr.toml` | `~/.claude/skills/`, `~/.cursor/skills/`, … |

Global skills are available across every project on the machine. Useful for
personal productivity skills the user wants everywhere; not useful for
team-shared, project-specific skills.

Ralphs are project-scoped only — `-g` is rejected for ralph deps.

## Sources

A **source** is a Git URL template. Default source is `github`:

```toml
[[source]]
name = "github"
type = "git"
url = "https://github.com/{owner}/{repo}.git"
```

Add a custom source for GitLab, self-hosted, or mirrored Git:

```bash
agr config add sources gitlab --url "https://gitlab.com/{owner}/{repo}.git"
agr add team/internal-tool --source gitlab
agr config set default_source gitlab     # change the default
```

`{owner}` and `{repo}` are substituted from the handle.

## Private repos

Set `GITHUB_TOKEN` (or the equivalent for your source) before running agr:

```bash
export GITHUB_TOKEN="ghp_..."
agr add my-org/private-skills/secret-skill
```

For CI, set the token as a secret. The token needs read access to the repo.

## Pinning a single dep to a non-default source

In `agr.toml`:

```toml
dependencies = [
    {handle = "team/internal-tool", type = "skill", source = "gitlab"},
]
```

Or via CLI:

```bash
agr add team/internal-tool --source gitlab
```

## See also

- [installing-skills.md](installing-skills.md) — `agr add` and `agr remove` in depth
- [configuration.md](configuration.md) — the full `agr config` surface
