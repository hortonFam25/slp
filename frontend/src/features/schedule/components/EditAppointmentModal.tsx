import React, { useState, useMemo, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Typography,
  Box,
  Chip,
  Alert,
  Autocomplete,
  FormControlLabel,
  Checkbox,
  Divider,
  Grid,
  IconButton,
  Paper
} from '@mui/material';
import { TimePicker } from '@mui/x-date-pickers/TimePicker';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { format, setHours, setMinutes, addMinutes, isSameDay, parseISO } from 'date-fns';
import { Person, Schedule, AccessTime, School, Assignment, ExpandMore, ExpandLess, Close } from '@mui/icons-material';
import { AppointmentSummary } from '../../../lib/api/scheduling';
import { StudentScheduleView } from '../../../lib/api/schedulingStudents';
import { RecurringSchedule, RecurringConfig } from './RecurringSchedule';
import { useStudentActiveGoals } from '../../../lib/hooks/useStudentGoals';

// Helper function to parse selected goals and objectives (reused from StudentSchedulingModal)
const parseSelectedGoalsAndObjectives = (selectedIds: number[], studentGoals: any[]) => {
  const goalIds: number[] = [];
  const objectiveIds: number[] = [];
  const objectiveToGoalMap: { [key: number]: number } = {};

  // Build mapping of objective ID to goal ID
  studentGoals.forEach(goal => {
    if (goal.objectives) {
      goal.objectives.forEach((objective: any) => {
        objectiveToGoalMap[objective.id] = goal.id;
      });
    }
  });

  selectedIds.forEach(id => {
    const goal = studentGoals.find(g => g.id === id);
    if (goal && !goalIds.includes(id)) {
      goalIds.push(id);
    }
    
    const objective = studentGoals.find(g => 
      g.objectives && g.objectives.some((obj: any) => obj.id === id)
    );
    if (objective && !objectiveIds.includes(id)) {
      objectiveIds.push(id);
    }
  });

  const uniqueGoalIds = [...new Set(goalIds)];
  const uniqueObjectiveIds = [...new Set(objectiveIds)];
  
  return { goalIds: uniqueGoalIds, objectiveIds: uniqueObjectiveIds, objectiveToGoalMap };
};

