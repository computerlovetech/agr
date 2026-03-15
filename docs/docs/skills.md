---
title: Skill Directory
---

# Skill Directory

Browse available skills and find ones that fit your workflow. Every skill below
can be tried instantly without installing:

```bash
agrx anthropics/skills/pdf -p "Extract tables from report.pdf"
```

---

## Official Skills

Maintained by Anthropic in the [anthropics/skills](https://github.com/anthropics/skills) repository.

### Documents & Data

| Skill | Description | Install |
|-------|-------------|---------|
| PDF | Read, extract, create, and modify PDF files | `agr add anthropics/skills/pdf` |
| DOCX | Create, read, edit, and manipulate Word documents | `agr add anthropics/skills/docx` |
| PPTX | Create and work with PowerPoint slide decks | `agr add anthropics/skills/pptx` |
| XLSX | Create and manipulate spreadsheet files | `agr add anthropics/skills/xlsx` |
| Doc Co-authoring | Structured workflow for co-authoring documentation | `agr add anthropics/skills/doc-coauthoring` |

### Design & Frontend

| Skill | Description | Install |
|-------|-------------|---------|
| Frontend Design | Build distinctive, production-grade frontend interfaces | `agr add anthropics/skills/frontend-design` |
| Canvas Design | Create visual art in PNG and PDF using design principles | `agr add anthropics/skills/canvas-design` |
| Algorithmic Art | Create algorithmic art with p5.js and seeded randomness | `agr add anthropics/skills/algorithmic-art` |
| Theme Factory | Style artifacts (slides, docs, landing pages) with themes | `agr add anthropics/skills/theme-factory` |
| Brand Guidelines | Apply Anthropic's official brand colors and typography | `agr add anthropics/skills/brand-guidelines` |

### Development

| Skill | Description | Install |
|-------|-------------|---------|
| Claude API | Build apps with the Claude API and Anthropic SDKs | `agr add anthropics/skills/claude-api` |
| MCP Builder | Create MCP servers for LLM-to-service interaction | `agr add anthropics/skills/mcp-builder` |
| Web Artifacts Builder | Create multi-component HTML artifacts with modern frontend tech | `agr add anthropics/skills/web-artifacts-builder` |
| Webapp Testing | Test local web applications using Playwright | `agr add anthropics/skills/webapp-testing` |

### Productivity

| Skill | Description | Install |
|-------|-------------|---------|
| Skill Creator | Create, modify, and improve skills | `agr add anthropics/skills/skill-creator` |
| Internal Comms | Write internal communications in your company's formats | `agr add anthropics/skills/internal-comms` |
| Slack GIF Creator | Create animated GIFs optimized for Slack | `agr add anthropics/skills/slack-gif-creator` |

Browse the full list at [github.com/anthropics/skills](https://github.com/anthropics/skills).

---

## Community Skills

Skills built and shared by the community.

### Go

| Skill | Description | Author | Install |
|-------|-------------|--------|---------|
| Go Pro | Expert Go 1.21+ development for concurrent, scalable systems | [@dsjacobsen](https://github.com/dsjacobsen) | `agr add dsjacobsen/agent-resources/golang-pro` |

### Drupal

| Skill | Description | Author | Install |
|-------|-------------|--------|---------|
| Drupal Expert | Drupal 10/11 modules, themes, hooks, services, and config | [@madsnorgaard](https://github.com/madsnorgaard) | `agr add madsnorgaard/drupal-agent-resources/drupal-expert` |
| Drupal Security | Prevent XSS, SQL injection, and access bypass in Drupal | [@madsnorgaard](https://github.com/madsnorgaard) | `agr add madsnorgaard/drupal-agent-resources/drupal-security` |
| Drupal Migration | D7-to-D10 migrations, CSV imports, and migration plugins | [@madsnorgaard](https://github.com/madsnorgaard) | `agr add madsnorgaard/drupal-agent-resources/drupal-migration` |
| DDEV Expert | DDEV local development, containers, and configuration | [@madsnorgaard](https://github.com/madsnorgaard) | `agr add madsnorgaard/drupal-agent-resources/ddev-expert` |
| Docker Local | Docker Compose local development patterns | [@madsnorgaard](https://github.com/madsnorgaard) | `agr add madsnorgaard/drupal-agent-resources/docker-local` |

### Workflow

| Skill | Description | Author | Install |
|-------|-------------|--------|---------|
| Collaboration | Contributing to GitHub projects, PRs, and code reviews | [@maragudk](https://github.com/maragudk) | `agr add maragudk/skills/collaboration` |
| Commit Work | Run quality checks, update changelog, and create commits | [@kasperjunge](https://github.com/kasperjunge) | `agr add kasperjunge/commit-work` |
| Migrate to Skills | Convert legacy agent resources to the Agent Skills format | [@kasperjunge](https://github.com/kasperjunge) | `agr add kasperjunge/agent-resources/migrate-to-skills` |

---

## Discovering More Skills

### Search GitHub

Any GitHub repository with a `SKILL.md` file can be installed with agr:

- [Search for SKILL.md files on GitHub](https://github.com/search?q=filename%3ASKILL.md&type=code)

### List skills in a repository

Use the Python SDK to list all skills in any repo:

```python
from agr import list_skills

for info in list_skills("anthropics/skills"):
    print(f"{info.handle}: {info.description}")
```

Or check a repo manually — agr looks for any directory containing a `SKILL.md`
file.

### Try before you install

Use `agrx` to run any skill without adding it to your project:

```bash
agrx anthropics/skills/webapp-testing
agrx anthropics/skills/pdf -i   # Interactive: continue chatting after the skill runs
```

---

## Share Your Own Skills

### 1. Create a skill

```bash
agr init my-skill
```

Edit the generated `my-skill/SKILL.md` with your instructions.

### 2. Push to GitHub

Push your skill to a GitHub repository. The recommended structure is a repo named `skills` with one directory per skill:

```
your-username/skills/
├── my-skill/
│   └── SKILL.md
└── another-skill/
    └── SKILL.md
```

Others can then install with:

```bash
agr add your-username/my-skill
```

### 3. List it here

Open an issue at [github.com/kasperjunge/agent-resources](https://github.com/kasperjunge/agent-resources/issues) to get your skill added to this directory.

See [Creating Skills](creating.md) for a full guide on writing effective skills.
