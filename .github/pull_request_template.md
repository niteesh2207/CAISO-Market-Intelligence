## Summary

Describe the user-visible and engineering changes.

## Trust and data controls

- [ ] Implemented capabilities are separated from roadmap items.
- [ ] Structured and web-research evidence are labelled correctly.
- [ ] No raw credentials, licensed data, or private connector details are included.
- [ ] Public exceptions are sanitized.

## Validation

- [ ] `python -m compileall -q app.py market_intelligence tests`
- [ ] `python -m ruff check app.py market_intelligence tests`
- [ ] `python -m pytest`
- [ ] Public README and API version are consistent.
