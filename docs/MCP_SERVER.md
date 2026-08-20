# MCP server — developer reference

The `/mcp` endpoint is SLP Pro's machine door: a Model Context Protocol
server exposing one therapist's caseload — students, IEP goals, objectives,
progress entries, therapy sessions, and schedule — to an MCP-speaking agent
like Claude. This document is for developers working on it. For the
user-facing "how do I connect" guide, see
[`docs/CONNECT_CLAUDE.md`](CONNECT_CLAUDE.md).

Source: `backend/app/mcp/server.py` (tools), `backend/app/mcp/auth.py`
(the auth door), `backend/app/mcp/__init__.py` (exports),
`backend/app/routers/oauth_public.py` (OAuth 2.1 facade),
`backend/app/routers/api_tokens.py` (manual key management),
`backend/app/services/api_tokens.py` (key scheme).

---

## Architecture

### Stateless FastMCP, not a session per connection

`mcp_server = FastMCP(SERVER_NAME, instructions=..., stateless_http=True,
json_response=True)`. No SSE, no server-held session state: every call
carries its own `Authorization` header and is answered on the spot. This is
what lets the app run as an ordinary Azure worker that can be recycled
between two calls from the same agent — there's no in-memory session to lose.

### A `ContextVar`, not a FastAPI dependency

`/mcp` is not a FastAPI route. `FastMCP`'s Starlette sub-application is
handed to Starlette as a mount, and tool bodies are invoked directly by the
MCP SDK — several frames below anything this app wrote, with no `Request`
object to hang `Depends(get_db)` off of. So instead:

- `app/mcp/auth.py`'s `McpAuthMiddleware` resolves the caller (see below)
  and stashes an `McpPrincipal` in a `ContextVar` (`_CURRENT`).
- Tool bodies call `current_principal()` (aliased as `_ctx()` in
  `server.py`) to read it back. This works because the MCP SDK's
  per-request task group inherits the context the middleware set it in.
- Each tool also opens its **own** SQLAlchemy session via `_session()`
  (`SessionLocal()`), for the same reason — no request-scoped session
  exists to inject.

### Why the middleware owns the path, not a `Mount`

`FastMCP`'s Starlette app carries its route at `/mcp`. Starlette's `Mount`
only matches `/mcp/<something>` — a bare `POST /mcp` (which is exactly what
`claude mcp add ... /mcp` sends) would fall through and answer 404/405.
`McpAuthMiddleware` intercepts the request **before** routing, normalizes
both `/mcp` and `/mcp/` onto the SDK's expected path, authenticates, and
only then hands off to the SDK's ASGI app.

### Why `lifespan` matters

```python
async with mcp_server.session_manager.run():
    yield
```

in `backend/main.py`'s `lifespan`. `FastMCP`'s session manager runs inside an
`anyio` task group that something has to enter — and the ASGI app handed to
the middleware is a Starlette sub-application whose own lifespan is never
invoked by the outer app. Skip this and the first `POST /mcp` fails with
`"task group is not initialized"`.

### DNS-rebinding protection is turned off, deliberately

```python
_TRANSPORT_SECURITY = TransportSecuritySettings(enable_dns_rebinding_protection=False)
```

The SDK's DNS-rebinding guard defaults on when it thinks it's serving
localhost, and its allow-list is localhost-only — which would answer `421`
to every request in production, where the `Host` header is the Azure
hostname. Turning it off is safe here specifically because the protection
exists to stop a browser page from driving a local MCP server using
*ambient* credentials (e.g. a cookie), and this endpoint has none of those —
it accepts exactly one credential, an `slp_` bearer token, that no browser
attaches on its own and that CORS would never forward automatically.

### Same repositories, same schemas, same access rules as the REST API

Tools call the identical repository classes and Pydantic schemas the REST
routers use (`ProgressEntryRepository`, `ObjectiveProgressEntryRead`, etc.),
and repeat the same access checks. There is no MCP-only data path — a rule
added to the API is a rule the agent gets too, on the same deploy.

---

## Token model

Two kinds of `slp_` bearer key exist, sharing one table and one validation
path (`app/services/api_tokens.py`):

