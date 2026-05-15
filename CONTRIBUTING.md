# Contributing to DataForge

Thank you for being part of the DataForge team. This document defines the rules every team member follows to keep the repository clean, traceable, and easy to review by Emrah.

---

## Table of Contents

- [Branch Strategy](#branch-strategy)
- [Commit Message Convention](#commit-message-convention)
- [Pull Request Process](#pull-request-process)
- [Code Style](#code-style)
- [Weekly Workflow](#weekly-workflow)

---

## Branch Strategy

DataForge uses a structured Gitflow adapted for a 3-person team.

### Branch Map

```
main
 └── develop
      ├── milestone/m2-schema-design
      ├── milestone/m3-data-generation
      ├── feature/kafka-topic-config        ← Omer
      ├── feature/dashboard-home-page       ← Beyza
      └── feature/shap-integration          ← Abdalla
```

### Branch Rules

| Branch | Purpose | Who merges here | Protected? |
|--------|---------|-----------------|------------|
| `main` | Stable, demo-ready code — Emrah sees this | Only from `develop` via PR | ✅ Yes |
| `develop` | Integration branch — all features merge here first | Feature / milestone branches | ✅ Yes |
| `milestone/m*` | Milestone-scoped work — spans 4 weeks | Feature branches within the milestone | No |
| `feature/*` | Individual feature or task | Your own work | No |
| `hotfix/*` | Emergency fix to `main` | Merges to both `main` and `develop` | No |

### Rules for `main` and `develop`

- **Never push directly to `main` or `develop`**
- All changes go through a Pull Request
- At least **one team member must review** before merge
- `main` is only updated at the end of a milestone, after Emrah sign-off

### Creating a Branch

```bash
# Always branch from develop (not main)
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name

# For milestone-scoped work
git checkout -b milestone/m2-schema-design
```

---

## Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/).

### Format

```
type(scope): short description

[optional body — explain WHY, not WHAT]

[optional footer — refs, breaking changes]
```

### Types

| Type | When to use |
|------|------------|
| `feat` | New feature or module |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no logic change |
| `refactor` | Restructure without feature change |
| `test` | Adding or fixing tests |
| `chore` | Build config, CI, dependencies |
| `perf` | Performance improvement |

### Scopes (match module numbers)

| Scope | Module |
|-------|--------|
| `alice` | Module 1 — ALICE ingestion |
| `sensors` | Module 2 — Sensor generators |
| `adaptation` | Module 3 — Data adaptation layer |
| `kafka` | Module 4 — Streaming layer |
| `spark` | Module 5 — Cleaning & sync |
| `fusion` | Module 6 — Data fusion |
| `ml` | Module 7 — Anomaly detection |
| `xai` | Module 8 — Explainable AI |
| `dashboard` | Module 9a — React frontend |
| `api` | Module 9b — FastAPI backend |
| `testing` | Module 10 — Validation |
| `infra` | Docker, CI, scripts |
| `docs` | Documentation |

### Examples

```bash
feat(kafka): add topic partitioning config for sensor streams
fix(spark): correct watermark window size for LIDAR events
docs(api): add OpenAPI spec for /anomalies endpoint
chore(infra): add docker-compose health checks for TimescaleDB
test(ml): add AUC validation test against prototype bar threshold
refactor(fusion): extract timestamp alignment into shared utility
```

---

## Pull Request Process

### Before Opening a PR

- [ ] Your branch is up to date with `develop` (`git rebase develop`)
- [ ] Code runs locally without errors
- [ ] Docker Compose still builds (`docker compose build`)
- [ ] You have written or updated tests where relevant
- [ ] Documentation updated if behaviour changed

### PR Title

Use the same format as commit messages:
```
feat(kafka): add Kafka topic setup for all 10 data streams
```

### PR Description

Use the PR template (auto-loaded from `.github/pull_request_template.md`).

### Review Rules

- Minimum **1 approval** required before merge to `develop`
- Minimum **2 approvals** required before merge to `main`
- The PR author **cannot approve their own PR**
- Address all review comments before merging

### Merging

Use **Squash and Merge** for feature branches into `develop`.  
Use **Merge Commit** for `develop` into `main` (preserves milestone history).

---

## Code Style

### Python

- Formatter: **Black** (`black .`)
- Linter: **flake8** (`flake8 .`)
- Max line length: 100 characters
- Type hints are encouraged for all public functions
- Docstrings: Google style

```python
def process_event(event: dict, source: str) -> dict:
    """Validate and normalize a raw event record.

    Args:
        event: Raw event dictionary from Kafka consumer.
        source: Source identifier ('alice' or sensor type).

    Returns:
        Normalized event dict with unified schema fields.

    Raises:
        ValueError: If required fields are missing.
    """
```

### JavaScript / React

- Formatter: **Prettier**
- Linter: **ESLint** (Airbnb config)
- Component files: PascalCase (`LiveStreamPage.jsx`)
- Utility files: camelCase (`formatTimestamp.js`)

### Docker / YAML

- Use 2-space indentation
- Pin image versions explicitly (e.g. `kafka:3.7.0`, not `kafka:latest`)
- All services must have health checks

---

## Weekly Workflow

This is the expected rhythm for each team member each week:

| Day | Action |
|-----|--------|
| Monday | Pull `develop`, create or continue feature branch |
| Wednesday | Push work-in-progress — open draft PR if blockers exist |
| Friday | Push completed work, open PR for review |
| Saturday | Team sync — review open PRs, resolve blockers |
| Sunday | Merge approved PRs into `develop` |

**Every Friday:** Abdalla sends the weekly update to Emrah summarising what was merged into `develop` that week.

---

*Questions? Open a GitHub Discussion or ping the team on the Saturday sync.*
