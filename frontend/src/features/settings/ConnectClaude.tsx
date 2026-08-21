/**
 * Connect Claude — the screen `docs/CONNECT_CLAUDE.md` keeps promising exists.
 *
 * Two jobs, in this order:
 *
 * 1. Tell the therapist what a connection actually is, because a connection key
 *    is equivalent to their sign-in and the page has to say so before it offers
 *    to mint one.
 * 2. Mint, list and revoke those keys.
 *
 * The one irreversible moment in the whole flow is the 201 body: `token` is the
 * only time the plaintext exists outside this browser, and the server keeps a
 * sha256 digest it cannot reverse. That is why the create dialog does not close
 * itself, why the value is rendered selectable rather than masked, and why the
 * warning sits above the value rather than below it.
 */

import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  IconButton,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { ContentCopy, Check, Add, DeleteOutline, Refresh } from '@mui/icons-material';
import { Plug } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  apiTokensApi,
  isTokenLimitError,
  tokenLimitMessage,
  MAX_MANUAL_TOKENS,
  type ApiToken,
  type ApiTokenCreated,
} from '../../lib/api/apiTokens';
import { apiClient } from '../../lib/api/client';

export const TOKENS_QUERY_KEY = ['api-tokens'] as const;

/**
 * The MCP endpoint, derived from whichever API this build talks to rather than
 * hard-coded — a developer running against localhost needs the localhost URL,
 * and a page that shows production's is a page that quietly wastes their
 * afternoon.
 */
function mcpUrl(): string {
  const base = (apiClient.defaults.baseURL || window.location.origin).replace(/\/+$/, '');
  return `${base}/mcp`;
}

function formatWhen(iso: string | null): string {
  if (!iso) return '—';
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** A copy button that says it worked, because a clipboard write is invisible. */
function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard permission denied, or a non-secure origin. The value is on
      // screen and selectable either way, so this is a convenience failing and
      // not a task failing.
      setCopied(false);
    }
  };

  return (
    <Tooltip title={copied ? 'Copied' : label}>
      <IconButton onClick={() => void copy()} size="small" aria-label={label}>
        {copied ? <Check fontSize="small" color="success" /> : <ContentCopy fontSize="small" />}
      </IconButton>
    </Tooltip>
  );
}

/** A fixed-width block with a copy button, for URLs and shell commands. */
function CodeBlock({ value, copyLabel }: { value: string; copyLabel: string }) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1.25,
        display: 'flex',
        alignItems: 'flex-start',
        gap: 1,
        bgcolor: 'action.hover',
      }}
    >
      <Box
        component="code"
        sx={{
          flex: 1,
          fontFamily: 'monospace',
          fontSize: '0.8125rem',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
          lineHeight: 1.6,
        }}
      >
        {value}
      </Box>
      <CopyButton value={value} label={copyLabel} />
    </Paper>
  );
}

