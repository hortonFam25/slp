import React, { useState, useMemo } from 'react';
import {
  Box,
  Typography,
  Paper,
  IconButton,
  Grid,
  Chip,
  Tooltip,
  Button,
  Card,
  CardContent,
  Divider
} from '@mui/material';
import {
  ChevronLeft,
  ChevronRight,
  Add,
  Person,
  Group,
  Assessment,
  LocationOn,
  AccessTime,
  PlayArrow
} from '@mui/icons-material';
import { format, startOfWeek, addDays, addWeeks, subWeeks, isSameDay, parse } from 'date-fns';
import { AppointmentSummary, TimeBlockSummary } from '../../../lib/api/scheduling';
import { StudentScheduleView } from '../../../lib/api/schedulingStudents';
import { UnscheduledStudentsPanel } from './UnscheduledStudentsPanel';

interface WeeklyCalendarProps {
  appointments: AppointmentSummary[];
  timeBlocks: TimeBlockSummary[];
  selectedDate: Date;
  onDateChange: (date: Date) => void;
  onAppointmentClick?: (appointment: AppointmentSummary) => void;
  onTimeBlockClick?: (timeBlock: TimeBlockSummary) => void;
  onCreateAppointment?: (date: Date, hour: number) => void;
  onCreateTimeBlock?: (date: Date, hour: number) => void;
  showTimeBlocks?: boolean;
  loading?: boolean;
  // Students panel props
  showStudentsPanel?: boolean;
  studentScheduleData?: {
    all: Array<{ student: StudentScheduleView; hasAppointments: boolean; appointmentCount: number; appointments: any[] }>;
    scheduled: Array<{ student: StudentScheduleView; hasAppointments: boolean; appointmentCount: number; appointments: any[] }>;
    unscheduled: Array<{ student: StudentScheduleView; hasAppointments: boolean; appointmentCount: number; appointments: any[] }>;
    counts: { total: number; scheduled: number; unscheduled: number };
  };
  schools?: Array<{ id: number; name: string }>;
  teachers?: Array<{ id: number; full_name: string }>;
  onQuickSchedule?: (student: StudentScheduleView) => void;
}

const HOURS = Array.from({ length: 12 }, (_, i) => i + 7); // 7 AM to 6 PM
const DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

