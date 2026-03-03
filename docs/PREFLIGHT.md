# Preflight Checklist

## Status: ✅ READY

## Accounts Required

None. wyby is a standalone Python library with no external service dependencies.

## API Keys / Environment Variables

None required. wyby has no external API integrations.

The optional `.env.example` mentioned in the PRD (T010) is for **local dev flags only** (e.g., debug mode, log level) — not for service credentials.

## Local Toolchain

- [x] **Python >= 3.10** — required by `pyproject.toml`
- [ ] **git** — required at runtime by `project_init.py` (scaffolds game projects)
- [ ] **Virtual environment active** — `.venv/` exists, run `source .venv/bin/activate`
- [ ] **Dev dependencies installed** — `pip install -e .` plus `pytest` and `ruff`

## Python Dependencies (pip)

| Package | Role | Status |
|---------|------|--------|
| `rich` | Terminal rendering (core runtime dep) | **Not yet in pyproject.toml `dependencies`** |
| `pytest` | Test runner | Available in .venv |
| `ruff` | Linter | Available in .venv |
| `pillow` (optional, future) | Image-to-cell-grid conversion | Not needed for MVP |
| `cairosvg` (optional, future) | SVG rasterization | Not needed for MVP |

## Manual Setup

- [ ] Add `rich` to `pyproject.toml` `[project.dependencies]` before implementing renderer

## Cost Estimate (monthly)

| Service | Free Tier | Paid |
|---------|-----------|------|
| PyPI (publish) | Unlimited | $0 |

No paid services required. wyby is a pure Python library.
