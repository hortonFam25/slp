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
  RadioGroup,
  Radio,
  Paper,
  Stack,
  Accordion,
  AccordionSummary,
  AccordionDetails
} from '@mui/material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { format, addHours, setMinutes, setHours } from 'date-fns';
import { 
  PlayArrow, 
  Person, 
  Schedule, 
  Assignment, 
  Link as LinkIcon,
  AddCircle,
  Psychology,
  ExpandMore,
  Notes
} from '@mui/icons-material';
import { StudentScheduleView } from '../../../lib/api/schedulingStudents';
import { AppointmentSummary } from '../../../lib/api/scheduling';
import { useStudentActiveGoals, flattenGoalsAndObjectives, parseSelectedGoalsAndObjectives } from '../../../lib/hooks/useStudentGoals';
import { useStartTherapySession } from '../../../lib/hooks/useTherapySessions';
import { StartSessionRequest, PlannedObjectiveForSession } from '../../../lib/api/therapySessions';
import { useNavigate } from 'react-router-dom';

interface StartTherapySessionModalProps {
  open: boolean;
  onClose: () => void;
  students: StudentScheduleView[];
  existingAppointments: AppointmentSummary[];
  onSessionStarted?: (sessionId: number) => void;
}

export type SessionStartType = 'unscheduled' | 'link_existing';

const SESSION_START_OPTIONS = [
  {
    value: 'unscheduled' as const,
    label: 'Start New Session',
    description: 'Start therapy session (appointment will be automatically created)',
    icon: <Psychology color="primary" />
  },
  {
    value: 'link_existing' as const,
    label: 'Link to Existing Appointment',
    description: 'Connect this session to a scheduled appointment',
    icon: <LinkIcon color="success" />
  }
];

