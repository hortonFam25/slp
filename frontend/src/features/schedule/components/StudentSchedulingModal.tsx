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
  useMediaQuery,
  useTheme
} from '@mui/material';
import { TimePicker } from '@mui/x-date-pickers/TimePicker';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { format, setHours, setMinutes, addMinutes, isSameDay, parseISO } from 'date-fns';
import { Person, Schedule, AccessTime, School, Assignment, ExpandMore, ExpandLess } from '@mui/icons-material';
import { StudentScheduleView } from '../../../lib/api/schedulingStudents';
import { AppointmentSummary } from '../../../lib/api/scheduling';
import { RecurringSchedule, RecurringConfig } from './RecurringSchedule';

// Helper function to parse selected goals and objectives
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

  // Simple logic: When we select a goal, we add [goalId, ...objectiveIds]
  // So we need to separate them based on the data structure, not position
  selectedIds.forEach(id => {
    // Check if this ID exists as a goal
    const goal = studentGoals.find(g => g.id === id);
    if (goal && !goalIds.includes(id)) {
      console.log(`🔍 ID ${id} identified as GOAL`);
      goalIds.push(id);
    }
    
    // Check if this ID exists as an objective  
    const objective = studentGoals.find(g => 
      g.objectives && g.objectives.some((obj: any) => obj.id === id)
    );
    if (objective && !objectiveIds.includes(id)) {
      console.log(`🔍 ID ${id} identified as OBJECTIVE`);
      objectiveIds.push(id);
    }
  });

  // Remove duplicates just in case
  const uniqueGoalIds = [...new Set(goalIds)];
  const uniqueObjectiveIds = [...new Set(objectiveIds)];
  
  return { goalIds: uniqueGoalIds, objectiveIds: uniqueObjectiveIds, objectiveToGoalMap };
};

import { useStudentActiveGoals } from '../../../lib/hooks/useStudentGoals';

interface StudentSchedulingModalProps {
  open: boolean;
  onClose: () => void;
  selectedDate: Date;
  selectedHour: number;
  students: StudentScheduleView[];
  existingAppointments: AppointmentSummary[];
  onScheduleStudent: (appointmentData: {
    student_id: number;
    start_datetime: string;
    end_datetime: string;
    notes?: string;
    goal_ids?: number[];
    objective_ids?: number[];
    objective_to_goal_map?: { [key: number]: number };
    recurring_config?: RecurringConfig;
  }) => void;
}

// Generate 5-minute increment times for a full day
const generateTimeOptions = () => {
  const options = [];
  for (let hour = 0; hour < 24; hour++) {
    for (let minute = 0; minute < 60; minute += 5) {
      const timeString = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
      const displayString = format(setMinutes(setHours(new Date(), hour), minute), 'h:mm a');
      options.push({ value: timeString, label: displayString, hour, minute });
    }
  }
  return options;
};

const TIME_OPTIONS = generateTimeOptions();

// Generate focused time options for a specific hour (showing 1 hour window)
const generateFocusedTimeOptions = (centerHour: number) => {
  const options = [];
  // Show times from centerHour to centerHour + 1 (full hour range)
  for (let hour = centerHour; hour <= centerHour; hour++) {
    for (let minute = 0; minute < 60; minute += 5) {
      if (hour < 24) { // Ensure we don't go beyond 23:59
        const timeString = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
        const displayString = format(setMinutes(setHours(new Date(), hour), minute), 'h:mm a');
        options.push({ value: timeString, label: displayString, hour, minute });
      }
    }
  }
  return options;
};

