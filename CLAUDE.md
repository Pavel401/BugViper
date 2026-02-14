# CLAUDE.md - BugViper

## Project Overview

BugViper is a full-stack AI-powered code review and repository intelligence platform. It ingests repositories into a Neo4j graph database via Tree-sitter AST parsing (17 languages), then uses multi-agent LLM pipelines to perform automated PR reviews (bug detection + security auditing). The frontend is a Next.js dashboard for repository management, code search, and graph exploration.

**Status**: Work In Progress (Alpha)

## Tech Stack

### Backend (Python 3.13+)
- **Framework**: FastAPI + Uvicorn
- **Package Manager**: uv (lockfile: `uv.lock`)
- **Database**: Neo4j (graph database)
- **Code Parsing**: Tree-sitter (17 language parsers)
- **AI/LLM**: Pydantic AI + OpenRouter
- **GitHub**: PyGithub + GitHub App webhooks
- **Firebase**: firebase-admin SDK
- **Observability**: Logfire

### Frontend (Node.js)
- **Framework**: Next.js 16 (App Router) + React 19
- **Language**: TypeScript (strict mode)
- **Styling**: TailwindCSS 4 + shadcn/ui (Radix primitives)
- **Icons**: Lucide React

## Project Structure

```
api/                    # FastAPI backend
├── app.py              # Entry point, CORS, router registration
├── dependencies.py     # DI (Neo4j client injection)
├── models/schemas.py   # Pydantic request/response models
├── routers/            # REST endpoints
│   ├── ingestion.py    #   POST /repository, /setup
│   ├── query.py        #   GET /search, /stats, /code-finder/*
│   ├── repository.py   #   GET/DELETE repositories
│   └── webhook.py      #   POST /onPush, /onComment, /github
├── services/           # Business logic
│   ├── review_service.py   # PR review pipeline orchestration
│   └── push_service.py     # Incremental push handling
└── utils/              # Helpers (comment_formatter, graph_context)

db/                     # Neo4j database layer
├── client.py           # Connection management + retry logic
├── ingestion.py        # Graph ingestion service
├── queries.py          # CodeQueryService (search, stats, CRUD)
└── schema.py           # Constraints, indexes, schema init

deepagent/              # AI agent system
├── config.py           # Agent config (models, temperature)
├── prompts.py          # System prompts (bug-hunter, security-auditor)
└── agent/
    └── review_pipeline.py  # Multi-agent parallel execution + dedup

ingestion/              # Code parsing & ingestion engine
├── repo_ingestion_engine.py  # Main orchestrator (AdvancedIngestionEngine)
├── graph_builder.py          # Graph construction from parsed ASTs
├── github_client.py          # GitHub API interactions
├── code_search.py            # Code search functionality
├── language_query.py         # Language-specific queries
├── languages/                # Per-language Tree-sitter parsers (17 files)
├── handlers/                 # Indexing, analysis, management handlers
├── core/                     # Database helpers, job management
└── utils/                    # tree_sitter_manager, debug_log

common/                 # Shared utilities
├── diff_parser.py      # Unified diff parsing
└── bugviper_firebase_service.py  # Firebase integration

frontend/               # Next.js 16 frontend
├── app/                # App Router pages
│   ├── layout.tsx      #   Root layout + sidebar
│   ├── page.tsx        #   Dashboard (repo stats)
│   ├── query/page.tsx  #   Code search interface
│   └── repositories/page.tsx  # Repo management + ingestion
├── components/         # React components
│   ├── sidebar.tsx     #   Navigation
│   └── ui/             #   shadcn/ui components (15+)
└── lib/
    ├── api.ts          # API client
    └── utils.ts        # Utilities
```

## Commands

### Run Everything
```bash
./start.sh              # Starts API + Frontend + Ngrok
```

### Backend
```bash
uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd frontend && npm run dev     # Dev server on :3000
cd frontend && npm run build   # Production build
cd frontend && npm run lint    # ESLint
```

### Python Quality
```bash
pytest                  # Run tests
pytest --cov            # With coverage
black .                 # Format code
ruff check .            # Lint
mypy .                  # Type check
```

## Coding Conventions

### Python
- Line length: 100 (Black + Ruff)
- Full type annotations (Pydantic models everywhere)
- Classes: PascalCase, functions: snake_case, constants: UPPER_SNAKE_CASE
- Linting rules: E, F, I, W (Ruff)
- Async/await for API handlers

### TypeScript/React
- Strict mode enabled
- `"use client"` directive on client components
- Import alias: `@/*` maps to project root
- Components: PascalCase filenames

### API Design
- RESTful routes under `/api/v1/{resource}/{action}`
- API version: v0.2.0
- Auto-docs at `/docs` (Swagger) and `/redoc`

## Environment Variables

Key variables (see `.env.example` for full list):
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` - Database
- `OPENROUTER_API_KEY` - LLM provider
- `CONTEXT_MODEL`, `REVIEW_MODEL` - Model selection
- `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY_PATH`, `GITHUB_WEBHOOK_SECRET` - GitHub App
- `ENABLE_LOGFIRE`, `LOGFIRE_TOKEN` - Observability

## Architecture Notes

- **Layered backend**: Routers → Services → Queries → Neo4j Client
- **Multi-agent reviews**: Bug-hunter + Security-auditor run in parallel, results deduplicated
- **Incremental ingestion**: Push webhooks trigger partial graph updates (not full re-ingestion)
- **Graph model**: 14+ node types with constraints and full-text indexes
- **17 language parsers**: Each in `ingestion/languages/` with Tree-sitter queries

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/ingest/repository` | Ingest a repository |
| POST | `/api/v1/ingest/setup` | Initialize DB schema |
| GET | `/api/v1/query/search` | Full-text code search |
| GET | `/api/v1/query/stats` | Graph statistics |
| GET | `/api/v1/repositories/` | List repositories |
| POST | `/api/v1/webhook/onPush` | GitHub push webhook |
| POST | `/api/v1/webhook/onComment` | GitHub PR comment webhook |
