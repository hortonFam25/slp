"""
The upload door: where a caseload spreadsheet enters WITHOUT touching the model.

This is a two-route router and it is the load-bearing part of the whole blind
import. Everything else in the feature is about not showing the model things;
this is the path by which those things arrive at all.

Why it is unauthenticated
-------------------------
It is not, quite: the URL IS the credential. `/import/upload/{token}` carries a
`slpu_` secret with 160 bits of `secrets` randomness, sha256 at rest, thirty
minutes of life, and exactly one use. What it deliberately does NOT require is
an Entra session, and that is the point -- the therapist may be uploading from
the school laptop that has the file on it rather than the one she is signed in
on, and a flow that demands a sign-in in the middle is a flow she abandons in
favour of pasting the spreadsheet into a chat window, which is the exact
outcome this feature exists to prevent.

The token buys ONE thing: the right to add rows to one empty batch belonging to
one user. It cannot read a batch, cannot list anything, and stops working the
moment the file lands.

Why the page is hand-written HTML
---------------------------------
No external assets, no CDN, no script. A page that pulls a stylesheet from
somewhere else is a page that tells somewhere else a therapist is uploading a
caseload right now, and a plain form POST needs none of it. The response to the
POST is a rendered result page for the same reason -- there is no JSON API here
to get out of sync with, and no JavaScript that has to be trusted with the
file.

`include_in_schema=False`: these are not API routes. They are two pages for one
human, and putting them in the OpenAPI document would advertise a credential
format to every reader of /docs for no benefit.
"""

from __future__ import annotations

import html
import logging

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services import blind_import
from app.services.blind_import import MAX_DATA_ROWS, MAX_UPLOAD_BYTES, UploadRejected

logger = logging.getLogger(__name__)

router = APIRouter(include_in_schema=False, tags=["blind-import"])

# 64 KiB at a time. The cap has to be enforced while READING rather than after,
# because "read it all and then check the length" is a way to be handed five
# gigabytes.
_CHUNK = 64 * 1024

_STYLE = """
  :root { color-scheme: light; }
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
         margin: 0; padding: 48px 20px; background: #f6f7f9; color: #17202b; }
  .card { max-width: 34rem; margin: 0 auto; background: #fff; border-radius: 14px;
          padding: 28px 30px; box-shadow: 0 1px 3px rgba(0,0,0,.12); }
  h1 { font-size: 1.25rem; margin: 0 0 .6rem; }
  p { line-height: 1.5; margin: 0 0 .8rem; }
  ul { line-height: 1.5; margin: 0 0 .9rem 1.1rem; padding: 0; }
  .muted { color: #5b6672; font-size: .9rem; }
  .ok { color: #14682f; font-weight: 600; }
  .bad { color: #a4242c; font-weight: 600; }
  input[type=file] { display: block; margin: 1rem 0; width: 100%; }
  button { font: inherit; padding: .55rem 1.15rem; border: 0; border-radius: 8px;
           background: #1f6feb; color: #fff; cursor: pointer; }
"""


def _page(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        content=(
            "<!doctype html>\n"
            '<html lang="en"><head><meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{html.escape(title)}</title>\n"
            f"<style>{_STYLE}</style></head>\n"
            f'<body><div class="card">{body}</div></body></html>'
        ),
        status_code=status_code,
        # A page whose URL is a one-shot credential must not sit in a proxy or
        # a back button.
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


def _problem(message: str, status_code: int) -> HTMLResponse:
    return _page(
        "SLP Pro - upload link",
        "<h1>This upload link cannot be used</h1>"
        f'<p class="bad">{html.escape(message)}</p>'
        '<p class="muted">Nothing was uploaded. Ask Claude to create a new '
        "import link and try again.</p>",
        status_code,
    )


@router.get("/import/upload/{token}", response_class=HTMLResponse)
def upload_page(token: str, db: Session = Depends(get_db)) -> HTMLResponse:
    """The form. Validating the token here means a dead link says so up front."""
    try:
        blind_import.resolve_upload_batch(db, token)
    except UploadRejected as rejected:
        return _problem(rejected.message, rejected.status_code)

    megabytes = MAX_UPLOAD_BYTES // (1024 * 1024)
    return _page(
        "SLP Pro - upload your caseload",
        "<h1>Upload your caseload spreadsheet</h1>"
        "<p>Choose the file and press Upload. It goes straight into SLP Pro.</p>"
        "<ul>"
        "<li>.xlsx or .csv</li>"
        f"<li>up to {megabytes} MB and {MAX_DATA_ROWS:,} rows</li>"
        "<li>every sheet in the workbook is read</li>"
        "</ul>"
        '<form method="post" enctype="multipart/form-data">'
        '<input type="file" name="file" accept=".xlsx,.csv" required>'
        '<button type="submit">Upload</button>'
        "</form>"
        '<p class="muted">This link works once and expires 30 minutes after it '
        "was created. Claude sees the structure of your file - how many columns, "
        "what shape the values are - and never the names, birthdays or "
        "identifiers in it.</p>",
    )


@router.post("/import/upload/{token}", response_class=HTMLResponse)
async def upload_submit(
    token: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """
    Take the file, parse every sheet, store the rows, spend the token.

    The order matters: the token is resolved BEFORE the body is read, so an
    expired link costs nothing, and the batch is only moved off
    `pending_upload` once the rows are safely stored -- a parse that fails
    leaves the link usable for the corrected file rather than burning it.
    """
    try:
        batch = blind_import.resolve_upload_batch(db, token)
    except UploadRejected as rejected:
        return _problem(rejected.message, rejected.status_code)

    try:
        content = await _read_capped(file)
        sheets = blind_import.parse_upload(file.filename or "", content)
        stored = blind_import.store_rows(db, batch, sheets, file.filename)
    except UploadRejected as rejected:
        db.rollback()
        return _problem(rejected.message, rejected.status_code)
    except Exception:
        db.rollback()
        # The message is not shown: whatever a parser says about a file it
        # could not read may quote the file.
        logger.exception("Blind import upload failed for batch %s", batch.id)
        return _problem(
            "That file could not be read. Check that it is a normal .xlsx or "
            ".csv export and try again.",
            400,
        )

    return _page(
        "SLP Pro - upload received",
        "<h1>Uploaded</h1>"
        f'<p class="ok">{stored:,} rows across {len(sheets)} sheet(s) are now '
        "staged in SLP Pro.</p>"
        "<p>Go back to Claude and carry on - it can see the structure of the "
        "file now and will propose how to read your columns.</p>"
        '<p class="muted">This link is now used up. You can close this tab.</p>',
    )


async def _read_capped(file: UploadFile) -> bytes:
    buffer = bytearray()
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > MAX_UPLOAD_BYTES:
            megabytes = MAX_UPLOAD_BYTES // (1024 * 1024)
            raise UploadRejected(
                f"That file is larger than {megabytes} MB. Remove any extra "
                f"sheets or split it, then upload again.",
                413,
            )
    if not buffer:
        raise UploadRejected("No file was chosen.")
    return bytes(buffer)
