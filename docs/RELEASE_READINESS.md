# Public Release Readiness

Use this checklist before placing the repository in LinkedIn Featured or announcing it publicly.

## Repository contract

- [ ] README, `/health`, `/api/status`, OpenAPI title, screenshots, and social preview all say **V4.0.0**.
- [ ] Implemented capabilities and planned connectors are separated.
- [ ] No claim suggests that licensed premium feeds are bundled.
- [ ] No claim suggests that web research is settlement-grade data.
- [ ] Demo questions have deterministic fixtures or clearly state that live answers may change.

## Engineering evidence

- [ ] CI is required on pull requests.
- [ ] All tests pass on Python 3.12.
- [ ] `allow_web_fallback=false` is covered by a contract test.
- [ ] Internal exceptions are logged server-side and sanitized client-side.
- [ ] A tagged release and changelog entry identify the public portfolio baseline.

## Security

- [ ] GitHub secret scanning and push protection are enabled.
- [ ] Dependabot is enabled for Python and GitHub Actions.
- [ ] Branch protection requires a pull request and passing checks.
- [ ] Deployment secrets are stored only in the hosting platform.
- [ ] Production deployments have authentication, authorization, rate limiting, audit logs, and request-size controls.

## Demo quality

- [ ] Public preview and API documentation work in an incognito browser.
- [ ] The preview does not request a user-supplied API key in browser code.
- [ ] Empty, ambiguous, unsupported, stale, and provider-failure states are demonstrated.
- [ ] Social preview image is readable at LinkedIn card size.

## LinkedIn publication gate

Publish only after all repository-contract and engineering-evidence items are complete. Production security items can remain roadmap items only when the repository is explicitly labelled **engineering alpha** and the public deployment is appropriately isolated.
