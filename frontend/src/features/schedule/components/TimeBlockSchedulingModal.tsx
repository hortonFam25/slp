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
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Card,
  CardContent,
  Collapse,
  useMediaQuery,
  useTheme
} from '@mui/material';
import { TimePicker } from '@mui/x-date-pickers/TimePicker';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { format, setHours, setMinutes, addMinutes, isSameDay, parseISO } from 'date-fns';
import { 
  Person, 
  Schedule, 
  AccessTime, 
  School, 
  Assignment, 
  ExpandMore, 
  ExpandLess,
  ChevronRight,
  Add,
  Delete,
  Group,
  PlayArrow,
  DragIndicator
} from '@mui/icons-material';
import { StudentScheduleView } from '../../../lib/api/schedulingStudents';
import { AppointmentSummary } from '../../../lib/api/scheduling';
import { RecurringSchedule, RecurringConfig } from './RecurringSchedule';
import { useStudentActiveGoals } from '../../../lib/hooks/useStudentGoals';
import { useTeachers } from '../../../lib/hooks/useTeachers';

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

// Time Block Activity interface
interface TimeBlockActivity {
  id?: number;
  start_minute: number;
  duration_minutes: number;
  activity_name: string;
  activity_type?: string;
  description?: string;
  materials_needed?: string;
  notes?: string;
  sequence_order: number;
}

// Student Goal Assignment interface
interface StudentGoalAssignment {
  student_id: number;
  selected_goal_ids: number[];
  expanded_goals: number[];
}

interface TimeBlockSchedulingModalProps {
  open: boolean;
  onClose: () => void;
  selectedDate: Date;
  selectedHour: number;
  students: StudentScheduleView[];
  existingAppointments: AppointmentSummary[];
  onScheduleTimeBlock: (timeBlockData: {
    // Time block fields
    teacher_id?: number;
    school_id?: number;
    start_datetime: string;
    end_datetime: string;
    title: string;
    max_students?: number;
    location?: string;
    notes?: string;
    am_pm_indicator?: string;
    // Student assignments
    assigned_students: number[];
    // Goal/objective assignments per student
    student_goal_assignments?: { [key: number]: { goals: number[]; objectives: number[] } };
    // Activities
    activities?: TimeBlockActivity[];
    // Recurring config
    recurring_config?: RecurringConfig;
  }) => void;
}

// Generate 5-minute increment times (reused from StudentSchedulingModal)
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

// Activity types for dropdown
const ACTIVITY_TYPES = [
  { value: 'warm_up', label: 'Warm Up' },
  { value: 'main_activity', label: 'Main Activity' },
  { value: 'transition', label: 'Transition' },
  { value: 'practice', label: 'Practice' },
  { value: 'assessment', label: 'Assessment' },
  { value: 'closing', label: 'Closing' },
  { value: 'break', label: 'Break' },
  { value: 'other', label: 'Other' }
];

// AM/PM options
const AM_PM_OPTIONS = [
  { value: 'AM', label: 'AM' },
  { value: 'PM', label: 'PM' },
  { value: 'Morning', label: 'Morning' },
  { value: 'Afternoon', label: 'Afternoon' },
  { value: 'Evening', label: 'Evening' }
];

