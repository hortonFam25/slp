import React, { useState, useMemo } from 'react';
import { 
  Card, 
  CardContent, 
  Typography, 
  Box, 
  IconButton, 
  Button,
  Chip, 
  Avatar,
  Paper,
  Stack,
  Tooltip,
  Badge,
  Divider,
  useMediaQuery,
  useTheme
} from '@mui/material';
import {
  ChevronLeft,
  ChevronRight,
  Today,
  Person,
  Group,
  PlayArrow,
  AccessTime,
  Assignment,
  School,
  CalendarToday,
  Timeline
} from '@mui/icons-material';
import { format, addDays, subDays, isSameDay, startOfDay } from 'date-fns';
import { useNavigate } from 'react-router-dom';
import { useAppointments } from '../../../lib/hooks/useScheduling';
import { useStartTherapySession } from '../../../lib/hooks/useTherapySessions';
import { AppointmentSummary } from '../../../lib/api/scheduling';
import { StartSessionRequest } from '../../../lib/api/therapySessions';
import { StudentTherapyHistoryDialog } from '../../../components/StudentTherapyHistoryDialog';

interface DailyScheduleViewProps {
  className?: string;
  onAppointmentSelect?: (appointment: AppointmentSummary) => void;
}

interface DayAppointment extends AppointmentSummary {
  startTime: Date;
  endTime: Date;
  duration: number;
}