export function StartTherapySessionModal({
  open,
  onClose,
  students,
  existingAppointments,
  onSessionStarted
}: StartTherapySessionModalProps) {
  // Form state
  const [selectedStudent, setSelectedStudent] = useState<StudentScheduleView | null>(null);
  const [sessionStartType, setSessionStartType] = useState<SessionStartType>('unscheduled');
  const [selectedAppointment, setSelectedAppointment] = useState<AppointmentSummary | null>(null);
  const [sessionDateTime, setSessionDateTime] = useState<Date>(new Date());
  const [plannedDuration, setPlannedDuration] = useState(30); // minutes
  const [selectedGoalIds, setSelectedGoalIds] = useState<number[]>([]);
  const [prepNotes, setPrepNotes] = useState('');
  const [objectivePreSessionNotes, setObjectivePreSessionNotes] = useState<Record<number, string>>({});

  // API hooks
  const startSessionMutation = useStartTherapySession();
  const navigate = useNavigate();

  // Fetch student goals when a student is selected
  const { data: studentGoals = [], isLoading: goalsLoading } = useStudentActiveGoals(
    selectedStudent?.id || 0,
    !!selectedStudent?.id
  );

  // Flatten goals and objectives for selection
  const { goals, objectives, all: allGoalsAndObjectives } = useMemo(() => {
    return flattenGoalsAndObjectives(studentGoals);
  }, [studentGoals]);

  // Get available appointments for the selected student
  const studentAppointments = useMemo(() => {
    if (!selectedStudent) return [];
    
    return existingAppointments.filter(apt => 
      apt.student_id === selectedStudent.id &&
      apt.start_datetime &&
      new Date(apt.start_datetime) >= new Date(Date.now() - 24 * 60 * 60 * 1000) // Within last 24 hours or future
    ).sort((a, b) => new Date(a.start_datetime!).getTime() - new Date(b.start_datetime!).getTime());
  }, [selectedStudent, existingAppointments]);

  // Get selected objectives for pre-session notes
  const selectedObjectives = useMemo(() => {
    const { objectiveIds } = parseSelectedGoalsAndObjectives(selectedGoalIds, studentGoals);
    return objectives.filter(obj => objectiveIds.includes(obj.id));
  }, [selectedGoalIds, studentGoals, objectives]);

  // Reset form when modal closes
  useEffect(() => {
    if (!open) {
      setSelectedStudent(null);
      setSessionStartType('unscheduled');
      setSelectedAppointment(null);
      setSessionDateTime(new Date());
      setPlannedDuration(30);
      setSelectedGoalIds([]);
      setPrepNotes('');
      setObjectivePreSessionNotes({});
    }
  }, [open]);

  // Clear appointment selection when type changes
  useEffect(() => {
    if (sessionStartType !== 'link_existing') {
      setSelectedAppointment(null);
    }
  }, [sessionStartType]);

  // Clear selected goals when student changes
  useEffect(() => {
    if (selectedStudent) {
      setSelectedGoalIds([]);
      setObjectivePreSessionNotes({});
    }
  }, [selectedStudent]);

  // Auto-set session time from appointment if linked
  useEffect(() => {
    if (selectedAppointment?.start_datetime) {
      setSessionDateTime(new Date(selectedAppointment.start_datetime));
      
      // Calculate duration from appointment
      if (selectedAppointment.end_datetime) {
        const start = new Date(selectedAppointment.start_datetime);
        const end = new Date(selectedAppointment.end_datetime);
        const durationMinutes = Math.round((end.getTime() - start.getTime()) / (1000 * 60));
        setPlannedDuration(durationMinutes);
      }
    }
  }, [selectedAppointment]);

  const handleStartSession = async () => {
    if (!selectedStudent) return;

    try {
      // Parse selected goals and objectives
      const { goalIds, objectiveIds } = parseSelectedGoalsAndObjectives(selectedGoalIds, studentGoals);

      // Build planned objectives with notes
      const plannedObjectivesWithNotes: PlannedObjectiveForSession[] = selectedObjectives.map(objective => ({
        objective_id: objective.id,
        goal_id: objective.goalId,
        priority: 1,
        pre_session_notes: objectivePreSessionNotes[objective.id] || undefined
      }));

      const request: StartSessionRequest = {
        student_id: selectedStudent.id,
        session_type: sessionStartType,
        appointment_id: selectedAppointment?.id,
        create_appointment: sessionStartType === 'unscheduled', // Auto-create appointment if no existing appointment
        planned_duration_minutes: plannedDuration,
        prep_notes: prepNotes || undefined,
        planned_goals: goalIds,
        planned_objectives: objectiveIds,
        planned_objectives_with_notes: plannedObjectivesWithNotes.length > 0 ? plannedObjectivesWithNotes : undefined
      };

      const newSession = await startSessionMutation.mutateAsync(request);
      
      // Navigate to the therapy session interface
      navigate(`/therapy/session/${newSession.id}`);
      
      if (onSessionStarted) {
        onSessionStarted(newSession.id);
      }
      
      onClose();
    } catch (error) {
      console.error('Failed to start therapy session:', error);
      // Error handling is managed by the mutation
    }
  };

  const handleClose = () => {
    if (startSessionMutation.isPending) return; // Prevent closing during API call
    onClose();
  };

  const isFormValid = selectedStudent && 
    (sessionStartType !== 'link_existing' || selectedAppointment);

  return (
    <Dialog 
      open={open} 
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { minHeight: '80vh' }
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1, pb: 1 }}>
        <PlayArrow color="primary" />
        <Box>
          <Typography variant="h6">
            Start Therapy Session
          </Typography>
          <Typography variant="subtitle2" color="text.secondary">
            Begin a new therapy session with flexible scheduling options
          </Typography>
        </Box>
      </DialogTitle>

      <DialogContent sx={{ pt: 2 }}>
        <Grid container spacing={3}>
          {/* Student Selection */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Person color="primary" />
              Student Selection
            </Typography>
            <Autocomplete
              fullWidth
              options={students}
              getOptionLabel={(student) => `${student.first?.trim()} ${student.last?.trim()}`}
              value={selectedStudent}
              onChange={(_, newValue) => setSelectedStudent(newValue)}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Select Student"
                  placeholder="Search by student name..."
                />
              )}
              renderOption={(props, student) => (
                <Box component="li" {...props}>
                  <Box>
                    <Typography variant="body1">
                      {student.first?.trim()} {student.last?.trim()}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {student.school?.name || 'No School'} • {student.primary_teacher?.full_name || 'No Teacher'}
                    </Typography>
                  </Box>
                </Box>
              )}
            />
          </Grid>

          {/* Session Start Type */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Schedule color="primary" />
              Session Type
            </Typography>
            
            <RadioGroup
              value={sessionStartType}
              onChange={(e) => setSessionStartType(e.target.value as SessionStartType)}
            >
              <Stack spacing={1}>
                {SESSION_START_OPTIONS.map((option) => (
                  <Paper 
                    key={option.value}
                    variant="outlined" 
                    sx={{ 
                      p: 2, 
                      cursor: 'pointer',
                      '&:hover': { bgcolor: 'action.hover' },
                      ...(sessionStartType === option.value && {
                        borderColor: 'primary.main',
                        bgcolor: 'primary.50'
                      })
                    }}
                    onClick={() => setSessionStartType(option.value)}
                  >
                    <FormControlLabel
                      value={option.value}
                      control={<Radio />}
                      label={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                          {option.icon}
                          <Box>
                            <Typography variant="subtitle2" fontWeight="bold">
                              {option.label}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              {option.description}
                            </Typography>
                          </Box>
                        </Box>
                      }
                      sx={{ m: 0, width: '100%', '& .MuiFormControlLabel-label': { width: '100%' } }}
                    />
                  </Paper>
                ))}
              </Stack>
            </RadioGroup>
          </Grid>

          {/* Link to Existing Appointment */}
          {sessionStartType === 'link_existing' && (
            <Grid item xs={12}>
              <Typography variant="subtitle1" gutterBottom>
                Select Appointment to Link
              </Typography>
              
              {!selectedStudent ? (
                <Alert severity="info">
                  Select a student first to see their appointments
                </Alert>
              ) : studentAppointments.length === 0 ? (
                <Alert severity="warning">
                  No recent or upcoming appointments found for this student
                </Alert>
              ) : (
                <Autocomplete
                  fullWidth
                                          options={studentAppointments}
                        getOptionLabel={(apt) => 
                          `${format(new Date(apt.start_datetime!), 'MMM d, yyyy h:mm a')} - ${format(new Date(apt.end_datetime!), 'h:mm a')}`
                        }
                  value={selectedAppointment}
                  onChange={(_, newValue) => setSelectedAppointment(newValue)}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="Select Appointment"
                      placeholder="Choose appointment to link this session to..."
                    />
                  )}
                  renderOption={(props, appointment) => (
                    <Box component="li" {...props}>
                      <Box>
                        <Typography variant="body2">
                          {format(new Date(appointment.start_datetime!), 'EEEE, MMMM d, yyyy')}
                        </Typography>
                        <Typography variant="body1" fontWeight="bold">
                          {format(new Date(appointment.start_datetime!), 'h:mm a')} - {format(new Date(appointment.end_datetime!), 'h:mm a')}
                        </Typography>
                        {appointment.notes && (
                          <Typography variant="caption" color="text.secondary">
                            Notes: {appointment.notes}
                          </Typography>
                        )}
                      </Box>
                    </Box>
                  )}
                />
              )}
            </Grid>
          )}

          {/* Session DateTime */}
          <Grid item xs={12} md={6}>
            <Typography variant="subtitle1" gutterBottom>
              Session Date & Time
            </Typography>
            <DateTimePicker
              label="Session start time"
              value={sessionDateTime}
              onChange={(newValue) => newValue && setSessionDateTime(newValue)}
              disabled={sessionStartType === 'link_existing' && !!selectedAppointment}
              slotProps={{
                textField: {
                  fullWidth: true,
                  helperText: sessionStartType === 'link_existing' && selectedAppointment 
                    ? 'Time is set from selected appointment' 
                    : undefined
                }
              }}
            />
          </Grid>

          {/* Planned Duration */}
          <Grid item xs={12} md={6}>
            <Typography variant="subtitle1" gutterBottom>
              Planned Duration
            </Typography>
            <FormControl fullWidth>
              <InputLabel>Duration (minutes)</InputLabel>
              <Select
                value={plannedDuration}
                label="Duration (minutes)"
                onChange={(e) => setPlannedDuration(Number(e.target.value))}
                disabled={sessionStartType === 'link_existing' && !!selectedAppointment}
              >
                <MenuItem value={15}>15 minutes</MenuItem>
                <MenuItem value={20}>20 minutes</MenuItem>
                <MenuItem value={30}>30 minutes</MenuItem>
                <MenuItem value={45}>45 minutes</MenuItem>
                <MenuItem value={60}>60 minutes</MenuItem>
                <MenuItem value={90}>90 minutes</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          {/* Goals Selection */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Assignment color="primary" />
              Session Goals & Objectives (Optional)
            </Typography>
            
            {!selectedStudent ? (
              <TextField
                fullWidth
                disabled
                label="Select goals to work on"
                placeholder="Select a student first to see their goals..."
                helperText="Choose a student to view their active IEP goals and objectives"
              />
            ) : goalsLoading ? (
              <TextField
                fullWidth
                disabled
                label="Loading goals..."
                placeholder="Loading student goals and objectives..."
              />
            ) : allGoalsAndObjectives.length === 0 ? (
              <TextField
                fullWidth
                disabled
                label="No goals available"
                placeholder="This student has no active IEP goals"
                helperText="Goals can be added in the IEP management section"
              />
            ) : (
              <Autocomplete
                multiple
                options={allGoalsAndObjectives}
                value={selectedGoalIds}
                onChange={(_, newValue) => setSelectedGoalIds(newValue)}
                getOptionLabel={(option) => `${option.title} ${option.type === 'objective' ? `(${option.goalTitle})` : ''}`}
                groupBy={(option) => option.type === 'goal' ? 'IEP Goals' : 'Goal Objectives'}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Select goals and objectives to work on"
                    placeholder="Choose what to focus on this session..."
                    helperText={`Available: ${goals.length} goals, ${objectives.length} objectives`}
                  />
                )}
                renderOption={(props, option) => (
                  <Box component="li" {...props}>
                    <Box sx={{ width: '100%' }}>
                      <Typography variant="body2" sx={{ fontWeight: option.type === 'goal' ? 'bold' : 'normal' }}>
                        {option.type === 'goal' ? '🎯' : '📋'} {option.title}
                      </Typography>
                      {option.type === 'objective' && (
                        <Typography variant="caption" color="text.secondary">
                          Goal: {option.goalTitle}
                          {option.successRate !== undefined && ` • Success Rate: ${option.successRate}%`}
                        </Typography>
                      )}
                      {option.type === 'goal' && option.category && (
                        <Typography variant="caption" color="text.secondary">
                          Category: {option.category} • Status: {option.status}
                        </Typography>
                      )}
                    </Box>
                  </Box>
                )}
                renderTags={(value, getTagProps) =>
                  value.map((optionId, index) => {
                    const option = allGoalsAndObjectives.find(opt => opt.id === optionId);
                    if (!option) return null;
                    
                    return (
                      <Chip
                        key={optionId}
                        variant="outlined"
                        label={`${option.type === 'goal' ? '🎯' : '📋'} ${option.title}`}
                        color={option.type === 'goal' ? 'primary' : 'secondary'}
                        {...getTagProps({ index })}
                        size="small"
                      />
                    );
                  })
                }
              />
            )}
          </Grid>

          {/* Prep Notes */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom>
              Preparation Notes (Optional)
            </Typography>
            <TextField
              fullWidth
              multiline
              rows={3}
              value={prepNotes}
              onChange={(e) => setPrepNotes(e.target.value)}
              label="Session preparation notes"
              placeholder="e.g., Materials needed, student mood/status, session objectives, reminders..."
            />
          </Grid>

          {/* Objective Pre-Session Notes */}
          {selectedObjectives.length > 0 && (
            <Grid item xs={12}>
              <Accordion>
                <AccordionSummary 
                  expandIcon={<ExpandMore />}
                  sx={{ 
                    bgcolor: '#f5f5f5',
                    '& .MuiAccordionSummary-content': { 
                      alignItems: 'center',
                      gap: 1
                    }
                  }}
                >
                  <Notes color="primary" />
                  <Typography variant="subtitle1">
                    Objective Pre-Session Notes ({selectedObjectives.length} objectives selected)
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Stack spacing={2}>
                    <Alert severity="info" sx={{ mb: 2 }}>
                      Add specific preparation notes for each selected objective to help plan your session approach.
                    </Alert>
                    {selectedObjectives.map((objective) => (
                      <Paper key={objective.id} sx={{ p: 2, bgcolor: '#fafafa' }}>
                        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                          Objective {objective.objectiveNumber}: {objective.title}
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                          Goal: {objective.goalTitle}
                        </Typography>
                        <TextField
                          fullWidth
                          multiline
                          rows={3}
                          label="Pre-Session Notes"
                          value={objectivePreSessionNotes[objective.id] || ''}
                          onChange={(e) => setObjectivePreSessionNotes(prev => ({
                            ...prev,
                            [objective.id]: e.target.value
                          }))}
                          placeholder="Add specific preparation notes for this objective..."
                          sx={{
                            '& .MuiOutlinedInput-root': {
                              bgcolor: 'white'
                            }
                          }}
                        />
                      </Paper>
                    ))}
                  </Stack>
                </AccordionDetails>
              </Accordion>
            </Grid>
          )}

          {/* Session Type Info */}
          <Grid item xs={12}>
            <Divider sx={{ my: 1 }} />
            {sessionStartType === 'unscheduled' && (
              <Alert severity="info">
                <Typography variant="body2">
                  <strong>Unscheduled Session:</strong> This session will not be linked to any appointment. 
                  You can optionally create an appointment record later for billing purposes.
                </Typography>
              </Alert>
            )}
            {sessionStartType === 'link_existing' && (
              <Alert severity="success">
                <Typography variant="body2">
                  <strong>Link to Appointment:</strong> This session will be connected to the selected appointment. 
                  The appointment will be marked as having an active therapy session.
                </Typography>
              </Alert>
            )}
            {sessionStartType === 'create_appointment' && (
              <Alert severity="info">
                <Typography variant="body2">
                  <strong>Create Appointment:</strong> A new appointment record will be automatically created 
                  for this session with the specified date, time, and duration.
                </Typography>
              </Alert>
            )}
          </Grid>
        </Grid>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 3 }}>
        <Button 
          onClick={handleClose}
          disabled={startSessionMutation.isPending}
        >
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleStartSession}
          disabled={!isFormValid || startSessionMutation.isPending}
          startIcon={<PlayArrow />}
        >
          {startSessionMutation.isPending ? 'Starting Session...' : 'Start Session'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
