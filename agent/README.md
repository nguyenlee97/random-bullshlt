# Advertising Agent — Autonomous Ad Campaign Manager

> An AI agent that autonomously drives the full lifecycle of a display advertising campaign — from brief to live reporting — built on **GreenNode AgentBase** and **GreenNode MaaS**.

---

## Demo

**Live agent:** https://agent.pawgrammers.io.vn  
**API health:** https://agent-api.pawgrammers.io.vn/health  
**AdsPilot platform:** https://adspilot.pawgrammers.io.vn

---

## Problem

Running a display ad campaign today is a multi-tool, multi-step process that forces ad ops teams to manually:

1. Define the campaign brief (brand, KPIs, budget, schedule)
2. Select and configure ad zones (placements across news, entertainment, music sites)
3. Upload and assign creative assets (banners, video, native) per format and size
4. Set up audience targeting (DMP segments, demographic layers)
5. Monitor live performance and generate weekly analytical reports
6. Export and email reports to stakeholders

Each step is manual, siloed, and error-prone. Campaign managers spend 60-70% of their time on coordination, not strategy.

---

## Solution

**Advertising Agent** is a conversational AI agent that supports both a guided campaign workflow and a durable Campaign Autopilot — making grounded decisions, populating the workspace, requesting human review, generating insights, and delivering the final PDF report to stakeholders via email.

### How it works

```
User ─── Chat ──► Agent (FastAPI + GreenNode MaaS)
                      │
                      ├─ Brief Step      → validates KPIs, brand, budget, timeline
                      ├─ Creative Step   → AI image generation + format assignment
                      ├─ Audience Step   → DMP segment recommendation
                      ├─ Setup Step      → auto-assigns zones, calls AdsPilot API
                      ├─ Report Step     → polls analytics, generates AI insights (6 tabs)
                      └─ Email Step      → generates PDF, sends via Resend
                                               │
                                         AdsPilot API (Express + MongoDB)
```

### Key capabilities

| Capability | Detail |
|---|---|
| **Conversational campaign setup** | Step-by-step guided chat, with auto-advance on confirmation |
| **AI creative generation** | Direct OpenAI GPT Image 2 with named assets, exact-format safe zones and a durable 20-output daily actor quota |
| **AI analytics (6 tabs)** | Daily Ops, Awareness, Consideration, Conversion, Retention, Executive |
| **PDF report generation** | Server-side via pdfkit — no headless browser required |
| **Email delivery** | Resend API — PDF + optional CSV/JSON raw data |
| **Real-time polling** | Frontend polls report status every 3s with progress indicator |
| **Conversation engines** | Independent, immutable per-run GreenNode MiniMax or OpenAI GPT-5.4-mini components; no cross-provider fallback |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Agent Frontend (React + Vite)                                  │
│  agent.pawgrammers.io.vn                                        │
│  ├─ 6-step WorkspacePane (Brief/Creative/Audience/Setup/Report/Email) │
│  └─ Chat panel (streaming agent messages + suggestion chips)    │
└────────────────────┬────────────────────────────────────────────┘
                     │ REST
┌────────────────────▼────────────────────────────────────────────┐
│  Advertising Agent  ◄── THIS REPO                               │
│  FastAPI · Python 3.11 · Port 8080                              │
│  agent-api.pawgrammers.io.vn                                    │
│  ├─ router.py        (6-step state machine)                     │
│  ├─ handlers/        (brief / creative / audience / setup /     │
│  │                    report / email)                           │
│  ├─ llm.py           (GreenNode MaaS — minimax-m2.5)            │
│  └─ session.py       (MongoDB-backed conversation memory)       │
└────────┬───────────────────────────┬────────────────────────────┘
         │ REST                      │ REST
┌────────▼──────────┐   ┌───────────▼──────────────────────────┐
│  AdsPilot Backend  │   │  GreenNode MaaS                      │
│  Express + MongoDB │   │  LLM_BASE_URL = maas-llm-aiplatform- │
│  api.pawgrammers.  │   │  hcm.api.vngcloud.vn/v1              │
│  io.vn             │   │  Model: minimax/minimax-m2.5         │
└────────────────────┘   └──────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Agent runtime** | FastAPI · Python 3.11 · Uvicorn |
| **Campaign LLMs** | Independent GreenNode MiniMax and OpenAI GPT-5.4-mini components, locked per conversation |
| **Session memory** | MongoDB (Motor async driver) |
| **AI report generation** | Fixed OpenAI GPT-5.4-mini specialist with report-evidence-v1 metric contracts |
| **PDF generation** | pdfkit (server-side, no puppeteer) |
| **Email delivery** | Resend API |
| **Image generation** | Direct OpenAI GPT Image 2; GPT-5.4-nano visual QA |
| **Frontend** | React 18 · Vite · Recharts · Tailwind |
| **Ad platform** | AdsPilot (Express + MongoDB) |
| **Deployment** | GreenNode AgentBase Custom Agent Runtime |

---

## Deploy on GreenNode AgentBase

This agent is deployed as a **Custom Agent** on GreenNode AgentBase — a Docker image pushed to the AgentBase Container Registry and served as a managed runtime.

