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
  Collapse,
  Chip,
  useMediaQuery,
  useTheme
} from '@mui/material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { TimePicker } from '@mui/x-date-pickers/TimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { format, setHours, setMinutes, addMinutes, isSameDay, parseISO, differenceInDays } from 'date-fns';
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
  Close,
  Repeat,
  Warning,
  Info
} from '@mui/icons-material';
import { StudentScheduleView } from '../../../lib/api/schedulingStudents';
import { TimeBlockSummary } from '../../../lib/api/scheduling';
import { RecurringSchedule, RecurringConfig } from './RecurringSchedule';
import { SeriesActionDialog } from './SeriesActionDialog';
import { SeriesPatternDialog } from './SeriesPatternDialog';
import { useStudentActiveGoals } from '../../../lib/hooks/useStudentGoals';
import { useTeachers } from '../../../lib/hooks/useTeachers';

// Helper function to analyze series update requirements (copied from EditAppointmentModal)
const analyzeSeriesUpdate = (originalDate: Date, newDate: Date) => {
  const originalDateOnly = new Date(originalDate.getFullYear(), originalDate.getMonth(), originalDate.getDate());
  const newDateOnly = new Date(newDate.getFullYear(), newDate.getMonth(), newDate.getDate());
  
  // Check if date changed
  const dateChanged = !isSameDay(originalDateOnly, newDateOnly);
  
  if (!dateChanged) {
    return { type: 'time_only' as const };
  }
  
  // Calculate offset in days
  const offsetDays = differenceInDays(newDateOnly, originalDateOnly);
  const originalDayOfWeek = originalDate.getDay();
  const newDayOfWeek = newDate.getDay();
  const dayOfWeekChanged = originalDayOfWeek !== newDayOfWeek;
  
  return {
    type: 'date_changed' as const,
    offsetDays,
    originalDayOfWeek,
    newDayOfWeek,
    dayOfWeekChanged
  };
};

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
  start_datetime?: string;
  end_datetime?: string;
  activity_name: string;
  activity_type?: string;
  description?: string;
  materials_needed?: string;
  notes?: string;
  sequence_order: number;
  assigned_student_ids?: number[];
}

// Student Goal Assignment interface
interface StudentGoalAssignment {
  student_id: number;
  selected_goal_ids: number[];
  expanded_goals: number[];
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
    // Series management fields
    updateType?: 'single' | 'series' | 'pattern';
    seriesPatternUpdate?: any;
  }) => void;
}

// Generate time options (reused from TimeBlockSchedulingModal)
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
  { value: 'PM', label: 'PM' }
];

