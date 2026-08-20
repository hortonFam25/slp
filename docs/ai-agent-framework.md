# SLPPro AI Agent Framework (Current Implementation)

This document describes the current AI agent framework in the SLPPro codebase so another developer or AI agent can continue building without reverse engineering.

---

## 1) High-Level Architecture

The AI stack uses a supervisor + specialist pattern built on the OpenAI Python Agents SDK.

- **Supervisor agent** receives each chat turn and delegates to specialist tools.
- **Specialists** are full agents configured up front with their own toolsets:
  - `StudentReadSpecialist` (read-only data/Q&A)
  - `ProgressNotesSpecialist` (read + write tools for note drafting/saving)
- **FastAPI service layer** orchestrates:
  - chat/session persistence
  - privacy redaction/hydration
  - runtime invocation of the supervisor
- **AI-specific database tables** store chat history and saved notes.
- **Frontend chat UI** interacts with `/api/ai-chat` endpoints.

Core entry points:

- Backend API router: `backend/app/routers/ai_chat.py`
- Backend service orchestration: `backend/app/services/ai_chat_service.py`
- Supervisor build: `backend/app/ai/orchestrator.py`
- Specialist tool wrapping: `backend/app/ai/tools/agent_tools.py`
- Specialist factories:
  - `backend/app/ai/specialists/student_read_agent.py`
  - `backend/app/ai/specialists/progress_notes_agent.py`
- Tool definitions:
  - Read tools: `backend/app/ai/tools/read_tools.py`
  - Write tools: `backend/app/ai/tools/write_tools.py`

---

## 2) OpenAI SDK Usage and References

Primary SDK primitives currently used:

- `Agent` (build model runtime units)
- `Runner.run_sync(...)` (execute agents synchronously)
- `@function_tool` (register callable tools for agents)
- `set_default_openai_key(...)` (explicit key wiring for Agents SDK client)

Relevant project docs:

- Agents SDK overview: https://openai.github.io/openai-agents-python/
- Agents SDK tools: https://openai.github.io/openai-agents-python/tools/
- Model/API compatibility guidance: https://developers.openai.com/api/docs/guides/latest-model

Current model defaults in app settings:

- `ai_model = "gpt-5.2"`
- `ai_reasoning_effort = "low"`
- `ai_verbosity = "medium"`
- `ai_max_output_tokens = 100000`

Settings file: `backend/app/settings.py`

Note: the current `create_agent(...)` wrapper centralizes model defaults and ensures the API key is passed to Agents SDK through `set_default_openai_key(...)` in `backend/app/ai/factory.py`.

---

## 3) Agent Construction Pattern

## 3.1 Shared Agent Factory

File: `backend/app/ai/factory.py`

- `create_agent(...)` is the single constructor for all framework agents.
- It calls `configure_agents_openai()` once (cached) to set key for SDK client.
- It returns `Agent(name=..., model=..., instructions=..., tools=...)`.

## 3.2 Supervisor (Orchestrator)

File: `backend/app/ai/orchestrator.py`

- `build_supervisor_agent(tools=[...])` builds `SLPProSupervisor`.
- Supervisor instructions explicitly tell it to delegate to specialists and return specialist output.

## 3.3 Specialist Creation

Files:

- `backend/app/ai/specialists/student_read_agent.py`
- `backend/app/ai/specialists/progress_notes_agent.py`

Pattern:

1. Resolve student alias context
2. Build tools inside specialist constructor
3. Pass instructions + tools to `create_agent(...)`

Progress notes specialist additionally:

- Loads template from `backend/app/ai/templates/progress_note_template.md` (cached)
- Embeds template in agent instructions
- Instructs tool usage order for first-pass testing:
  1. `get_student_year_plan_context`
  2. `get_student_therapy_dataset`
  3. `get_prior_saved_progress_notes`

---

## 4) Tool System Design

## 4.1 Why tools are wrapped at orchestrator level

File: `backend/app/ai/tools/agent_tools.py`

- `build_specialist_tools(...)` creates fully configured specialist agents up front.
- It exposes orchestrator-callable function tools:
  - `student_read_specialist(question: str)`
  - `progress_notes_specialist(request: str)`
- Each wrapper sanitizes input and executes specialist via `Runner.run_sync(...)`.

This gives a clean supervisor tool surface while keeping specialist internals encapsulated.

## 4.2 Read Tools

File: `backend/app/ai/tools/read_tools.py`

Important implementation detail:

- Every tool opens its own `SessionLocal()` database session and closes it in `finally`.
- This was done to avoid SQL Server/pyodbc busy-connection concurrency issues.

Current read tools:

- `get_student_year_plan_context()`
- `get_student_profile()`
- `get_student_goals_and_objectives()`
- `get_student_therapy_sessions(limit=20)`
- `get_student_therapy_dataset()`
- `get_student_progress_snapshot(limit=50)`
- `get_prior_saved_progress_notes(limit=10)`

Behavior notes:

- Legacy `objective_progress_entries` are intentionally excluded from current testing output in `get_student_progress_snapshot()`.
- `get_student_therapy_dataset()` is the comprehensive evidence tool joining session records, session goals, and session objectives for full-year analysis.

## 4.3 Write Tools

File: `backend/app/ai/tools/write_tools.py`

Current write tools:

- `save_progress_note_draft(...)`
- `save_internal_agent_message(...)`

Both sanitize content and write to AI-specific tables.

---

## 5) Privacy Model (PII Handling)

File: `backend/app/ai/privacy.py`