### Prerequisites

- GreenNode IAM service account credentials (`GREENNODE_CLIENT_ID`, `GREENNODE_CLIENT_SECRET`)
- Docker installed locally
- Access to `vcr.vngcloud.vn` (AgentBase Container Registry)

### Step 1 — Login to Container Registry

```bash
export GREENNODE_CLIENT_ID="your-client-id"
export GREENNODE_CLIENT_SECRET="your-client-secret"

bash .claude/skills/agentbase-deploy/scripts/cr.sh credentials docker-login
```

### Step 2 — Get your registry repo info

```bash
bash .claude/skills/agentbase-deploy/scripts/cr.sh repo get
# Note: registryUrl (vcr.vngcloud.vn) and repoName
```

### Step 3 — Build & push image

```bash
# Build for linux/amd64 (required by AgentBase)
docker build --platform linux/amd64 \
  -t vcr.vngcloud.vn/<your-repo>/camp-ads-agent:latest .

docker push vcr.vngcloud.vn/<your-repo>/camp-ads-agent:latest
```

### Step 4 — Create runtime

```bash
bash .claude/skills/agentbase-deploy/scripts/runtime.sh create \
  --name "camp-ads-agent" \
  --image "vcr.vngcloud.vn/<your-repo>/camp-ads-agent:latest" \
  --flavor "1x1-general" \
  --env-file .env.production \
  --from-cr \
  --min-replicas 1 \
  --max-replicas 2 \
  --cpu-scale 70 \
  --mem-scale 70
```

### Step 5 — Verify

```bash
# Get your endpoint URL
bash .claude/skills/agentbase-deploy/scripts/runtime.sh endpoints list <runtime-id>

# Health check
curl https://<endpoint-url>/health
# → {"status": "ok", "version": "2026-06-17.39"}
```

### Environment variables

The container reads from `.env` at startup. See `.env.example` for all variables.

| Variable | Required | Description |
|---|---|---|
| `AI_PLATFORM_API_KEY` | ✅ | GreenNode MaaS API key |
| `LLM_BASE_URL` | ✅ | GreenNode MaaS endpoint |
| `LLM_MODEL` | ✅ | `minimax/minimax-m2.5` |
| `BACKEND_URL` | ✅ | AdsPilot API URL |
| `MONGODB_URI` | ✅ | MongoDB connection string |
| `OPENAI_API_KEY` | ✅ | For report AI analysis |
| `AGENT_PORT` | — | Default: `8080` (AgentBase contract) |

> **Auto-injected by AgentBase Runtime** — do NOT set in `.env`:  
> `GREENNODE_CLIENT_ID`, `GREENNODE_CLIENT_SECRET`, `GREENNODE_AGENT_IDENTITY`, `GREENNODE_ENDPOINT_URL`

---

## Local Development

```bash
# 1. Clone and install deps
git clone https://github.com/your-org/camp-ads-agent
cd camp-ads-agent
pip install -r requirements.lock
# Required by the live-ad screenshot feature. Re-run after Playwright upgrades.
python -m playwright install chromium

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Start agent
uvicorn main:app --reload --port 8080

# 4. Health check
curl http://localhost:8080/health
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | AgentBase health check (returns 200) |
| `GET` | `/api/health` | Detailed health with version + features |
| `POST` | `/api/agent/chat` | Main chat endpoint (streaming) |
| `POST` | `/api/agent/reset` | Reset session state |
| `GET` | `/api/agent/session` | Get current session form state |

---

## Project Structure

```
agent/
├── main.py            # FastAPI app, health endpoints, CORS
├── router.py          # 6-step state machine + intent routing
├── config.py          # Environment configuration
├── llm.py             # GreenNode MaaS LLM client (OpenAI-compatible)
├── models.py          # Pydantic request/response models
├── session.py         # MongoDB-backed session + conversation memory
├── handlers/
│   ├── brief.py       # Step 1: Campaign brief extraction
│   ├── creative.py    # Step 2: AI image generation + assignment
│   ├── audience.py    # Step 3: DMP audience recommendation
│   ├── setup.py       # Step 4: Zone setup + AdsPilot API
│   ├── report.py      # Step 5: Analytics polling + AI insights
│   └── email.py       # Step 6: PDF + Resend email delivery
├── prompts/           # System + step-specific LLM prompts
├── tools/             # Agent tool definitions
├── Dockerfile         # Port 8080, linux/amd64
├── .dockerignore
├── .env.example
└── requirements.txt
```

---

## Benefits of Running on GreenNode AgentBase

| Benefit | Detail |
|---|---|
| **Always on** | Lives on GreenNode infrastructure — not a personal machine |
| **Auto-scaling** | Scales from 1-2 replicas based on CPU/memory thresholds |
| **GreenNode MaaS** | Uses `minimax-m2.5` via the integrated AI Platform — no external API key needed for LLM |
| **Container Registry** | Fully integrated — no DockerHub account needed |
| **Managed networking** | Public HTTPS endpoint auto-provisioned |
| **IAM service account** | Auto-injected credentials for platform services |

---

## Team

Built for **Claw-a-thon 2026** — GreenNode × VNG Group internal AI hackathon.
