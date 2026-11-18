![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-Chromium-2EAD33?logo=playwright&logoColor=white)
![MongoDB Atlas](https://img.shields.io/badge/MongoDB-Atlas-47A248?logo=mongodb&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

<!-- Banner: add docs/banner.png and uncomment -->
<!-- ![Caramelo](docs/banner.png) -->

# 🐕 Caramelo API

> The guard dog that lives in grandma's phone. This is where Caramelo opens suspicious links far from her device and does online chores together with her, asking permission first.

Backend of **Caramelo**, an assistant that protects and helps older adults in Brazil. Built for the FIAP Global Solution 2026 (CitizenTech). The client lives in [`caramelo-app`](https://github.com/evamyuu/caramelo-app).

## 📖 About

| Capability | Status | Endpoint |
| --- | --- | --- |
| Isolated link scan (disposable headless browser, explainable score) | Real | `POST /api/v1/links/scan` |
| Secure co-browsing with consent gate and credential handover | Real | `WS /api/v1/secure-session` |
| Call risk score (weighted, explainable signals) | Real scoring, simulated call | `POST /api/v1/calls/assess` |
| Anonymous scam insights (MongoDB aggregation) | Real | `GET /api/v1/insights/summary` |
| Assistant chat | Real when an LLM key is set | `POST /api/v1/assistant/chat` |
| Carrier SIM Swap (CAMARA) and Open Finance balance | Stubs in the real payload shape | `GET /api/v1/accounts/balance` |

Interactive docs: `http://localhost:8000/docs`.

## 🏗️ Architecture

```
app/
├── main.py            Application factory and lifespan (composition root)
├── config.py          Settings from environment variables
├── api/               HTTP/WebSocket layer
│   ├── router.py        API v1 aggregation
│   ├── routers/         One router per module: guard, companion, insights, secure_session, system
│   ├── dependencies.py  Dependency injection (repositories)
│   └── schemas.py       Request models
├── services/          Business rules: risk scoring, link scanner, secure session
├── ai/                AI layer
│   ├── client.py        Model-agnostic entry point with deterministic fallback
│   ├── prompts.py       Every prompt, in one reviewed place
│   └── providers/       Strategy per vendor: Anthropic, Gemini
├── db/                Persistence
│   ├── mongo.py         Atlas client lifecycle
│   └── repositories/    Repository contract + MongoDB and in-memory implementations
├── integrations/      Partner APIs (carrier, Open Finance) behind stubs
└── core/              Browser launcher
demo_sites/            Fictitious pages used by the demo and e2e tests
tests/                 Unit and end-to-end tests
docs/                  Architecture notes
```

Design decisions:

- **Layered, dependencies point inward.** Routers call services; services depend on protocols (`EventRepository`, `LLMProvider`), never on a vendor.
- **Open for extension.** A new model vendor is one class in `ai/providers`; a new storage is one repository.
- **AI never decides safety.** Verdicts, consent and credentials are enforced in code. The model only words explanations and suggests navigation steps, and the service works with no model at all (`rules` mode).
- **Privacy by design.** Risk events carry no phone number, URL or user id, and expire through a TTL index. Passwords typed during a handover are forwarded to the page and never logged or sent to a model.

More in [`docs/architecture.md`](docs/architecture.md) and [`SECURITY.md`](SECURITY.md).

## 🛠️ Technologies

- **FastAPI + Uvicorn**: async HTTP and WebSocket
- **Playwright (Chromium)**: disposable browser sessions
- **MongoDB Atlas (PyMongo Async)**: risk events, `$facet` aggregation, TTL index, Stable API v1
- **Anthropic / Gemini**: pluggable LLM, optional
- **Pytest + Ruff**: tests and linting
- **Docker + GitHub Actions**: container and CI

## 🚀 How to Run

Prerequisites: Python 3.11+.

```bash
git clone https://github.com/evamyuu/caramelo-api.git
cd caramelo-api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env
uvicorn app.main:app --reload
```

Or with Docker (API + local MongoDB): `docker compose up --build`.

| Variable | Purpose | Default |
| --- | --- | --- |
| `GEMINI_API_KEY` | Free-tier LLM | empty (`rules` mode) |
| `ANTHROPIC_API_KEY` | Takes precedence over Gemini | empty |
| `MONGODB_URI` | Atlas connection string | empty (in-memory) |
| `CORS_ORIGINS` | Allowed web origins | `http://localhost:5173` |

Tests and lint: `pytest` and `ruff check .`

## 🤝 How to Contribute

1. Create a branch: `git checkout -b feat/short-description`
2. Follow [Conventional Commits](https://www.conventionalcommits.org)
3. Run `ruff check . && pytest` before opening a pull request

## 👥 Team

| [<img src="https://github.com/evamyuu.png" width="80" alt="evamyuu" />](https://github.com/evamyuu) |
| :---: |
| [evamyuu](https://github.com/evamyuu) |

## 📄 License

[MIT](LICENSE)

---

Made with 🤎 by the Caramelo team
