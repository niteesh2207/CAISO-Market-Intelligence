# CAISO Market Intelligence — Live Research V3

This is the first version of the project that is designed to **research the web at question time** instead of returning canned answers.

## What changed

Every `/api/ask` request:

1. classifies the market question;
2. resolves the current Pacific Time context;
3. searches current high-authority web sources;
4. prioritizes CAISO/OASIS, BPA, NRC, FERC/EIA/CEC/CPUC, utilities and weather authorities;
5. uses reputable market-news sources only as secondary context;
6. broadens the search automatically if the authority-constrained pass is too weak;
7. returns a concise answer plus URLs actually consulted.

The backend uses the OpenAI **Responses API** with the hosted `web_search` tool.

As of **2026-08-06**, OpenAI's model documentation lists the
`gpt-5.6` alias as supporting the Responses API and web search. See
the [official OpenAI model documentation](https://developers.openai.com/api/docs/models).

## Important limitation

This package can become live once deployed with a valid `OPENAI_API_KEY`.

It includes public-source executors for CAISO OASIS prices, EIA
operating data, NRC reactor status and citation-aware research. It
does **not** include:
- licensed ICE data;
- licensed Bloomberg/S&P/WoodMac/Argus/NGI feeds;
- private utility credentials;
- redistribution rights for proprietary market data.

Licensed premium feeds must be integrated only with valid customer
credentials and redistribution terms. Public research prioritizes
controlling and primary sources; reputable news is supporting context,
not a substitute for official numerical evidence.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export OPENAI_API_KEY="..."
uvicorn app:app --reload
```

Open:

`http://127.0.0.1:8000`

## Test locally

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

## Docker

```bash
docker build -t caiso-market-intelligence .
docker run -p 8000:8000 -e OPENAI_API_KEY="$OPENAI_API_KEY" caiso-market-intelligence
```

## Deploy

The included `render.yaml` is suitable as a starting point for Render.

A static GitHub Pages site is **not sufficient** for this version because API credentials must remain server-side.

## Recommended next data connectors

P0:
- CAISO OASIS constraint and outage queries
- CAISO generator/outage reports
- BPA 5-minute wind/load/interchange data

P1:
- NOAA/NWS structured weather
- FERC/CPUC/CEC retrieval
- SoCalGas / PG&E operational notices
- licensed premium market-data connectors where authorized


## GitHub deployment surfaces

### Public GitHub Pages preview

The `site/` folder is deployed by `.github/workflows/pages.yml`.

Expected URL after Pages is enabled:

`https://niteesh2207.github.io/CAISO-Market-Intelligence/`

This preview is intentionally static and does not make authenticated research calls.

### Full live demo in GitHub Codespaces

1. In repository **Settings → Secrets and variables → Codespaces**, add:
   - `OPENAI_API_KEY`
2. Create a codespace.
3. Port `8000` is forwarded by the devcontainer configuration.
4. Open the forwarded URL.

The full FastAPI app will research current web sources at question time.

## Baseline

Repository documentation, routing behavior and deployment assumptions
were re-verified on **August 6, 2026**.