export function WeeklyCalendar({
  appointments,
  timeBlocks,
  selectedDate,
  onDateChange,
  onAppointmentClick,
  onTimeBlockClick,
  onCreateAppointment,
  onCreateTimeBlock,
  showTimeBlocks = true,
  loading = false,
  showStudentsPanel = false,
  studentScheduleData,
  schools = [],
  teachers = [],
  onQuickSchedule
}: WeeklyCalendarProps) {
  const [currentWeek, setCurrentWeek] = useState(() => startOfWeek(selectedDate, { weekStartsOn: 1 }));

  // Calculate week dates (Monday to Sunday)
  const weekDates = useMemo(() => {
    return Array.from({ length: 7 }, (_, i) => addDays(currentWeek, i));
  }, [currentWeek]);

  // Navigate weeks
  const goToPreviousWeek = () => {
    const newWeek = subWeeks(currentWeek, 1);
    setCurrentWeek(newWeek);
    onDateChange(newWeek);
  };

  const goToNextWeek = () => {
    const newWeek = addWeeks(currentWeek, 1);
    setCurrentWeek(newWeek);
    onDateChange(newWeek);
  };

  const goToToday = () => {
    const today = new Date();
    const weekOfToday = startOfWeek(today, { weekStartsOn: 1 });
    setCurrentWeek(weekOfToday);
    onDateChange(today);
  };

  // Get appointments for a specific date and hour
  const getAppointmentsForSlot = (date: Date, hour: number) => {
    return appointments.filter(apt => {
      const aptDate = new Date(apt.start_datetime);
      return isSameDay(aptDate, date) && aptDate.getHours() === hour;
    });
  };

  // Get time blocks for a specific date and hour
  const getTimeBlocksForSlot = (date: Date, hour: number) => {
    return timeBlocks.filter(block => {
      const blockDate = new Date(block.start_datetime);
      return isSameDay(blockDate, date) && blockDate.getHours() === hour;
    });
  };

  // Get appointment type icon
  const getAppointmentIcon = (type: string) => {
    switch (type) {
      case 'group':
        return <Group fontSize="small" />;
      case 'assessment':
        return <Assessment fontSize="small" />;
      default:
        return <Person fontSize="small" />;
    }
  };

  // Get appointment color based on status
  const getAppointmentColor = (status: string) => {
    switch (status) {
      case 'completed':
        return '#4caf50';
      case 'cancelled':
        return '#f44336';
      case 'no_show':
        return '#ff9800';
      default:
        return '#2196f3';
    }
  };

  // Get time block color
  const getTimeBlockColor = (type: string) => {
    switch (type) {
      case 'group_therapy':
        return '#9c27b0';
      case 'assessment_block':
        return '#ff5722';
      default:
        return '#607d8b';
    }
  };

  // Render time slot content
  const renderTimeSlot = (date: Date, hour: number) => {
    const slotsAppointments = getAppointmentsForSlot(date, hour);
    const slotsTimeBlocks = showTimeBlocks ? getTimeBlocksForSlot(date, hour) : [];

    return (
      <Box
        sx={{
          minHeight: 80,
          p: 0.5,
          borderBottom: '1px solid #e0e0e0',
          position: 'relative',
          '&:hover': {
            bgcolor: '#f5f5f5',
            '& .add-buttons': {
              opacity: 1
            }
          }
        }}
      >
        {/* Add buttons - show on hover */}
        <Box
          className="add-buttons"
          sx={{
            position: 'absolute',
            top: 4,
            right: 4,
            opacity: 0,
            transition: 'opacity 0.2s',
            display: 'flex',
            gap: 0.5
          }}
        >
          {onCreateAppointment && (
            <Tooltip title="Add Appointment">
              <IconButton
                size="small"
                onClick={() => onCreateAppointment(date, hour)}
                sx={{ bgcolor: 'white', '&:hover': { bgcolor: '#f0f0f0' } }}
              >
                <Add fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {onCreateTimeBlock && (
            <Tooltip title="Add Time Block">
              <IconButton
                size="small"
                onClick={() => onCreateTimeBlock(date, hour)}
                sx={{ bgcolor: 'white', '&:hover': { bgcolor: '#f0f0f0' } }}
              >
                <Group fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>

        {/* Appointments */}
        {slotsAppointments.map(appointment => (
          <Card
            key={appointment.id}
            sx={{
              mb: 0.5,
              cursor: onAppointmentClick ? 'pointer' : 'default',
              bgcolor: getAppointmentColor(appointment.status),
              color: 'white',
              minHeight: 36,
              '&:hover': {
                opacity: onAppointmentClick ? 0.8 : 1
              }
            }}
            onClick={() => onAppointmentClick?.(appointment)}
          >
            <CardContent sx={{ p: 1, '&:last-child': { pb: 1 } }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                {getAppointmentIcon(appointment.appointment_type)}
                <Typography variant="caption" sx={{ fontWeight: 600 }}>
                  {appointment.student_name}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <AccessTime fontSize="small" sx={{ fontSize: 12 }} />
                <Typography variant="caption">
                  {format(new Date(appointment.start_datetime), 'h:mm a')} - 
                  {format(new Date(appointment.end_datetime), 'h:mm a')}
                </Typography>
              </Box>
              {appointment.location && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <LocationOn fontSize="small" sx={{ fontSize: 12 }} />
                  <Typography variant="caption">{appointment.location}</Typography>
                </Box>
              )}
              {appointment.status === 'scheduled' && (
                <Chip
                  icon={<PlayArrow fontSize="small" />}
                  label="Start Session"
                  size="small"
                  sx={{ 
                    mt: 0.5, 
                    height: 20, 
                    bgcolor: 'rgba(255,255,255,0.2)',
                    color: 'white'
                  }}
                />
              )}
            </CardContent>
          </Card>
        ))}

        {/* Time Blocks */}
        {slotsTimeBlocks.map(timeBlock => (
          <Card
            key={timeBlock.id}
            sx={{
              mb: 0.5,
              cursor: onTimeBlockClick ? 'pointer' : 'default',
              bgcolor: getTimeBlockColor(timeBlock.block_type),
              color: 'white',
              minHeight: 36,
              border: '2px dashed rgba(255,255,255,0.5)',
              '&:hover': {
                opacity: onTimeBlockClick ? 0.8 : 1
              }
            }}
            onClick={() => onTimeBlockClick?.(timeBlock)}
          >
            <CardContent sx={{ p: 1, '&:last-child': { pb: 1 } }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                <Group fontSize="small" />
                <Typography variant="caption" sx={{ fontWeight: 600 }}>
                  {timeBlock.title}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <AccessTime fontSize="small" sx={{ fontSize: 12 }} />
                <Typography variant="caption">
                  {format(new Date(timeBlock.start_datetime), 'h:mm a')} - 
                  {format(new Date(timeBlock.end_datetime), 'h:mm a')}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Person fontSize="small" sx={{ fontSize: 12 }} />
                <Typography variant="caption">
                  {timeBlock.current_student_count}
                  {timeBlock.max_students ? ` / ${timeBlock.max_students}` : ''}
                </Typography>
              </Box>
              {timeBlock.location && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <LocationOn fontSize="small" sx={{ fontSize: 12 }} />
                  <Typography variant="caption">{timeBlock.location}</Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        ))}
      </Box>
    );
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
        <Typography>Loading calendar...</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ 
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    }}>
      {/* Sticky Calendar Header */}
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between', 
        mb: 2,
        flexShrink: 0,
        pb: 2,
        borderBottom: '1px solid #e0e0e0'
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <IconButton onClick={goToPreviousWeek}>
            <ChevronLeft />
          </IconButton>
          <Typography variant="h6" sx={{ minWidth: 200, textAlign: 'center' }}>
            {format(currentWeek, 'MMMM d')} - {format(addDays(currentWeek, 6), 'MMMM d, yyyy')}
          </Typography>
          <IconButton onClick={goToNextWeek}>
            <ChevronRight />
          </IconButton>
        </Box>
        <Button variant="outlined" onClick={goToToday}>
          Today
        </Button>
      </Box>

      {/* Calendar Grid with Students Panel Layout */}
      <Box sx={{ 
        display: 'flex', 
        gap: 2,
        flex: 1,
        overflow: 'hidden',
        minHeight: 0
      }}>
        {/* Scrollable Calendar Grid */}
        <Box sx={{ 
          flex: 1, 
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}>
          <Paper elevation={1} sx={{ 
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}>
            {/* Sticky Day Headers */}
            <Box sx={{ 
              bgcolor: '#f5f5f5',
              borderBottom: '1px solid #e0e0e0',
              position: 'sticky',
              top: 0,
              zIndex: 1,
              flexShrink: 0
            }}>
              <Grid container>
                <Grid item xs={1}>
                  <Box sx={{ p: 1, borderRight: '1px solid #e0e0e0', height: 60 }}>
                    <Typography variant="caption" color="text.secondary">Time</Typography>
                  </Box>
                </Grid>
                {weekDates.map((date, index) => (
                  <Grid item xs key={index} sx={{ borderRight: index < 6 ? '1px solid #e0e0e0' : 'none' }}>
                    <Box sx={{ p: 1, textAlign: 'center', height: 60 }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                        {DAYS_OF_WEEK[index]}
                      </Typography>
                      <Typography 
                        variant="h6" 
                        sx={{ 
                          color: isSameDay(date, new Date()) ? '#2196f3' : 'text.primary',
                          fontWeight: isSameDay(date, new Date()) ? 700 : 400
                        }}
                      >
                        {format(date, 'd')}
                      </Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>
            </Box>

            {/* Scrollable Time Slots */}
            <Box sx={{ 
              flex: 1, 
              overflow: 'auto'
            }}>
              {HOURS.map(hour => (
          <Grid container key={hour} sx={{ borderBottom: '1px solid #e0e0e0' }}>
            {/* Time Label */}
            <Grid item xs={1}>
              <Box 
                sx={{ 
                  p: 1, 
                  borderRight: '1px solid #e0e0e0', 
                  height: 80,
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'center',
                  bgcolor: '#fafafa'
                }}
              >
                <Typography variant="caption" color="text.secondary">
                  {format(new Date().setHours(hour, 0, 0, 0), 'h a')}
                </Typography>
              </Box>
            </Grid>
            
            {/* Day Columns */}
            {weekDates.map((date, dayIndex) => (
              <Grid 
                item 
                xs 
                key={dayIndex} 
                sx={{ borderRight: dayIndex < 6 ? '1px solid #e0e0e0' : 'none' }}
              >
                {renderTimeSlot(date, hour)}
              </Grid>
              ))}
            </Grid>
          ))}
            </Box>
          </Paper>
        </Box>

        {/* Students Panel */}
        {showStudentsPanel && studentScheduleData && onQuickSchedule && (
          <Box sx={{ flexShrink: 0 }}>
            <UnscheduledStudentsPanel
              studentScheduleData={studentScheduleData}
              schools={schools}
              teachers={teachers}
              onQuickSchedule={onQuickSchedule}
              loading={loading}
            />
          </Box>
        )}
      </Box>
    </Box>
  );
}