| | manual | OAuth-issued |
| --- | --- | --- |
| minted by | `POST /api/tokens` (signed-in user) | the `/oauth/token` exchange |
| shown in full | once, in the mint response | once, to the connector, never to a human |
| lifetime | until revoked | 24h access token, rotating refresh token |
| cap | 10 live keys per user | none (bounded by TTL + revocability instead) |
| revoke | `DELETE /api/tokens/{id}` | same call — also kills the whole refresh-token family |

**Scheme** (`api_tokens.py`):

```
secret   "slp_" + secrets.token_hex(20)   -> "slp_" + 40 hex chars
prefix   secret[:12]                      -> display only, e.g. "slp_a1b2c3d4"
stored   sha256(secret).hexdigest()       -> looked up on every call
```

`sha256`, not a slow password KDF — the secret is 160 bits of `secrets`
randomness with no dictionary to defend against, and the digest is looked up
on *every* MCP call, where a deliberately slow hash would be a per-request
tax for no security gain.

**`resolve_principal(secret)`** (`app/mcp/auth.py`) is the single place a
key becomes an `McpPrincipal`. It opens its own session, resolves the token,
loads the user, checks `is_active`, re-derives `allowed_student_ids` via the
*same* `resolve_allowed_student_ids` helper the HTTP auth dependency uses
(`app/dependencies/auth.py`), and stamps `token.last_used_at`. Nothing about
a user's caseload is cached into the key — it's recomputed from the database
on every call, so a student removed from someone's access list disappears
from their view on the very next tool call, not on key rotation.

`McpPrincipal.may_see_student(student_id)` mirrors `access_control_mode`
exactly as the REST layer does: `off` allows everything, `enforce` denies
outside the allow-list, `monitor` logs a would-be denial and allows anyway.
Admins bypass the check entirely.

---

## OAuth 2.1 connector facade

Lets claude.ai (or any RFC-compliant MCP client) add SLP Pro as a connector
without a human ever copying a key. All endpoints are in
`backend/app/routers/oauth_public.py`, mounted first in `main.py` — ahead of
any future catch-all route — and `include_in_schema=False` (RFC paths for
machines, not therapist-facing API docs).

| method | path | RFC | auth | purpose |
| --- | --- | --- | --- | --- |
| GET | `/.well-known/oauth-protected-resource` | 9728 | none | protected-resource metadata |
| GET | `/.well-known/oauth-protected-resource/mcp` | 9728 | none | same, at the path derived from the resource URI — the one `/mcp`'s 401 challenge points at; both are served because clients differ on which they fetch |
| GET | `/.well-known/oauth-authorization-server` | 8414 | none | authorization-server metadata (issuer = `settings.public_origin`) |
| POST | `/oauth/register` | 7591 (DCR) | none | dynamic client registration — public clients only (`token_endpoint_auth_method: "none"`), PKCE required |
| GET | `/oauth/authorize` | 6749 + PKCE | none | validates `client_id`/`redirect_uri` against the DCR registration, then 302s the browser to the SPA's consent page with the original query forwarded verbatim |
| POST | `/oauth/token` | 6749 | none (public client, PKCE stands in) | exchanges an authorization code, or refreshes, for an `slp_` key |
| POST | `/api/oauth/consent` | — | session (`require_session_auth`) | the human "Approve" — mints a single-use, 10-minute authorization code bound to (client, redirect, PKCE challenge, this user) |
| POST | `/api/oauth/consent/deny` | — | session | the human "Deny" — redirects back with `error=access_denied` |

**Flow:** `/mcp` returns `401` with a `WWW-Authenticate` header naming
`resource_metadata` → client fetches the protected-resource document →
follows it to the authorization-server metadata → registers itself via DCR
→ sends the user's browser to `/oauth/authorize` → SLP Pro validates the
client/redirect and 302s to the SPA (`{consent_origin}/connect/authorize`)
→ user signs in via the app's normal Entra flow and approves on the consent
card (`frontend/src/features/connect/ConnectAuthorize.tsx`) → SLP Pro mints
an auth code → client exchanges it at `/oauth/token` for an `slp_` access
key (24h) + refresh token.