export default function ConnectClaude() {
  const queryClient = useQueryClient();
  const url = useMemo(mcpUrl, []);

  const [createOpen, setCreateOpen] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);
  /** The plaintext, held ONLY between the 201 and the user closing the dialog. */
  const [minted, setMinted] = useState<ApiTokenCreated | null>(null);

  const [revokeTarget, setRevokeTarget] = useState<ApiToken | null>(null);
  const [revokeError, setRevokeError] = useState<string | null>(null);

  const {
    data: tokens,
    isLoading,
    isFetching,
    error: listError,
    refetch,
  } = useQuery({
    queryKey: TOKENS_QUERY_KEY,
    queryFn: () => apiTokensApi.listTokens(),
  });

  const createMutation = useMutation({
    mutationFn: (name: string) => apiTokensApi.createToken(name),
    onSuccess: (created) => {
      setMinted(created);
      setNewKeyName('');
      setCreateError(null);
      void queryClient.invalidateQueries({ queryKey: TOKENS_QUERY_KEY });
    },
    onError: (error: unknown) => {
      setCreateError(
        isTokenLimitError(error)
          ? tokenLimitMessage(error)
          : error instanceof Error
            ? error.message
            : 'Could not create that key.'
      );
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (id: number) => apiTokensApi.revokeToken(id),
    onSuccess: () => {
      setRevokeTarget(null);
      setRevokeError(null);
      void queryClient.invalidateQueries({ queryKey: TOKENS_QUERY_KEY });
    },
    onError: (error: unknown) => {
      setRevokeError(error instanceof Error ? error.message : 'Could not revoke that key.');
    },
  });

  const rows = tokens ?? [];
  const manualCount = rows.filter((t) => t.kind === 'manual').length;
  const atLimit = manualCount >= MAX_MANUAL_TOKENS;

  const closeCreateDialog = () => {
    setCreateOpen(false);
    setMinted(null);
    setNewKeyName('');
    setCreateError(null);
  };

  const claudeCodeCommand =
    `claude mcp add --transport http slppro \\\n  ${url} \\\n` +
    `  --header "Authorization: Bearer ${minted?.token ?? 'slp_your_key_here'}"`;

  return (
    <Box sx={{ p: { xs: 1.5, sm: 2 }, height: '100%', minHeight: 0, overflow: 'auto' }}>
      <Stack spacing={2.5} sx={{ maxWidth: 900 }}>
        <Typography
          component="h1"
          sx={{
            display: 'flex',
            alignItems: 'center',
            color: '#41AAB7',
            fontWeight: 700,
            gap: 1.25,
            fontSize: { xs: '1.35rem', sm: '1.5rem' },
            lineHeight: 1.2,
          }}
        >
          <Plug size={24} />
          Connect Claude
        </Typography>

        <Typography variant="body1" color="text.secondary">
          Connecting Claude lets it read and — with your say-so — write against{' '}
          <strong>your own caseload</strong>: the same students, goals, objectives, sessions
          and schedule you see when you sign in here. It cannot see another therapist&apos;s
          caseload, and your access is re-checked live on every single call rather than baked
          in when the connection was made.
        </Typography>

        <Alert severity="warning">
          A connection key is equivalent to your SLP Pro login. Anyone holding it can read and
          write your caseload exactly as you can. Never paste one into a chat, a shared
          document, or a repository.
        </Alert>

        {/* ---------------------------------------------------------------- */}
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Option A — claude.ai custom connector
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              The point-and-click path, and the one most people want. You never see or store a
              key: claude.ai sends you here to sign in with your normal Microsoft account and
              keeps a key that refreshes itself for as long as the connector stays connected.
            </Typography>
            <Stack component="ol" spacing={0.5} sx={{ pl: 2.5, my: 1.5 }}>
              <Typography component="li" variant="body2">
                In claude.ai, go to <strong>Settings → Connectors → Add custom connector</strong>.
              </Typography>
              <Typography component="li" variant="body2">
                Enter the URL below.
              </Typography>
              <Typography component="li" variant="body2">
                Sign in when Claude redirects you here, and approve the consent screen.
              </Typography>
            </Stack>
            <CodeBlock value={url} copyLabel="Copy connector URL" />
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              A connector that has been approved appears in the list below with kind
              <strong> oauth</strong>.
            </Typography>
          </CardContent>
        </Card>

        {/* ---------------------------------------------------------------- */}
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Option B — manual connection key
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Use this for Claude Code, or any other MCP client. Create a key below, then add
              the connector with it:
            </Typography>
            <CodeBlock
              value={
                `claude mcp add --transport http slppro \\\n  ${url} \\\n` +
                `  --header "Authorization: Bearer slp_your_key_here"`
              }
              copyLabel="Copy Claude Code command"
            />
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              You can hold up to {MAX_MANUAL_TOKENS} manual keys at a time.
            </Typography>
          </CardContent>
        </Card>

        <Divider />

        {/* ---------------------------------------------------------------- */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 2,
            flexWrap: 'wrap',
          }}
        >
          <Typography variant="h6">Your connection keys</Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            <Tooltip title="Refresh">
              <span>
                <IconButton
                  onClick={() => void refetch()}
                  disabled={isFetching}
                  aria-label="refresh connection keys"
                >
                  <Refresh />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip
              title={
                atLimit
                  ? `You already have ${MAX_MANUAL_TOKENS} manual keys. Revoke one first.`
                  : ''
              }
            >
              <span>
                <Button
                  variant="contained"
                  startIcon={<Add />}
                  onClick={() => setCreateOpen(true)}
                  disabled={atLimit}
                >
                  Create key
                </Button>
              </span>
            </Tooltip>
          </Stack>
        </Box>

        {listError && (
          <Alert severity="error">
            {listError instanceof Error ? listError.message : 'Could not load your keys.'}
          </Alert>
        )}
        {revokeError && (
          <Alert severity="error" onClose={() => setRevokeError(null)}>
            {revokeError}
          </Alert>
        )}

        {isLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : rows.length === 0 ? (
          <Card variant="outlined">
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                No connection keys yet. Add the connector in claude.ai (Option A), or create a
                key here for Claude Code (Option B).
              </Typography>
            </CardContent>
          </Card>
        ) : (
          <TableContainer component={Paper} variant="outlined">
            <Table size="small" aria-label="Your connection keys">
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Key</TableCell>
                  <TableCell>Kind</TableCell>
                  <TableCell>Created</TableCell>
                  <TableCell>Last used</TableCell>
                  <TableCell align="right">Revoke</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((token) => (
                  <TableRow key={token.id} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight={600}>
                        {token.name}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {token.prefix}…
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={token.kind === 'oauth' ? 'claude.ai' : 'manual'}
                        color={token.kind === 'oauth' ? 'primary' : 'default'}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{formatWhen(token.createdAt)}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color={token.lastUsedAt ? 'text.primary' : 'text.secondary'}>
                        {token.lastUsedAt ? formatWhen(token.lastUsedAt) : 'never'}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Revoke this key">
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => {
                            setRevokeError(null);
                            setRevokeTarget(token);
                          }}
                          aria-label={`Revoke ${token.name}`}
                        >
                          <DeleteOutline fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        <Typography variant="caption" color="text.secondary">
          A revoked key is kept on record as revoked rather than removed, so its name and
          history stay readable — it just no longer authenticates anything. The full write-up,
          including how caseload imports work without Claude ever seeing your spreadsheet, is in
          the project&apos;s <Box component="code" sx={{ fontFamily: 'monospace' }}>docs/CONNECT_CLAUDE.md</Box>.
        </Typography>
      </Stack>

      {/* ------------------------------------------------------------------ */}
      {/* Create key                                                          */}
      <Dialog
        open={createOpen}
        onClose={minted ? undefined : closeCreateDialog}
        maxWidth="sm"
        fullWidth
        aria-labelledby="create-key-title"
      >
        <DialogTitle id="create-key-title">
          {minted ? 'Copy your new key now' : 'Create a connection key'}
        </DialogTitle>
        <DialogContent dividers>
          {minted ? (
            <Stack spacing={2}>
              <Alert severity="warning">
                This is the only time this key will ever be shown. Copy it now — nothing on the
                server can produce it again, and a key you lose has to be revoked and replaced.
              </Alert>
              <CodeBlock value={minted.token} copyLabel="Copy connection key" />
              <Typography variant="body2" color="text.secondary">
                Add it to Claude Code with:
              </Typography>
              <CodeBlock value={claudeCodeCommand} copyLabel="Copy Claude Code command" />
            </Stack>
          ) : (
            <Stack spacing={2}>
              <DialogContentText>
                Name the key after the thing that will hold it — “my laptop”, “Claude Code” —
                so the list below means something later.
              </DialogContentText>
              {createError && <Alert severity="error">{createError}</Alert>}
              <TextField
                autoFocus
                fullWidth
                label="Key name"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && newKeyName.trim() && !createMutation.isPending) {
                    createMutation.mutate(newKeyName.trim());
                  }
                }}
                inputProps={{ maxLength: 80 }}
                helperText="Up to 80 characters."
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          {minted ? (
            <Button variant="contained" onClick={closeCreateDialog}>
              I&apos;ve copied it
            </Button>
          ) : (
            <>
              <Button onClick={closeCreateDialog} disabled={createMutation.isPending}>
                Cancel
              </Button>
              <Button
                variant="contained"
                onClick={() => createMutation.mutate(newKeyName.trim())}
                disabled={!newKeyName.trim() || createMutation.isPending}
              >
                {createMutation.isPending ? 'Creating…' : 'Create key'}
              </Button>
            </>
          )}
        </DialogActions>
      </Dialog>

      {/* ------------------------------------------------------------------ */}
      {/* Revoke                                                              */}
      <Dialog
        open={Boolean(revokeTarget)}
        onClose={() => (revokeMutation.isPending ? undefined : setRevokeTarget(null))}
        maxWidth="sm"
        fullWidth
        aria-labelledby="revoke-key-title"
      >
        <DialogTitle id="revoke-key-title">Revoke “{revokeTarget?.name}”?</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2}>
            <DialogContentText>
              {revokeTarget?.kind === 'oauth'
                ? 'This key belongs to a claude.ai connector. Revoking it disconnects that connection entirely — its refresh chain is cut at the same time, so the connector cannot quietly issue itself a replacement. You will have to add the connector again in claude.ai to reconnect.'
                : 'This key stops working immediately. Anything using it — Claude Code, a script — loses access until you create a new key and reconfigure it. Nothing else is affected.'}
            </DialogContentText>
            <Alert severity="info">
              Your caseload is untouched. Revoking a key only removes a way in.
            </Alert>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setRevokeTarget(null)} disabled={revokeMutation.isPending}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={() => revokeTarget && revokeMutation.mutate(revokeTarget.id)}
            disabled={revokeMutation.isPending}
          >
            {revokeMutation.isPending ? 'Revoking…' : 'Revoke key'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
