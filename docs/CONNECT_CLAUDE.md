# Connecting Claude to SLP Pro

SLP Pro can act as a tool source for Claude: once connected, Claude can read
and (with your say-so) write against **your own caseload** — the same
students, goals, objectives, sessions and schedule you see when you sign in
to the app. Nothing more.

This is a real clinical-record connection, not a demo. Treat it with the same
care you'd give your SLP Pro password.

---

## What Claude can see and do

Every connection is scoped to **one SLP Pro user** — whoever created it. When
Claude calls into SLP Pro it is answered exactly as if that person were
signed in:

- It can see the students on your caseload, their IEP goals, the objectives
  under each goal, the progress entries logged against those objectives, your
  therapy session notes, and your appointment/schedule blocks.
- It **cannot** see another therapist's caseload. A student outside your
  access list doesn't come back as someone else's data — it comes back as
  "not found or not on your caseload." There is no way to hand Claude a
  student ID and have it work around that.
- It can write: log a progress entry, create or edit a goal or objective,
  create or complete a therapy session, update a student's administrative
  details. Before it does, it's expected to tell you what it's about to
  write and for whom — you're looking at a document a school's IEP paperwork
  gets built from.
- Two actions are destructive — deleting a progress entry and deleting a
  goal (which takes every objective and progress entry under that goal with
  it). Both refuse to run unless Claude explicitly confirms it, so a passing
  "delete that" can't silently wipe a record.