**The redirect target for `/oauth/authorize` on success is always
`settings.consent_url`** (`{consent_origin}/connect/authorize`) — read from
configuration (`SLP_FRONTEND_ORIGIN`), never derived from the incoming
request. A redirect target taken from the request would be an open redirect.
`client_id`/`redirect_uri` mismatches render an in-process HTML error page
instead of redirecting at all, per RFC 6749 §4.1.2.1 — the address that
failed verification is exactly the address it would be unsafe to send the
browser to.

The access token this flow produces is an ordinary `slp_` key — `/mcp`
needed no new code path to accept it.

---

## Environment variables

| variable | default | effect |
| --- | --- | --- |
| `SLP_PUBLIC_ORIGIN` | `https://slppro-api-a7caazgxa2gcaaaz.eastus2-01.azurewebsites.net` | This API's own canonical origin. Used to build the MCP resource URI (`{origin}/mcp`), the `resource_metadata` 401 challenge, and the OAuth issuer/discovery URLs. Read from env rather than the `Host` header on purpose — a spoofed `Host` must not be able to redirect discovery elsewhere. |
| `SLP_FRONTEND_ORIGIN` | environment-dependent (`http://localhost:3000` in dev, the deployed `slppro` host otherwise) | Where the OAuth consent page (`/connect/authorize`) lives. SLP Pro is split across two App Services, so this can't be inferred — it has to be configured explicitly. |
| `AUTH_JWT_VERIFY` | unset | `unset` = verify Entra JWT signatures unless `ENVIRONMENT=development`. Set explicitly (`1`/`0`) to override that default in either direction — e.g. to exercise the production validator locally against a real tenant. |
| `AAD_TENANT_ID` | `""` | The Entra tenant whose JWKS signs the access tokens the API's REST routes verify. Must be set correctly wherever `AUTH_JWT_VERIFY` resolves to true, or every signed-in request fails. |
| `AAD_API_AUDIENCE` | `api://604604d7-697a-4111-8845-a1bc1014bd49` | The audience an Entra access token must carry for the production validator to accept it. Override only if the app's registered API scope changes. |
| `ENVIRONMENT` | `development` | `development` enables `Base.metadata.create_all` on startup and relaxes the JWT-verify default (see above). Anything else assumes Alembic-managed schema and always verifies signatures. |
| `ACCESS_CONTROL_MODE` | `monitor` | `off` / `monitor` / `enforce` — how strictly `allowed_student_ids` is enforced, on both the REST routers and `/mcp`. |
| `SQL_SERVER_CONNECTION_STRING` | `sqlite:///./local.db` (via code fallback) | The database. Empty locally means a sqlite file in the working directory — see the local-dev caveat below. |

> **Production behavior change to flag when deploying this facade:** with
> `AUTH_JWT_VERIFY` unset, production now **signature-verifies** Entra JWTs
> against `AAD_TENANT_ID`'s JWKS (previously this may not have been
> enforced the same way). Confirm `AAD_TENANT_ID` is correct before
> shipping, and confirm the App Service has outbound HTTPS access to
> `login.microsoftonline.com` — the validator needs it to fetch JWKS. No new
> Entra redirect URI is needed for any of this; the frontend origin must
> remain a registered SPA redirect URI with `api://.../access_as_user`
> consented, same as before. The claude.ai OAuth callback registers
> dynamically with *this app's own facade* (`/oauth/register`) — it is never
> registered with Entra.

---

## Adding a new tool

Every tool in `server.py` follows the same shape. To add one:

```python
@tool()                           # NOT @mcp_server.tool() - see "PII filtering"
def my_new_tool(some_id: int, note: Optional[str] = None) -> dict:
    """
    One line an agent that's never seen this app can act on: what comes
    back, what the ids mean, which tool to call first/next.
    """
    db = _session()               # this call's own session — never Depends(get_db)
    try:
        ctx = _ctx()               # the McpPrincipal for this caller
        row = _load_goal(db, ctx, some_id)   # or write a similar _load_* helper —
                                              # it must raise/deny for a student
                                              # outside ctx.allowed_student_ids
        # ... call the SAME repository + Pydantic schema the REST router uses ...
        result = SomeRepository(db).do_the_thing(row.id, note)
        return _dump(SomeSchemaRead, result)
    finally:
        db.close()
```

