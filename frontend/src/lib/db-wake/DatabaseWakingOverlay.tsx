/**
 * The one thing a therapist actually sees when Azure SQL has gone to sleep.
 *
 * It replaces a raw "Network Error" toast and an instruction to refresh. The
 * copy is specific on purpose — "about 30-60 seconds after a quiet period" is
 * true, and a person who knows the wait is normal and bounded waits calmly,
 * where a person watching an unexplained spinner reloads and starts the clock
 * over.
 *
 * Two states:
 *
 * - **waiting** — a spinner, the attempt count, and a live elapsed counter.
 *   There is nothing to press because there is nothing useful to do; the
 *   interceptor is re-sending on its own and will dismiss this when it lands.
 * - **asking** — a write lost its connection and we will not re-send it without
 *   being told to, because it might already have been saved. Buttons, and copy
 *   that says exactly that rather than pretending it is a simple retry.
 *
 * Never mounted inside the login route's tree (see App.tsx): the MSAL redirect
 * must never be covered by a backdrop.
 */

import { useEffect, useState } from 'react';
import {
  Backdrop,
  Box,
  Button,
  CircularProgress,
  LinearProgress,
  Paper,
  Stack,
  Typography,
  useTheme,
} from '@mui/material';

import { useDbWakeStore } from './store';

/** Live "Xs elapsed", ticking only while the overlay is actually up. */
function useElapsedSeconds(startedAt: number | null): number {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (startedAt === null) {
      setElapsed(0);
      return;
    }
    const tick = () => setElapsed(Math.max(0, Math.round((Date.now() - startedAt) / 1000)));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [startedAt]);

  return elapsed;
}

export function DatabaseWakingOverlay() {
  const theme = useTheme();
  const waking = useDbWakeStore((s) => s.waking);
  const attempt = useDbWakeStore((s) => s.attempt);
  const startedAt = useDbWakeStore((s) => s.startedAt);
  const manualCount = useDbWakeStore((s) => s.manualRetries.length);
  const retryAllManual = useDbWakeStore((s) => s.retryAllManual);
  const dismissAllManual = useDbWakeStore((s) => s.dismissAllManual);

  const elapsed = useElapsedSeconds(waking ? startedAt : null);

  if (!waking) return null;

  const needsAHuman = manualCount > 0;

  return (
    <Backdrop
      open
      sx={{
        // Above dialogs and drawers — a modal form that keeps its own backdrop
        // must not sit on top of the explanation for why it is not responding.
        zIndex: theme.zIndex.modal + 10,
        backgroundColor: 'rgba(0, 0, 0, 0.55)',
        px: 2,
      }}
      // Not dismissible by clicking away: in the waiting state there is nothing
      // behind it that works yet, and in the asking state the question needs an
      // answer.
      role="status"
      aria-live="polite"
    >
      <Paper
        elevation={8}
        sx={{
          maxWidth: 460,
          width: '100%',
          p: 3,
          borderRadius: 2,
          // Backdrop forces a light-on-dark palette on its children; put the
          // Paper back on the theme's own surface colours.
          color: 'text.primary',
        }}
      >
        <Stack spacing={2}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            {!needsAHuman && <CircularProgress size={22} />}
            <Typography variant="h6" component="h2">
              {needsAHuman ? 'Lost connection to the database' : 'Waking up the database…'}
            </Typography>
          </Stack>

          {needsAHuman ? (
            <>
              <Typography variant="body2" color="text.secondary">
                The connection dropped while saving your change, so we cannot tell whether
                it was recorded. We have not sent it again on our own — that could save it
                twice.
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Check the record before retrying if you are not sure. Dismissing leaves
                everything as it is and shows the original error.
              </Typography>
            </>
          ) : (
            <>
              <Typography variant="body2" color="text.secondary">
                This takes about 30-60 seconds after a quiet period. The database pauses
                itself when nobody has used it for a while, and your work will continue on
                its own as soon as it is back — there is no need to refresh.
              </Typography>
              <Box>
                <LinearProgress sx={{ borderRadius: 1, height: 6 }} />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                  {attempt > 0 ? `Attempt ${attempt} · ` : ''}
                  {elapsed}s elapsed
                </Typography>
              </Box>
            </>
          )}

          {needsAHuman && (
            <Stack direction="row" spacing={1} justifyContent="flex-end">
              <Button onClick={dismissAllManual} color="inherit">
                Dismiss
              </Button>
              <Button onClick={retryAllManual} variant="contained" autoFocus>
                Try again
              </Button>
            </Stack>
          )}
        </Stack>
      </Paper>
    </Backdrop>
  );
}

export default DatabaseWakingOverlay;
