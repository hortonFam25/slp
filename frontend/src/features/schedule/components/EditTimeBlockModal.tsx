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
  Alert,
  Autocomplete,
  FormControlLabel,
  Checkbox,
  Divider,
  Grid,
  IconButton,
  Paper,
  Card,
  CardContent,
  Collapse
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
  Close
} from '@mui/icons-material';
import { StudentScheduleView } from '../../../lib/api/schedulingStudents';
import { TimeBlockSummary } from '../../../lib/api/scheduling';
import { RecurringSchedule, RecurringConfig } from './RecurringSchedule';
import { useStudentActiveGoals } from '../../../lib/hooks/useStudentGoals';
import { useTeachers } from '../../../lib/hooks/useTeachers';

// Helper function to parse selected goals and objectives (reused from other modals)
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

// Time Block Activity interface
interface TimeBlockActivity {
  id?: number;
  start_minute: number;
  duration_minutes: number;
  activity_name: string;
  sequence_order: number;
}

// Student Goal Assignment interface
interface StudentGoalAssignment {
  student_id: number;
  student_name: string;
  selected_goal_ids: number[];
  expanded: boolean;
}

interface EditTimeBlockModalProps {
  open: boolean;
  onClose: () => void;
  timeBlock: TimeBlockSummary;
  students: StudentScheduleView[];
  onUpdateTimeBlock: (timeBlockData: {
    id: number;
    title: string;
    start_datetime: string;
    end_datetime: string;
    location?: string;
    notes?: string;
    teacher_id?: number;
    am_pm_indicator?: string;
    activities?: TimeBlockActivity[];
    student_goal_assignments?: { [key: number]: { goals: number[]; objectives: number[] } };
    recurring_config?: RecurringConfig;
  }) => void;
}