Rules that keep this consistent with every other tool:

1. **Own session, own close.** `db = _session(); try: ... finally: db.close()`.
   Never assume a request-scoped session exists.
2. **Reuse the REST layer's repository and schema.** Don't hand-roll a
   dict or duplicate a query the router already has — reuse is what keeps
   the agent's view and the app's view from drifting apart. `_dump(schema,
   obj)` runs the object through the same Pydantic model the API returns.
3. **Check access before touching data.** Use or extend the `_load_*`
   helpers (`_load_goal`, `_load_objective`, `_load_entry`,
   `_load_session`) or `_require_student(ctx, student_id, what)` — every one
   of them raises a `ValueError` an agent can read ("Student N is not on
   your caseload…") rather than leaking a 403/404 distinction that would
   tell an agent whether an id exists.
4. **Write a docstring for an agent, not a teammate.** It's the tool
   description the MCP client shows the model. Say what comes back, what
   the ids mean, and which tool to call first or next.
5. **Destructive tools require `confirm: bool = False`.** Follow
   `delete_progress_entry` / `delete_goal`'s pattern exactly: refuse with a
   clear reason unless `confirm is True` (not truthy — literally `True`),
   and say so in the docstring so an agent asks a human first.
6. Update `SERVER_INSTRUCTIONS` at the top of `server.py` if the new tool
   changes the recommended starting point or the id hierarchy an agent
   should assume.
7. **Register with `@tool()`, never `@mcp_server.tool()`.** `@tool()` is the
   project-local decorator defined near the top of `server.py`; it registers
   with FastMCP *and* wraps the function in the PII filter.
   `backend/tests/test_mcp_pii.py` fails the build if any registered tool is
   missing the filter's marker.
8. **Add an `ARG_FACTORY` entry** in `backend/tests/test_mcp_pii.py` and run
   `pytest backend/tests`. See the checklist under "PII filtering" below.

---

## Local development

Standard backend setup applies (`backend/README.md`): `poetry install`,
`poetry run uvicorn app.main:app --reload`. With `ENVIRONMENT=development`
and no `SQL_SERVER_CONNECTION_STRING` set, the app falls back to a local
sqlite file and calls `Base.metadata.create_all()` on startup
(`backend/main.py`'s `lifespan`) instead of relying on Alembic.

**Known caveat — sqlite `create_all` and `GETDATE()`.** Most models declare
`server_default=text("GETDATE()")` for `created_date`/`modified_date`
columns — correct for Azure SQL, but `GETDATE()` doesn't exist in sqlite, so
the raw DDL sqlite executes for those tables fails with `near "(": syntax
error`. The **test suite** works around this today
(`backend/tests/conftest.py` installs a SQLAlchemy `before_cursor_execute`
hook, scoped to the sqlite dialect, that rewrites `GETDATE()` →
`CURRENT_TIMESTAMP` before the driver sees it) — but that shim lives in
`conftest.py` only. **It is not yet applied to the actual local-dev startup
path** (`backend/main.py`), so a fresh `local.db` created by just running
the app against sqlite can hit the same failure outside of pytest. A pending
fix task exists to either apply the same rewrite more generally or move the
affected columns to a portable default (`server_default=text("CURRENT_TIMESTAMP")`
or `func.now()`); until it lands, running against a real SQL Server /
Azure SQL connection string locally sidesteps the issue entirely, and is the
more reliable path if you hit it.

**Testing the MCP server locally:**

1. Run the API (`ENVIRONMENT=development`, `AUTH_REQUIRE_BEARER=false` gives
   you the anonymous fallback user).
2. Mint a key against your local instance: `POST /api/tokens` while signed
   in as (or falling back to) that local user.
3. Point a client at it:
   ```
   claude mcp add --transport http slppro-local http://localhost:8000/mcp \
     --header "Authorization: Bearer slp_..."
   ```
4. `get_caseload_overview` is the right first call to sanity-check a new
   local setup — it returns who the key resolves to and a snapshot of their
   caseload.

## Tool reference

25 tools total, grouped as the server itself groups them. Full parameter
lists and semantics live in each tool's docstring in `server.py` — this is
an index, not a spec.

**Read**
`get_caseload_overview`, `list_students`, `get_student`, `list_goals`,
`get_goal`, `list_objectives`, `list_progress_entries`,
`list_therapy_sessions`, `get_therapy_session`, `get_schedule`,
`list_schools`, `list_teachers`, `list_eligibility_categories`,
`list_goal_categories`.

**Write**
`create_progress_entry`, `update_progress_entry`, `create_goal`,
`update_goal`, `create_objective`, `update_objective`,
`create_therapy_session`, `complete_therapy_session`, `update_student`.

**Write — destructive (`confirm=True` required)**
`delete_progress_entry`, `delete_goal` (cascades: every objective and
progress entry under the goal goes with it).

## PII filtering

`/mcp` is an AI-facing door. What comes back through it is handed to a model,
may be quoted into a transcript, and may be retained by a vendor the district
never signed a DPA with. That is a different risk from the REST API, where the
reader is the therapist herself, sitting in front of the app that owns the
record — so the rule here is stricter than `app/routers/students.py` and has
**no owner exception**. `_should_mask_student_names()` shows real names to the
therapist who owns the caseload and masks only for admins and impersonators;
over MCP *every* caller is masked, including the owner, because the caller is
never really the therapist — it is a model acting on her behalf.

**Students are identified by alias, never by name.** `student_12`. The scheme
is the org's existing one (`app/ai/privacy.py`'s `build_student_alias`,
mirrored by `Student.alias`), so an alias an agent sees over MCP is the same
string the in-app AI chat uses and the same string `hydrate_aliases_for_ui`
turns back into a name *inside the app*, where that is allowed.

### The policy

Implemented in `backend/app/mcp/privacy.py`. Applied to every result and every
error of every tool.

**Removed, or replaced by the alias**

| What | How |
| --- | --- |
| `first`, `last`, and any camelCase/snake_case spelling | replaced by the alias when the surrounding object identifies its student (a sibling `studentId` / `student_alias` / `alias`), dropped otherwise |
| `student`, `student_name` / `studentName`, `studentFullName`, `studentDisplayName`, `studentFirstName`, `studentLastName` | same rule |
| `date_of_birth` / `dateOfBirth` / `dob` / `birthDate` | dropped outright — there is no useful aliased form of a DOB |
| `uic` (the state identifier) | dropped outright |
| **any student's first, last or full name appearing in ANY string, at any depth** | replaced by that student's alias |

A name field that cannot be attributed to a student is **dropped**, not kept —
an unattributable name is the worst case, not the harmless one.

That last table row is the one structure cannot reach: a name composed into a
progress comment, a session note, an objective description, or an error
message. It runs against **every** student in the database, not only the
caller's caseload — the names most worth catching are exactly the ones
belonging to students the caller may *not* see, e.g. a peer named inside an
accessible student's group-session note ("worked in a pair with Jane Doe").
Scoping the scrubber to `allowed_student_ids` would let that through by
construction.

**Kept — the clinical function has to survive**

Student `id` and `alias`, grade level, enrollment status, archived flag, all
six IEP dates, school / teacher / case-manager references and their ids,
eligibility categories, goal and objective text, progress entries, and all
therapy-session data.

### Policy constants

Both at the top of `backend/app/mcp/privacy.py`:

- **`REDACT_STAFF_NAMES = False`** — v1 does **not** strip teacher, case
  manager, school-contact or principal names. A teacher's name is
  *organisational* context (which adult owns this IEP, which classroom, which
  building), not student PII, and stripping it would make the schedule and the
  case-manager fields useless to an agent without protecting a student. If a
  district's DPA says otherwise this is a **one-line change** to `True`, which
  folds `_STAFF_NAME_KEYS` into the deny list;
  `test_staff_names_are_kept_in_v1` is the test that tells you the policy moved
  rather than something breaking by accident.
- **`MIN_REDACTABLE_NAME_LENGTH = 2`** — names shorter than this are not
  redacted from free text. Redaction also uses `\b` word boundaries, so a short
  surname cannot rewrite the middle of an unrelated word.

### How enforcement works

There is **one choke point**, not per-tool discipline.

`server.py` defines a project-local `@tool()` decorator. It registers with
FastMCP exactly as `@mcp_server.tool()` did, and additionally wraps the
function so that:

- its **return value** goes through `sanitize_tool_result()`;
- any **exception it raises** has its message run through
  `sanitize_error_message()` before it is re-raised (`from None`, so the
  original text cannot survive as a `__cause__` some formatter later prints).
  Error text is a real leak path: a message can compose a name, or — easier to
  miss — echo an argument the caller supplied, which is how a date parser turns
  into an exfiltration oracle;
- the wrapper carries `__pii_filtered__ = True`.

`functools.wraps` preserves the signature and the docstring, so FastMCP builds
the same schema and description a client saw before, and no tool signature
changed. The roster the scrubber redacts against is rebuilt per call from a
short session of its own — the same pattern tool bodies use — and is
**uncached**: a cached roster is a roster that can be stale, and a stale roster
is a name that does not get redacted. Failure is **closed** — if the roster
cannot be built, the exception propagates and the unfiltered result is
discarded rather than returned unscrubbed.

Two payload shapes are additionally fixed **at the source**, so an agent gets a
clean object rather than a record with holes where the names used to be. The
recursive sanitizer still runs over everything afterwards (belt and braces):

- `get_student` / `list_students` / `update_student` emit `alias` and
  `displayName` instead of `first` / `last` (`_student_identity`);
- `_AuthShim` — the stand-in `AuthContext` handed to the REST layer's
  `_build_session_response` / `_build_session_summary`, both of which compose a
  `student_name` field — always answers "mask", for every caller. `_student_label`
  likewise returns the alias unconditionally, with no caller branch.

### The drift tests

`backend/tests/test_mcp_pii.py`, run by CI on every PR
(`.github/workflows/ci.yml`). It is written to fail on the three realistic ways
this protection rots:

1. **Registry completeness** — walks the *live* FastMCP registry
   (`registered_tools()`, which exposes `Tool.fn`) and asserts every registered
   tool carries `__pii_filtered__`. A tool added with the raw
   `@mcp_server.tool()` fails here.
2. **ARG_FACTORY completeness** — the same registry walk asserts every
   registered tool has an entry in the module's `ARG_FACTORY` map (tool name ->
   callable producing valid args against the seeded data), and that no entry
   names a tool that no longer exists. A new tool nobody exercises is red CI.