export function StudentSchedulingModal({
  open,
  onClose,
  selectedDate,
  selectedHour,
  students,
  existingAppointments,
  onScheduleStudent
}: StudentSchedulingModalProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  // Form state
  const [selectedStudent, setSelectedStudent] = useState<StudentScheduleView | null>(null);
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [sessionNotes, setSessionNotes] = useState('');
  const [selectedGoalIds, setSelectedGoalIds] = useState<number[]>([]);
  const [expandedGoals, setExpandedGoals] = useState<number[]>([]);
  const [allowOverlap, setAllowOverlap] = useState(false);
  const [startTimeMenuOpen, setStartTimeMenuOpen] = useState(false);
  const [endTimeMenuOpen, setEndTimeMenuOpen] = useState(false);
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

  // Fetch student goals when a student is selected
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

  // Initialize start time when modal opens
  useEffect(() => {
    if (open && selectedHour !== undefined) {
      const initialTime = `${selectedHour.toString().padStart(2, '0')}:00`;
      setStartTime(initialTime);
      
      // Set default end time to 30 minutes later
      const endHour = selectedHour;
      const endMinute = 30;
      const defaultEndTime = `${endHour.toString().padStart(2, '0')}:${endMinute.toString().padStart(2, '0')}`;
      setEndTime(defaultEndTime);
    }
  }, [open, selectedHour]);

  // Reset form when modal closes
  useEffect(() => {
    if (!open) {
      setSelectedStudent(null);
      setStartTime('');
      setEndTime('');
      setSessionNotes('');
      setSelectedGoalIds([]);
      setAllowOverlap(false);
      setStartTimeMenuOpen(false);
      setEndTimeMenuOpen(false);
      setObjectivePreSessionNotes({});
      setRecurringConfig({
        isRecurring: false,
        frequency: 'weekly',
        interval: 1,
        daysOfWeek: [],
        endType: 'occurrences',
        maxOccurrences: 10,
        endDate: undefined // Explicitly clear any previous end date
      });
    }
  }, [open]);

  // Get existing appointments for the selected date
  const dayAppointments = useMemo(() => {
    return existingAppointments.filter(apt => {
      if (!apt.start_datetime) return false;
      const aptDate = new Date(apt.start_datetime);
      return isSameDay(aptDate, selectedDate);
    });
  }, [existingAppointments, selectedDate]);

  // Get focused start time options (showing current hour + surrounding context)
  const focusedStartTimes = useMemo(() => {
    if (!startTime) return generateFocusedTimeOptions(selectedHour);
    
    const [currentHour] = startTime.split(':').map(Number);
    return generateFocusedTimeOptions(currentHour);
  }, [startTime, selectedHour]);

  // Calculate available start times (avoiding conflicts unless overlap is allowed)
  const availableStartTimes = useMemo(() => {
    const baseOptions = startTimeMenuOpen ? TIME_OPTIONS : focusedStartTimes;
    if (allowOverlap) return baseOptions;

    return baseOptions.filter(timeOption => {
      const proposedStart = setMinutes(setHours(selectedDate, timeOption.hour), timeOption.minute);
      
      // Check if this time conflicts with existing appointments
      return !dayAppointments.some(apt => {
        if (!apt.start_datetime || !apt.end_datetime) return false;
        const aptStart = new Date(apt.start_datetime);
        const aptEnd = new Date(apt.end_datetime);
        return proposedStart >= aptStart && proposedStart < aptEnd;
      });
    });
  }, [dayAppointments, selectedDate, allowOverlap, startTimeMenuOpen, focusedStartTimes]);

  // Get focused end time options 
  const focusedEndTimes = useMemo(() => {
    if (!startTime) return [];
    
    const [startHour] = startTime.split(':').map(Number);
    // For end time, show the current hour and the next hour for context
    const endOptions = [
      ...generateFocusedTimeOptions(startHour),
      ...generateFocusedTimeOptions(Math.min(startHour + 1, 23))
    ];
    
    // Remove duplicates and sort
    const uniqueOptions = endOptions.filter((option, index, arr) => 
      arr.findIndex(o => o.value === option.value) === index
    );
    return uniqueOptions.sort((a, b) => a.value.localeCompare(b.value));
  }, [startTime]);

  // Calculate available end times based on selected start time
  const availableEndTimes = useMemo(() => {
    if (!startTime) return [];

    const [startHour, startMinute] = startTime.split(':').map(Number);
    const startDateTime = setMinutes(setHours(selectedDate, startHour), startMinute);
    const baseOptions = endTimeMenuOpen ? TIME_OPTIONS : focusedEndTimes;

    // End time must be after start time
    return baseOptions.filter(timeOption => {
      const endDateTime = setMinutes(setHours(selectedDate, timeOption.hour), timeOption.minute);
      
      if (endDateTime <= startDateTime) return false;

      // If overlap not allowed, check for conflicts
      if (!allowOverlap) {
        return !dayAppointments.some(apt => {
          if (!apt.start_datetime || !apt.end_datetime) return false;
          const aptStart = new Date(apt.start_datetime);
          const aptEnd = new Date(apt.end_datetime);
          // Check if our proposed end time would overlap with existing appointment
          return endDateTime > aptStart && endDateTime <= aptEnd;
        });
      }

      return true;
    });
  }, [startTime, selectedDate, dayAppointments, allowOverlap, endTimeMenuOpen, focusedEndTimes]);

  // Check for scheduling conflicts
  const hasConflicts = useMemo(() => {
    if (!startTime || !endTime || allowOverlap) return false;

    const [startHour, startMinute] = startTime.split(':').map(Number);
    const [endHour, endMinute] = endTime.split(':').map(Number);
    const proposedStart = setMinutes(setHours(selectedDate, startHour), startMinute);
    const proposedEnd = setMinutes(setHours(selectedDate, endHour), endMinute);

    return dayAppointments.some(apt => {
      if (!apt.start_datetime || !apt.end_datetime) return false;
      const aptStart = new Date(apt.start_datetime);
      const aptEnd = new Date(apt.end_datetime);
      
      // Check for any overlap
      return (proposedStart < aptEnd && proposedEnd > aptStart);
    });
  }, [startTime, endTime, selectedDate, dayAppointments, allowOverlap]);

  // Clear selected goals when student changes and expand all goals by default
  useEffect(() => {
    if (selectedStudent) {
      setSelectedGoalIds([]);
      setObjectivePreSessionNotes({});
      // Expand all goals by default when student changes
      setExpandedGoals(goals.map(goal => goal.id));
    }
  }, [selectedStudent, goals]);

  const handleSchedule = () => {
    if (!selectedStudent || !startTime || !endTime) return;

    const [startHour, startMinute] = startTime.split(':').map(Number);
    const [endHour, endMinute] = endTime.split(':').map(Number);
    
    // Create dates in local timezone for the selected date and times
    const appointmentStart = new Date(selectedDate);
    appointmentStart.setHours(startHour, startMinute, 0, 0);
    
    const appointmentEnd = new Date(selectedDate);
    appointmentEnd.setHours(endHour, endMinute, 0, 0);

    // Parse selected goals and objectives
    console.log('🔍 Pre-parsing selectedGoalIds:', selectedGoalIds);
    console.log('🔍 Available studentGoals:', studentGoals);
    const { goalIds, objectiveIds, objectiveToGoalMap } = parseSelectedGoalsAndObjectives(selectedGoalIds, studentGoals);
    console.log('🔍 Post-parsing results:', { goalIds, objectiveIds, objectiveToGoalMap });

    // Format datetime to preserve local timezone
    const formatLocalDateTime = (date: Date) => {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');
      return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}`;
    };

    const appointmentData = {
      student_id: selectedStudent.id,
      start_datetime: formatLocalDateTime(appointmentStart),
      end_datetime: formatLocalDateTime(appointmentEnd),
      notes: sessionNotes || undefined,
      goal_ids: goalIds.length > 0 ? goalIds : undefined,
      objective_ids: objectiveIds.length > 0 ? objectiveIds : undefined,
      objective_to_goal_map: objectiveToGoalMap,
      objective_pre_session_notes: objectivePreSessionNotes,
      recurring_config: recurringConfig.isRecurring ? recurringConfig : undefined
    };
    
    console.log('🕐 Time debugging:', {
      selectedDate: selectedDate.toString(),
      startTime,
      endTime,
      appointmentStart: appointmentStart.toString(),
      appointmentEnd: appointmentEnd.toString(),
      formattedStart: formatLocalDateTime(appointmentStart),
      formattedEnd: formatLocalDateTime(appointmentEnd),
      appointmentStartISO: appointmentStart.toISOString(),
      appointmentEndISO: appointmentEnd.toISOString(),
      timezoneOffset: appointmentStart.getTimezoneOffset()
    });

    console.log('🎯 Goals debugging:', {
      selectedGoalIds,
      goalIds,
      objectiveIds,
      objectiveToGoalMap,
      totalGoals: goals.length,
      duplicateGoalIds: goalIds.filter((id, index) => goalIds.indexOf(id) !== index),
      duplicateObjectiveIds: objectiveIds.filter((id, index) => objectiveIds.indexOf(id) !== index)
    });

    onScheduleStudent(appointmentData);
    onClose();
  };

  const handleClose = () => {
    onClose();
  };

  const isFormValid = selectedStudent && startTime && endTime;

  return (
    <Dialog 
      open={open} 
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      fullScreen={isMobile}
      PaperProps={{
        sx: { 
          minHeight: isMobile ? '100vh' : '70vh',
          maxHeight: isMobile ? '100vh' : '90vh'
        }
      }}
    >
      <DialogTitle sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: 1, 
        pb: 1,
        px: isMobile ? 2 : 3,
        py: isMobile ? 1.5 : 2
      }}>
        <Schedule color="primary" sx={{ fontSize: isMobile ? 20 : 24 }} />
        <Box>
          <Typography 
            variant={isMobile ? "subtitle1" : "h6"}
            sx={{ fontSize: isMobile ? '1.1rem' : undefined }}
          >
            {isMobile ? "Schedule Appointment" : "Schedule Student Appointment"}
          </Typography>
          <Typography 
            variant={isMobile ? "body2" : "subtitle2"} 
            color="text.secondary"
            sx={{ fontSize: isMobile ? '0.8rem' : undefined }}
          >
            {format(selectedDate, isMobile ? 'MMM d, yyyy' : 'EEEE, MMMM d, yyyy')} • {selectedHour}:00 hour block
          </Typography>
        </Box>
      </DialogTitle>

      <DialogContent sx={{ 
        pt: 2,
        px: isMobile ? 2 : 3
      }}>
        <Grid container spacing={isMobile ? 2 : 3}>
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
                      {student.school?.name || 'No School'} • {student.primary_teacher?.teacher_name || 'No Teacher'}
                    </Typography>
                  </Box>
                </Box>
              )}
            />
          </Grid>

          {/* Time Selection */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <AccessTime color="primary" />
              Time Selection (5-minute increments)
            </Typography>
            
            {hasConflicts && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                This time slot conflicts with existing appointments. Check "Allow Overlap" to proceed anyway.
              </Alert>
            )}

            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <FormControl fullWidth>
                <InputLabel>Start Time</InputLabel>
                <Select
                  value={startTime}
                  label="Start Time"
                  onChange={(e) => setStartTime(e.target.value)}
                  open={startTimeMenuOpen}
                  onOpen={() => setStartTimeMenuOpen(true)}
                  onClose={() => setStartTimeMenuOpen(false)}
                  MenuProps={{
                    PaperProps: {
                      sx: {
                        maxHeight: 200, // Limit height to show focused view
                      }
                    }
                  }}
                >
                  {!startTimeMenuOpen && availableStartTimes.length <= 12 && (
                    <MenuItem disabled sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
                      Showing {availableStartTimes[0]?.label} - {availableStartTimes[availableStartTimes.length - 1]?.label} • Scroll for more times
                    </MenuItem>
                  )}
                  {availableStartTimes.map((option) => (
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
                  open={endTimeMenuOpen}
                  onOpen={() => setEndTimeMenuOpen(true)}
                  onClose={() => setEndTimeMenuOpen(false)}
                  MenuProps={{
                    PaperProps: {
                      sx: {
                        maxHeight: 200, // Limit height to show focused view
                      }
                    }
                  }}
                >
                  {!endTimeMenuOpen && availableEndTimes.length <= 24 && (
                    <MenuItem disabled sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
                      Showing {availableEndTimes[0]?.label} - {availableEndTimes[availableEndTimes.length - 1]?.label} • Scroll for more times
                    </MenuItem>
                  )}
                  {availableEndTimes.map((option) => (
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
                                // Select goal and all its objectives - DON'T deduplicate here
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
                  
                  {goals.length === 0 && (
                    <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                      No goals available for this student
                    </Typography>
                  )}
                </Box>
              </Box>
            )}

                            {/* Selected Goals/Objectives Summary */}
                {selectedGoalIds.length > 0 && (
              <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
                <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Assignment color="primary" />
                  Selected for This Session ({selectedGoalIds.length})
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  {(() => {
                    const { goalIds, objectiveIds } = parseSelectedGoalsAndObjectives(selectedGoalIds, goals);
                    
                    return [
                      // Render unique goals
                      ...goalIds.map(goalId => {
                        const goal = goals.find(g => g.id === goalId);
                        return goal ? (
                          <Chip
                            key={`summary-goal-${goalId}`}
                            label={`🎯 ${goal.goal_description}`}
                            color="primary"
                            size="small"
                            variant="outlined"
                            onDelete={() => {
                              const goalObjectives = goal.objectives?.map(obj => obj.id) || [];
                              const idsToRemove = [goalId, ...goalObjectives];
                              setSelectedGoalIds(prev => prev.filter(id => !idsToRemove.includes(id)));
                            }}
                            sx={{ maxWidth: 250 }}
                          />
                        ) : null;
                      }),
                      // Render unique objectives
                      ...objectiveIds.map(objectiveId => {
                        let objective = null;
                        for (const g of goals) {
                          if (g.objectives) {
                            objective = g.objectives.find((obj: any) => obj.id === objectiveId);
                            if (objective) break;
                          }
                        }
                        return objective ? (
                          <Chip
                            key={`summary-objective-${objectiveId}`}
                            label={`📋 ${objective.objective_description}`}
                            color="secondary"
                            size="small"
                            variant="outlined"
                            onDelete={() => setSelectedGoalIds(prev => prev.filter(id => id !== objectiveId))}
                            sx={{ maxWidth: 250 }}
                          />
                        ) : null;
                      })
                    ].filter(Boolean);
                  })()}
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                  These goals/objectives will be pre-planned for your therapy session
                </Typography>
              </Box>
            )}
          </Grid>

          {/* Recurring Schedule */}
          <Grid item xs={12}>
            <RecurringSchedule
              value={recurringConfig}
              onChange={setRecurringConfig}
              startDate={selectedDate}
              disabled={!selectedStudent || !startTime || !endTime}
              maxOccurrences={50}
              maxEndDate={new Date(selectedDate.getTime() + 365 * 24 * 60 * 60 * 1000)} // 1 year from start
            />
          </Grid>

          {/* Session Notes */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom>
              Session Notes (Optional)
            </Typography>
            <TextField
              fullWidth
              multiline
              rows={3}
              value={sessionNotes}
              onChange={(e) => setSessionNotes(e.target.value)}
              label="Add reminders, prep notes, or session details"
              placeholder="e.g., Bring visual aids, work on homework vocabulary, parent wants update on progress..."
            />
          </Grid>

          {/* Existing Appointments Info */}
          {dayAppointments.length > 0 && (
            <Grid item xs={12}>
              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle2" gutterBottom>
                Existing Appointments Today ({dayAppointments.length})
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {dayAppointments.map((apt) => (
                  <Chip
                    key={apt.id}
                    label={`${apt.student_name} • ${format(new Date(apt.start_datetime!), 'h:mm a')} - ${format(new Date(apt.end_datetime!), 'h:mm a')}`}
                    size="small"
                    variant="outlined"
                  />
                ))}
              </Box>
            </Grid>
          )}
        </Grid>
      </DialogContent>

      <DialogActions sx={{ 
        px: isMobile ? 2 : 3, 
        pb: isMobile ? 2 : 3,
        flexDirection: isMobile ? 'column' : 'row',
        gap: isMobile ? 1 : 0
      }}>
        <Button 
          onClick={handleClose}
          fullWidth={isMobile}
          size={isMobile ? 'medium' : 'small'}
          sx={{ order: isMobile ? 2 : 1 }}
        >
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleSchedule}
          disabled={!isFormValid || (hasConflicts && !allowOverlap)}
          fullWidth={isMobile}
          size={isMobile ? 'medium' : 'small'}
          sx={{ order: isMobile ? 1 : 2 }}
        >
          {isMobile ? "Schedule" : "Schedule Appointment"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
