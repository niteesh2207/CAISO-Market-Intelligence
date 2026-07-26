# Security

- `OPENAI_API_KEY` must exist only in the server environment.
- Never put API keys in `static/index.html`, GitHub Pages, browser JavaScript, or public JSON.
- ICE, Bloomberg, S&P Global, Wood Mackenzie, Argus, NGI, etc. require appropriate licenses for premium/private content. Public web search does **not** equal licensed premium-feed access.
- Add authenticated connectors server-side when commercial licenses are available.
- Rate-limit `/api/ask` before public deployment.
- Add authentication before exposing expensive Deep mode publicly.
