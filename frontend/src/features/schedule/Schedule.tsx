import React, { useState, useMemo } from 'react';
import {
  Box,
  Typography,
  Paper,
  Tabs,
  Tab,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Grid,
  TextField,
  Button,
  Alert,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  useMediaQuery,
  useTheme
} from '@mui/material';
import {
  CalendarToday,
  FilterList,
  Add,
  Refresh,
  School,
  Person,
  Group,
  Visibility,
  VisibilityOff,
  People,
  PlayArrow
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { format, startOfWeek, endOfWeek } from 'date-fns';

import { WeeklyCalendarDataGrid } from './components/WeeklyCalendarDataGrid';
import { UnscheduledStudentsPanel } from './components/UnscheduledStudentsPanel';
import { StudentSchedulingModal } from './components/StudentSchedulingModal';
import { TimeBlockSchedulingModal } from './components/TimeBlockSchedulingModal';
import { StartTherapySessionModal } from './components/StartTherapySessionModal';
import { CellDetailModal } from './components/CellDetailModal';
import { AppointmentProgress, useAppointmentProgress } from '../../components/ui/AppointmentProgress';
import { useAppointments, useTimeBlocks } from '../../lib/hooks/useScheduling';
import { useStudents } from '../../lib/hooks/useStudents';
import { useSchools } from '../../lib/hooks/useSchools';
import { useTeachers } from '../../lib/hooks/useTeachers';
import { useSchedulingStudents } from '../../lib/hooks/useSchedulingStudents';
import { useStartTherapySession } from '../../lib/hooks/useTherapySessions';
import { StartSessionRequest } from '../../lib/api/therapySessions';
import { AppointmentSummary, TimeBlockSummary, schedulingApi } from '../../lib/api/scheduling';
import { StudentSummary } from '../../lib/api/students';
import { StudentScheduleView } from '../../lib/api/schedulingStudents';
import { useNavigate } from 'react-router-dom';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`schedule-tabpanel-${index}`}
      aria-labelledby={`schedule-tab-${index}`}
      style={{ 
        height: '100%', 
        display: value === index ? 'flex' : 'none',
        flexDirection: 'column'
      }}
      {...other}
    >
      {value === index && (
        <Box sx={{ 
          flex: 1, 
          display: 'flex', 
          flexDirection: 'column',
          overflow: 'hidden',
          minHeight: 0
        }}>
          {children}
        </Box>
      )}
    </div>
  );
}

