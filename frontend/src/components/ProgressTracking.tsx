import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Stack,
  Alert,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Grid,
  Divider
} from '@mui/material';
import {
  Add,
  Edit,
  Archive as ArchiveIcon,
  TrendingUp,
  Assessment,
  Notes,
  Person,
  DateRange
} from '@mui/icons-material';
import { goalsApi } from '../lib/api/goals';
import type {
  GoalObjective,
  ObjectiveProgressEntry,
  CreateProgressEntryRequest,
  UpdateProgressEntryRequest,
  SESSION_TYPE_OPTIONS
} from '../lib/api';
import { useArchiveWithUndo, archiveMessage, archiveTitle } from '../lib/archive';
import { ConfirmationModal } from './ui/ConfirmationModal';

interface ProgressTrackingProps {
  objective: GoalObjective;
  onProgressUpdate?: () => void;
}

export function ProgressTracking({ objective, onProgressUpdate }: ProgressTrackingProps) {
  const [progressEntries, setProgressEntries] = useState<ObjectiveProgressEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingEntry, setEditingEntry] = useState<ObjectiveProgressEntry | null>(null);

  const archiveWithUndo = useArchiveWithUndo();
  const [archiveTarget, setArchiveTarget] = useState<ObjectiveProgressEntry | null>(null);
  const [archiving, setArchiving] = useState(false);

  useEffect(() => {
    loadProgressEntries();
  }, [objective.id]);

  const loadProgressEntries = async () => {
    try {
      setLoading(true);
      setError(null);
      const entries = await goalsApi.getObjectiveProgressEntries(objective.id);
      setProgressEntries(entries);
    } catch (error) {
      console.error('Error loading progress entries:', error);
      setError('Failed to load progress entries');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateEntry = () => {
    setEditingEntry(null);
    setDialogOpen(true);
  };

  const handleEditEntry = (entry: ObjectiveProgressEntry) => {
    setEditingEntry(entry);
    setDialogOpen(true);
  };

  const handleArchiveConfirm = async () => {
    if (!archiveTarget) return;
    setArchiving(true);
    try {
      await archiveWithUndo({
        entity: 'progress_entry',
        name: archiveTarget.progress_date,
        archive: () => goalsApi.deleteProgressEntry(archiveTarget.id),
        onChanged: async () => {
          await loadProgressEntries();
          onProgressUpdate?.();
        },
      });
      setArchiveTarget(null);
      setError(null);
    } catch (error) {
      console.error('Failed to archive progress entry:', error);
      setError('Failed to archive progress entry');
    } finally {
      setArchiving(false);
    }
  };

  const handleSaveEntry = async (entryData: any) => {
    try {
      if (editingEntry) {
        await goalsApi.updateProgressEntry(editingEntry.id, entryData);
      } else {
        await goalsApi.createProgressEntry({
          ...entryData,
          objective_id: objective.id
        });
      }
      
      await loadProgressEntries();
      onProgressUpdate?.();
      setDialogOpen(false);
    } catch (error) {
      console.error('Failed to save progress entry:', error);
      setError('Failed to save progress entry');
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" p={2}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6" component="h3">
          Progress Tracking
        </Typography>
        <Button
          variant="outlined"
          size="small"
          startIcon={<Add />}
          onClick={handleCreateEntry}
        >
          Add Progress Entry
        </Button>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Progress Summary */}
      <Card variant="outlined" sx={{ mb: 2 }}>
        <CardContent>
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <Box display="flex" alignItems="center" mb={1}>
                <Assessment color="primary" sx={{ mr: 1 }} />
                <Typography variant="subtitle2">Total Entries</Typography>
              </Box>
              <Typography variant="h6">{progressEntries.length}</Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <Box display="flex" alignItems="center" mb={1}>
                <TrendingUp color="success" sx={{ mr: 1 }} />
                <Typography variant="subtitle2">Latest Progress</Typography>
              </Box>
              <Typography variant="body2">
                {progressEntries.length > 0
                  ? new Date(
                      Math.max(...progressEntries.map(e => new Date(e.progress_date).getTime()))
                    ).toLocaleDateString()
                  : 'No entries yet'
                }
              </Typography>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Progress Entries Table */}
      {progressEntries.length === 0 ? (
        <Card>
          <CardContent sx={{ textAlign: 'center', py: 4 }}>
            <Notes sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
            <Typography variant="h6" color="text.secondary" mb={1}>
              No Progress Entries Yet
            </Typography>
            <Typography color="text.secondary" mb={3}>
              Start tracking progress for this objective.
            </Typography>
            <Button variant="contained" startIcon={<Add />} onClick={handleCreateEntry}>
              Add First Entry
            </Button>
          </CardContent>
        </Card>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Date</TableCell>
                <TableCell>Progress</TableCell>
                <TableCell>Comments</TableCell>
                <TableCell>Therapist</TableCell>
                <TableCell>Session Type</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {progressEntries
                .sort((a, b) => new Date(b.progress_date).getTime() - new Date(a.progress_date).getTime())
                .map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell>
                      <Box display="flex" alignItems="center">
                        <DateRange fontSize="small" sx={{ mr: 1, color: 'text.secondary' }} />
                        {new Date(entry.progress_date).toLocaleDateString()}
                      </Box>
                    </TableCell>
                    <TableCell>
                      {entry.progress_on_objective && (
                        <Chip label={entry.progress_on_objective} size="small" />
                      )}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ maxWidth: 200 }}>
                        {entry.progress_comments
                          ? entry.progress_comments.length > 50
                            ? `${entry.progress_comments.substring(0, 50)}...`
                            : entry.progress_comments
                          : '-'
                        }
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {entry.therapist_initials && (
                        <Box display="flex" alignItems="center">
                          <Person fontSize="small" sx={{ mr: 1, color: 'text.secondary' }} />
                          {entry.therapist_initials}
                        </Box>
                      )}
                    </TableCell>
                    <TableCell>
                      {entry.session_type && (
                        <Chip label={entry.session_type} variant="outlined" size="small" />
                      )}
                    </TableCell>
                    <TableCell align="right">
                      <IconButton
                        size="small"
                        onClick={() => handleEditEntry(entry)}
                      >
                        <Edit fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        color="warning"
                        onClick={() => setArchiveTarget(entry)}
                        title="Archive entry"
                        aria-label="Archive progress entry"
                      >
                        <ArchiveIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Progress Entry Dialog */}
      <ProgressEntryDialog
        open={dialogOpen}
        entry={editingEntry}
        onClose={() => setDialogOpen(false)}
        onSave={handleSaveEntry}
      />

      <ConfirmationModal
        open={Boolean(archiveTarget)}
        onClose={() => setArchiveTarget(null)}
        onConfirm={() => void handleArchiveConfirm()}
        title={archiveTitle('progress_entry')}
        message={
          archiveTarget
            ? archiveMessage('progress_entry', `entry from ${archiveTarget.progress_date}`)
            : ''
        }
        confirmText="Archive"
        severity="warning"
        loading={archiving}
        loadingText="Archiving..."
      />
    </Box>
  );
}

