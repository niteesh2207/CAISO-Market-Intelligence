## Summary

Describe the user-visible and engineering changes.

## Trust and data controls

- [ ] Implemented capabilities are separated from roadmap items.
- [ ] Structured and web-research evidence are labelled correctly.
- [ ] No raw credentials, licensed data, or private connector details are included.
- [ ] Public exceptions are sanitized.
- [ ] Public claims avoid unsupported live, production, accuracy, or premium-data assertions.
- [ ] Licensed sources use entitled server-side delivery only; authenticated or paywalled pages are not scraped.

## Validation

- [ ] `python -m compileall -q app.py market_intelligence tests`
- [ ] `python -m ruff check app.py market_intelligence tests`
- [ ] `python -m pytest`
- [ ] Public README and API version are consistent.
- [ ] `python -m pytest -q tests/test_public_release_assets.py`
- [ ] `node --check assets/preview.js` and `node --check static/app.js`
- [ ] Docker build and `/health` smoke test pass in CI.