export function TimeBlockSchedulingModal({
  open,
  onClose,
  selectedDate,
  selectedHour,
  students,
  existingAppointments,
  onScheduleTimeBlock
}: TimeBlockSchedulingModalProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  // Time block form state
  const [title, setTitle] = useState('');
  const [teacherId, setTeacherId] = useState<number | ''>('');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [maxStudents, setMaxStudents] = useState<number | ''>('');
  const [location, setLocation] = useState('');
  const [notes, setNotes] = useState('');
  const [amPmIndicator, setAmPmIndicator] = useState('');
  
  // Student assignment state
  const [selectedStudents, setSelectedStudents] = useState<StudentScheduleView[]>([]);
  const [studentGoalAssignments, setStudentGoalAssignments] = useState<{ [key: number]: StudentGoalAssignment }>({});
  const [studentGoalsData, setStudentGoalsData] = useState<{ [key: number]: any[] }>({});
  
  // Activities state
  const [activities, setActivities] = useState<TimeBlockActivity[]>([]);
  const [showActivities, setShowActivities] = useState(false);
  
  // UI state
  const [activeStudentTab, setActiveStudentTab] = useState<number | null>(null);
  const [recurringConfig, setRecurringConfig] = useState<RecurringConfig>({
    isRecurring: false,
    frequency: 'weekly',
    interval: 1,
    daysOfWeek: [],
    endType: 'occurrences',
    maxOccurrences: 10,
    endDate: undefined
  });

  // Load teachers - fetch summary data on mount
  const { teachersSummary: teachers = [], fetchTeachersSummary } = useTeachers();
  
  // Load teachers on mount
  useEffect(() => {
    fetchTeachersSummary(true); // active only = true
  }, [fetchTeachersSummary]);

  // Initialize times when modal opens
  useEffect(() => {
    if (open && selectedHour !== undefined) {
      const initialTime = `${selectedHour.toString().padStart(2, '0')}:00`;
      setStartTime(initialTime);
      
      // Set default end time to 60 minutes later (typical group session)
      const endHour = selectedHour + 1;
      const defaultEndTime = `${(endHour % 24).toString().padStart(2, '0')}:00`;
      setEndTime(defaultEndTime);
    }
  }, [open, selectedHour]);

  // Reset form when modal closes
  useEffect(() => {
    if (!open) {
      setTitle('');
      setTeacherId('');
      setStartTime('');
      setEndTime('');
      setMaxStudents('');
      setLocation('');
      setNotes('');
      setAmPmIndicator('');
      setSelectedStudents([]);
      setStudentGoalAssignments({});
      setActivities([]);
      setShowActivities(false);
      setActiveStudentTab(null);
      setRecurringConfig({
        isRecurring: false,
        frequency: 'weekly',
        interval: 1,
        daysOfWeek: [],
        endType: 'occurrences',
        maxOccurrences: 10,
        endDate: undefined
      });
    }
  }, [open]);

  // Calculate block duration in minutes
  const blockDurationMinutes = useMemo(() => {
    if (!startTime || !endTime) return 0;
    const [startHour, startMinute] = startTime.split(':').map(Number);
    const [endHour, endMinute] = endTime.split(':').map(Number);
    const startMinutes = startHour * 60 + startMinute;
    const endMinutes = endHour * 60 + endMinute;
    return Math.max(0, endMinutes - startMinutes);
  }, [startTime, endTime]);

  // Generate time options for activity start/end times (5-minute increments within the block)
  const activityTimeOptions = useMemo(() => {
    const options = [];
    for (let minute = 0; minute <= blockDurationMinutes; minute += 5) {
      if (minute <= blockDurationMinutes) {
        const hours = Math.floor(minute / 60);
        const mins = minute % 60;
        const label = hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
        options.push({ value: minute, label: `${label} (${minute}m)` });
      }
    }
    return options;
  }, [blockDurationMinutes]);

  // Add student to selection
  const handleAddStudent = (student: StudentScheduleView) => {
    if (!selectedStudents.find(s => s.id === student.id)) {
      setSelectedStudents(prev => [...prev, student]);
      setStudentGoalAssignments(prev => ({
        ...prev,
        [student.id]: {
          student_id: student.id,
          selected_goal_ids: [],
          expanded_goals: []
        }
      }));
      // Don't auto-expand - let user choose when to expand
    }
  };

  // Remove student from selection
  const handleRemoveStudent = (studentId: number) => {
    setSelectedStudents(prev => prev.filter(s => s.id !== studentId));
    setStudentGoalAssignments(prev => {
      const updated = { ...prev };
      delete updated[studentId];
      return updated;
    });
    setStudentGoalsData(prev => {
      const updated = { ...prev };
      delete updated[studentId];
      return updated;
    });
    if (activeStudentTab === studentId) {
      setActiveStudentTab(null);
    }
  };

  // Handle when student goals are loaded
  const handleGoalsLoaded = (studentId: number, goals: any[]) => {
    setStudentGoalsData(prev => ({
      ...prev,
      [studentId]: goals
    }));
  };

  // Add activity
  const handleAddActivity = () => {
    const nextOrder = activities.length + 1;
    // Find next available start time
    let startMinute = 0;
    if (activities.length > 0) {
      const lastActivity = activities[activities.length - 1];
      startMinute = lastActivity.start_minute + lastActivity.duration_minutes;
    }
    
    const newActivity: TimeBlockActivity = {
      start_minute: Math.min(startMinute, blockDurationMinutes - 5), // Ensure it fits in the block
      duration_minutes: 5,
      activity_name: '',
      activity_type: 'main_activity',
      description: '',
      materials_needed: '',
      notes: '',
      sequence_order: nextOrder
    };
    setActivities(prev => [...prev, newActivity]);
  };

  // Remove activity
  const handleRemoveActivity = (index: number) => {
    setActivities(prev => prev.filter((_, i) => i !== index));
  };

  // Update activity
  const handleUpdateActivity = (index: number, field: keyof TimeBlockActivity, value: any) => {
    setActivities(prev => prev.map((activity, i) => 
      i === index ? { ...activity, [field]: value } : activity
    ));
  };

  // Validate form
  const isFormValid = useMemo(() => {
    return (
      title.trim() !== '' &&
      startTime !== '' &&
      endTime !== '' &&
      selectedStudents.length > 0 &&
      blockDurationMinutes > 0
    );
  }, [title, startTime, endTime, selectedStudents.length, blockDurationMinutes]);

  // Handle form submission
  const handleSubmit = () => {
    if (!isFormValid) return;

    // Build start and end datetime strings
    const [startHour, startMinute] = startTime.split(':').map(Number);
    const [endHour, endMinute] = endTime.split(':').map(Number);
    
    const startDateTime = new Date(selectedDate);
    startDateTime.setHours(startHour, startMinute, 0, 0);
    
    const endDateTime = new Date(selectedDate);
    endDateTime.setHours(endHour, endMinute, 0, 0);

    // Build student goal assignments
    const goalAssignments: { [key: number]: { goals: number[]; objectives: number[] } } = {};
    Object.values(studentGoalAssignments).forEach(assignment => {
      if (assignment.selected_goal_ids.length > 0) {
        // Get the student's goal data for proper parsing
        const studentGoals = studentGoalsData[assignment.student_id] || [];
        console.log(`🔍 Time Block - Student ${assignment.student_id}:`, {
          selected_goal_ids: assignment.selected_goal_ids,
          studentGoals: studentGoals.length,
          hasGoalsData: studentGoals.length > 0
        });
        
        const parsed = parseSelectedGoalsAndObjectives(assignment.selected_goal_ids, studentGoals);
        console.log(`🔍 Time Block - Parsed for student ${assignment.student_id}:`, parsed);
        
        goalAssignments[assignment.student_id] = {
          goals: parsed.goalIds,
          objectives: parsed.objectiveIds
        };
      }
    });
    
    console.log('🔍 Time Block - Final goalAssignments:', goalAssignments);

    // Format datetime to preserve local timezone (same as single appointments)
    const formatLocalDateTime = (date: Date) => {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');
      return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}`;
    };

    // Submit the form
    const timeBlockData = {
      teacher_id: teacherId || undefined,
      start_datetime: formatLocalDateTime(startDateTime),
      end_datetime: formatLocalDateTime(endDateTime),
      title: title.trim(),
      max_students: maxStudents || undefined,
      location: location.trim() || undefined,
      notes: notes.trim() || undefined,
      am_pm_indicator: amPmIndicator || undefined,
      assigned_students: selectedStudents.map(s => s.id),
      student_goal_assignments: Object.keys(goalAssignments).length > 0 ? goalAssignments : undefined,
      activities: activities.length > 0 ? activities : undefined,
      recurring_config: recurringConfig.isRecurring ? recurringConfig : undefined
    };
    
    console.log('🚀 Submitting Time Block Data:', JSON.stringify(timeBlockData, null, 2));
    
    onScheduleTimeBlock(timeBlockData);

    onClose();
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Dialog 
        open={open} 
        onClose={onClose} 
        maxWidth="lg" 
        fullWidth
        fullScreen={isMobile}
        PaperProps={{ 
          sx: { 
            height: isMobile ? '100vh' : '90vh',
            maxHeight: isMobile ? '100vh' : '90vh'
          } 
        }}
      >
        <DialogTitle sx={{ 
          pb: 1,
          px: isMobile ? 2 : 3,
          py: isMobile ? 1.5 : 2
        }}>
          <Box display="flex" alignItems="center" gap={1}>
            <Group color="primary" sx={{ fontSize: isMobile ? 20 : 24 }} />
            <Typography 
              variant={isMobile ? "subtitle1" : "h6"}
              sx={{ fontSize: isMobile ? '1.1rem' : undefined }}
            >
              {isMobile ? "Schedule Group" : "Schedule Time Block / Therapy Group"}
            </Typography>
          </Box>
          <Typography 
            variant="body2" 
            color="text.secondary"
            sx={{ fontSize: isMobile ? '0.8rem' : undefined }}
          >
            {format(selectedDate, isMobile ? 'MMM d, yyyy' : 'EEEE, MMMM d, yyyy')}
          </Typography>
        </DialogTitle>

        <DialogContent sx={{ 
          p: isMobile ? 2 : 3,
          overflow: 'auto'
        }}>
          <Grid container spacing={isMobile ? 2 : 3}>
            {/* Time Block Details */}
            <Grid item xs={12}>
              <Paper sx={{ p: 2 }}>
                <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold', color: 'primary.main' }}>
                  📋 Time Block Details
                </Typography>
                
                <Grid container spacing={2}>
                  <Grid item xs={12} md={6}>
                    <TextField
                      label="Block Title"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      fullWidth
                      required
                      placeholder="e.g., Morning Speech Group, Articulation Block"
                    />
                  </Grid>
                  
                  <Grid item xs={12} md={3}>
                    <FormControl fullWidth>
                      <InputLabel>AM/PM Indicator</InputLabel>
                      <Select
                        value={amPmIndicator}
                        onChange={(e) => setAmPmIndicator(e.target.value)}
                      >
                        {AM_PM_OPTIONS.map(option => (
                          <MenuItem key={option.value} value={option.value}>
                            {option.label}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Grid>

                  <Grid item xs={12} md={3}>
                    <TextField
                      label="Max Students"
                      type="number"
                      value={maxStudents}
                      onChange={(e) => setMaxStudents(e.target.value ? parseInt(e.target.value) : '')}
                      fullWidth
                      inputProps={{ min: 1 }}
                    />
                  </Grid>

                  <Grid item xs={12} md={4}>
                    <FormControl fullWidth>
                      <InputLabel>Start Time</InputLabel>
                      <Select
                        value={startTime}
                        onChange={(e) => setStartTime(e.target.value)}
                        required
                      >
                        {TIME_OPTIONS.map(option => (
                          <MenuItem key={option.value} value={option.value}>
                            {option.label}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Grid>

                  <Grid item xs={12} md={4}>
                    <FormControl fullWidth>
                      <InputLabel>End Time</InputLabel>
                      <Select
                        value={endTime}
                        onChange={(e) => setEndTime(e.target.value)}
                        required
                      >
                        {TIME_OPTIONS.map(option => (
                          <MenuItem key={option.value} value={option.value}>
                            {option.label}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Grid>

                  <Grid item xs={12} md={4}>
                    <Box display="flex" alignItems="center" gap={1} sx={{ mt: 1 }}>
                      <AccessTime fontSize="small" color="primary" />
                      <Typography variant="body2" color="primary">
                        Duration: {blockDurationMinutes} minutes
                      </Typography>
                    </Box>
                  </Grid>

                  <Grid item xs={12} md={6}>
                    <FormControl fullWidth>
                      <InputLabel>Teacher</InputLabel>
                      <Select
                        value={teacherId}
                        onChange={(e) => setTeacherId(e.target.value as number)}
                      >
                        {teachers.map(teacher => (
                          <MenuItem key={teacher.id} value={teacher.id}>
                            {teacher.full_name}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Grid>

                  <Grid item xs={12} md={6}>
                    <TextField
                      label="Location"
                      value={location}
                      onChange={(e) => setLocation(e.target.value)}
                      fullWidth
                      placeholder="Room number, building, etc."
                    />
                  </Grid>

                  <Grid item xs={12}>
                    <TextField
                      label="Notes"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      fullWidth
                      multiline
                      rows={2}
                      placeholder="Additional notes about this time block..."
                    />
                  </Grid>
                </Grid>
              </Paper>
            </Grid>

            {/* Student Assignment */}
            <Grid item xs={12}>
              <Paper sx={{ p: 2 }}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 'bold', color: 'primary.main' }}>
                    👥 Assign Students ({selectedStudents.length})
                  </Typography>
                </Box>

                <Grid container spacing={2}>
                  <Grid item xs={12} md={6}>
                    <Autocomplete
                      options={students.filter(s => !selectedStudents.find(sel => sel.id === s.id))}
                      getOptionLabel={(student) => `${student.first} ${student.last} (${student.grade_level})`}
                      renderInput={(params) => (
                        <TextField {...params} label="Add Student" placeholder="Search students..." />
                      )}
                      onChange={(_, student) => {
                        if (student) {
                          handleAddStudent(student);
                        }
                      }}
                      value={null}
                    />
                  </Grid>

                  <Grid item xs={12}>
                    {/* Student Cards - No more chips! */}
                    {selectedStudents.length > 0 && (
                      <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mb: 2 }}>
                        💡 Click "Show Goals" or the arrow to expand and select goals for each student
                      </Typography>
                    )}
                    <Box sx={{ mt: selectedStudents.length > 0 ? 1 : 0 }}>
                      {selectedStudents.map(student => {
                        const isExpanded = activeStudentTab === student.id;
                        const assignment = studentGoalAssignments[student.id] || {
                          student_id: student.id,
                          selected_goal_ids: [],
                          expanded_goals: []
                        };
                        const selectedCount = assignment.selected_goal_ids.length;

                        return (
                          <Card key={student.id} variant="outlined" sx={{ mb: 2, overflow: 'visible' }}>
                            {/* Student Header - Always Visible */}
                            <CardContent sx={{ pb: 1 }}>
                              <Box display="flex" justifyContent="space-between" alignItems="center">
                                <Box display="flex" alignItems="center" gap={2}>
                                  <IconButton
                                    size="small"
                                    onClick={() => setActiveStudentTab(isExpanded ? null : student.id)}
                                    sx={{ 
                                      transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                                      transition: 'transform 0.2s ease'
                                    }}
                                  >
                                    <ChevronRight />
                                  </IconButton>
                                  
                                  <Box>
                                    <Typography variant="subtitle1" sx={{ fontWeight: 'medium' }}>
                                      👤 {student.first} {student.last}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                      Grade {student.grade_level} • {selectedCount} goal{selectedCount !== 1 ? 's' : ''} selected
                                    </Typography>
                                  </Box>
                                </Box>

                                <Box display="flex" alignItems="center" gap={1}>
                                  <Button
                                    size="small"
                                    variant="outlined"
                                    onClick={() => setActiveStudentTab(isExpanded ? null : student.id)}
                                    startIcon={isExpanded ? <ExpandLess /> : <ExpandMore />}
                                  >
                                    {isExpanded ? 'Hide' : 'Show'} Goals
                                  </Button>
                                  
                                  <IconButton
                                    size="small"
                                    color="error"
                                    onClick={() => handleRemoveStudent(student.id)}
                                    sx={{ ml: 1 }}
                                  >
                                    <Delete />
                                  </IconButton>
                                </Box>
                              </Box>
                            </CardContent>

                            {/* Expandable Goals Section */}
                            <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                              <Divider />
                              <CardContent sx={{ pt: 2 }}>
                                <StudentGoalAssignmentPanel
                                  studentId={student.id}
                                  student={student}
                                  assignment={assignment}
                                  onUpdateAssignment={(assignment) => 
                                    setStudentGoalAssignments(prev => ({ ...prev, [student.id]: assignment }))
                                  }
                                  onGoalsLoaded={handleGoalsLoaded}
                                />
                              </CardContent>
                            </Collapse>
                          </Card>
                        );
                      })}
                    </Box>
                  </Grid>
                </Grid>
              </Paper>
            </Grid>

            {/* Activities Section */}
            <Grid item xs={12}>
              <Paper sx={{ p: 2 }}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 'bold', color: 'primary.main' }}>
                    ⏱️ Block Activities (Optional)
                  </Typography>
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={() => setShowActivities(!showActivities)}
                  >
                    {showActivities ? 'Hide' : 'Show'} Activities
                  </Button>
                </Box>

                {showActivities && (
                  <Box>
                    <Box mb={2}>
                      <Button
                        variant="outlined"
                        startIcon={<Add />}
                        onClick={handleAddActivity}
                        size="small"
                      >
                        Add Activity
                      </Button>
                    </Box>

                    {activities.map((activity, index) => (
                      <Paper key={index} variant="outlined" sx={{ p: 2, mb: 2 }}>
                        <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                          <Typography variant="subtitle2">
                            Activity {index + 1} ({
                              activityTimeOptions.find(opt => opt.value === activity.start_minute)?.label || `${activity.start_minute}m`
                            } - {
                              activityTimeOptions.find(opt => opt.value === activity.start_minute + activity.duration_minutes)?.label || `${activity.start_minute + activity.duration_minutes}m`
                            })
                          </Typography>
                          <IconButton 
                            size="small" 
                            onClick={() => handleRemoveActivity(index)}
                            color="error"
                          >
                            <Delete />
                          </IconButton>
                        </Box>

                        <Grid container spacing={2}>
                          <Grid item xs={12} md={3}>
                            <FormControl fullWidth size="small">
                              <InputLabel>Start Time</InputLabel>
                              <Select
                                value={activity.start_minute}
                                onChange={(e) => {
                                  const newStartMinute = e.target.value as number;
                                  const maxEndMinute = Math.min(newStartMinute + activity.duration_minutes, blockDurationMinutes);
                                  handleUpdateActivity(index, 'start_minute', newStartMinute);
                                  if (newStartMinute + activity.duration_minutes > blockDurationMinutes) {
                                    handleUpdateActivity(index, 'duration_minutes', blockDurationMinutes - newStartMinute);
                                  }
                                }}
                              >
                                {activityTimeOptions.filter(opt => opt.value < blockDurationMinutes).map(option => (
                                  <MenuItem key={option.value} value={option.value}>
                                    {option.label}
                                  </MenuItem>
                                ))}
                              </Select>
                            </FormControl>
                          </Grid>

                          <Grid item xs={12} md={3}>
                            <FormControl fullWidth size="small">
                              <InputLabel>End Time</InputLabel>
                              <Select
                                value={activity.start_minute + activity.duration_minutes}
                                onChange={(e) => {
                                  const endMinute = e.target.value as number;
                                  const newDuration = endMinute - activity.start_minute;
                                  handleUpdateActivity(index, 'duration_minutes', Math.max(5, newDuration));
                                }}
                              >
                                {activityTimeOptions.filter(opt => opt.value > activity.start_minute && opt.value <= blockDurationMinutes).map(option => (
                                  <MenuItem key={option.value} value={option.value}>
                                    {option.label}
                                  </MenuItem>
                                ))}
                              </Select>
                            </FormControl>
                          </Grid>

                          <Grid item xs={12} md={3}>
                            <FormControl fullWidth size="small">
                              <InputLabel>Type</InputLabel>
                              <Select
                                value={activity.activity_type || ''}
                                onChange={(e) => handleUpdateActivity(index, 'activity_type', e.target.value)}
                              >
                                {ACTIVITY_TYPES.map(type => (
                                  <MenuItem key={type.value} value={type.value}>
                                    {type.label}
                                  </MenuItem>
                                ))}
                              </Select>
                            </FormControl>
                          </Grid>

                          <Grid item xs={12} md={3}>
                            <TextField
                              label="Activity Name"
                              value={activity.activity_name}
                              onChange={(e) => handleUpdateActivity(index, 'activity_name', e.target.value)}
                              fullWidth
                              size="small"
                              required
                            />
                          </Grid>

                          <Grid item xs={12} md={6}>
                            <TextField
                              label="Description"
                              value={activity.description || ''}
                              onChange={(e) => handleUpdateActivity(index, 'description', e.target.value)}
                              fullWidth
                              size="small"
                              multiline
                              rows={2}
                            />
                          </Grid>

                          <Grid item xs={12} md={6}>
                            <TextField
                              label="Materials Needed"
                              value={activity.materials_needed || ''}
                              onChange={(e) => handleUpdateActivity(index, 'materials_needed', e.target.value)}
                              fullWidth
                              size="small"
                              multiline
                              rows={2}
                            />
                          </Grid>
                        </Grid>
                      </Paper>
                    ))}
                  </Box>
                )}
              </Paper>
            </Grid>

            {/* Recurring Schedule */}
            <Grid item xs={12}>
              <RecurringSchedule
                value={recurringConfig}
                onChange={setRecurringConfig}
                startDate={selectedDate}
              />
            </Grid>

            {/* Summary */}
            {isFormValid && (
              <Grid item xs={12}>
                <Alert severity="info">
                  <Typography variant="body2">
                    <strong>Ready to schedule:</strong> "{title}" on {format(selectedDate, 'MMM d, yyyy')} from {
                      TIME_OPTIONS.find(t => t.value === startTime)?.label
                    } to {
                      TIME_OPTIONS.find(t => t.value === endTime)?.label
                    } for {selectedStudents.length} student{selectedStudents.length !== 1 ? 's' : ''}.
                    {activities.length > 0 && ` Includes ${activities.length} planned activit${activities.length !== 1 ? 'ies' : 'y'}.`}
                  </Typography>
                </Alert>
              </Grid>
            )}
          </Grid>
        </DialogContent>

        <DialogActions sx={{ 
          px: isMobile ? 2 : 3, 
          pb: isMobile ? 2 : 2,
          flexDirection: isMobile ? 'column' : 'row',
          gap: isMobile ? 1 : 0
        }}>
          <Button 
            onClick={onClose}
            fullWidth={isMobile}
            size={isMobile ? 'medium' : 'small'}
            sx={{ order: isMobile ? 2 : 1 }}
          >
            Cancel
          </Button>
          <Button 
            variant="contained" 
            onClick={handleSubmit}
            disabled={!isFormValid}
            fullWidth={isMobile}
            size={isMobile ? 'medium' : 'small'}
            startIcon={!isMobile ? <Schedule /> : undefined}
            sx={{ order: isMobile ? 1 : 2 }}
          >
            {isMobile ? "Schedule Group" : "Schedule Time Block"}
          </Button>
        </DialogActions>
      </Dialog>
    </LocalizationProvider>
  );
}

// Separate component for student goal assignment (rewritten to match existing style)
interface StudentGoalAssignmentPanelProps {
  studentId: number;
  student: StudentScheduleView;
  assignment: StudentGoalAssignment;
  onUpdateAssignment: (assignment: StudentGoalAssignment) => void;
  onGoalsLoaded: (studentId: number, goals: any[]) => void;
}

function StudentGoalAssignmentPanel({ 
  studentId, 
  student, 
  assignment, 
  onUpdateAssignment,
  onGoalsLoaded
}: StudentGoalAssignmentPanelProps) {
  // Fetch student goals
  const { data: studentGoals = [], isLoading: goalsLoading } = useStudentActiveGoals(studentId, true);
  
  // Store goals data when loaded
  useEffect(() => {
    if (studentGoals.length > 0) {
      onGoalsLoaded(studentId, studentGoals);
    }
  }, [studentGoals, studentId, onGoalsLoaded]);

  const handleGoalSelectionChange = (selectedIds: number[]) => {
    onUpdateAssignment({
      ...assignment,
      selected_goal_ids: selectedIds
    });
  };

  const handleGoalExpand = (goalId: number) => {
    const isExpanded = assignment.expanded_goals.includes(goalId);
    onUpdateAssignment({
      ...assignment,
      expanded_goals: isExpanded 
        ? assignment.expanded_goals.filter(id => id !== goalId)
        : [...assignment.expanded_goals, goalId]
    });
  };

  if (goalsLoading) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">Loading goals...</Typography>
      </Box>
    );
  }

  if (studentGoals.length === 0) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">No active goals found for this student</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="subtitle2" gutterBottom sx={{ color: 'primary.main', mb: 2 }}>
        🎯 Select Goals & Objectives
      </Typography>

      <Box sx={{ 
        maxHeight: 350, 
        overflow: 'auto',
        border: 1,
        borderColor: 'grey.300',
        borderRadius: 1,
        p: 1,
        bgcolor: 'grey.50'
      }}>
        {studentGoals.map(goal => {
          const goalObjectives = goal.objectives || [];
          const goalSelected = assignment.selected_goal_ids.includes(goal.id);
          const selectedObjectives = goalObjectives.filter(obj => assignment.selected_goal_ids.includes(obj.id));
          const allObjectivesSelected = goalObjectives.length > 0 && selectedObjectives.length === goalObjectives.length;
          const someObjectivesSelected = selectedObjectives.length > 0 && selectedObjectives.length < goalObjectives.length;
          const isExpanded = assignment.expanded_goals.includes(goal.id);

          return (
            <Box key={goal.id} sx={{ mb: 1 }}>
              <Box display="flex" alignItems="center" gap={1} sx={{ 
                p: 1, 
                borderRadius: 1,
                bgcolor: goalSelected || someObjectivesSelected ? 'primary.50' : 'transparent',
                '&:hover': { bgcolor: 'grey.100' }
              }}>
                <Checkbox
                  checked={goalSelected || allObjectivesSelected}
                  indeterminate={someObjectivesSelected && !goalSelected}
                  onChange={(e) => {
                    if (e.target.checked) {
                      // Select goal and all its objectives
                      const newIds = [goal.id, ...goalObjectives.map(obj => obj.id)];
                      handleGoalSelectionChange([...assignment.selected_goal_ids, ...newIds]);
                    } else {
                      // Deselect goal and all its objectives
                      const idsToRemove = [goal.id, ...goalObjectives.map(obj => obj.id)];
                      handleGoalSelectionChange(assignment.selected_goal_ids.filter(id => !idsToRemove.includes(id)));
                    }
                  }}
                  size="small"
                />
                <Typography 
                  variant="body2" 
                  sx={{ fontWeight: 'medium', color: 'primary.main', flex: 1 }}
                >
                  🎯 {goal.goal_description}
                </Typography>
                {goalObjectives.length > 0 && (
                  <IconButton
                    size="small"
                    onClick={() => handleGoalExpand(goal.id)}
                  >
                    {isExpanded ? <ExpandLess /> : <ExpandMore />}
                  </IconButton>
                )}
              </Box>

              {isExpanded && goalObjectives.length > 0 && (
                <Box sx={{ ml: 4, mt: 1 }}>
                  {goalObjectives.map(objective => (
                    <Box key={objective.id} display="flex" alignItems="center" gap={1} sx={{ 
                      mb: 0.5, 
                      p: 0.5,
                      borderRadius: 1,
                      bgcolor: assignment.selected_goal_ids.includes(objective.id) ? 'secondary.50' : 'transparent',
                      '&:hover': { bgcolor: 'grey.100' }
                    }}>
                      <Checkbox
                        checked={assignment.selected_goal_ids.includes(objective.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            handleGoalSelectionChange([...assignment.selected_goal_ids, objective.id]);
                          } else {
                            handleGoalSelectionChange(assignment.selected_goal_ids.filter(id => id !== objective.id));
                          }
                        }}
                        size="small"
                      />
                      <Typography variant="body2" color="text.secondary">
                        📋 {objective.objective_description}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              )}
            </Box>
          );
        })}
      </Box>

      {assignment.selected_goal_ids.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="caption" color="text.secondary">
            Selected: {assignment.selected_goal_ids.length} item{assignment.selected_goal_ids.length !== 1 ? 's' : ''}
          </Typography>
        </Box>
      )}
    </Box>
  );
}