export function EditTimeBlockModal({
  open,
  onClose,
  timeBlock,
  students,
  onUpdateTimeBlock
}: EditTimeBlockModalProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  // Form state
  const [title, setTitle] = useState('');
  const [teacherId, setTeacherId] = useState<number | ''>('');
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [maxStudents, setMaxStudents] = useState<number | ''>('');
  const [location, setLocation] = useState('');
  const [notes, setNotes] = useState('');
  const [amPmIndicator, setAmPmIndicator] = useState('');
  
  // Student assignment state
  const [selectedStudents, setSelectedStudents] = useState<StudentScheduleView[]>([]);
  const [filteredStudents, setFilteredStudents] = useState<StudentScheduleView[]>([]);
  const [loadingFilteredStudents, setLoadingFilteredStudents] = useState(false);
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
  
  // Loading and error state
  const [loading, setLoading] = useState(false);
  const [dataLoading, setDataLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Series management state
  const [isSeriesTimeBlock, setIsSeriesTimeBlock] = useState(false);
  const [seriesAppointment, setSeriesAppointment] = useState<any>(null);
  const [seriesActionDialogOpen, setSeriesActionDialogOpen] = useState(false);
  const [seriesPatternDialogOpen, setSeriesPatternDialogOpen] = useState(false);
  const [pendingUpdate, setPendingUpdate] = useState<any>(null);
  const [originalDate, setOriginalDate] = useState<Date | null>(null);

  // Load teachers
  const { teachersSummary: teachers = [], fetchTeachersSummary } = useTeachers();

  // Load teachers on mount
  useEffect(() => {
    fetchTeachersSummary(true); // active only = true
  }, [fetchTeachersSummary]);

  // Load filtered students when teacher is selected
  useEffect(() => {
    const loadFilteredStudents = async () => {
      if (teacherId && typeof teacherId === 'number') {
        try {
          setLoadingFilteredStudents(true);
          const { schedulingApi } = await import('../../../lib/api/scheduling');
          const eligibleStudents = await schedulingApi.getStudentsByTeacher(teacherId);
          
          // Convert StudentSummary to StudentScheduleView format
          const scheduleViewStudents: StudentScheduleView[] = eligibleStudents.map(student => ({
            id: student.id,
            first: student.first,
            last: student.last,
            uic: student.uic || undefined,
            grade_level: student.grade_level || undefined,
            case_manager_name: null,
            enrollment_status: student.enrollment_status,
            school_id: undefined,
            school: null,
            teacher_assignments: [],
            primary_teacher: null,
            current_appointments: [],
            appointment_count: 0,
            has_appointments: false,
            full_name: `${student.first} ${student.last}`,
            school_name: 'School Assignment',
            primary_teacher_name: 'Teacher Assignment'
          }));
          
          setFilteredStudents(scheduleViewStudents);
        } catch (error) {
          console.error('Failed to load filtered students:', error);
          setFilteredStudents([]);
        } finally {
          setLoadingFilteredStudents(false);
        }
      } else {
        // No teacher selected, show all students
        setFilteredStudents(students);
      }
    };

    loadFilteredStudents();
  }, [teacherId, students]);

  // Load time block data when modal opens
  useEffect(() => {
    const loadTimeBlockData = async () => {
      if (!open || !timeBlock.id) return;

      setDataLoading(true);
      setError(null);

      try {
        const { schedulingApi } = await import('../../../lib/api/scheduling');
        
        // Load detailed time block data
        const [detailedData, studentGoalsData] = await Promise.all([
          schedulingApi.getTimeBlockDetailed(timeBlock.id),
          schedulingApi.getTimeBlockStudentGoals(timeBlock.id)
        ]);

        console.log('📋 Loaded time block data:', detailedData);
        console.log('🎯 Loaded student goals:', studentGoalsData);

        // Populate basic fields
        setTitle(detailedData.title || '');
        setLocation(detailedData.location || '');
        setNotes(detailedData.notes || '');
        setAmPmIndicator(detailedData.am_pm_indicator || '');
        setTeacherId(detailedData.teacher_id || '');
        setMaxStudents(detailedData.max_students || '');

        // Set date and times
        if (detailedData.start_datetime && detailedData.end_datetime) {
          const startDate = new Date(detailedData.start_datetime);
          const endDate = new Date(detailedData.end_datetime);
          
          setOriginalDate(startDate);
          setSelectedDate(startDate); // Set the date picker
          
          const startTimeString = `${startDate.getHours().toString().padStart(2, '0')}:${startDate.getMinutes().toString().padStart(2, '0')}`;
          const endTimeString = `${endDate.getHours().toString().padStart(2, '0')}:${endDate.getMinutes().toString().padStart(2, '0')}`;
          
          setStartTime(startTimeString);
          setEndTime(endTimeString);
        }

        // Set activities
        if (detailedData.activities && detailedData.activities.length > 0) {
          setActivities(detailedData.activities);
          setShowActivities(true);
        } else {
      setActivities([]);
          setShowActivities(false);
        }

        // Set students
        if (detailedData.assigned_students && detailedData.assigned_students.length > 0) {
          // Convert to StudentScheduleView format
          const assignedStudents: StudentScheduleView[] = detailedData.assigned_students.map((student: any) => ({
            id: student.id,
            first: student.first,
            last: student.last,
            uic: student.uic || undefined,
            grade_level: student.grade_level || undefined,
            case_manager_name: null,
            enrollment_status: student.enrollment_status,
            school_id: student.school_id,
            school: null,
            teacher_assignments: [],
            primary_teacher: null,
            current_appointments: [],
            appointment_count: 0,
            has_appointments: false,
            full_name: `${student.first} ${student.last}`,
            school_name: 'School Assignment',
            primary_teacher_name: 'Teacher Assignment'
          }));
          
          setSelectedStudents(assignedStudents);

          // Set up goal assignments
          const goalAssignments: { [key: number]: StudentGoalAssignment } = {};
          assignedStudents.forEach(student => {
            const studentGoals = studentGoalsData.find(sg => sg.student_id === student.id);
            goalAssignments[student.id] = {
              student_id: student.id,
              selected_goal_ids: studentGoals ? [...studentGoals.goals, ...studentGoals.objectives] : [],
              expanded_goals: []
            };
          });
          
          setStudentGoalAssignments(goalAssignments);
        }

        // Check if this is part of a series (check for appointments with series_id)
        const appointments = await schedulingApi.getTimeBlockAppointments(timeBlock.id);
        const seriesAppointment = appointments.find((apt: any) => (apt as any).series_id);
        
        if (seriesAppointment) {
          setIsSeriesTimeBlock(true);
          setSeriesAppointment({
            id: seriesAppointment.id,
            series_id: (seriesAppointment as any).series_id,
            student_id: seriesAppointment.student_id,
            student_name: seriesAppointment.student_name,
            start_datetime: seriesAppointment.start_datetime,
            end_datetime: seriesAppointment.end_datetime,
            appointment_type: 'group',
            status: seriesAppointment.status
          });
        }

      } catch (error) {
        console.error('❌ Failed to load time block data:', error);
        setError('Failed to load time block data. Please try again.');
      } finally {
        setDataLoading(false);
      }
    };

    loadTimeBlockData();
  }, [open, timeBlock.id]);

  // Calculate block duration in minutes
  const blockDurationMinutes = useMemo(() => {
    if (!startTime || !endTime) return 0;
    const [startHour, startMinute] = startTime.split(':').map(Number);
    const [endHour, endMinute] = endTime.split(':').map(Number);
    const startMinutes = startHour * 60 + startMinute;
    const endMinutes = endHour * 60 + endMinute;
    return Math.max(0, endMinutes - startMinutes);
  }, [startTime, endTime]);

  // Generate time options for activity start/end times
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

  // Form validation
  const canSubmit = useMemo(() => {
    return (
      title.trim() !== '' &&
      startTime !== '' &&
      endTime !== '' &&
      selectedStudents.length > 0 &&
      blockDurationMinutes > 0 &&
      !dataLoading
    );
  }, [title, startTime, endTime, selectedStudents.length, blockDurationMinutes, dataLoading]);

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
    let startMinute = 0;
    if (activities.length > 0) {
      const lastActivity = activities[activities.length - 1];
      startMinute = lastActivity.start_minute + lastActivity.duration_minutes;
    }
    
    const newActivity: TimeBlockActivity = {
      start_minute: Math.min(startMinute, blockDurationMinutes - 5),
      duration_minutes: 5,
      activity_name: '',
      activity_type: 'main_activity',
      description: '',
      materials_needed: '',
      notes: '',
      sequence_order: nextOrder,
      assigned_student_ids: [] // Initialize empty student assignments
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

  // Analyze changes (similar to EditAppointmentModal)
  const changeAnalysis = useMemo(() => {
    if (!originalDate) return null;
    return analyzeSeriesUpdate(originalDate, selectedDate);
  }, [originalDate, selectedDate]);

  // Check if date has changed
  const hasDateChanged = changeAnalysis?.type === 'date_changed';
  
  // Check if only time has changed
  const hasTimeOnlyChanged = useMemo(() => {
    if (!originalDate || !startTime || !endTime) return false;
    
    const [startHour, startMinute] = startTime.split(':').map(Number);
    const [endHour, endMinute] = endTime.split(':').map(Number);
    
    return (
      originalDate.getHours() !== startHour ||
      originalDate.getMinutes() !== startMinute
    ) && !hasDateChanged;
  }, [originalDate, startTime, endTime, hasDateChanged]);

  // Check if activities have changed
  const hasActivitiesChanged = useMemo(() => {
    // Simple check: if activities array has content (indicating user made changes)
    return activities.length > 0;
  }, [activities]);

  // Handle form submission
  const handleSubmit = async () => {
    if (!canSubmit) return;

    const updateData = buildUpdateData();

    // Check if this time block is part of a series
    if (isSeriesTimeBlock) {
      // Check what type of changes were made
      const hasTimeBlockChanges = changeAnalysis?.type === 'date_changed' || hasTimeOnlyChanged;
      
      if (hasTimeBlockChanges) {
        // Time block changes - use existing series logic
        if (changeAnalysis?.type === 'date_changed') {
          // Date changed - show pattern dialog for more options
          setPendingUpdate(updateData);
          setSeriesPatternDialogOpen(true);
          return;
        } else if (hasTimeOnlyChanged) {
          // Time only changed - show simple series dialog
          setPendingUpdate(updateData);
          setSeriesActionDialogOpen(true);
          return;
        }
      } else if (hasActivitiesChanged) {
        // Only activities changed - show series dialog for activity updates
        setPendingUpdate(updateData);
        setSeriesActionDialogOpen(true);
        return;
      }
    }

    // Direct update (single time block or no series)
    await performUpdate(updateData);
  };

  // Helper function to build update data
  const buildUpdateData = () => {
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
          const studentGoals = studentGoalsData[assignment.student_id] || [];
          const parsed = parseSelectedGoalsAndObjectives(assignment.selected_goal_ids, studentGoals);
          
          goalAssignments[assignment.student_id] = {
            goals: parsed.goalIds,
            objectives: parsed.objectiveIds
          };
        }
      });

    return {
        id: timeBlock.id,
        title: title.trim(),
        start_datetime: formatLocalDateTime(startDateTime),
        end_datetime: formatLocalDateTime(endDateTime),
        location: location.trim() || undefined,
        notes: notes.trim() || undefined,
      teacher_id: teacherId ? Number(teacherId) : undefined,
        am_pm_indicator: amPmIndicator || undefined,
        activities: activities.length > 0 ? activities : undefined,
        student_goal_assignments: Object.keys(goalAssignments).length > 0 ? goalAssignments : undefined,
      recurring_config: recurringConfig.isRecurring ? recurringConfig : undefined
    };
  };

  // Perform the actual update
  const performUpdate = async (updateData: any) => {
    setLoading(true);
    setError(null);

    try {
      console.log('🔄 Edit Time Block - Submitting:', updateData);
      await onUpdateTimeBlock(updateData);
      onClose();
    } catch (err) {
      console.error('❌ Edit Time Block Error:', err);
      setError(err instanceof Error ? err.message : 'Failed to update time block');
    } finally {
      setLoading(false);
    }
  };

  // Handle series action dialog close
  const handleSeriesActionClose = () => {
    setSeriesActionDialogOpen(false);
    setPendingUpdate(null);
  };

  // Handle single action
  const handleSingleAction = async () => {
    if (pendingUpdate) {
      const updateData = {
        ...pendingUpdate,
        updateType: 'single'
      };
      await performUpdate(updateData);
    }
    setSeriesActionDialogOpen(false);
    setPendingUpdate(null);
  };

  // Handle series action
  const handleSeriesAction = async () => {
    if (pendingUpdate) {
      const updateData = {
        ...pendingUpdate,
        updateType: 'series'
      };
      await performUpdate(updateData);
    }
    setSeriesActionDialogOpen(false);
    setPendingUpdate(null);
  };

  // Handle pattern dialog close
  const handlePatternDialogClose = () => {
    setSeriesPatternDialogOpen(false);
    setPendingUpdate(null);
  };

  // Handle single update from pattern dialog
  const handlePatternSingleUpdate = async () => {
    if (pendingUpdate) {
      const updateData = {
        ...pendingUpdate,
        updateType: 'single'
      };
      await performUpdate(updateData);
    }
    setSeriesPatternDialogOpen(false);
    setPendingUpdate(null);
  };

  // Handle offset update from pattern dialog
  const handlePatternOffsetUpdate = async () => {
    if (pendingUpdate) {
      const updateData = {
        ...pendingUpdate,
        updateType: 'pattern',
        seriesPatternUpdate: { type: 'offset' }
      };
      await performUpdate(updateData);
    }
    setSeriesPatternDialogOpen(false);
    setPendingUpdate(null);
  };

  // Handle day alignment update from pattern dialog
  const handlePatternDayAlignmentUpdate = async () => {
    if (pendingUpdate) {
      const updateData = {
        ...pendingUpdate,
        updateType: 'pattern',
        seriesPatternUpdate: { type: 'dayAlignment' }
      };
      await performUpdate(updateData);
    }
    setSeriesPatternDialogOpen(false);
    setPendingUpdate(null);
  };

  const handleClose = () => {
    setError(null);
    onClose();
  };

  if (dataLoading) {
    return (
      <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
        <DialogContent sx={{ textAlign: 'center', py: 4 }}>
          <Typography>Loading time block data...</Typography>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Dialog 
        open={open} 
        onClose={handleClose}
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
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Box display="flex" alignItems="center" gap={1}>
              <Group color="primary" sx={{ fontSize: isMobile ? 20 : 24 }} />
          <Box>
                <Typography variant={isMobile ? "subtitle1" : "h6"}>
              Edit Time Block
                  {isSeriesTimeBlock && (
                    <Chip 
                      icon={<Repeat />} 
                      label="Recurring Series" 
                      size="small" 
                      color="primary" 
                      sx={{ ml: 1 }} 
                    />
                  )}
            </Typography>
                <Typography variant="body2" color="text.secondary">
                  {originalDate && format(originalDate, 'EEEE, MMMM d, yyyy')}
            </Typography>
              </Box>
          </Box>
          <IconButton onClick={handleClose} size="small">
            <Close />
          </IconButton>
          </Box>
        </DialogTitle>

        <DialogContent sx={{ 
          p: isMobile ? 2 : 3,
          overflow: 'auto'
        }}>
          {error && (
            <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

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
                        <MenuItem value="">
                          <em>None</em>
                        </MenuItem>
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

                  <Grid item xs={12} md={3}>
                    <DatePicker
                      label="Time Block Date"
                      value={selectedDate}
                      onChange={(newDate) => setSelectedDate(newDate || new Date())}
                      minDate={new Date()} // Prevent scheduling in the past
                      slotProps={{
                        textField: {
                          fullWidth: true,
                          helperText: "Select the date for this time block"
                        }
                      }}
                    />
          </Grid>

                  <Grid item xs={12} md={3}>
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

                  <Grid item xs={12} md={3}>
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

                  <Grid item xs={12} md={3}>
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
                  <MenuItem value="">
                          <em>No teacher assigned</em>
                  </MenuItem>
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
                      options={filteredStudents.filter(s => !selectedStudents.find(sel => sel.id === s.id))}
                      getOptionLabel={(student) => `${student.first} ${student.last} (${student.grade_level})`}
                      loading={loadingFilteredStudents}
                      renderInput={(params) => (
                        <TextField 
                          {...params} 
                          label="Add Student" 
                          placeholder={teacherId ? "Students assigned to selected teacher/case manager..." : "Select a teacher first to see eligible students"}
                          helperText={teacherId ? `Showing ${filteredStudents.length} eligible students` : "Select a teacher/case manager to filter students"}
                        />
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
                    {selectedStudents.length > 0 && (
                      <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mb: 2 }}>
                        💡 Click "Show Goals" or the arrow to expand and select goals for each student
                      </Typography>
                    )}
                    
                    {/* Student Time Slots Display */}
                    {selectedStudents.length > 0 && blockDurationMinutes > 0 && (
                      <Box sx={{ mb: 3 }}>
                        <Typography variant="subtitle2" gutterBottom sx={{ color: 'primary.main', mb: 2 }}>
                          ⏰ Individual Student Time Slots
                        </Typography>
                        <Paper sx={{ p: 2, bgcolor: 'grey.50', border: 1, borderColor: 'grey.300' }}>
                          <Grid container spacing={1}>
                            {selectedStudents.map((student, index) => {
                              const studentsCount = selectedStudents.length;
                              const minutesPerStudent = Math.floor(blockDurationMinutes / studentsCount / 5) * 5; // Round to 5-min increments
                              const startMinute = index * minutesPerStudent;
                              
                              // Calculate actual times
                              const [blockStartHour, blockStartMinute] = startTime.split(':').map(Number);
                              const studentStartTime = new Date(selectedDate);
                              studentStartTime.setHours(blockStartHour, blockStartMinute + startMinute, 0, 0);
                              
                              const studentEndTime = new Date(studentStartTime);
                              studentEndTime.setMinutes(studentEndTime.getMinutes() + minutesPerStudent);
                              
                              return (
                                <Grid item xs={12} md={6} key={student.id}>
                                  <Box sx={{ 
                                    display: 'flex', 
                                    alignItems: 'center', 
                                    gap: 2,
                                    p: 1.5,
                                    bgcolor: 'white',
                                    borderRadius: 1,
                                    border: 1,
                                    borderColor: 'primary.light'
                                  }}>
                                    <Box sx={{ 
                                      minWidth: 40,
                                      height: 40,
                                      borderRadius: '50%',
                                      bgcolor: 'primary.main',
                                      color: 'white',
                                      display: 'flex',
                                      alignItems: 'center',
                                      justifyContent: 'center',
                                      fontSize: '0.875rem',
                                      fontWeight: 'bold'
                                    }}>
                                      {index + 1}
                                    </Box>
                                    <Box sx={{ flex: 1 }}>
                                      <Typography variant="subtitle2" sx={{ fontWeight: 'medium' }}>
                                        {student.first} {student.last}
                                      </Typography>
                                      <Typography variant="caption" color="text.secondary">
                                        {format(studentStartTime, 'h:mm a')} - {format(studentEndTime, 'h:mm a')} ({minutesPerStudent} min)
                                      </Typography>
                                    </Box>
                                  </Box>
                                </Grid>
                              );
                            })}
                          </Grid>
                          {selectedStudents.length > 0 && (
                            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2, fontStyle: 'italic' }}>
                              * Time slots are automatically calculated based on equal distribution of the {blockDurationMinutes}-minute block
                            </Typography>
                          )}
                        </Paper>
                      </Box>
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
                          {/* Activity Name and Type */}
                  <Grid item xs={12} md={6}>
                    <TextField
                      label="Activity Name"
                      value={activity.activity_name}
                              onChange={(e) => handleUpdateActivity(index, 'activity_name', e.target.value)}
                      fullWidth
                      size="small"
                              required
                              placeholder="e.g., Warm Up, Reading Practice"
                    />
                  </Grid>

                          <Grid item xs={12} md={6}>
                            <FormControl fullWidth size="small">
                              <InputLabel>Activity Type</InputLabel>
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

                          {/* Time Selection */}
                          <Grid item xs={12} md={6}>
                            <TimePicker
                              label="Activity Start Time"
                              value={(() => {
                                if (!startTime || !endTime) return null;
                                const [blockStartHour, blockStartMinute] = startTime.split(':').map(Number);
                                const activityStart = new Date(selectedDate);
                                activityStart.setHours(blockStartHour, blockStartMinute + activity.start_minute, 0, 0);
                                return activityStart;
                              })()}
                              onChange={(newTime) => {
                                if (newTime && startTime) {
                                  const [blockStartHour, blockStartMinute] = startTime.split(':').map(Number);
                                  const blockStart = new Date(selectedDate);
                                  blockStart.setHours(blockStartHour, blockStartMinute, 0, 0);
                                  
                                  const minutesFromBlockStart = Math.floor((newTime.getTime() - blockStart.getTime()) / (1000 * 60));
                                  const clampedMinutes = Math.max(0, Math.min(minutesFromBlockStart, blockDurationMinutes - 5));
                                  
                                  handleUpdateActivity(index, 'start_minute', clampedMinutes);
                                  
                                  // Update datetime field (use local time format)
                                  const activityStartDateTime = new Date(blockStart.getTime() + clampedMinutes * 60 * 1000);
                                  const localDateTimeString = formatLocalDateTime(activityStartDateTime);
                                  handleUpdateActivity(index, 'start_datetime', localDateTimeString);
                                }
                              }}
                              slotProps={{
                                textField: { 
                                  size: 'small',
                                  fullWidth: true,
                                  helperText: "Must be within time block timeframe"
                                }
                              }}
                            />
                </Grid>

                          <Grid item xs={12} md={6}>
                            <TimePicker
                              label="Activity End Time"
                              value={(() => {
                                if (!startTime || !endTime) return null;
                                const [blockStartHour, blockStartMinute] = startTime.split(':').map(Number);
                                const activityEnd = new Date(selectedDate);
                                activityEnd.setHours(blockStartHour, blockStartMinute + activity.start_minute + activity.duration_minutes, 0, 0);
                                return activityEnd;
                              })()}
                              onChange={(newTime) => {
                                if (newTime && startTime) {
                                  const [blockStartHour, blockStartMinute] = startTime.split(':').map(Number);
                                  const blockStart = new Date(selectedDate);
                                  blockStart.setHours(blockStartHour, blockStartMinute, 0, 0);
                                  
                                  const minutesFromBlockStart = Math.floor((newTime.getTime() - blockStart.getTime()) / (1000 * 60));
                                  const clampedEndMinutes = Math.max(activity.start_minute + 5, Math.min(minutesFromBlockStart, blockDurationMinutes));
                                  
                                  const newDuration = clampedEndMinutes - activity.start_minute;
                                  handleUpdateActivity(index, 'duration_minutes', newDuration);
                                  
                                  // Update datetime field (use local time format)
                                  const activityEndDateTime = new Date(blockStart.getTime() + clampedEndMinutes * 60 * 1000);
                                  const localEndDateTimeString = formatLocalDateTime(activityEndDateTime);
                                  handleUpdateActivity(index, 'end_datetime', localEndDateTimeString);
                                }
                              }}
                              slotProps={{
                                textField: { 
                                  size: 'small',
                                  fullWidth: true,
                                  helperText: "Must end before time block ends"
                                }
                              }}
                            />
                          </Grid>

                          {/* Student Assignment */}
                          <Grid item xs={12}>
              <Autocomplete
                              multiple
                              options={selectedStudents}
                              getOptionLabel={(student) => `${student.first} ${student.last}`}
                              value={selectedStudents.filter(student => 
                                activity.assigned_student_ids?.includes(student.id) || false
                              )}
                              onChange={(_, newValue) => {
                                const studentIds = newValue.map(student => student.id);
                                handleUpdateActivity(index, 'assigned_student_ids', studentIds);
                              }}
                renderInput={(params) => (
                  <TextField
                    {...params}
                                  label="Assign Students to Activity"
                                  placeholder="Select students who will participate in this activity..."
                    size="small"
                                  helperText={`${activity.assigned_student_ids?.length || 0} student(s) assigned`}
                                />
                              )}
                              renderTags={(value, getTagProps) =>
                                value.map((student, index) => (
                                  <Chip
                                    key={student.id}
                                    label={`${student.first} ${student.last}`}
                                    size="small"
                                    {...getTagProps({ index })}
                                  />
                                ))
                              }
                            />
                          </Grid>

                          {/* Description and Materials */}
                          <Grid item xs={12} md={6}>
                            <TextField
                              label="Description"
                              value={activity.description || ''}
                              onChange={(e) => handleUpdateActivity(index, 'description', e.target.value)}
                              fullWidth
                              size="small"
                              multiline
                              rows={2}
                              placeholder="Describe what happens in this activity..."
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
                              placeholder="List materials, tools, or resources needed..."
                            />
                          </Grid>
                        </Grid>
                      </Paper>
            ))}
          </Box>
                )}
              </Paper>
            </Grid>

            {/* Recurring Schedule (only show if not already a series) */}
            {!isSeriesTimeBlock && (
              <Grid item xs={12}>
          <RecurringSchedule
            value={recurringConfig}
            onChange={setRecurringConfig}
                  startDate={originalDate || new Date()}
                />
              </Grid>
            )}

            {/* Summary */}
            {canSubmit && (
              <Grid item xs={12}>
                <Alert severity="info">
                  <Typography variant="body2">
                    <strong>Ready to update:</strong> "{title}" 
                    {originalDate && ` on ${format(originalDate, 'MMM d, yyyy')}`} from {
                      TIME_OPTIONS.find(t => t.value === startTime)?.label
                    } to {
                      TIME_OPTIONS.find(t => t.value === endTime)?.label
                    } for {selectedStudents.length} student{selectedStudents.length !== 1 ? 's' : ''}.
                    {activities.length > 0 && ` Includes ${activities.length} planned activit${activities.length !== 1 ? 'ies' : 'y'}.`}
                    {isSeriesTimeBlock && (hasDateChanged || hasTimeOnlyChanged) && (
                      <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Warning fontSize="small" />
                        <span>This will affect the recurring series. You'll be asked how to apply the changes.</span>
                      </Box>
                    )}
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
            onClick={handleClose} 
            disabled={loading}
            fullWidth={isMobile}
            size={isMobile ? 'medium' : 'small'}
            sx={{ order: isMobile ? 2 : 1 }}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={!canSubmit || loading}
            fullWidth={isMobile}
            size={isMobile ? 'medium' : 'small'}
            startIcon={!isMobile ? <Schedule /> : undefined}
            sx={{ order: isMobile ? 1 : 2 }}
          >
            {loading ? 'Updating...' : (isMobile ? "Update Time Block" : "Update Time Block")}
          </Button>
        </DialogActions>

        {/* Series Action Dialog */}
        {seriesAppointment && (
          <SeriesActionDialog
            open={seriesActionDialogOpen}
            onClose={handleSeriesActionClose}
            appointment={seriesAppointment}
            action="edit"
            onSingleAction={handleSingleAction}
            onSeriesAction={handleSeriesAction}
          />
        )}

        {/* Series Pattern Dialog */}
        {seriesAppointment && originalDate && changeAnalysis && changeAnalysis.type === 'date_changed' && (
          <SeriesPatternDialog
            open={seriesPatternDialogOpen}
            onClose={handlePatternDialogClose}
            appointment={seriesAppointment}
            originalDate={originalDate}
            newDate={selectedDate}
            offsetDays={changeAnalysis.offsetDays}
            dayOfWeekChanged={changeAnalysis.dayOfWeekChanged}
            originalDayOfWeek={changeAnalysis.originalDayOfWeek}
            newDayOfWeek={changeAnalysis.newDayOfWeek}
            onSingleUpdate={handlePatternSingleUpdate}
            onOffsetUpdate={handlePatternOffsetUpdate}
            onDayAlignmentUpdate={handlePatternDayAlignmentUpdate}
          />
        )}
      </Dialog>
    </LocalizationProvider>
  );
}

// Student Goal Assignment Panel Component (reused from TimeBlockSchedulingModal)
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
  const { data: studentGoals = [], isLoading: goalsLoading } = useStudentActiveGoals(studentId, true);
  
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
                      const newIds = [goal.id, ...goalObjectives.map(obj => obj.id)];
                      handleGoalSelectionChange([...assignment.selected_goal_ids, ...newIds]);
                    } else {
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