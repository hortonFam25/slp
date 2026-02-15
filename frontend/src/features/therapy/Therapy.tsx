import React, { useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  TextField,
  Autocomplete,
  Button,
  Alert,
  Divider,
  FormControlLabel,
  Radio,
  RadioGroup,
  Paper,
  Chip,
  CircularProgress,
  useMediaQuery,
  useTheme
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { format } from 'date-fns';
import { 
  MedicalServices, 
  CalendarToday, 
  Person,
  PlayArrow,
  Assessment,
  Link,
  Psychology
} from '@mui/icons-material';
import { Stethoscope } from 'lucide-react';
import { useStudents } from '../../lib/hooks/useStudents';
import { useAppointments } from '../../lib/hooks/useScheduling';
import { useStartTherapySession } from '../../lib/hooks/useTherapySessions';
import { useStudentActiveGoals, flattenGoalsAndObjectives, parseSelectedGoalsAndObjectives } from '../../lib/hooks/useStudentGoals';
import { StartSessionRequest } from '../../lib/api/therapySessions';
import { AppointmentSummary } from '../../lib/api/scheduling';
import { useNavigate } from 'react-router-dom';
import type { Student } from '../../lib/api/students';

export default function Therapy() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const { students, loading: studentsLoading, error: studentsError } = useStudents();
  const [selectedStudent, setSelectedStudent] = useState<Student | null>(null);
  const [sessionDate, setSessionDate] = useState<Date>(new Date());

  const [selectedAppointment, setSelectedAppointment] = useState<AppointmentSummary | null>(null);
  
  const startSessionMutation = useStartTherapySession();
  const navigate = useNavigate();

  // Get appointments for the selected student (next 60 days)
  const today = new Date();
  const sixtyDaysFromNow = new Date();
  sixtyDaysFromNow.setDate(today.getDate() + 60);
  
  const appointmentFilters = selectedStudent?.id ? {
    start_date: today.toISOString().split('T')[0],
    end_date: sixtyDaysFromNow.toISOString().split('T')[0],
    student_id: selectedStudent.id,
    status: 'scheduled'
  } : undefined;

  const { appointments = [], loading: appointmentsLoading } = useAppointments(appointmentFilters);

  const handleStartSession = async () => {
    if (!selectedStudent) return;

    try {
      const request: StartSessionRequest = {
        student_id: selectedStudent.id,
        session_type: selectedAppointment ? 'link_existing' : 'unscheduled',
        appointment_id: selectedAppointment?.id,
        create_appointment: !selectedAppointment, // Auto-create if no appointment selected
        planned_duration_minutes: selectedAppointment?.duration_minutes || 30,
        planned_goals: [], // TODO: Get from appointment if existing
        planned_objectives: [] // TODO: Get from appointment if existing
      };

      const newSession = await startSessionMutation.mutateAsync(request);
      
      // Navigate to the unified therapy session interface
      navigate(`/therapy/session/${newSession.id}`);
    } catch (error) {
      console.error('Failed to start therapy session:', error);
    }
  };

  // Reset selected appointment when student changes
  React.useEffect(() => {
    setSelectedAppointment(null);
  }, [selectedStudent]);

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ 
        height: '100%', 
        display: 'flex', 
        flexDirection: 'column',
        overflow: 'hidden',
        minHeight: 0
      }}>
        {/* Header */}
        <Box sx={{ 
          bgcolor: 'white',
          borderBottom: '1px solid #e8f4f5',
          py: isMobile ? 2 : 3,
          px: isMobile ? 2 : 3,
          boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
          flexShrink: 0
        }}>
          <Typography 
            variant={isMobile ? "h5" : "h4"} 
            component="h1" 
            sx={{ 
              display: 'flex', 
              alignItems: 'center',
              color: '#41AAB7',
              fontWeight: 700,
              fontSize: isMobile ? '1.5rem' : undefined,
              gap: 2
            }}
          >
            <Stethoscope size={isMobile ? 24 : 32} />
            Therapy
          </Typography>
        </Box>

        {/* Scrollable Content Area */}
        <Box sx={{ 
          flex: 1,
          overflow: 'auto',
          px: isMobile ? 2 : 3,
          py: isMobile ? 2 : 3
        }}>

        {/* Error Alert */}
        {studentsError && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {studentsError}
          </Alert>
        )}

        {/* Session Setup Card */}
        <Card sx={{ 
          maxWidth: isMobile ? '100%' : 800, 
          mx: 'auto',
          boxShadow: isMobile ? '0 2px 8px rgba(0,0,0,0.1)' : '0 4px 12px rgba(0,0,0,0.1)',
          border: '1px solid #e0e0e0',
          borderRadius: isMobile ? 2 : 3
        }}>
          <CardContent sx={{ p: isMobile ? 3 : 4 }}>
            <Typography 
              variant={isMobile ? "h6" : "h5"} 
              sx={{ 
                mb: isMobile ? 2 : 3, 
                color: '#40A8B6', 
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                fontSize: isMobile ? '1.25rem' : undefined
              }}
            >
              <Assessment sx={{ mr: isMobile ? 1 : 2, fontSize: isMobile ? 20 : 24 }} />
              Start New Session
            </Typography>

            <Grid container spacing={isMobile ? 2 : 3}>
              {/* Student Selection */}
              <Grid item xs={12} md={6}>
                <Box sx={{ 
                  p: isMobile ? 2 : 3, 
                  bgcolor: '#f8fffe', 
                  borderRadius: 2, 
                  border: '1px solid #e8f4f5' 
                }}>
                  <Typography 
                    variant={isMobile ? "subtitle1" : "h6"} 
                    sx={{ 
                      mb: isMobile ? 1.5 : 2, 
                      color: '#40A8B6', 
                      fontWeight: 600,
                      display: 'flex',
                      alignItems: 'center',
                      fontSize: isMobile ? '1.1rem' : undefined
                    }}
                  >
                    <Person sx={{ mr: 1, fontSize: isMobile ? 20 : 24 }} />
                    Select Student
                  </Typography>
                  <Autocomplete
                    options={students || []}
                    getOptionLabel={(student) => `${student.first} ${student.last}`}
                    value={selectedStudent}
                    onChange={(_, newValue) => setSelectedStudent(newValue as Student)}
                    loading={studentsLoading}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Search for student"
                        variant="outlined"
                        fullWidth
                        placeholder="Type student name..."
                      />
                    )}
                    renderOption={(props, student) => {
                      const { key, ...optionProps } = props;
                      return (
                        <Box component="li" key={key} {...optionProps}>
                          <Box>
                            <Typography variant="body1">
                              {student.first} {student.last}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Grade: {student.grade_level || 'N/A'} | 
                              UIC: {student.uic || 'N/A'}
                            </Typography>
                          </Box>
                        </Box>
                      );
                    }}
                  />
                </Box>
              </Grid>

              {/* Appointment Selection */}
              {selectedStudent && (
                <Grid item xs={12}>
                  <Box sx={{ 
                    p: isMobile ? 2 : 3, 
                    bgcolor: '#f8fffe', 
                    borderRadius: 2, 
                    border: '1px solid #e8f4f5' 
                  }}>
                    <Typography 
                      variant={isMobile ? "subtitle1" : "h6"} 
                      sx={{ 
                        mb: isMobile ? 1.5 : 2, 
                        color: '#40A8B6', 
                        fontWeight: 600,
                        display: 'flex',
                        alignItems: 'center',
                        fontSize: isMobile ? '1.1rem' : undefined
                      }}
                    >
                      <CalendarToday sx={{ mr: 1, fontSize: isMobile ? 20 : 24 }} />
                      Upcoming Appointments
                    </Typography>

                    {appointmentsLoading ? (
                      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                        <CircularProgress />
                      </Box>
                    ) : appointments.length > 0 ? (
                      <Box>
                        <Typography 
                          variant="body2" 
                          color="text.secondary" 
                          sx={{ 
                            mb: isMobile ? 1.5 : 2,
                            fontSize: isMobile ? '0.85rem' : undefined
                          }}
                        >
                          Select an appointment to link your session, or click "Start Session" below to create an ad-hoc session.
                        </Typography>
                        <Box sx={{ 
                          maxHeight: isMobile ? '200px' : '240px', 
                          overflowY: 'auto' 
                        }}>
                          <RadioGroup
                            value={selectedAppointment?.id || ''}
                            onChange={(e) => {
                              const appointmentId = parseInt(e.target.value);
                              const appointment = appointments.find(apt => apt.id === appointmentId);
                              setSelectedAppointment(appointment || null);
                            }}
                          >
                          {appointments.map((appointment) => (
                            <Paper 
                              key={appointment.id}
                              sx={{ 
                                p: isMobile ? 1.5 : 2, 
                                mb: 1,
                                cursor: 'pointer',
                                border: selectedAppointment?.id === appointment.id ? '2px solid #40A8B6' : '1px solid #e0e0e0',
                                bgcolor: selectedAppointment?.id === appointment.id ? '#f0f9fa' : 'white',
                                '&:hover': { bgcolor: selectedAppointment?.id === appointment.id ? '#f0f9fa' : '#f5f5f5' }
                              }}
                              onClick={() => setSelectedAppointment(appointment)}
                            >
                              <FormControlLabel
                                value={appointment.id}
                                control={<Radio />}
                                label={
                                  <Box sx={{ width: '100%' }}>
                                    <Typography 
                                      variant="body1" 
                                      fontWeight="bold"
                                      sx={{ fontSize: isMobile ? '0.9rem' : undefined }}
                                    >
                                      {format(new Date(appointment.start_datetime), isMobile ? 'MMM d, yyyy' : 'EEEE, MMMM d, yyyy')}
                                    </Typography>
                                    <Typography 
                                      variant="body2" 
                                      color="primary"
                                      sx={{ fontSize: isMobile ? '0.8rem' : undefined }}
                                    >
                                      {format(new Date(appointment.start_datetime), 'h:mm a')} - {format(new Date(appointment.end_datetime), 'h:mm a')}
                                    </Typography>

                                    <Box sx={{ mt: 1 }}>
                                      <Chip 
                                        label={appointment.appointment_type} 
                                        size="small" 
                                        variant="outlined"
                                        color="primary"
                                        sx={{ fontSize: isMobile ? '0.7rem' : undefined }}
                                      />
                                      {appointment.location && (
                                        <Chip 
                                          label={appointment.location} 
                                          size="small" 
                                          variant="outlined" 
                                          sx={{ 
                                            ml: 1,
                                            fontSize: isMobile ? '0.7rem' : undefined
                                          }}
                                        />
                                      )}
                                    </Box>
                                  </Box>
                                }
                                sx={{ margin: 0, width: '100%' }}
                              />
                            </Paper>
                          ))}
                          </RadioGroup>
                        </Box>
                      </Box>
                    ) : (
                      <Alert severity="info">
                        No scheduled appointments found for this student in the next 60 days. Click "Start Session" below to create an ad-hoc session.
                      </Alert>
                    )}
                  </Box>
                </Grid>
              )}


            </Grid>

            <Divider sx={{ my: isMobile ? 3 : 4, borderColor: '#e8f4f5' }} />

            {/* Start Session Button */}
            <Box sx={{ textAlign: 'center' }}>
              <Button
                variant="contained"
                size={isMobile ? "medium" : "large"}
                startIcon={<PlayArrow />}
                onClick={handleStartSession}
                disabled={
                  !selectedStudent || 
                  startSessionMutation.isPending
                }
                fullWidth={isMobile}
                sx={{
                  bgcolor: '#40A8B6',
                  '&:hover': {
                    bgcolor: '#369aa6'
                  },
                  '&:disabled': {
                    bgcolor: '#e0e0e0'
                  },
                  textTransform: 'none',
                  fontWeight: 600,
                  px: isMobile ? 3 : 4,
                  py: isMobile ? 1.25 : 1.5,
                  borderRadius: 2,
                  fontSize: isMobile ? '1rem' : '1.1rem'
                }}
              >
                {startSessionMutation.isPending ? 'Starting Session...' : 'Start Therapy Session'}
              </Button>
            </Box>
          </CardContent>
        </Card>
        </Box> {/* End scrollable content area */}
      </Box> {/* End main container with flex layout */}
    </LocalizationProvider>
  );
}