export function DailyScheduleView({ className, onAppointmentSelect }: DailyScheduleViewProps) {
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [therapyHistoryStudent, setTherapyHistoryStudent] = useState<{
    id: number;
    name: string;
  } | null>(null);
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  // API hooks for direct therapy session creation
  const startSessionMutation = useStartTherapySession();

  // Fetch appointments for the selected date
  const { appointments, loading } = useAppointments({
    start_date: format(selectedDate, 'yyyy-MM-dd'),
    end_date: format(selectedDate, 'yyyy-MM-dd')
  });

  // Process appointments for the selected day
  const dayAppointments = useMemo<DayAppointment[]>(() => {
    return appointments
      .filter(apt => {
        if (!apt.start_datetime || !apt.end_datetime) return false;
        const aptDate = new Date(apt.start_datetime);
        return isSameDay(aptDate, selectedDate);
      })
      .map(apt => {
        const startTime = new Date(apt.start_datetime!);
        const endTime = new Date(apt.end_datetime!);
        const duration = apt.duration_minutes || Math.round((endTime.getTime() - startTime.getTime()) / (1000 * 60));
        
        return {
          ...apt,
          startTime,
          endTime,
          duration
        };
      })
      .sort((a, b) => a.startTime.getTime() - b.startTime.getTime());
  }, [appointments, selectedDate]);

  // Navigation handlers
  const goToPreviousDay = () => setSelectedDate(prev => subDays(prev, 1));
  const goToNextDay = () => setSelectedDate(prev => addDays(prev, 1));
  const goToToday = () => setSelectedDate(new Date());

  // Get status styling
  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'scheduled':
        return 'primary';
      case 'completed':
        return 'success';
      case 'in-progress':
        return 'info';
      case 'cancelled':
        return 'error';
      case 'no-show':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type?.toLowerCase()) {
      case 'group':
        return <Group fontSize="small" />;
      case 'assessment':
        return <Assignment fontSize="small" />;
      default:
        return <Person fontSize="small" />;
    }
  };

  const formatTimeRange = (start: Date, end: Date) => {
    return `${format(start, 'h:mm a')} - ${format(end, 'h:mm a')}`;
  };

  const formatDuration = (minutes: number) => {
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
  };

  const isToday = isSameDay(selectedDate, new Date());
  const isPast = selectedDate < startOfDay(new Date());

  // Handle start session - copied from CellDetailModal
  const handleStartSession = async (appointment: AppointmentSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    
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

  return (
    <Card className={className} sx={{ 
      height: '100%', 
      display: 'flex', 
      flexDirection: 'column'
    }}>
      <CardContent sx={{ 
        p: isMobile ? 2 : 3, 
        flexShrink: 0 
      }}>
        {/* Header with date navigation */}
        <Box sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between', 
          mb: isMobile ? 2 : 3
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CalendarToday color="primary" />
            <Typography variant="h6" sx={{ 
              fontWeight: 600,
              fontSize: isMobile ? '1.1rem' : '1.25rem'
            }}>
              Daily Schedule
            </Typography>
          </Box>
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <IconButton onClick={goToPreviousDay} size="small">
              <ChevronLeft />
            </IconButton>
            
            <Tooltip title="Go to today">
              <IconButton onClick={goToToday} size="small" color={isToday ? 'primary' : 'default'}>
                <Today />
              </IconButton>
            </Tooltip>
            
            <IconButton onClick={goToNextDay} size="small">
              <ChevronRight />
            </IconButton>
          </Box>
        </Box>

        {/* Date display */}
        <Box sx={{ textAlign: 'center', mb: isMobile ? 2 : 3 }}>
          <Typography variant="h5" sx={{ 
            fontWeight: 600, 
            color: 'primary.main',
            fontSize: isMobile ? '1.3rem' : '1.5rem'
          }}>
            {format(selectedDate, 'EEEE')}
          </Typography>
          <Typography variant="subtitle1" color="text.secondary" sx={{
            fontSize: isMobile ? '0.9rem' : '1rem'
          }}>
            {format(selectedDate, 'MMMM d, yyyy')}
            {isToday && (
              <Chip 
                label="Today" 
                size="small" 
                color="primary" 
                sx={{ ml: 1 }} 
              />
            )}
            {isPast && !isToday && (
              <Chip 
                label="Past" 
                size="small" 
                color="default" 
                sx={{ ml: 1 }} 
              />
            )}
          </Typography>
        </Box>

      </CardContent>
      
      {/* Schedule content - scrollable area */}
      <Box sx={{ 
        flex: 1, 
        overflow: 'auto',
        px: isMobile ? 2 : 3,
        pb: isMobile ? 2 : 3,
        '&::-webkit-scrollbar': {
          width: isMobile ? '4px' : '8px',
        },
        '&::-webkit-scrollbar-track': {
          backgroundColor: 'rgba(0,0,0,0.1)',
          borderRadius: '4px',
        },
        '&::-webkit-scrollbar-thumb': {
          backgroundColor: 'rgba(0,0,0,0.3)',
          borderRadius: '4px',
          '&:hover': {
            backgroundColor: 'rgba(0,0,0,0.5)',
          },
        },
      }}>
          {loading ? (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Typography color="text.secondary">Loading schedule...</Typography>
            </Box>
          ) : dayAppointments.length === 0 ? (
            <Box sx={{ textAlign: 'center', py: 6 }}>
              <CalendarToday sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                No appointments scheduled
              </Typography>
              <Typography variant="body2" color="text.disabled">
                {isToday ? "You have a free day today!" : "No appointments on this date"}
              </Typography>
            </Box>
          ) : (
            <Stack spacing={2}>
              {/* Schedule summary */}
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
                <Chip 
                  icon={<AccessTime />}
                  label={`${dayAppointments.length} appointments`}
                  size="small"
                  variant="outlined"
                />
                <Chip 
                  icon={<Person />}
                  label={`${new Set(dayAppointments.map(apt => apt.student_id)).size} students`}
                  size="small"
                  variant="outlined"
                />
                <Chip 
                  icon={<AccessTime />}
                  label={`${dayAppointments.reduce((total, apt) => total + apt.duration, 0)} min total`}
                  size="small"
                  variant="outlined"
                />
              </Box>

              <Divider />

              {/* Appointment list */}
              {dayAppointments.map((appointment, index) => (
                <Paper
                  key={appointment.id}
                  elevation={1}
                  onClick={(event) => {
                    const target = event.target as HTMLElement;
                    if (target.closest('button, a, input, textarea, select, [role="button"]')) {
                      return;
                    }
                    onAppointmentSelect?.(appointment);
                  }}
                  sx={{
                    p: isMobile ? 1.5 : 2,
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 2,
                    cursor: onAppointmentSelect ? 'pointer' : 'default',
                    '&:hover': {
                      boxShadow: 2,
                      borderColor: 'primary.light',
                      bgcolor: onAppointmentSelect ? 'action.hover' : 'transparent'
                    },
                    transition: 'all 0.2s ease'
                  }}
                >
                  <Box sx={{ 
                    display: 'flex', 
                    alignItems: 'flex-start', 
                    gap: isMobile ? 1.5 : 2,
                    flexDirection: isMobile ? 'column' : 'row'
                  }}>
                    {/* Time badge */}
                    <Box
                      sx={{
                        minWidth: isMobile ? '100%' : 80,
                        backgroundColor: 'primary.main',
                        color: 'white',
                        borderRadius: 2,
                        px: isMobile ? 2 : 1.5,
                        py: isMobile ? 0.75 : 1,
                        textAlign: 'center',
                        display: 'flex',
                        flexDirection: isMobile ? 'row' : 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: isMobile ? 0.5 : 0
                      }}
                    >
                      <Typography variant="body2" sx={{ 
                        fontWeight: 600, 
                        lineHeight: 1.2,
                        fontSize: isMobile ? '0.85rem' : '0.875rem'
                      }}>
                        {format(appointment.startTime, 'h:mm')}
                      </Typography>
                      <Typography variant="caption" sx={{ 
                        opacity: 0.9, 
                        lineHeight: 1,
                        fontSize: isMobile ? '0.7rem' : '0.75rem'
                      }}>
                        {format(appointment.startTime, 'a')}
                      </Typography>
                    </Box>

                    {/* Appointment details */}
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      {/* Student info and status */}
                      <Box sx={{ 
                        display: 'flex', 
                        alignItems: isMobile ? 'flex-start' : 'center', 
                        justifyContent: 'space-between', 
                        mb: 1,
                        flexDirection: isMobile ? 'column' : 'row',
                        gap: isMobile ? 1 : 0
                      }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {getTypeIcon(appointment.appointment_type)}
                          <Typography variant="subtitle1" sx={{ 
                            fontWeight: 600,
                            fontSize: isMobile ? '0.95rem' : '1rem'
                          }}>
                            {appointment.student_name || 'Unknown Student'}
                          </Typography>
                          {onAppointmentSelect && (
                            <Typography variant="caption" sx={{ 
                              color: 'primary.main',
                              fontSize: '0.7rem',
                              fontStyle: 'italic',
                              opacity: 0.8
                            }}>
                              Click to plan
                            </Typography>
                          )}
                        </Box>
                        
                        <Box sx={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          gap: 1,
                          alignSelf: isMobile ? 'flex-end' : 'center'
                        }}>
                          <Chip
                            label={appointment.status}
                            size="small"
                            color={getStatusColor(appointment.status)}
                            sx={{ fontSize: isMobile ? '0.65rem' : '0.75rem' }}
                          />
                          
                          {/* Start Session Button */}
                          {appointment.status === 'scheduled' && (
                            <Tooltip title="Start therapy session">
                              <IconButton
                                size="small"
                                onClick={(e) => handleStartSession(appointment, e)}
                                disabled={startSessionMutation.isPending}
                                sx={{
                                  backgroundColor: '#41AAB7',
                                  color: 'white',
                                  width: isMobile ? 28 : 32,
                                  height: isMobile ? 28 : 32,
                                  '&:hover': { 
                                    backgroundColor: '#369da8',
                                    transform: 'scale(1.05)'
                                  },
                                  '&:disabled': {
                                    backgroundColor: 'rgba(65, 170, 183, 0.5)',
                                    color: 'rgba(255, 255, 255, 0.7)'
                                  },
                                  transition: 'all 0.2s ease'
                                }}
                              >
                                <PlayArrow fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          )}
                        </Box>
                      </Box>

                      {/* Session details */}
                      <Box sx={{ 
                        display: 'flex', 
                        flexWrap: 'wrap', 
                        gap: 1, 
                        mb: 1
                      }}>
                        <Typography variant="body2" color="text.secondary">
                          {formatTimeRange(appointment.startTime, appointment.endTime)}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          • {formatDuration(appointment.duration)}
                        </Typography>
                        {appointment.appointment_type && (
                          <Typography variant="body2" color="text.secondary">
                            • {appointment.appointment_type}
                          </Typography>
                        )}
                      </Box>

                      {/* Location */}
                      {appointment.location && (
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
                          <School fontSize="small" color="action" />
                          <Typography variant="body2" color="text.secondary">
                            {appointment.location}
                          </Typography>
                        </Box>
                      )}

                      {/* Recurring indicator */}
                      <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                        {appointment.series_id && (
                          <Chip
                            label="Recurring"
                            size="small"
                            variant="outlined"
                            color="secondary"
                          />
                        )}
                        <Tooltip title="Therapy History">
                          <IconButton
                            size="small"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            setTherapyHistoryStudent({
                              id: appointment.student_id,
                              name: appointment.student_name || `Student ${appointment.student_id}`
                            });
                          }}
                          sx={{
                            border: '1px solid',
                            borderColor: 'divider',
                            color: '#41AAB7',
                            width: isMobile ? 28 : 32,
                            height: isMobile ? 28 : 32,
                            '&:hover': {
                              borderColor: '#41AAB7',
                              backgroundColor: 'rgba(65, 170, 183, 0.08)'
                            }
                          }}
                        >
                          <Timeline fontSize="small" />
                        </IconButton>
                        </Tooltip>
                      </Box>
                    </Box>
                  </Box>
                </Paper>
              ))}
            </Stack>
          )}
      </Box>

      {therapyHistoryStudent && (
        <StudentTherapyHistoryDialog
          open={Boolean(therapyHistoryStudent)}
          onClose={() => setTherapyHistoryStudent(null)}
          studentId={therapyHistoryStudent.id}
          studentName={therapyHistoryStudent.name}
        />
      )}
    </Card>
  );
}
