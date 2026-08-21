/**
 * "Goal archived. [UNDO]"
 *
 * Mounted once, in `App.tsx`, next to the database wake-up overlay. Every
 * archive in the application goes through `useArchiveWithUndo`, which writes to
 * the store this reads — so the undo affordance is identical whether the
 * therapist archived a goal from the student drawer, a session from the history
 * table, or a time block from the calendar.
 *
 * It renders nothing at all until something has been archived.
 */

import { Alert, Button, CircularProgress, Snackbar } from '@mui/material';

import { useArchiveUndoStore } from './store';

/** Long enough to notice and reach, short enough not to sit in the way. */
const AUTO_HIDE_MS = 8000;

export function ArchiveUndoSnackbar() {
  const pending = useArchiveUndoStore((s) => s.pending);
  const undoing = useArchiveUndoStore((s) => s.undoing);
  const error = useArchiveUndoStore((s) => s.error);
  const runUndo = useArchiveUndoStore((s) => s.runUndo);
  const dismiss = useArchiveUndoStore((s) => s.dismiss);

  if (!pending) return null;

  return (
    <Snackbar
      // Remount on every new offer so the auto-hide timer restarts rather than
      // inheriting the previous archive's remaining seconds.
      key={pending.key}
      open
      // A failed undo must stay put: its message is the only place the reason
      // ("restore the student first") is shown.
      autoHideDuration={error || undoing ? null : AUTO_HIDE_MS}
      onClose={(_event, reason) => {
        // Clicking anywhere on the page should not silently retire an undo the
        // user has not read yet.
        if (reason === 'clickaway') return;
        dismiss();
      }}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
    >
      <Alert
        severity={error ? 'error' : 'info'}
        variant="filled"
        // Announced without stealing focus. An error is assertive because the
        // thing the user asked for did not happen. No `onClose` here on
        // purpose: MUI's Alert drops its own close button whenever `action` is
        // given, and the explicit "Dismiss" below is the one that survives.
        role="status"
        aria-live={error ? 'assertive' : 'polite'}
        action={
          <>
            <Button
              color="inherit"
              size="small"
              onClick={() => void runUndo()}
              disabled={undoing}
              startIcon={undoing ? <CircularProgress size={14} color="inherit" /> : undefined}
            >
              {undoing ? 'Undoing' : 'Undo'}
            </Button>
            <Button color="inherit" size="small" onClick={dismiss} disabled={undoing}>
              Dismiss
            </Button>
          </>
        }
        sx={{ alignItems: 'center' }}
      >
        {error ? `Could not undo: ${error}` : pending.message}
      </Alert>
    </Snackbar>
  );
}