Core privacy rule:

- Model-facing content should use student alias/ID, not student name.

Key functions:

- `build_alias_context(student_id, first_name, last_name)`
- `redact_student_name_from_value(value, ctx)`
- `hydrate_aliases_for_ui(text, ctx)`

Current flow:

1. User message enters service
2. Student names are redacted before model execution
3. Assistant output is stored as sanitized model content
4. Alias text is hydrated back to display name for UI output

This allows model isolation from direct student names while preserving readable UI.

---

## 6) Backend Request/Execution Flow

Primary file: `backend/app/services/ai_chat_service.py`

For `POST /api/ai-chat/sessions/{id}/messages`:

1. Load and validate session ownership
2. Build alias context from student
3. Save user message (`model_content` redacted, `ui_content` raw)
4. Build supervisor with specialist tool wrappers
5. Execute `Runner.run_sync(supervisor, input=sanitized_user_content)`
6. Redact assistant model output
7. Hydrate aliases for UI view
8. Persist assistant message with both model/ui content
9. Return `AIChatMessageRead`

Other important operations:

- Create/list sessions
- List/delete chat messages
- Save/list/update/delete saved progress notes

Router file with endpoints:

- `backend/app/routers/ai_chat.py`

Schemas:

- `backend/app/schemas/ai_chat.py`

---

## 7) Data Model and Persistence

AI-specific SQLAlchemy models:

- `backend/app/models/ai_chat_session.py` -> `ai_chat_sessions`
- `backend/app/models/ai_chat_message.py` -> `ai_chat_messages`
- `backend/app/models/ai_saved_progress_note.py` -> `ai_saved_progress_notes`

Repository abstraction:

- `backend/app/repositories/ai_chat_repository.py`

Important columns:

- `ai_chat_messages.model_content` (sanitized text)
- `ai_chat_messages.ui_content` (display text)
- `ai_saved_progress_notes.note_content` (sanitized persisted content)
- `student_alias` stored with sessions and notes for privacy-aware traceability

---

## 8) Frontend Integration

Key files:

- API client: `frontend/src/lib/api/aiChat.ts`
- State hook: `frontend/src/lib/hooks/useAIChat.ts`
- Chat page: `frontend/src/features/chat/Chat.tsx`

Current UX includes:

- Student selection + per-student session loading
- Chat send/receive
- Save/delete message actions
- "Save As" menu on assistant messages (currently first option: Progress Note)
- Copy assistant message
- Saved note editing/deletion flow
- Reusable themed confirmation modals for save/delete actions

---

## 9) Runtime and Bootstrapping Notes

- AI router is mounted in `backend/main.py` via `app.include_router(ai_chat.router)`.
- On backend startup, `Base.metadata.create_all(...)` still runs for local/dev convenience.
- Production should continue to rely on migrations and controlled schema management.

---

## 10) How To Add New Agent Capabilities

Recommended extension process:

1. **Define capability**: retrieval, transformation, or write side effect.
2. **Choose specialist**:
   - If read-only Q&A -> `StudentReadSpecialist`
   - If note-generation/refinement -> `ProgressNotesSpecialist`
   - If neither fits -> add a new specialist module.
3. **Add tool(s)** in `read_tools.py` or `write_tools.py`:
   - Use `@function_tool`
   - Open/close `SessionLocal()` inside each tool
   - Sanitize output with `redact_student_name_from_value(...)`
4. **Expose tool to specialist** by updating the specialist constructor.
5. **Adjust specialist instructions** for deterministic behavior when needed.
6. **If supervisor must delegate differently**, update `orchestrator.py` instructions and/or wrapped specialist tools in `agent_tools.py`.
7. **If UI needs it**, add endpoint + schema + API client + hook + component wiring.

---

## 11) Guardrails and Current Constraints

- Do not intentionally send student names to model-facing content.
- Keep AI data in AI-specific tables.
- Legacy objective progress entries are currently excluded from the active progress-note test flow.
- Prefer tool-grounded specialist output; avoid freeform hallucination.
- Keep specialist instructions explicit when deterministic tool calling is required.

---

## 12) Known Improvement Opportunities

Potential next steps (not yet implemented):

- Add persisted template management (DB-backed templates and template versions).
- Replace prompt-based note title inputs with structured save-as dialog metadata.
- Add structured telemetry around tool calls and execution latency.
- Add automated tests for tool payload shape and privacy redaction.
- Add stronger authorization checks tied to school/teacher assignments beyond current user/session ownership checks.

---

## 13) Quick Reference File Map

- `backend/app/ai/factory.py`
- `backend/app/ai/orchestrator.py`
- `backend/app/ai/privacy.py`
- `backend/app/ai/tools/agent_tools.py`
- `backend/app/ai/tools/read_tools.py`
- `backend/app/ai/tools/write_tools.py`
- `backend/app/ai/specialists/student_read_agent.py`
- `backend/app/ai/specialists/progress_notes_agent.py`
- `backend/app/services/ai_chat_service.py`
- `backend/app/routers/ai_chat.py`
- `backend/app/repositories/ai_chat_repository.py`
- `backend/app/schemas/ai_chat.py`
- `backend/app/models/ai_chat_session.py`
- `backend/app/models/ai_chat_message.py`
- `backend/app/models/ai_saved_progress_note.py`
- `backend/app/ai/templates/progress_note_template.md`
- `frontend/src/lib/api/aiChat.ts`
- `frontend/src/lib/hooks/useAIChat.ts`
- `frontend/src/features/chat/Chat.tsx`