3. **Every tool, every result** — seeds sqlite with two students carrying
   unmistakable sentinel PII (`Zebulonqx Vandergriff`, `Quixotellez Marchetti`,
   `UICSENTINEL123`, sentinel DOBs), one on the test principal's caseload and
   one deliberately off it, with the off-caseload student's name composed into
   the on-caseload student's goal and notes — then calls **every** registered
   tool and asserts over the full serialized JSON of each result: no sentinel
   substring (case-insensitive) and no denylisted key at any depth.

Plus error-path tests (a name passed as `progress_date`, which the parser
echoes back verbatim; an access-denied refusal), an alias-presence test so
utility is not silently traded away, and unit tests of the sanitizer itself
(recursion, idempotence, short-name safety).

### Checklist: adding a new tool

1. Register it with **`@tool()`** from `app/mcp/server.py` — never
   `@mcp_server.tool()`.
2. Add an **`ARG_FACTORY`** entry in `backend/tests/test_mcp_pii.py`, keyed by
   the tool's name, returning valid kwargs against the seeded data. Write tools
   may really write (the test DB is a throwaway sqlite file); destructive tools
   are called with `confirm=False`.
3. If the tool composes its own student-facing payload, use `_student_label()`
   or `_student_identity()` rather than emitting a name and relying on the
   sanitizer to take it back out.
4. Run:
   ```
   backend/venv/Scripts/python.exe -m pytest backend/tests -q
   backend/venv/Scripts/python.exe -m ruff check backend
   ```

---

## Related documentation

- [`docs/CONNECT_CLAUDE.md`](CONNECT_CLAUDE.md) — user-facing connection
  guide.
- [`docs/CICD.md`](CICD.md) — how changes to this server ship.
- [`docs/ai-agent-framework.md`](ai-agent-framework.md) — the separate
  in-app AI chat framework (OpenAI Agents SDK), not to be confused with this
  MCP server.