export function EditTimeBlockModal({
  open,
  onClose,
  timeBlock,
  students,
  onUpdateTimeBlock
}: EditTimeBlockModalProps) {
  // Initialize state with time block data
  const [title, setTitle] = useState('');
  const [startDateTime, setStartDateTime] = useState<Date>(new Date());
  const [endDateTime, setEndDateTime] = useState<Date>(new Date());
  const [location, setLocation] = useState('');
  const [notes, setNotes] = useState('');
  const [selectedTeacher, setSelectedTeacher] = useState<number | ''>('');
  const [amPmIndicator, setAmPmIndicator] = useState<string>('');
  const [activities, setActivities] = useState<TimeBlockActivity[]>([]);
  const [studentGoalAssignments, setStudentGoalAssignments] = useState<{ [key: number]: StudentGoalAssignment }>({});
  const [studentGoalsData, setStudentGoalsData] = useState<{ [key: number]: any[] }>({});
  const [recurringConfig, setRecurringConfig] = useState<RecurringConfig>({
    enabled: false,
    frequency: 'weekly',
    interval: 1,
    endDate: null,
    daysOfWeek: []
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load teachers
  const { teachers, fetchTeachersSummary } = useTeachers();

  // Load teachers on mount
  useEffect(() => {
    fetchTeachersSummary(true); // Load active teachers
  }, [fetchTeachersSummary]);

  // Initialize form with time block data
  useEffect(() => {
    if (timeBlock) {
      setTitle(timeBlock.title || '');
      setLocation(timeBlock.location || '');
      setNotes(timeBlock.notes || '');
      setAmPmIndicator(timeBlock.am_pm_indicator || '');
      setSelectedTeacher(timeBlock.teacher_id || '');
      
      if (timeBlock.start_datetime) {
        setStartDateTime(new Date(timeBlock.start_datetime));
      }
      if (timeBlock.end_datetime) {
        setEndDateTime(new Date(timeBlock.end_datetime));
      }

      // TODO: Load existing activities and student assignments
      setActivities([]);
      setStudentGoalAssignments({});
    }
  }, [timeBlock]);

  // Form validation
  const canSubmit = useMemo(() => {
    return title.trim() && startDateTime && endDateTime && endDateTime > startDateTime;
  }, [title, startDateTime, endDateTime]);

  // Generate time options for activities
  const generateActivityTimeOptions = useMemo(() => {
    if (!startDateTime || !endDateTime) return [];
    
    const options = [];
    const blockStart = startDateTime;
    const blockEnd = endDateTime;
    const diffMinutes = Math.floor((blockEnd.getTime() - blockStart.getTime()) / (1000 * 60));
    
    for (let minute = 0; minute <= diffMinutes; minute += 5) {
      const timeInBlock = new Date(blockStart.getTime() + minute * 60 * 1000);
      options.push({
        value: minute,
        label: format(timeInBlock, 'h:mm a'),
        minutes: minute
      });
    }
    
    return options;
  }, [startDateTime, endDateTime]);

  // Handle adding new activity
  const handleAddActivity = () => {
    const newActivity: TimeBlockActivity = {
      start_minute: 0,
      duration_minutes: 5,
      activity_name: '',
      sequence_order: activities.length + 1
    };
    setActivities([...activities, newActivity]);
  };

  // Handle removing activity
  const handleRemoveActivity = (index: number) => {
    const newActivities = activities.filter((_, i) => i !== index);
    setActivities(newActivities);
  };

  // Handle activity change
  const handleActivityChange = (index: number, field: keyof TimeBlockActivity, value: any) => {
    const newActivities = [...activities];
    newActivities[index] = { ...newActivities[index], [field]: value };
    setActivities(newActivities);
  };

  // Handle adding student to assignments
  const handleAddStudent = (student: StudentScheduleView) => {
    setStudentGoalAssignments(prev => ({
      ...prev,
      [student.student_id]: {
        student_id: student.student_id,
        student_name: student.student_name,
        selected_goal_ids: [],
        expanded: true
      }
    }));
  };

  // Handle removing student from assignments
  const handleRemoveStudent = (studentId: number) => {
    setStudentGoalAssignments(prev => {
      const newAssignments = { ...prev };
      delete newAssignments[studentId];
      return newAssignments;
    });
  };

  // Component for student goal assignment (similar to TimeBlockSchedulingModal)
  const StudentGoalAssignmentPanel = ({ 
    assignment, 
    onGoalsLoaded 
  }: { 
    assignment: StudentGoalAssignment;
    onGoalsLoaded?: (studentId: number, goals: any[]) => void;
  }) => {
    const { studentGoals, loading: goalsLoading } = useStudentActiveGoals(
      assignment.student_id,
      true
    );

    useEffect(() => {
      if (studentGoals.length > 0 && onGoalsLoaded) {
        onGoalsLoaded(assignment.student_id, studentGoals);
      }
    }, [studentGoals, assignment.student_id, onGoalsLoaded]);

    const handleGoalSelectionChange = (selectedIds: number[]) => {
      setStudentGoalAssignments(prev => ({
        ...prev,
        [assignment.student_id]: {
          ...prev[assignment.student_id],
          selected_goal_ids: selectedIds
        }
      }));
    };

    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Person color="primary" />
              <Typography variant="h6">{assignment.student_name}</Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <IconButton
                size="small"
                onClick={() => setStudentGoalAssignments(prev => ({
                  ...prev,
                  [assignment.student_id]: {
                    ...prev[assignment.student_id],
                    expanded: !prev[assignment.student_id].expanded
                  }
                }))}
              >
                {assignment.expanded ? <ExpandLess /> : <ExpandMore />}
              </IconButton>
              <IconButton
                size="small"
                onClick={() => handleRemoveStudent(assignment.student_id)}
                color="error"
              >
                <Delete />
              </IconButton>
            </Box>
          </Box>

          <Collapse in={assignment.expanded}>
            {goalsLoading ? (
              <Typography color="text.secondary">Loading goals...</Typography>
            ) : studentGoals.length === 0 ? (
              <Typography color="text.secondary">No active goals found for this student.</Typography>
            ) : (
              <Autocomplete
                multiple
                options={studentGoals.flatMap(goal => [
                  { id: goal.id, label: `🎯 ${goal.goal_text}`, type: 'goal' },
                  ...(goal.objectives || []).map((obj: any) => ({
                    id: obj.id,
                    label: `  📋 ${obj.objective_text}`,
                    type: 'objective'
                  }))
                ])}
                getOptionLabel={(option) => option.label}
                value={assignment.selected_goal_ids.map(id => {
                  const goal = studentGoals.find(g => g.id === id);
                  if (goal) return { id, label: `🎯 ${goal.goal_text}`, type: 'goal' };
                  
                  const objective = studentGoals.flatMap(g => g.objectives || []).find((obj: any) => obj.id === id);
                  if (objective) return { id, label: `  📋 ${objective.objective_text}`, type: 'objective' };
                  
                  return { id, label: `Unknown (${id})`, type: 'unknown' };
                }).filter(Boolean)}
                onChange={(_, newValue) => {
                  handleGoalSelectionChange(newValue.map(item => item.id));
                }}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Select Goals & Objectives"
                    placeholder="Choose goals and objectives for this student..."
                    size="small"
                  />
                )}
              />
            )}
          </Collapse>
        </CardContent>
      </Card>
    );
  };

  const handleSubmit = async () => {
    if (!canSubmit) return;

    setLoading(true);
    setError(null);

    try {
      // Build student goal assignments
      const goalAssignments: { [key: number]: { goals: number[]; objectives: number[] } } = {};
      Object.values(studentGoalAssignments).forEach(assignment => {
        if (assignment.selected_goal_ids.length > 0) {
          const studentGoals = studentGoalsData[assignment.student_id] || [];
          const parsed = parseSelectedGoalsAndObjectives(assignment.selected_goal_ids, studentGoals);
          
          goalAssignments[assignment.student_id] = {
            goals: parsed.goalIds,
            objectives: parsed.objectiveIds
          };
        }
      });

      const timeBlockData = {
        id: timeBlock.id,
        title: title.trim(),
        start_datetime: formatLocalDateTime(startDateTime),
        end_datetime: formatLocalDateTime(endDateTime),
        location: location.trim() || undefined,
        notes: notes.trim() || undefined,
        teacher_id: selectedTeacher ? Number(selectedTeacher) : undefined,
        am_pm_indicator: amPmIndicator || undefined,
        activities: activities.length > 0 ? activities : undefined,
        student_goal_assignments: Object.keys(goalAssignments).length > 0 ? goalAssignments : undefined,
        recurring_config: recurringConfig.enabled ? recurringConfig : undefined
      };

      console.log('🔄 Edit Time Block - Submitting:', timeBlockData);
      await onUpdateTimeBlock(timeBlockData);
      onClose();
    } catch (err) {
      console.error('❌ Edit Time Block Error:', err);
      setError(err instanceof Error ? err.message : 'Failed to update time block');
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
        maxWidth="lg"
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
              Edit Time Block
            </Typography>
            <Typography variant="subtitle2" color="text.secondary">
              Modify time block details, activities, and student assignments
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

          {/* Basic Information */}
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <TextField
                label="Time Block Title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                fullWidth
                required
                placeholder="Enter time block title..."
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                label="Location"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                fullWidth
                placeholder="Room or location..."
              />
            </Grid>
          </Grid>

          {/* Teacher and AM/PM */}
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Teacher</InputLabel>
                <Select
                  value={selectedTeacher}
                  label="Teacher"
                  onChange={(e) => setSelectedTeacher(e.target.value)}
                >
                  <MenuItem value="">
                    <em>No teacher assigned</em>
                  </MenuItem>
                  {teachers.map((teacher) => (
                    <MenuItem key={teacher.id} value={teacher.id}>
                      {teacher.first_name} {teacher.last_name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>AM/PM Indicator</InputLabel>
                <Select
                  value={amPmIndicator}
                  label="AM/PM Indicator"
                  onChange={(e) => setAmPmIndicator(e.target.value)}
                >
                  <MenuItem value="">
                    <em>None</em>
                  </MenuItem>
                  <MenuItem value="AM">AM</MenuItem>
                  <MenuItem value="PM">PM</MenuItem>
                  <MenuItem value="All Day">All Day</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>

          {/* Date and Time Selection */}
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <DateTimePicker
                label="Start Date & Time"
                value={startDateTime}
                onChange={(newValue) => newValue && setStartDateTime(newValue)}
                slotProps={{
                  textField: { fullWidth: true }
                }}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <DateTimePicker
                label="End Date & Time"
                value={endDateTime}
                onChange={(newValue) => newValue && setEndDateTime(newValue)}
                slotProps={{
                  textField: { fullWidth: true }
                }}
              />
            </Grid>
          </Grid>

          {/* Notes */}
          <TextField
            label="Notes"
            multiline
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            fullWidth
            placeholder="Add any notes about this time block..."
          />

          {/* Activities Section */}
          <Divider />
          <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                <AccessTime sx={{ mr: 1, verticalAlign: 'middle' }} />
                5-Minute Activities
              </Typography>
              <Button
                startIcon={<Add />}
                onClick={handleAddActivity}
                size="small"
                variant="outlined"
              >
                Add Activity
              </Button>
            </Box>

            {activities.map((activity, index) => (
              <Paper key={index} sx={{ p: 2, mb: 2 }}>
                <Grid container spacing={2} alignItems="center">
                  <Grid item xs={12} md={3}>
                    <FormControl fullWidth size="small">
                      <InputLabel>Start Time</InputLabel>
                      <Select
                        value={activity.start_minute}
                        label="Start Time"
                        onChange={(e) => handleActivityChange(index, 'start_minute', Number(e.target.value))}
                      >
                        {generateActivityTimeOptions.map((option) => (
                          <MenuItem key={option.value} value={option.value}>
                            {option.label}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid item xs={12} md={2}>
                    <FormControl fullWidth size="small">
                      <InputLabel>Duration</InputLabel>
                      <Select
                        value={activity.duration_minutes}
                        label="Duration"
                        onChange={(e) => handleActivityChange(index, 'duration_minutes', Number(e.target.value))}
                      >
                        <MenuItem value={5}>5 min</MenuItem>
                        <MenuItem value={10}>10 min</MenuItem>
                        <MenuItem value={15}>15 min</MenuItem>
                        <MenuItem value={20}>20 min</MenuItem>
                        <MenuItem value={30}>30 min</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <TextField
                      label="Activity Name"
                      value={activity.activity_name}
                      onChange={(e) => handleActivityChange(index, 'activity_name', e.target.value)}
                      fullWidth
                      size="small"
                      placeholder="Activity description..."
                    />
                  </Grid>
                  <Grid item xs={12} md={1}>
                    <IconButton
                      onClick={() => handleRemoveActivity(index)}
                      color="error"
                      size="small"
                    >
                      <Delete />
                    </IconButton>
                  </Grid>
                </Grid>
              </Paper>
            ))}
          </Box>

          {/* Student Assignments */}
          <Divider />
          <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                <Group sx={{ mr: 1, verticalAlign: 'middle' }} />
                Student Assignments
              </Typography>
              <Autocomplete
                options={students.filter(s => !studentGoalAssignments[s.student_id])}
                getOptionLabel={(option) => option.student_name}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Add Student"
                    size="small"
                    sx={{ minWidth: 200 }}
                  />
                )}
                onChange={(_, student) => {
                  if (student) {
                    handleAddStudent(student);
                  }
                }}
                value={null}
              />
            </Box>

            {Object.values(studentGoalAssignments).map((assignment) => (
              <StudentGoalAssignmentPanel
                key={assignment.student_id}
                assignment={assignment}
                onGoalsLoaded={(studentId, goals) => {
                  setStudentGoalsData(prev => ({
                    ...prev,
                    [studentId]: goals
                  }));
                }}
              />
            ))}
          </Box>

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
            disabled={!canSubmit || loading}
            sx={{ minWidth: 120 }}
          >
            {loading ? 'Updating...' : 'Update Time Block'}
          </Button>
        </DialogActions>
      </Dialog>
    </LocalizationProvider>
  );
}