// Helper function to format datetime for local timezone
const formatLocalDateTime = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  
  return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}`;
};

// Generate 5-minute increment times for a full day
const generateTimeOptions = () => {
  const options = [];
  for (let hour = 0; hour < 24; hour++) {
    for (let minute = 0; minute < 60; minute += 5) {
      const timeString = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
      options.push({ value: timeString, label: format(new Date(2024, 0, 1, hour, minute), 'h:mm a') });
    }
  }
  return options;
};

interface EditAppointmentModalProps {
  open: boolean;
  onClose: () => void;
  appointment: AppointmentSummary;
  students: StudentScheduleView[];
  existingAppointments: AppointmentSummary[];
  onUpdateAppointment: (appointmentData: {
    id: number;
    student_id: number;
    start_datetime: string;
    end_datetime: string;
    notes?: string;
    planned_goals?: Array<{
      goal_id: number;
      planned: boolean;
      worked_on: boolean;
      priority: number;
    }>;
    planned_objectives?: Array<{
      objective_id: number;
      goal_id: number;
      planned: boolean;
      worked_on: boolean;
      priority: number;
    }>;
  }) => void;
  onLoadTherapySession?: (appointmentId: number) => Promise<{
    goals: Array<{ goal_id: number; goal_text: string; planned: boolean; worked_on: boolean }>;
    objectives: Array<{ objective_id: number; goal_id: number; objective_text: string; planned: boolean; worked_on: boolean }>;
  }>;
}

export function EditAppointmentModal({
  open,
  onClose,
  appointment,
  students,
  existingAppointments,
  onUpdateAppointment,
  onLoadTherapySession
}: EditAppointmentModalProps) {
  // Initialize state with appointment data - using same structure as create modal
  const [selectedStudent, setSelectedStudent] = useState<StudentScheduleView | null>(null);
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [sessionNotes, setSessionNotes] = useState('');
  const [selectedGoalIds, setSelectedGoalIds] = useState<number[]>([]);
  const [expandedGoals, setExpandedGoals] = useState<number[]>([]);
  const [allowOverlap, setAllowOverlap] = useState(false);
  const [objectivePreSessionNotes, setObjectivePreSessionNotes] = useState<Record<number, string>>({});
  const [recurringConfig, setRecurringConfig] = useState<RecurringConfig>({
    isRecurring: false,
    frequency: 'weekly',
    interval: 1,
    daysOfWeek: [],
    endType: 'occurrences',
    maxOccurrences: 10,
    endDate: undefined
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingTherapySession, setLoadingTherapySession] = useState(false);
  const [therapySessionError, setTherapySessionError] = useState<string | null>(null);

  // Find the student for this appointment and load therapy session data
  useEffect(() => {
    if (appointment && students.length > 0) {
      // Fix: StudentScheduleView uses 'id', not 'student_id'
      const student = students.find(s => s.id === appointment.student_id);
      if (student) {
        setSelectedStudent(student);
      }
      
      // Set time values from datetime - convert to HH:MM format like create modal
      if (appointment.start_datetime) {
        const startDate = new Date(appointment.start_datetime);
        const startTimeStr = `${startDate.getHours().toString().padStart(2, '0')}:${startDate.getMinutes().toString().padStart(2, '0')}`;
        setStartTime(startTimeStr);
      }
      if (appointment.end_datetime) {
        const endDate = new Date(appointment.end_datetime);
        const endTimeStr = `${endDate.getHours().toString().padStart(2, '0')}:${endDate.getMinutes().toString().padStart(2, '0')}`;
        setEndTime(endTimeStr);
      }
      
      // Set notes
      setSessionNotes(appointment.notes || '');
      
      // Load existing goals and objectives from therapy session
      if (onLoadTherapySession && appointment.id) {
        setLoadingTherapySession(true);
        setTherapySessionError(null);
        
        onLoadTherapySession(appointment.id)
          .then((sessionData) => {
            console.log('📋 Loaded therapy session data:', sessionData);
            
            // Combine goal and objective IDs - same pattern as create modal
            const goalIds = sessionData.goals.map(g => g.goal_id);
            const objectiveIds = sessionData.objectives.map(o => o.objective_id);
            const combinedIds = [...goalIds, ...objectiveIds];
            
            setSelectedGoalIds(combinedIds);
            // Auto-expand goals that have selected objectives
            const goalsWithSelectedObjectives = sessionData.objectives.map(o => o.goal_id);
            setExpandedGoals([...new Set(goalsWithSelectedObjectives)]);
          })
          .catch((err) => {
            console.error('❌ Failed to load therapy session data:', err);
            setTherapySessionError('Failed to load existing goals and objectives');
            setSelectedGoalIds([]);
          })
          .finally(() => {
            setLoadingTherapySession(false);
          });
      } else {
        setSelectedGoalIds([]);
      }
    }
  }, [appointment, students, onLoadTherapySession]);

  // Load student goals - using same pattern as create modal
  const { data: studentGoals = [], isLoading: goalsLoading } = useStudentActiveGoals(
    selectedStudent?.id || 0,
    !!selectedStudent?.id
  );

  // Use the raw goals data directly (already has nested objectives)
  const goals = studentGoals;

  // Expand all goals initially when goals are loaded
  useEffect(() => {
    if (goals.length > 0 && selectedStudent) {
      setExpandedGoals(goals.map(goal => goal.id));
    }
  }, [goals, selectedStudent]);

  const timeOptions = useMemo(() => generateTimeOptions(), []);

  // Form validation
  const canSubmit = useMemo(() => {
    return selectedStudent && startTime && endTime;
  }, [selectedStudent, startTime, endTime]);

  // Check for conflicts (simplified for now)
  const hasConflicts = useMemo(() => {
    return false; // TODO: Implement proper conflict detection with time strings
  }, []);



  const handleSubmit = async () => {
    if (!canSubmit || !selectedStudent) return;

    setLoading(true);
    setError(null);

    try {
      // Parse selected goals and objectives - same as create modal
      let goalIds: number[] = [];
      let objectiveIds: number[] = [];
      let objectiveToGoalMap: { [key: number]: number } = {};

      if (selectedGoalIds.length > 0 && goals.length > 0) {
        const parsed = parseSelectedGoalsAndObjectives(selectedGoalIds, goals);
        goalIds = parsed.goalIds;
        objectiveIds = parsed.objectiveIds;
        objectiveToGoalMap = parsed.objectiveToGoalMap;
      }

      // Create start and end datetime from selected date and times
      const selectedDate = appointment.start_datetime ? new Date(appointment.start_datetime) : new Date();
      const [startHour, startMinute] = startTime.split(':').map(Number);
      const [endHour, endMinute] = endTime.split(':').map(Number);
      
      const startDateTime = new Date(selectedDate);
      startDateTime.setHours(startHour, startMinute, 0, 0);
      
      const endDateTime = new Date(selectedDate);
      endDateTime.setHours(endHour, endMinute, 0, 0);

      // Transform goal and objective IDs to PlannedGoal and PlannedObjective objects
      const plannedGoals = goalIds.map(goalId => ({
        goal_id: goalId,
        planned: true,
        worked_on: false,
        priority: 1
      }));

      const plannedObjectives = objectiveIds.map(objectiveId => ({
        objective_id: objectiveId,
        goal_id: objectiveToGoalMap[objectiveId],
        planned: true,
        worked_on: false,
        priority: 1,
        pre_session_notes: objectivePreSessionNotes[objectiveId] || undefined
      }));

      const appointmentData = {
        id: appointment.id,
        student_id: selectedStudent.id,
        start_datetime: formatLocalDateTime(startDateTime),
        end_datetime: formatLocalDateTime(endDateTime),
        notes: sessionNotes.trim() || undefined,
        planned_goals: plannedGoals.length > 0 ? plannedGoals : undefined,
        planned_objectives: plannedObjectives.length > 0 ? plannedObjectives : undefined
      };

      console.log('🔄 Edit Appointment - Submitting:', appointmentData);
      await onUpdateAppointment(appointmentData);
      onClose();
    } catch (err) {
      console.error('❌ Edit Appointment Error:', err);
      setError(err instanceof Error ? err.message : 'Failed to update appointment');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setError(null);
    onClose();
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Dialog 
        open={open} 
        onClose={handleClose}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: { height: '90vh', maxHeight: '90vh' }
        }}
      >
        <DialogTitle sx={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          pb: 1
        }}>
          <Box>
            <Typography variant="h6" component="div">
              Edit Appointment
            </Typography>
            <Typography variant="subtitle2" color="text.secondary">
              Modify appointment details and goals
            </Typography>
          </Box>
          <IconButton onClick={handleClose} size="small">
            <Close />
          </IconButton>
        </DialogTitle>

        <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {error && (
            <Alert severity="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          {hasConflicts && (
            <Alert severity="warning">
              ⚠️ This time slot conflicts with an existing appointment for this student.
            </Alert>
          )}

          {/* Student Info (Read-only) */}
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Box sx={{ 
                p: 2, 
                bgcolor: 'grey.50', 
                borderRadius: 1, 
                border: '1px solid',
                borderColor: 'grey.300',
                display: 'flex',
                alignItems: 'center',
                gap: 1
              }}>
                <Person color="primary" />
                <Box>
                  <Typography variant="subtitle1" fontWeight={600}>
                    {selectedStudent ? `${selectedStudent.first} ${selectedStudent.last}` : 'Unknown Student'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Student cannot be changed for existing appointments
                  </Typography>
                </Box>
              </Box>
            </Grid>
          </Grid>

          {/* Time Selection - Same as Create Modal */}
          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            <FormControl fullWidth>
              <InputLabel>Start Time</InputLabel>
              <Select
                value={startTime}
                label="Start Time"
                onChange={(e) => setStartTime(e.target.value)}
              >
                {timeOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl fullWidth>
              <InputLabel>End Time</InputLabel>
              <Select
                value={endTime}
                label="End Time"
                onChange={(e) => setEndTime(e.target.value)}
                disabled={!startTime}
              >
                {timeOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>

          <FormControlLabel
            control={
              <Checkbox
                checked={allowOverlap}
                onChange={(e) => setAllowOverlap(e.target.checked)}
              />
            }
            label="Allow time overlap with existing appointments"
          />

          {/* Session Notes */}
          <TextField
            label="Session Notes"
            multiline
            rows={3}
            value={sessionNotes}
            onChange={(e) => setSessionNotes(e.target.value)}
            fullWidth
            placeholder="Add any notes about this appointment..."
          />

          {/* Goals Selection - Exact same structure as create modal */}
          <Typography variant="subtitle1" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Assignment color="primary" />
            Session Goals & Objectives (Optional)
          </Typography>
          
          {loadingTherapySession && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Loading existing goals and objectives from therapy session...
            </Alert>
          )}
          {therapySessionError && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              {therapySessionError}
            </Alert>
          )}

          {!selectedStudent ? (
            <TextField
              fullWidth
              disabled
              label="Select goals to work on"
              placeholder="Student information is loading..."
              helperText="Student data is required to view their active IEP goals and objectives"
            />
          ) : goalsLoading ? (
            <TextField
              fullWidth
              disabled
              label="Loading goals..."
              placeholder="Loading student goals and objectives..."
            />
          ) : goals.length === 0 ? (
            <TextField
              fullWidth
              disabled
              label="No goals available"
              placeholder="This student has no active IEP goals"
              helperText="Goals can be added in the IEP management section"
            />
          ) : (
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
                Check goals to select all objectives, or expand to choose specific objectives
              </Typography>
              
              <Box sx={{ 
                maxHeight: 400, 
                overflowY: 'auto', 
                border: 1, 
                borderColor: 'divider', 
                borderRadius: 2, 
                p: 2,
                bgcolor: 'grey.25'
              }}>
                {goals.map((goal, goalIndex) => {
                  const goalObjectives = goal.objectives || [];
                  const goalSelected = selectedGoalIds.includes(goal.id);
                  const selectedObjectivesForGoal = goalObjectives.filter(obj => selectedGoalIds.includes(obj.id));
                  const allObjectivesSelected = goalObjectives.length > 0 && selectedObjectivesForGoal.length === goalObjectives.length;
                  const someObjectivesSelected = selectedObjectivesForGoal.length > 0 && selectedObjectivesForGoal.length < goalObjectives.length;
                  const isExpanded = expandedGoals.includes(goal.id);
                  
                  return (
                    <Box 
                      key={goal.id} 
                      sx={{ 
                        mb: 3,
                        p: 2,
                        border: 1,
                        borderColor: 'primary.light',
                        borderRadius: 2,
                        bgcolor: 'white',
                        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                        '&:last-child': { mb: 0 }
                      }}
                    >
                      {/* Goal Header */}
                      <Box sx={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        py: 1,
                        borderBottom: goalObjectives.length > 0 ? 1 : 0,
                        borderColor: 'grey.200',
                        mb: goalObjectives.length > 0 ? 2 : 0
                      }}>
                        <Checkbox
                          checked={goalSelected || allObjectivesSelected}
                          indeterminate={someObjectivesSelected && !goalSelected}
                          onChange={(e) => {
                            if (e.target.checked) {
                              // Select goal and all its objectives
                              const newIds = [goal.id, ...goalObjectives.map(obj => obj.id)];
                              console.log(`🎯 Selecting goal ${goal.id}:`, { goalObjectives, newIds });
                              setSelectedGoalIds(prev => [...prev, ...newIds]);
                            } else {
                              // Deselect goal and all its objectives
                              const idsToRemove = [goal.id, ...goalObjectives.map(obj => obj.id)];
                              console.log(`🎯 Deselecting goal ${goal.id}:`, { goalObjectives, idsToRemove });
                              setSelectedGoalIds(prev => prev.filter(id => !idsToRemove.includes(id)));
                            }
                          }}
                          size="medium"
                          sx={{ mr: 2 }}
                        />
                        <Box sx={{ flex: 1 }}>
                          <Typography 
                            variant="subtitle1" 
                            sx={{ 
                              fontWeight: 600, 
                              color: 'primary.main',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 1,
                              mb: 0.5
                            }}
                          >
                            🎯 Goal {goal.goal_number || goalIndex + 1}
                          </Typography>
                          <Typography variant="body2" sx={{ color: 'text.primary', lineHeight: 1.4 }}>
                            {goal.goal_description}
                          </Typography>
                          <Typography 
                            variant="caption" 
                            sx={{ 
                              color: 'text.secondary',
                              display: 'block',
                              mt: 0.5,
                              fontStyle: 'italic'
                            }}
                          >
                            {goal.goal_category_name || 'Goal'} • {goalObjectives.length} objective{goalObjectives.length !== 1 ? 's' : ''}
                          </Typography>
                        </Box>
                        {goalObjectives.length > 0 && (
                          <IconButton
                            size="small"
                            onClick={() => {
                              setExpandedGoals(prev => 
                                prev.includes(goal.id) 
                                  ? prev.filter(id => id !== goal.id)
                                  : [...prev, goal.id]
                              );
                            }}
                            sx={{ 
                              ml: 1,
                              color: 'primary.main',
                              bgcolor: 'primary.50',
                              '&:hover': {
                                bgcolor: 'primary.100'
                              }
                            }}
                          >
                            {isExpanded ? <ExpandLess /> : <ExpandMore />}
                          </IconButton>
                        )}
                      </Box>
                      
                      {/* Objectives (when expanded) */}
                      {isExpanded && goalObjectives.length > 0 && (
                        <Box sx={{ mt: 1 }}>
                          {goalObjectives.map((objective, objIndex) => {
                            const isObjectiveSelected = selectedGoalIds.includes(objective.id);
                            return (
                              <Box 
                                key={objective.id} 
                                sx={{ 
                                  mb: 2,
                                  p: 1.5,
                                  border: 1,
                                  borderColor: 'secondary.light',
                                  borderRadius: 1,
                                  bgcolor: 'grey.50',
                                  '&:last-child': { mb: 0 }
                                }}
                              >
                                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                                  <Checkbox
                                    checked={isObjectiveSelected}
                                    onChange={(e) => {
                                      if (e.target.checked) {
                                        console.log(`📋 Selecting objective ${objective.id} for goal ${goal.id}`);
                                        setSelectedGoalIds(prev => [...prev, objective.id]);
                                      } else {
                                        console.log(`📋 Deselecting objective ${objective.id} for goal ${goal.id}`);
                                        setSelectedGoalIds(prev => prev.filter(id => id !== objective.id));
                                        // Clear pre-session notes when deselecting
                                        setObjectivePreSessionNotes(prev => {
                                          const updated = { ...prev };
                                          delete updated[objective.id];
                                          return updated;
                                        });
                                      }
                                    }}
                                    size="small"
                                    sx={{ mt: 0.5 }}
                                  />
                                  <Box sx={{ flex: 1 }}>
                                    <Typography 
                                      variant="body2" 
                                      sx={{ 
                                        fontWeight: 500,
                                        color: 'secondary.main',
                                        mb: 0.5,
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 0.5
                                      }}
                                    >
                                      📋 Objective {objective.objective_number || objIndex + 1}
                                    </Typography>
                                    <Typography 
                                      variant="body2" 
                                      sx={{ 
                                        fontSize: '0.875rem', 
                                        color: 'text.primary',
                                        lineHeight: 1.3
                                      }}
                                    >
                                      {objective.objective_description}
                                    </Typography>
                                  </Box>
                                </Box>
                                
                                {/* Pre-session notes for selected objectives */}
                                {isObjectiveSelected && (
                                  <Box sx={{ mt: 2, ml: 4 }}>
                                    <TextField
                                      fullWidth
                                      multiline
                                      rows={2}
                                      size="small"
                                      label="Pre-Session Notes"
                                      value={objectivePreSessionNotes[objective.id] || ''}
                                      onChange={(e) => setObjectivePreSessionNotes(prev => ({
                                        ...prev,
                                        [objective.id]: e.target.value
                                      }))}
                                      placeholder="Add preparation notes for this objective..."
                                      sx={{
                                        '& .MuiOutlinedInput-root': {
                                          bgcolor: 'white',
                                          fontSize: '0.875rem'
                                        },
                                        '& .MuiInputLabel-root': {
                                          fontSize: '0.875rem'
                                        }
                                      }}
                                    />
                                  </Box>
                                )}
                              </Box>
                            );
                          })}
                        </Box>
                      )}
                    </Box>
                  );
                })}
              </Box>
            </Box>
          )}

          {/* Recurring Schedule */}
          <Divider />
          <RecurringSchedule
            value={recurringConfig}
            onChange={setRecurringConfig}
          />
        </DialogContent>

        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={handleClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            variant="contained"
            disabled={!canSubmit || loading || hasConflicts}
            sx={{ minWidth: 120 }}
          >
            {loading ? 'Updating...' : 'Update Appointment'}
          </Button>
        </DialogActions>
      </Dialog>
    </LocalizationProvider>
  );
}