export default function Schedule() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [tabValue, setTabValue] = useState(0);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [selectedSchool, setSelectedSchool] = useState<number | ''>('');
  const [selectedTeacher, setSelectedTeacher] = useState<number | ''>('');
  const [selectedStudent, setSelectedStudent] = useState<number | ''>('');
  const [appointmentStatus, setAppointmentStatus] = useState<string>('');
  const [showTimeBlocks, setShowTimeBlocks] = useState(true);
  const [showStudentsPanel, setShowStudentsPanel] = useState(true);
  
  // API hooks
  const startSessionMutation = useStartTherapySession();
  const navigate = useNavigate();
  
  // Student scheduling modal state
  const [schedulingModalOpen, setSchedulingModalOpen] = useState(false);
  const [schedulingDate, setSchedulingDate] = useState<Date | null>(null);
  const [schedulingHour, setSchedulingHour] = useState<number | null>(null);
  const [startSessionModalOpen, setStartSessionModalOpen] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  
  // Time block scheduling modal state
  const [timeBlockModalOpen, setTimeBlockModalOpen] = useState(false);
  const [timeBlockDate, setTimeBlockDate] = useState<Date | null>(null);
  const [timeBlockHour, setTimeBlockHour] = useState<number | null>(null);
  
  // Cell detail modal state
  const [cellDetailModalOpen, setCellDetailModalOpen] = useState(false);
  const [cellDetailDate, setCellDetailDate] = useState<Date | null>(null);
  const [cellDetailHour, setCellDetailHour] = useState<number | null>(null);

  // Appointment progress state
  const appointmentProgress = useAppointmentProgress();

  // Calculate date range for current week
  const weekStart = useMemo(() => startOfWeek(selectedDate, { weekStartsOn: 1 }), [selectedDate]);
  const weekEnd = useMemo(() => endOfWeek(selectedDate, { weekStartsOn: 1 }), [selectedDate]);

  // Fetch data - only fetch summaries to reduce API calls
  const { schools } = useSchools();
  const { teachers } = useTeachers();
  
  // Fetch comprehensive student data for scheduling
  const { 
    students: schedulingStudents, 
    loading: studentsLoading, 
    error: studentsError,
    refetch: refetchStudents 
  } = useSchedulingStudents({
    start_date: format(weekStart, 'yyyy-MM-dd'),
    end_date: format(weekEnd, 'yyyy-MM-dd'),
    school_id: selectedSchool || undefined,
    teacher_id: selectedTeacher || undefined
  });

  const { 
    appointments, 
    loading: appointmentsLoading, 
    error: appointmentsError,
    refetch: refetchAppointments 
  } = useAppointments({
    start_date: format(weekStart, 'yyyy-MM-dd'),
    end_date: format(weekEnd, 'yyyy-MM-dd'),
    school_id: selectedSchool || undefined,
    teacher_id: selectedTeacher || undefined,
    student_id: selectedStudent || undefined,
    status: appointmentStatus || undefined
  });

  const { 
    timeBlocks, 
    loading: timeBlocksLoading, 
    error: timeBlocksError,
    refetch: refetchTimeBlocks 
  } = useTimeBlocks({
    start_date: format(weekStart, 'yyyy-MM-dd'),
    end_date: format(weekEnd, 'yyyy-MM-dd'),
    school_id: selectedSchool || undefined,
    teacher_id: selectedTeacher || undefined
  });

  // Event handlers
  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleAppointmentClick = (appointment: AppointmentSummary) => {
    console.log('Appointment clicked:', appointment);
  };

  const handleTimeBlockClick = (timeBlock: TimeBlockSummary) => {
    console.log('Time block clicked:', timeBlock);
  };

  const handleCreateAppointment = (date: Date, hour: number) => {
    console.log('Create appointment:', { date, hour });
  };

  const handleCreateTimeBlock = (date: Date, hour: number) => {
    console.log('Create time block:', { date, hour });
  };

  const handleScheduleStudentModal = (date: Date, hour: number) => {
    console.log('Schedule student modal:', { date, hour });
    setSchedulingDate(date);
    setSchedulingHour(hour);
    setSchedulingModalOpen(true);
  };

  const handleCreateTherapyGroup = (date: Date, hour: number) => {
    console.log('Create therapy group:', { date, hour });
    handleOpenTimeBlockModal(date, hour);
  };

  const handleQuickSchedule = (student: StudentScheduleView) => {
    console.log('Quick schedule for student:', student);
  };

  const handleStartTherapySession = () => {
    setStartSessionModalOpen(true);
  };

  const handleSessionStarted = (sessionId: number) => {
    console.log('Therapy session started:', sessionId);
    // Session will automatically navigate via the StartTherapySessionModal
  };

  const handleStartSessionFromAppointment = async (appointment: AppointmentSummary) => {
    console.log('Start session from appointment:', appointment);
    
    try {
      // Create therapy session directly from appointment
      const request: StartSessionRequest = {
        student_id: appointment.student_id,
        session_type: 'link_existing',
        appointment_id: appointment.id,
        create_appointment: false, // Already linked to existing appointment
        planned_duration_minutes: appointment.duration_minutes || 30,
        planned_goals: [], // TODO: Get planned goals from appointment
        planned_objectives: [] // TODO: Get planned objectives from appointment
      };

      const newSession = await startSessionMutation.mutateAsync(request);
      
      // Navigate directly to therapy session interface
      navigate(`/therapy/session/${newSession.id}`);
    } catch (error) {
      console.error('Failed to start therapy session from appointment:', error);
    }
  };

  const handleScheduleStudent = async (appointmentData: {
    student_id: number;
    start_datetime: string;
    end_datetime: string;
    notes?: string;
    goal_ids?: number[];
    objective_ids?: number[];
    objective_to_goal_map?: { [key: number]: number };
    objective_pre_session_notes?: { [key: number]: string };
    recurring_config?: any;
    recurring_dates?: Date[];
  }) => {
    console.log('Creating appointment:', appointmentData);
    
    try {
      // Check if this is a recurring appointment
      if (appointmentData.recurring_config?.isRecurring) {
        console.log('Creating recurring appointments via backend');
        
        // Show progress indicator for recurring appointments
        appointmentProgress.showProgress('Creating recurring appointments...');
        
        // Prepare recurring appointment data for backend
        const recurringData = {
          student_id: appointmentData.student_id,
          start_datetime: appointmentData.start_datetime,
          end_datetime: appointmentData.end_datetime,
          notes: appointmentData.notes,
          appointment_type: 'individual',
          status: 'scheduled',
          // Add goal/objective planning if provided
          planned_goals: appointmentData.goal_ids?.length ? appointmentData.goal_ids.map(goalId => ({
            goal_id: goalId,
            planned: true,
            worked_on: false,
            priority: 1
          })) : undefined,
          planned_objectives: appointmentData.objective_ids?.length ? appointmentData.objective_ids.map(objectiveId => ({
            objective_id: objectiveId,
            goal_id: appointmentData.objective_to_goal_map?.[objectiveId] || 0,
            planned: true,
            worked_on: false,
            priority: 1,
            pre_session_notes: appointmentData.objective_pre_session_notes?.[objectiveId] || undefined
          })) : undefined,
          // Convert frontend recurring config to backend format
          recurring_config: {
            frequency: appointmentData.recurring_config.frequency,
            interval: appointmentData.recurring_config.interval,
            days_of_week: appointmentData.recurring_config.daysOfWeek,
            end_type: appointmentData.recurring_config.endType,
            end_date: appointmentData.recurring_config.endDate?.toISOString(),
            max_occurrences: appointmentData.recurring_config.maxOccurrences
          }
        };
        
        // Call the backend recurring appointment endpoint
        const result = await schedulingApi.createRecurringAppointments(recurringData);
        console.log(`✅ Created ${result.total_created} recurring appointments`);
        
        // Show success with details
        const hasConflicts = result.conflicts && result.conflicts.length > 0;
        const successMessage = hasConflicts 
          ? `Created ${result.total_created} appointments successfully! ${result.conflicts.length} appointments were skipped due to conflicts.`
          : `Successfully created ${result.total_created} recurring appointments!`;
        
        appointmentProgress.showSuccess(successMessage, {
          totalAppointments: (result.total_created || 0) + (result.conflicts?.length || 0),
          createdAppointments: result.total_created,
          conflicts: result.conflicts,
          seriesId: result.series_id
        });
        
      } else {
        // Show progress indicator for single appointment
        appointmentProgress.showProgress('Creating appointment...');
        
        // Create single appointment
        const createData = {
          student_id: appointmentData.student_id,
          start_datetime: appointmentData.start_datetime,
          end_datetime: appointmentData.end_datetime,
          notes: appointmentData.notes,
          appointment_type: 'individual',
          status: 'scheduled',
          // Add goal/objective planning if provided
          planned_goals: appointmentData.goal_ids?.length ? appointmentData.goal_ids.map(goalId => ({
            goal_id: goalId,
            planned: true,
            worked_on: false,
            priority: 1
          })) : undefined,
          planned_objectives: appointmentData.objective_ids?.length ? appointmentData.objective_ids.map(objectiveId => ({
            objective_id: objectiveId,
            goal_id: appointmentData.objective_to_goal_map?.[objectiveId] || 0,
            planned: true,
            worked_on: false,
            priority: 1,
            pre_session_notes: appointmentData.objective_pre_session_notes?.[objectiveId] || undefined
          })) : undefined
        };
        
        console.log('Creating single appointment with data:', JSON.stringify(createData, null, 2));
        
        // Call the API to create the appointment
        await schedulingApi.createAppointment(createData);
        
        // Show success for single appointment
        appointmentProgress.showSuccess('Appointment created successfully!', {
          createdAppointments: 1,
          totalAppointments: 1
        });
      }
      
      // Refresh appointment data
      refetchAppointments();
      
      // Close modal
      setSchedulingModalOpen(false);
    } catch (error) {
      console.error('Failed to create appointment:', error);
      
      // Show error in progress indicator
      const errorMessage = error instanceof Error ? error.message : 'Failed to create appointment. Please try again.';
      appointmentProgress.showError(errorMessage);
    }
  };

  // Handle time block scheduling
  const handleScheduleTimeBlock = async (timeBlockData: {
    // Time block fields
    teacher_id?: number;
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
    activities?: any[];
    // Recurring config
    recurring_config?: any;
  }) => {
    console.log('Creating time block:', timeBlockData);
    
    try {
      appointmentProgress.showProgress('Creating time block and scheduling appointments...');
      
      // Call the comprehensive time block creation API
      const result = await schedulingApi.createTimeBlockWithScheduling(timeBlockData);
      
      console.log('Time block created:', result);
      
      // Show success message
      const scheduleResult = result.schedule_result;
      let successMessage = `Time block "${timeBlockData.title}" created successfully!`;
      
      if (scheduleResult) {
        const totalAppointments = scheduleResult.total_appointments;
        const conflicts = scheduleResult.total_conflicts;
        
        if (totalAppointments > 0) {
          successMessage += ` Created ${totalAppointments} appointment${totalAppointments !== 1 ? 's' : ''} for assigned students.`;
        }
        
        if (conflicts > 0) {
          successMessage += ` ${conflicts} appointment${conflicts !== 1 ? 's' : ''} had conflicts and were skipped.`;
        }
      }
      
      appointmentProgress.showSuccess(successMessage, {
        totalAppointments: scheduleResult?.total_appointments || 0,
        createdAppointments: scheduleResult?.total_appointments || 0,
        conflicts: scheduleResult?.conflicts?.map(c => c.reason) || []
      });
      
      // Refresh data
      refetchAppointments();
      refetchTimeBlocks();
      
      // Close modal
      setTimeBlockModalOpen(false);
    } catch (error) {
      console.error('Failed to create time block:', error);
      
      // Show error in progress indicator
      const errorMessage = error instanceof Error ? error.message : 'Failed to create time block. Please try again.';
      appointmentProgress.showError(errorMessage);
    }
  };

  // Handle opening time block modal
  const handleOpenTimeBlockModal = (date: Date, hour: number) => {
    setTimeBlockDate(date);
    setTimeBlockHour(hour);
    setTimeBlockModalOpen(true);
  };

  // Handle viewing cell details
  const handleViewCellDetails = (date: Date, hour: number) => {
    setCellDetailDate(date);
    setCellDetailHour(hour);
    setCellDetailModalOpen(true);
  };

  // Handle editing appointment from cell detail modal
  const handleEditAppointment = (appointment: AppointmentSummary) => {
    console.log('Edit appointment:', appointment);
    // TODO: Open appointment edit modal
  };

  // Handle editing time block from cell detail modal
  const handleEditTimeBlock = (timeBlock: TimeBlockSummary) => {
    console.log('Edit time block:', timeBlock);
    // TODO: Open time block edit modal
  };

  // Handle starting therapy session from cell detail modal
  const handleStartTherapySessionFromDetail = (appointment: AppointmentSummary) => {
    console.log('Start therapy session from detail:', appointment);
    // TODO: Navigate to therapy session view
    // For now, close the detail modal and show the start session modal
    setCellDetailModalOpen(false);
    setStartSessionModalOpen(true);
  };

  // Handle deleting appointment from cell detail modal
  const handleDeleteAppointment = async (appointment: AppointmentSummary) => {
    console.log('🗑️ Deleting appointment:', appointment);
    try {
      const { schedulingApi } = await import('../../lib/api/scheduling');
      await schedulingApi.deleteAppointment(appointment.id);
      console.log('✅ Appointment deleted successfully');
      await refetchAppointments();
    } catch (error) {
      console.error('❌ Failed to delete appointment:', error);
      throw error; // Re-throw so the modal can show the error
    }
  };

  // Handle deleting time block from cell detail modal
  const handleDeleteTimeBlock = async (timeBlock: TimeBlockSummary) => {
    console.log('🗑️ Deleting time block:', timeBlock);
    try {
      const { schedulingApi } = await import('../../lib/api/scheduling');
      await schedulingApi.deleteTimeBlock(timeBlock.id);
      console.log('✅ Time block deleted successfully');
      await refetchTimeBlocks();
      await refetchAppointments(); // Also refresh appointments since they may be deleted
    } catch (error) {
      console.error('❌ Failed to delete time block:', error);
      throw error; // Re-throw so the modal can show the error
    }
  };

  // Process students data for the students panel
  const studentScheduleData = useMemo(() => {
    if (!schedulingStudents) return null;

    const all = schedulingStudents.map(student => ({
      student: {
        id: student.id,
        first: student.first,
        last: student.last,
        full_name: student.full_name,
        uic: student.uic,
        school_id: student.school_id,
        school_name: student.school_name,
        primary_teacher_name: student.primary_teacher_name,
        teacher_assignments: student.teacher_assignments,
        current_appointments: student.current_appointments
      } as StudentScheduleView,
      hasAppointments: student.has_appointments,
      appointmentCount: student.appointment_count,
      appointments: student.current_appointments
    }));

    const scheduled = all.filter(item => item.hasAppointments);
    const unscheduled = all.filter(item => !item.hasAppointments);

    return {
      all,
      scheduled,
      unscheduled,
      counts: {
        total: all.length,
        scheduled: scheduled.length,
        unscheduled: unscheduled.length
      }
    };
  }, [schedulingStudents]);

  // Combine loading states
  const loading = appointmentsLoading || timeBlocksLoading || studentsLoading;
  
  // Combine error states - only show non-empty error messages
  const error = (appointmentsError && appointmentsError.trim()) || 
                (timeBlocksError && timeBlocksError.trim()) || 
                (studentsError && studentsError.trim()) || '';

  console.log('🎯 Schedule component state:', {
    loading,
    error,
    appointmentsLength: appointments?.length || 0,
    timeBlocksLength: timeBlocks?.length || 0,
    schedulingStudentsLength: schedulingStudents?.length || 0,
    firstSchedulingStudent: schedulingStudents?.[0],
    selectedDate,
    showTimeBlocks,
    showStudentsPanel
  });

  const refreshData = () => {
    refetchAppointments();
    refetchTimeBlocks();
    refetchStudents();
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ 
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      }}>
        {/* Header */}
        <Box sx={{ 
          mb: isMobile ? 1.5 : 2, 
          flexShrink: 0,
          px: isMobile ? 1.5 : 2,
          pt: isMobile ? 1.5 : 2
        }}>
          <Box sx={{ 
            display: 'flex', 
            flexDirection: isMobile ? 'column' : 'row',
            justifyContent: 'space-between', 
            alignItems: isMobile ? 'stretch' : 'flex-start', 
            mb: isMobile ? 1.5 : 2,
            gap: isMobile ? 1.5 : 0
          }}>
            <Box>
              <Typography 
                variant={isMobile ? "h5" : "h4"} 
                component="h1" 
                sx={{ 
                  display: 'flex', 
                  alignItems: 'center',
                  color: '#40A8B6',
                  fontWeight: 600,
                  mb: isMobile ? 0.5 : 1,
                  fontSize: isMobile ? '1.5rem' : undefined
                }}
              >
                <CalendarToday sx={{ 
                  mr: isMobile ? 1 : 2, 
                  fontSize: isMobile ? 24 : 32 
                }} />
                {isMobile ? "Schedule" : "Therapy Schedule"}
              </Typography>
              <Typography 
                variant={isMobile ? "body1" : "h6"} 
                color="text.secondary"
                sx={{ fontSize: isMobile ? '0.9rem' : undefined }}
              >
                {isMobile ? "Manage appointments" : "Manage appointments and therapy sessions"}
              </Typography>
            </Box>
            <Button
              variant="contained"
              startIcon={<PlayArrow />}
              onClick={handleStartTherapySession}
              fullWidth={isMobile}
              size={isMobile ? 'medium' : 'large'}
              sx={{ 
                bgcolor: 'success.main',
                '&:hover': { bgcolor: 'success.dark' },
                fontSize: isMobile ? '0.9rem' : undefined
              }}
            >
              Start Session
            </Button>
          </Box>
        </Box>

        {/* Scrollable Content Area */}
        <Box sx={{ 
          flex: 1, 
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          px: isMobile ? 1.5 : 2,
          pb: isMobile ? 1.5 : 2
        }}>
          {/* Error Alert */}
          {error && error.trim() && (
            <Alert severity="error" sx={{ mb: 3, flexShrink: 0 }}>
              {error}
            </Alert>
          )}

          {/* Navigation Tabs */}
          <Paper elevation={1} sx={{ mb: 1, flexShrink: 0 }}>
            <Tabs 
              value={tabValue} 
              onChange={handleTabChange}
              variant={isMobile ? "fullWidth" : "standard"}
              sx={{ 
                borderBottom: 1, 
                borderColor: 'divider', 
                minHeight: isMobile ? 42 : 48 
              }}
            >
              <Tab 
                label={isMobile ? "Calendar" : "Calendar View"} 
                icon={!isMobile ? <CalendarToday /> : undefined} 
                iconPosition="start"
                sx={{ 
                  minHeight: isMobile ? 42 : 48, 
                  py: isMobile ? 0.5 : 1,
                  fontSize: isMobile ? '0.85rem' : undefined
                }}
              />
              <Tab 
                label={isMobile ? "Appt." : "Appointments"} 
                icon={!isMobile ? <Person /> : undefined} 
                iconPosition="start"
                sx={{ 
                  minHeight: isMobile ? 42 : 48, 
                  py: isMobile ? 0.5 : 1,
                  fontSize: isMobile ? '0.85rem' : undefined
                }}
              />
              <Tab 
                label={isMobile ? "Groups" : "Time Blocks"} 
                icon={!isMobile ? <Group /> : undefined} 
                iconPosition="start"
                sx={{ 
                  minHeight: isMobile ? 42 : 48, 
                  py: isMobile ? 0.5 : 1,
                  fontSize: isMobile ? '0.85rem' : undefined
                }}
              />
            </Tabs>
          </Paper>

          {/* Scrollable Tab Panels */}
          <Box sx={{ 
            flex: 1, 
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column'
          }}>
            <TabPanel value={tabValue} index={0}>
              {/* Calendar View with Students Panel */}
              <WeeklyCalendarDataGrid
                appointments={appointments}
                timeBlocks={timeBlocks}
                selectedDate={selectedDate}
                onDateChange={setSelectedDate}
                onAppointmentClick={handleAppointmentClick}
                onTimeBlockClick={handleTimeBlockClick}
                onCreateAppointment={handleCreateAppointment}
                onCreateTimeBlock={handleCreateTimeBlock}
                showTimeBlocks={showTimeBlocks}
                loading={loading}
                showStudentsPanel={showStudentsPanel}
                studentScheduleData={studentScheduleData}
                schools={schools}
                teachers={teachers}
                onQuickSchedule={handleQuickSchedule}
                onToggleTimeBlocks={() => setShowTimeBlocks(!showTimeBlocks)}
                onToggleStudentsPanel={() => setShowStudentsPanel(!showStudentsPanel)}
                onRefresh={refreshData}
                onScheduleStudent={handleScheduleStudentModal}
                onCreateTherapyGroup={handleCreateTherapyGroup}
                onStartSession={handleStartSessionFromAppointment}
                onViewCellDetails={handleViewCellDetails}
              />
            </TabPanel>

            <TabPanel value={tabValue} index={1}>
              {/* Appointments List View */}
              <Box sx={{ height: '100%', overflow: 'auto' }}>
                <Typography variant="h6" gutterBottom>
                  Appointments ({appointments.length})
                </Typography>
                {/* TODO: Add appointments list component */}
              </Box>
            </TabPanel>

            <TabPanel value={tabValue} index={2}>
              {/* Time Blocks List View */}
              <Box sx={{ height: '100%', overflow: 'auto' }}>
                <Typography variant="h6" gutterBottom>
                  Time Blocks ({timeBlocks.length})
                </Typography>
                {/* TODO: Add time blocks list component */}
              </Box>
            </TabPanel>
          </Box>
        </Box>
      </Box>

      {/* Student Scheduling Modal */}
      <StudentSchedulingModal
        open={schedulingModalOpen}
        onClose={() => setSchedulingModalOpen(false)}
        selectedDate={schedulingDate || new Date()}
        selectedHour={schedulingHour || 0}
        students={schedulingStudents || []}
        existingAppointments={appointments}
        onScheduleStudent={handleScheduleStudent}
      />

      {/* Time Block Scheduling Modal */}
      <TimeBlockSchedulingModal
        open={timeBlockModalOpen}
        onClose={() => setTimeBlockModalOpen(false)}
        selectedDate={timeBlockDate || new Date()}
        selectedHour={timeBlockHour || 0}
        students={schedulingStudents || []}
        existingAppointments={appointments}
        onScheduleTimeBlock={handleScheduleTimeBlock}
      />

      {/* Start Therapy Session Modal */}
      <StartTherapySessionModal
        open={startSessionModalOpen}
        onClose={() => setStartSessionModalOpen(false)}
        students={schedulingStudents || []}
        existingAppointments={appointments}
        onSessionStarted={handleSessionStarted}
      />

      {/* Cell Detail Modal */}
      <CellDetailModal
        open={cellDetailModalOpen}
        onClose={() => setCellDetailModalOpen(false)}
        date={cellDetailDate || new Date()}
        hour={cellDetailHour || 0}
        appointments={appointments}
        timeBlocks={timeBlocks}
        students={schedulingStudents || []}
        onEditAppointment={handleEditAppointment}
        onStartTherapySession={handleStartTherapySessionFromDetail}
        onEditTimeBlock={handleEditTimeBlock}
        onDeleteAppointment={handleDeleteAppointment}
        onDeleteTimeBlock={handleDeleteTimeBlock}
        onUpdateAppointment={async (appointmentData: any) => {
          console.log('🔄 Updating appointment:', appointmentData);
          try {
            const { schedulingApi } = await import('../../lib/api/scheduling');
            await schedulingApi.updateAppointment(appointmentData.id, appointmentData);
            console.log('✅ Appointment updated successfully');
            await refetchAppointments();
          } catch (error) {
            console.error('❌ Failed to update appointment:', error);
            throw error; // Re-throw so the modal can show the error
          }
        }}
        onUpdateTimeBlock={async (timeBlockData: any) => {
          console.log('🔄 Updating time block:', timeBlockData);
          // TODO: Implement time block update API call
          await refetchTimeBlocks();
        }}
        onLoadTherapySession={async (appointmentId: number) => {
          console.log('📋 Loading therapy session for appointment:', appointmentId);
          try {
            const { therapySessionsApi } = await import('../../lib/api/therapySessions');
            const sessionData = await therapySessionsApi.getTherapySessionByAppointment(appointmentId);
            console.log('📋 Loaded therapy session data:', sessionData);
            return sessionData;
          } catch (error) {
            console.error('❌ Failed to load therapy session:', error);
            // Return empty structure if API call fails
            return {
              goals: [],
              objectives: []
            };
          }
        }}
      />

      {/* Appointment Progress Indicator */}
      <AppointmentProgress
        state={appointmentProgress.state}
        onClose={() => {
          appointmentProgress.hide();
          // Keep modal closed since we already close it in the try block above
        }}
        onRetry={() => {
          // For retry, we'd need to store the appointment data and retry the creation
          // For now, just hide the progress and let user try again manually
          appointmentProgress.hide();
        }}
      />
    </LocalizationProvider>
  );
}