// Progress Entry Dialog Component
interface ProgressEntryDialogProps {
  open: boolean;
  entry: ObjectiveProgressEntry | null;
  onClose: () => void;
  onSave: (entryData: CreateProgressEntryRequest | UpdateProgressEntryRequest) => Promise<void>;
}

function ProgressEntryDialog({ open, entry, onClose, onSave }: ProgressEntryDialogProps) {
  const [formData, setFormData] = useState({
    progress_date: entry?.progress_date || new Date().toISOString().split('T')[0],
    progress_on_objective: entry?.progress_on_objective || '',
    progress_comments: entry?.progress_comments || '',
    therapist_initials: entry?.therapist_initials || '',
    session_type: entry?.session_type || ''
  });

  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (entry) {
      setFormData({
        progress_date: entry.progress_date,
        progress_on_objective: entry.progress_on_objective || '',
        progress_comments: entry.progress_comments || '',
        therapist_initials: entry.therapist_initials || '',
        session_type: entry.session_type || ''
      });
    } else {
      setFormData({
        progress_date: new Date().toISOString().split('T')[0],
        progress_on_objective: '',
        progress_comments: '',
        therapist_initials: '',
        session_type: ''
      });
    }
  }, [entry, open]);

  const handleSubmit = async () => {
    try {
      setSubmitting(true);
      await onSave(formData);
    } catch (error) {
      console.error('Failed to save progress entry:', error);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {entry ? 'Edit Progress Entry' : 'Add Progress Entry'}
      </DialogTitle>
      <DialogContent>
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              type="date"
              label="Progress Date"
              value={formData.progress_date}
              onChange={(e) => setFormData({ ...formData, progress_date: e.target.value })}
              InputLabelProps={{ shrink: true }}
              required
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Progress on Objective"
              value={formData.progress_on_objective}
              onChange={(e) => setFormData({ ...formData, progress_on_objective: e.target.value })}
              placeholder="e.g., 80%, 3/5 trials, Met criteria"
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              multiline
              rows={4}
              label="Progress Comments"
              value={formData.progress_comments}
              onChange={(e) => setFormData({ ...formData, progress_comments: e.target.value })}
              placeholder="Detailed observations, strategies used, recommendations..."
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Therapist Initials"
              value={formData.therapist_initials}
              onChange={(e) => setFormData({ ...formData, therapist_initials: e.target.value })}
              placeholder="e.g., TH, JS"
              inputProps={{ maxLength: 10 }}
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>Session Type</InputLabel>
              <Select
                value={formData.session_type}
                onChange={(e) => setFormData({ ...formData, session_type: e.target.value })}
                label="Session Type"
              >
                <MenuItem value="">None</MenuItem>
                {SESSION_TYPE_OPTIONS.map((type) => (
                  <MenuItem key={type} value={type}>
                    {type}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={submitting || !formData.progress_date}
        >
          {submitting ? <CircularProgress size={20} /> : entry ? 'Update' : 'Add'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
