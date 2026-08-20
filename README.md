# SLP Pro

A caseload manager for speech-language pathologists: students, IEP goals,
objectives, progress entries, therapy sessions, and scheduling.

- **Backend** — FastAPI, in `backend/` (see `backend/README.md` for local
  setup and migrations).
- **Frontend** — React SPA, in `frontend/` (see `frontend/README.md` for
  dev scripts and env vars).
- **Deployed on Azure** as two App Services — `slppro-api` (backend) and
  `slppro` (frontend), in the `hortonfam` resource group.

## Documentation

- [**Connect Claude**](docs/CONNECT_CLAUDE.md) — for SLP Pro users: how to
  connect Claude to your caseload via `/mcp`, what it can see and do, and how
  to manage or revoke a connection key.
- [**MCP server**](docs/MCP_SERVER.md) — for developers: the `/mcp`
  server's architecture, the OAuth 2.1 connector facade, the token model,
  environment variables, how to add a new tool, and local dev notes.
- [**CI/CD**](docs/CICD.md) — the GitHub Actions pipeline: PR checks,
  label-gated auto-merge, and the Azure deploy, including the one-time OIDC
  setup.
- [AI agent framework](docs/ai-agent-framework.md) — the separate in-app AI
  chat feature (OpenAI Agents SDK), distinct from the MCP server above.
