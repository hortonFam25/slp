import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  CircularProgress,
  Alert,
  IconButton,
  useTheme,
  useMediaQuery
} from '@mui/material';
import { Close, History } from '@mui/icons-material';
import { goalsApi } from '../lib/api/goals';
import type { IEPGoal } from '../lib/api/types/goals';
import type { TherapySession } from '../lib/api/therapySessions';

// Import the GridProgressView component from the therapy module
import { GridProgressView } from '../features/therapy/components/TherapySessionGoalsAndObjectives';

interface StudentTherapyHistoryDialogProps {
  open: boolean;
  onClose: () => void;
  studentId: number;
  studentName: string;
}

export function StudentTherapyHistoryDialog({
  open,
  onClose,
  studentId,
  studentName
}: StudentTherapyHistoryDialogProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [studentGoals, setStudentGoals] = useState<IEPGoal[]>([]);
  
  // Create a mock therapy session for the grid view
  // We only need the student_id and basic structure
  const mockSession: TherapySession = {
    id: 0, // Not used in grid view
    student_id: studentId,
    session_date: new Date().toISOString().split('T')[0],
    session_type: 'Individual',
    status: 'Completed',
    goals_addressed: false,
    follow_up_needed: false,
    session_goals: [],
    session_objectives: [],
    created_date: new Date().toISOString(),
    modified_date: new Date().toISOString(),
    // Required computed properties
    duration_minutes: 0,
    is_scheduled: false,
    is_group_session: false,
    is_active: false,
    is_completed: true,
    // Required counts
    planned_goals_count: 0,
    worked_goals_count: 0,
    planned_objectives_count: 0,
    worked_objectives_count: 0,
    progress_entries_count: 0
  };

  useEffect(() => {
    if (open && studentId) {
      fetchStudentGoals();
    }
  }, [open, studentId]);

  const fetchStudentGoals = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Fetch the student's active goals with objectives
      const goals = await goalsApi.getStudentActiveGoals(studentId);
      setStudentGoals(goals);
    } catch (err) {
      console.error('Failed to fetch student goals:', err);
      setError('Failed to load student therapy data. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setStudentGoals([]);
    setError(null);
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth={false}
      fullWidth
      fullScreen={isMobile}
      PaperProps={{
        sx: {
          width: isMobile ? '100%' : '95vw',
          height: isMobile ? '100%' : '90vh',
          maxWidth: 'none',
          m: isMobile ? 0 : 2
        }
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          bgcolor: '#f8fffe',
          borderBottom: 1,
          borderColor: 'grey.200',
          py: 2
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <History color="primary" />
          <Box>
            <Typography variant="h6" component="div">
              Therapy History - {studentName}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              View and edit therapy session notes across the school year
            </Typography>
          </Box>
        </Box>
        <IconButton
          onClick={handleClose}
          size="small"
          sx={{ color: 'grey.500' }}
        >
          <Close />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ p: 0, overflow: 'hidden' }}>
        {loading ? (
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              height: 400
            }}
          >
            <CircularProgress />
          </Box>
        ) : error ? (
          <Box sx={{ p: 3 }}>
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
            <Button onClick={fetchStudentGoals} variant="outlined">
              Try Again
            </Button>
          </Box>
        ) : studentGoals.length === 0 ? (
          <Box sx={{ p: 3 }}>
            <Alert severity="info">
              This student has no active IEP goals. Goals and objectives can be added in the IEP management section.
            </Alert>
          </Box>
        ) : (
          <Box sx={{ height: '100%', overflow: 'hidden' }}>
            <GridProgressView
              studentId={studentId}
              availableGoals={studentGoals}
              session={mockSession}
              disabled={false} // Allow editing
              onUpdateObjectiveProgress={(objectiveId, updates) => {
                // The GridProgressView handles its own API calls
                // No additional handling needed here
                console.log('Objective updated:', objectiveId, updates);
              }}
            />
          </Box>
        )}
      </DialogContent>

      <DialogActions
        sx={{
          px: 3,
          py: 2,
          bgcolor: '#fafbfc',
          borderTop: 1,
          borderColor: 'grey.200'
        }}
      >
        <Button onClick={handleClose} variant="outlined">
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
}
