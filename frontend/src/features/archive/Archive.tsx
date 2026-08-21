/**
 * The Archive — everything this app has hidden, and the button that puts it
 * back.
 *
 * One row per archive EVENT rather than per hidden record, because an event is
 * the unit a restore operates on: archiving a goal hid the goal, its objectives
 * and their progress entries under one id, and restoring that id brings exactly
 * that set back. A per-record list would invite the therapist to restore an
 * objective whose goal is still hidden, which the server refuses anyway.
 *
 * Two filters, both of which map straight onto query parameters the backend
 * already has: what kind of thing was archived, and whether to show events that
 * have already been put back. The second defaults to OFF — the common question
 * is "what is missing", not "what has ever been archived" — but the history is
 * one checkbox away because a restored event is an audit record, not litter.
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
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { Refresh, RestoreFromTrash } from '@mui/icons-material';
import { Archive as ArchiveIcon } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import {
  ARCHIVABLE_ENTITY_TYPES,
  CONTENT_LABELS,
  ENTITY_LABELS,
  archiveApi,
  type ArchivableEntityType,
  type ArchiveEventSummary,
} from '../../lib/api/archive';
import { ConfirmationModal } from '../../components/ui/ConfirmationModal';

/** Every query this page owns, so a restore can invalidate the lot. */
export const ARCHIVE_QUERY_KEY = ['archive', 'events'] as const;

/** "21 Aug 2026, 11:47" — or a dash, because `createdAt` is nullable. */
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

/** "progress entries" -> "progress entry". The labels are all regular or -ies. */
function singularize(plural: string): string {
  if (plural.endsWith('ies')) return `${plural.slice(0, -3)}y`;
  if (plural.endsWith('s')) return plural.slice(0, -1);
  return plural;
}

/** "1 goal, 3 objectives, 12 progress entries" — what the event still holds. */
function describeContents(contents: Record<string, number>): string {
  const parts = Object.entries(contents)
    .filter(([, count]) => count > 0)
    .map(([key, count]) => {
      const label = CONTENT_LABELS[key] ?? key;
      return `${count} ${count === 1 ? singularize(label) : label}`;
    });
  return parts.length ? parts.join(', ') : 'nothing (already restored)';
}

function entityLabel(type: string): string {
  return ENTITY_LABELS[type as ArchivableEntityType] ?? type;
}