- It will **refuse a pasted roster**. If you paste caseload rows into the
  chat, Claude is instructed to stop and offer you an upload link instead —
  see [Importing your caseload from a spreadsheet](#importing-your-caseload-from-a-spreadsheet).
- Access is re-checked on **every single call**, live against the database —
  not baked into the connection when it was created. If your caseload
  changes, or your account is deactivated, that takes effect on Claude's very
  next request, not on some future re-authorization.

## How to connect

There are two ways to give Claude a connection. Pick whichever fits how
you're using Claude.

### Option A — claude.ai custom connector (recommended for most people)

This is the point-and-click path: add SLP Pro as a connector in claude.ai and
sign in with your normal SLP Pro/Microsoft account. No key to copy or store.

1. In claude.ai, go to **Settings → Connectors → Add custom connector**.
2. Enter this URL:
   ```
   https://slppro-api-a7caazgxa2gcaaaz.eastus2-01.azurewebsites.net/mcp
   ```
3. Claude will redirect you to SLP Pro to sign in (Microsoft/Entra sign-in,
   the same one the app itself uses) and show a consent screen naming the
   app that's asking for access.
4. Approve it. Claude now has an access key for your caseload that
   auto-refreshes for as long as the connector stays connected — you don't
   do anything further.

Behind the scenes: claude.ai discovers how to authenticate by reading the
`401`/`WWW-Authenticate` challenge SLP Pro's `/mcp` endpoint returns, follows
that to SLP Pro's OAuth metadata, registers itself automatically, and only
then sends you to the sign-in/consent page. You never see or handle a raw
key with this option.

### Option B — manual connection key (Claude Code, or any MCP-compatible client)

Use this if you're running Claude Code (or another MCP client) rather than
claude.ai, or you just want a key you control directly.

1. Sign in to SLP Pro.
2. Mint a key by calling the token endpoint while signed in:
   ```
   POST /api/tokens
   { "name": "My laptop" }
   ```
   The response includes `token` — a value starting with `slp_...`. **This is
   the only time the full key is ever shown.** If a "Connect Claude" screen
   exists in the app's Settings when you read this, use it instead — same
   endpoint, no other API call needed.
3. Add the connector in Claude Code:
   ```
   claude mcp add --transport http slppro \
     https://slppro-api-a7caazgxa2gcaaaz.eastus2-01.azurewebsites.net/mcp \
     --header "Authorization: Bearer slp_your_key_here"
   ```
4. You're connected. Claude now has the same caseload access described above.

You can hold up to 10 manual keys at a time — enough for a laptop, a phone,
and Claude, with room to spare.

## Managing and revoking keys

Every key you've created — manual or the one behind a claude.ai connector —
shows up in your connection-key list (`GET /api/tokens`, or the equivalent
screen in Settings once it's built). Each entry shows a name, a display
prefix (`slp_a1b2c3d4…`, never the full secret again), and when it was last
used.

To disconnect Claude, revoke the key:

```
DELETE /api/tokens/{id}
```

- Revoking a **manual key** stops that key immediately. Nothing else is
  affected.
- Revoking the key behind a **claude.ai connector** cuts the whole
  connection, not just that moment's access token — its refresh chain is
  killed at the same time, so the connector can't quietly issue itself a
  replacement. This is the correct way to disconnect claude.ai: nothing
  short of it reliably stops a connector that auto-refreshes.

A revoked key is kept on record as revoked (not deleted outright), so its
name and history stay visible — it just no longer authenticates anything.

## Importing your caseload from a spreadsheet

If your students are still in a spreadsheet — an export from your district's
IEP system, or a list you keep yourself — Claude can get them into SLP Pro
whatever the file's layout is, **without ever seeing what's in it**.

### Never paste a roster into chat

Say this first because it's the part that matters: **do not paste your
caseload, or rows from it, or a screenshot of it, into a conversation with
Claude.** A chat transcript is stored by the AI vendor. Children's names,
birthdays and state identifiers pasted into one are a permanent copy in a
place your district never signed an agreement about, and nothing you do
afterwards takes it back.

Claude is instructed to refuse a pasted roster and offer you an upload link
instead. If you paste one anyway and Claude works with it, that's a bug —
tell someone.

### How it actually works

1. **Ask Claude to import your caseload.** It creates an upload link and
   gives it to you. Nothing has been sent anywhere yet.
2. **Open the link in your own browser and upload the file** (`.xlsx` or
   `.csv`, up to 5 MB and 5,000 rows). The file goes straight from your
   machine to SLP Pro. It does not pass through Claude. The link works once
   and expires 30 minutes after it was created.
3. **Claude looks at the file's shape.** This is the part worth
   understanding. It does not get your data — it gets a description of what
   the data *looks like*. A column of surnames comes back as `Xxxxxxx`. A
   column of birthdays comes back as `##/##/####`. A "Last, First" column
   comes back as `Xxxxxxx, Xxxxx`. It also gets your **column headings**,
   because it can't work out which column is which without them.
4. **Claude proposes what each column means** and asks you to confirm —
   "column C looks like dates; is that the IEP date or the annual review?"
   You can see the spreadsheet; it can't. Correct it where it's wrong.
5. **Once you've agreed the mapping**, Claude can see real values from a
   short list of columns: school, teacher, case manager, grade level,
   enrollment status, the three IEP dates, and eligibility. Those name a
   building, an adult or a date — not a child. Names, dates of birth,
   identifiers and any free-text "notes" column stay hidden permanently, no
   matter what.
6. **Claude checks every row** and tells you about problems by row number:
   "row 14's birthday can't be read", "rows 6 and 22 have the same state ID",
   "row 9's school is 'Nrthgate El' — did you mean 'Northgate Elementary'?"
   It never quotes a child's details back at you as part of that.
7. **You approve, and Claude commits.** The students are created from the
   file on the server, with their real names and birthdays, and added to your
   caseload. What Claude gets back is a count and a list of aliases
   (`student_41`, `student_42`) — the same way it refers to every student.
8. **Ask Claude to discard the import.** This deletes the staged copy of your
   spreadsheet from the server. Your students stay; the raw file rows go.
   Do it as soon as you're happy with the result.

### Things worth knowing

- **Every sheet in the workbook is read**, including "Legend" tabs and the
  like. Claude will tell you which one it thinks holds the students.
- **Junk rows above the header are fine.** So are merged title cells, blank
  rows and formula cells (Claude sees the calculated value, never the
  formula).
- **Unknown schools and teachers stop the import.** SLP Pro will not invent a
  building or a staff member from a spelling in your spreadsheet — that's how
  a district ends up with three versions of the same school. Claude will show
  you the unfamiliar spelling and the closest match it already has, and you
  decide.
- **It's all or nothing.** If any row fails while students are being created,
  every student from that import is removed again. You will not get half a
  caseload.
- **The import is yours.** Nobody else, including an administrator, can see
  or act on a batch you started.

## Security notes

- **A connection key is equivalent to your SLP Pro login.** Anyone who has
  it can read and write your caseload exactly as you can, for as long as the
  key is valid. Don't paste it into chat, a shared doc, or a public repo.
- SLP Pro never accepts a key that doesn't belong to a real, active,
  signed-in-at-some-point user — a key can grant access to your data, never
  invent a new account or reach someone else's.
- The manual-key path (`Bearer slp_...`) is the **only** credential
  SLP Pro's `/mcp` endpoint accepts. Your everyday app sign-in token is
  deliberately not honored there — it expires hourly, which would make any
  agent using it useless a moment after you looked away.
- If a key is ever exposed or you're not sure what's holding it, revoke it
  and mint a new one. It costs you re-connecting Claude, nothing more.

## Related documentation

- [`docs/MCP_SERVER.md`](MCP_SERVER.md) — architecture and tool reference,
  for developers extending or debugging the server.
- [`docs/CICD.md`](CICD.md) — how a change to any of this ships to
  production.
