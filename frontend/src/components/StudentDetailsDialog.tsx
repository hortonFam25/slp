import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Tabs,
  Tab,
  Box,
  Typography,
  IconButton,
  LinearProgress,
  Alert,
  Divider,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { Close, Person, TrackChanges, Event, Psychology } from '@mui/icons-material';
import { studentsApi, Student } from '../lib/api/students';
import { schedulingApi, AppointmentSummary } from '../lib/api/scheduling';
import { therapySessionsApi, TherapySessionSummary } from '../lib/api/therapySessions';

// Tab components
import { StudentBasicInfo } from './student-details/StudentBasicInfo';
import { StudentGoals } from './student-details/StudentGoals';
import { StudentAppointments } from './student-details/StudentAppointments';
import { StudentTherapySessions } from './student-details/StudentTherapySessions';

interface StudentDetailsDialogProps {
  open: boolean;
  onClose: () => void;
  studentId: number;
  studentName: string;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`student-tabpanel-${index}`}
      aria-labelledby={`student-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: isMobile ? 2 : 3 }}>{children}</Box>}
    </div>
  );
}

export function StudentDetailsDialog({ open, onClose, studentId, studentName }: StudentDetailsDialogProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Data states
  const [student, setStudent] = useState<Student | null>(null);
  const [appointments, setAppointments] = useState<AppointmentSummary[]>([]);
  const [therapySessions, setTherapySessions] = useState<TherapySessionSummary[]>([]);
  
  // Loading states for individual sections
  const [loadingStates, setLoadingStates] = useState({
    student: true,
    appointments: true,
    therapySessions: true,
  });

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const loadStudentData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Load student basic info
      setLoadingStates(prev => ({ ...prev, student: true }));
      const studentData = await studentsApi.getStudent(studentId);
      setStudent(studentData);
      setLoadingStates(prev => ({ ...prev, student: false }));

    } catch (err) {
      console.error('Error loading student data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load student data');
    } finally {
      setLoading(false);
    }
  };



  const loadAppointments = async () => {
    try {
      setLoadingStates(prev => ({ ...prev, appointments: true }));
      const appointmentsData = await schedulingApi.getStudentAppointments(studentId);
      setAppointments(appointmentsData);
    } catch (err) {
      console.error('Error loading appointments:', err);
    } finally {
      setLoadingStates(prev => ({ ...prev, appointments: false }));
    }
  };

  const loadTherapySessions = async () => {
    try {
      setLoadingStates(prev => ({ ...prev, therapySessions: true }));
      // Get many more sessions to handle users with 300+ sessions
      const sessionsData = await therapySessionsApi.getStudentSessions(studentId, 500);
      setTherapySessions(sessionsData);
    } catch (err) {
      console.error('Error loading therapy sessions:', err);
    } finally {
      setLoadingStates(prev => ({ ...prev, therapySessions: false }));
    }
  };

  // Load data when dialog opens
  useEffect(() => {
    if (open && studentId) {
      loadStudentData();
    }
  }, [open, studentId]);

  // Load additional data based on active tab
  useEffect(() => {
    if (!open || !studentId) return;

    switch (activeTab) {
      case 2: // Appointments tab
        if (loadingStates.appointments) {
          loadAppointments();
        }
        break;
      case 3: // Therapy Sessions tab
        if (loadingStates.therapySessions) {
          loadTherapySessions();
        }
        break;
    }
  }, [activeTab, open, studentId]);

  const handleStudentUpdate = (updatedStudent: Student) => {
    setStudent(updatedStudent);
  };

  const handleClose = () => {
    // Reset states when closing
    setActiveTab(0);
    setStudent(null);
    setAppointments([]);
    setTherapySessions([]);
    setLoadingStates({
      student: true,
      appointments: true,
      therapySessions: true,
    });
    setError(null);
    onClose();
  };

  const tabs = [
    { label: 'Basic Info', icon: <Person />, loading: loadingStates.student },
    { label: 'IEP Goals', icon: <TrackChanges />, loading: false }, // GoalManagement handles its own loading
    { label: 'Appointments', icon: <Event />, loading: loadingStates.appointments },
    { label: 'Therapy Sessions', icon: <Psychology />, loading: loadingStates.therapySessions },
  ];

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="xl"
      fullWidth
      fullScreen={isMobile}
      PaperProps={{
        sx: { 
          height: isMobile ? '100vh' : '90vh',
          display: 'flex',
          flexDirection: 'column'
        }
      }}
    >
      <DialogTitle sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between', 
        pb: 1,
        px: isMobile ? 2 : 3,
        py: isMobile ? 1.5 : 2,
        flexShrink: 0
      }}>
        <Typography 
          variant={isMobile ? 'h6' : 'h5'} 
          component="div"
          sx={{ 
            fontSize: isMobile ? '1.1rem' : '1.5rem',
            fontWeight: 600
          }}
        >
          {studentName} - Details
        </Typography>
        <IconButton 
          onClick={handleClose} 
          size="small"
          sx={{ 
            width: isMobile ? 32 : 40,
            height: isMobile ? 32 : 40
          }}
        >
          <Close fontSize={isMobile ? 'small' : 'medium'} />
        </IconButton>
      </DialogTitle>

      <Divider sx={{ flexShrink: 0 }} />

      {error && (
        <Alert severity="error" sx={{ m: isMobile ? 1.5 : 2, flexShrink: 0 }}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Box sx={{ p: isMobile ? 2 : 3, flexShrink: 0 }}>
          <LinearProgress />
          <Typography variant="body2" sx={{ mt: 2, textAlign: 'center' }}>
            Loading student information...
          </Typography>
        </Box>
      ) : (
        <>
          <Box sx={{ borderBottom: 1, borderColor: 'divider', flexShrink: 0 }}>
            <Tabs
              value={activeTab}
              onChange={handleTabChange}
              variant="scrollable"
              scrollButtons="auto"
              sx={{ px: isMobile ? 1 : 2 }}
            >
              {tabs.map((tab, index) => (
                <Tab
                  key={index}
                  icon={isMobile ? undefined : tab.icon}
                  iconPosition="start"
                  label={
                    isMobile ? (
                      tab.label
                    ) : (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {tab.label}
                        {tab.loading && activeTab === index && (
                          <LinearProgress size={16} sx={{ width: 20, height: 2 }} />
                        )}
                      </Box>
                    )
                  }
                  sx={{ 
                    minHeight: isMobile ? 48 : 64,
                    fontSize: isMobile ? '0.8rem' : '0.875rem'
                  }}
                />
              ))}
            </Tabs>
          </Box>

          <Box sx={{ 
            flex: 1, 
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column'
          }}>
            <TabPanel value={activeTab} index={0}>
              <StudentBasicInfo 
                student={student} 
                loading={loadingStates.student}
                onUpdate={handleStudentUpdate}
              />
            </TabPanel>

            <TabPanel value={activeTab} index={1}>
              <StudentGoals 
                studentId={studentId}
                studentName={student ? `${student.first} ${student.last}` : undefined}
              />
            </TabPanel>

            <TabPanel value={activeTab} index={2}>
              <StudentAppointments 
                studentId={studentId}
                appointments={appointments}
                loading={loadingStates.appointments}
                onRefresh={loadAppointments}
              />
            </TabPanel>

            <TabPanel value={activeTab} index={3}>
              <StudentTherapySessions 
                studentId={studentId}
                therapySessions={therapySessions}
                loading={loadingStates.therapySessions}
                onRefresh={loadTherapySessions}
              />
            </TabPanel>
          </Box>
        </>
      )}

      <DialogActions sx={{ 
        flexDirection: isMobile ? 'column' : 'row',
        justifyContent: 'space-between', 
        px: isMobile ? 2 : 3, 
        py: isMobile ? 1.5 : 2,
        gap: isMobile ? 1.5 : 0,
        flexShrink: 0
      }}>
        <Box sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 2,
          justifyContent: isMobile ? 'center' : 'flex-start'
        }}>
          <Typography variant="body2" color="text.secondary" sx={{
            fontSize: isMobile ? '0.8rem' : '0.875rem'
          }}>
            {activeTab + 1} of {tabs.length}
          </Typography>
          <LinearProgress 
            variant="determinate" 
            value={(activeTab + 1) / tabs.length * 100} 
            sx={{ width: isMobile ? 80 : 100, height: 6 }}
          />
        </Box>
        
        <Box sx={{ 
          display: 'flex', 
          gap: 1,
          flexDirection: isMobile ? 'column' : 'row',
          width: isMobile ? '100%' : 'auto'
        }}>
          <Box sx={{ 
            display: 'flex', 
            gap: 1,
            width: isMobile ? '100%' : 'auto'
          }}>
            <Button 
              onClick={() => setActiveTab(Math.max(0, activeTab - 1))}
              disabled={activeTab === 0}
              fullWidth={isMobile}
              size={isMobile ? 'medium' : 'small'}
            >
              Previous
            </Button>
            <Button 
              onClick={() => setActiveTab(Math.min(tabs.length - 1, activeTab + 1))}
              disabled={activeTab === tabs.length - 1}
              variant="contained"
              fullWidth={isMobile}
              size={isMobile ? 'medium' : 'small'}
            >
              Next
            </Button>
          </Box>
          <Button 
            onClick={handleClose} 
            color="inherit"
            fullWidth={isMobile}
            size={isMobile ? 'medium' : 'small'}
          >
            Close
          </Button>
        </Box>
      </DialogActions>
    </Dialog>
  );
}