export default function Archive() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const queryClient = useQueryClient();

  const [entityFilter, setEntityFilter] = useState<ArchivableEntityType | 'all'>('all');
  const [includeRestored, setIncludeRestored] = useState(false);

  const [confirmEvent, setConfirmEvent] = useState<ArchiveEventSummary | null>(null);
  const [restoring, setRestoring] = useState(false);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [restoreNotice, setRestoreNotice] = useState<string | null>(null);

  const filters = useMemo(
    () => ({
      include_restored: includeRestored,
      ...(entityFilter === 'all' ? {} : { root_entity_type: entityFilter }),
    }),
    [entityFilter, includeRestored]
  );

  const {
    data: events,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: [...ARCHIVE_QUERY_KEY, filters],
    queryFn: () => archiveApi.listEvents(filters),
  });

  const handleRestore = async () => {
    if (!confirmEvent) return;
    setRestoring(true);
    setRestoreError(null);
    try {
      const result = await archiveApi.restoreEvent(confirmEvent.eventId);
      setRestoreNotice(
        `Restored ${result.totalRows} ${result.totalRows === 1 ? 'record' : 'records'} ` +
          `from ${entityLabel(confirmEvent.rootEntityType).toLowerCase()} ` +
          `#${confirmEvent.rootEntityId}.`
      );
      setConfirmEvent(null);
      // Everything this restore could have put back on screen. Broad on
      // purpose: one event can span students, goals, sessions and appointments,
      // and a stale list that still hides a restored child is worse than a
      // refetch nobody notices. These are the query-key ROOTS actually in use
      // (see lib/hooks/*) -- a near-miss here invalidates nothing at all.
      await queryClient.invalidateQueries({ queryKey: ARCHIVE_QUERY_KEY });
      [
        'students',
        'goals',
        'appointments',
        'timeBlocks',
        'therapy-sessions',
        'scheduling-students',
      ].forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }));
    } catch (err) {
      // The most common failure is a 409 naming the parent event to restore
      // first, so the server's own message is the useful one.
      setRestoreError(err instanceof Error ? err.message : 'Could not restore that.');
    } finally {
      setRestoring(false);
    }
  };

  const rows = events ?? [];

  return (
    <Stack spacing={2} sx={{ p: { xs: 1.5, sm: 2 }, height: '100%', minHeight: 0 }}>
      <Box
        sx={{
          display: 'flex',
          flexDirection: isMobile ? 'column' : 'row',
          gap: isMobile ? 2 : 3,
          justifyContent: 'space-between',
          alignItems: isMobile ? 'stretch' : 'center',
        }}
      >
        <Typography
          component="h1"
          sx={{
            color: '#41AAB7',
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            gap: 1.25,
            fontSize: { xs: '1.35rem', sm: '1.5rem' },
            lineHeight: 1.2,
          }}
        >
          <ArchiveIcon size={24} />
          Archive
        </Typography>

        <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel id="archive-entity-filter-label">Type</InputLabel>
            <Select
              labelId="archive-entity-filter-label"
              id="archive-entity-filter"
              label="Type"
              value={entityFilter}
              onChange={(e) => setEntityFilter(e.target.value as ArchivableEntityType | 'all')}
            >
              <MenuItem value="all">All types</MenuItem>
              {ARCHIVABLE_ENTITY_TYPES.map((type) => (
                <MenuItem key={type} value={type}>
                  {ENTITY_LABELS[type]}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControlLabel
            control={
              <Switch
                checked={includeRestored}
                onChange={(e) => setIncludeRestored(e.target.checked)}
                inputProps={{ 'aria-label': 'Include events that have been restored' }}
              />
            }
            label="Show restored"
          />

          <Tooltip title="Refresh">
            <span>
              <IconButton onClick={() => void refetch()} disabled={isFetching} aria-label="refresh archive">
                <Refresh />
              </IconButton>
            </span>
          </Tooltip>
        </Stack>
      </Box>

      <Typography variant="body2" color="text.secondary">
        Nothing in SLP Pro is deleted. Archiving hides a record and everything under it;
        restoring an entry here brings back exactly what that entry hid — and nothing that
        was already archived before it.
      </Typography>

      {restoreNotice && (
        <Alert severity="success" onClose={() => setRestoreNotice(null)}>
          {restoreNotice}
        </Alert>
      )}
      {restoreError && (
        <Alert severity="error" onClose={() => setRestoreError(null)}>
          {restoreError}
        </Alert>
      )}
      {error && (
        <Alert severity="error">
          {error instanceof Error ? error.message : 'Could not load the archive.'}
        </Alert>
      )}

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress />
        </Box>
      ) : rows.length === 0 ? (
        <Card variant="outlined">
          <CardContent>
            <Typography variant="body1" color="text.secondary">
              {includeRestored
                ? 'No archive entries yet.'
                : 'Nothing is currently archived. Turn on “Show restored” to see entries that have been put back.'}
            </Typography>
          </CardContent>
        </Card>
      ) : (
        <TableContainer component={Paper} variant="outlined" sx={{ flex: 1, minHeight: 0 }}>
          <Table size="small" stickyHeader aria-label="Archive events, newest first">
            <TableHead>
              <TableRow>
                <TableCell>Type</TableCell>
                <TableCell>Archived</TableCell>
                <TableCell>Reason</TableCell>
                <TableCell>Contents</TableCell>
                <TableCell align="right">Restore</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((event) => (
                <TableRow key={event.eventId} hover>
                  <TableCell>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Typography variant="body2" fontWeight={600}>
                        {entityLabel(event.rootEntityType)}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        #{event.rootEntityId}
                      </Typography>
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{formatWhen(event.createdAt)}</Typography>
                    {event.restored && (
                      <Typography variant="caption" color="text.secondary">
                        restored {formatWhen(event.restoredAt)}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell sx={{ maxWidth: 260 }}>
                    <Typography variant="body2" color={event.reason ? 'text.primary' : 'text.secondary'}>
                      {event.reason || '—'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{describeContents(event.contents)}</Typography>
                  </TableCell>
                  <TableCell align="right">
                    {event.restored ? (
                      <Chip size="small" label="Restored" color="success" variant="outlined" />
                    ) : (
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<RestoreFromTrash />}
                        onClick={() => {
                          setRestoreError(null);
                          setConfirmEvent(event);
                        }}
                      >
                        Restore
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <ConfirmationModal
        open={Boolean(confirmEvent)}
        onClose={() => setConfirmEvent(null)}
        onConfirm={() => void handleRestore()}
        title="Restore from archive"
        message={
          confirmEvent
            ? [
                `Restore ${entityLabel(confirmEvent.rootEntityType).toLowerCase()} #${confirmEvent.rootEntityId}, archived ${formatWhen(confirmEvent.createdAt)}?`,
                '',
                `This brings back: ${describeContents(confirmEvent.contents)}.`,
                '',
                'Anything archived under an earlier entry stays archived — restoring this one will not resurrect work that was retired before it.',
              ].join('\n')
            : ''
        }
        confirmText="Restore"
        severity="info"
        loading={restoring}
        loadingText="Restoring..."
      />
    </Stack>
  );
}
