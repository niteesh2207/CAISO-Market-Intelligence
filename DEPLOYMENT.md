# Deployment — July 26, 2026

## Deployment model

This repository intentionally separates two surfaces:

### 1. GitHub Pages — public portfolio preview

Source: `site/`

Workflow: `.github/workflows/pages.yml`

GitHub Pages is static hosting. GitHub's official documentation states that Pages publishes HTML/CSS/JavaScript and **does not support server-side languages such as Python**.

Expected project URL:

`https://niteesh2207.github.io/CAISO-Market-Intelligence/`

### 2. GitHub Codespaces — full live research application

The repository contains `.devcontainer/devcontainer.json`.

Add a GitHub Codespaces repository secret:

`OPENAI_API_KEY`

Then create a codespace. Port `8000` is forwarded automatically and the FastAPI application starts when the secret is present.

Codespaces secrets are encrypted development-environment secrets supplied as environment variables. Forwarded ports are private by default; GitHub allows changing a forwarded port to public visibility when policy permits.

## Production hosting

Codespaces is useful for development/demo. For an always-on public application, deploy the same Dockerfile to a proper backend host.

Do not use GitHub Pages to expose `OPENAI_API_KEY`.
