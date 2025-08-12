import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Grid,
  Alert,
  CircularProgress,
  AppBar,
  Toolbar,
  IconButton,
  Chip,
  Paper,
  Divider,
  useMediaQuery,
  useTheme
} from '@mui/material';
import {
  ArrowBack,
  Person,
  Schedule,
  PlayArrow,
  Stop,
  Save,
  Assignment,
  CheckCircle
} from '@mui/icons-material';
import { format } from 'date-fns';
import { useTherapySession, useUpdateTherapySession, useCompleteTherapySession } from '../../lib/hooks/useTherapySessions';
import { useStudentActiveGoals } from '../../lib/hooks/useStudentGoals';
import { therapySessionsApi } from '../../lib/api/therapySessions';
import { TherapySessionGoalsAndObjectives } from './components/TherapySessionGoalsAndObjectives';
import { SessionNotesForm } from './components/SessionNotesForm';
import { SessionSummary } from './components/SessionSummary';
import type { TherapySession } from '../../lib/api/therapySessions';

interface TherapySessionInterfaceProps {
  // Optional: can be used when called programmatically with a specific session
  sessionId?: number;
  onExit?: () => void;
}

export function TherapySessionInterface({ 
  sessionId: propSessionId, 
  onExit 
}: TherapySessionInterfaceProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const { sessionId: routeSessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  
  // Use prop sessionId if provided, otherwise use route param
  const sessionId = propSessionId || (routeSessionId ? parseInt(routeSessionId) : null);
  
  // State management
  const [currentView, setCurrentView] = useState<'goals' | 'objectives' | 'notes' | 'summary'>('goals');
  const [sessionStarted, setSessionStarted] = useState(false);
  
  // API hooks
  const { 
    data: session, 
    isLoading: sessionLoading, 
    error: sessionError,
    refetch: refetchSession
  } = useTherapySession(sessionId!, !!sessionId);
  
  const { 
    data: studentGoals = [], 
    isLoading: goalsLoading 
  } = useStudentActiveGoals(session?.student_id || 0, !!session?.student_id);
  
  const updateSessionMutation = useUpdateTherapySession();
  const completeSessionMutation = useCompleteTherapySession();

  // Auto-start session if it's in planned status
  useEffect(() => {
    if (session && session.status === 'planned' && !sessionStarted) {
      handleStartSession();
    }
  }, [session, sessionStarted]);

  const handleStartSession = async () => {
    if (!session || !sessionId) return;
    
    try {
      await updateSessionMutation.mutateAsync({
        sessionId,
        sessionData: {
          status: 'in_progress',
          start_time: new Date().toISOString()
        }
      });
      setSessionStarted(true);
      await refetchSession();
    } catch (error) {
      console.error('Failed to start session:', error);
    }
  };

  const handleCompleteSession = async (sessionData: any) => {
    if (!sessionId) return;
    
    try {
          await completeSessionMutation.mutateAsync({
      sessionId,
      request: sessionData
      });
      
      // Navigate back or call onExit
      if (onExit) {
        onExit();
      } else {
        navigate('/therapy');
      }
    } catch (error) {
      console.error('Failed to complete session:', error);
    }
  };

  const handleBack = () => {
    if (onExit) {
      onExit();
    } else {
      navigate(-1);
    }
  };

  // Loading states
  if (!sessionId) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">
          No session ID provided. Please start a therapy session first.
        </Alert>
      </Box>
    );
  }

  if (sessionLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
        <CircularProgress size={40} />
      </Box>
    );
  }

  if (sessionError || !session) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">
          Failed to load therapy session. Please try again.
        </Alert>
      </Box>
    );
  }

  const isSessionActive = session.status === 'in_progress';
  const isSessionCompleted = session.status === 'completed';

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* Header */}
      <AppBar position="static" sx={{ bgcolor: '#40A8B6' }}>
        <Toolbar sx={{ 
          flexDirection: isMobile ? 'column' : 'row',
          alignItems: isMobile ? 'stretch' : 'center',
          py: isMobile ? 1 : undefined,
          gap: isMobile ? 1 : 0
        }}>
          <Box sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            width: isMobile ? '100%' : 'auto'
          }}>
            <IconButton
              edge="start"
              color="inherit"
              onClick={handleBack}
              sx={{ mr: 2 }}
              size={isMobile ? "small" : "medium"}
            >
              <ArrowBack />
            </IconButton>
            
            <Box sx={{ display: 'flex', alignItems: 'center', gap: isMobile ? 1 : 2, flex: 1 }}>
              <Person sx={{ fontSize: isMobile ? 20 : 24 }} />
              <Box sx={{ minWidth: 0, flex: 1 }}>
                <Typography 
                  variant={isMobile ? "subtitle1" : "h6"} 
                  component="div"
                  sx={{ 
                    fontSize: isMobile ? '1rem' : undefined,
                    fontWeight: 600,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}
                >
                  {isMobile ? session.student_name : `Therapy Session - ${session.student_name}`}
                </Typography>
                <Typography 
                  variant="body2" 
                  sx={{ 
                    opacity: 0.9,
                    fontSize: isMobile ? '0.75rem' : undefined,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}
                >
                  {format(new Date(session.session_date), isMobile ? 'MMM d, yyyy' : 'EEEE, MMMM d, yyyy')}
                  {!isMobile && session.appointment_id && ' • Scheduled Appointment'}
                  {!isMobile && session.start_time && ` • Started ${format(new Date(session.start_time), 'h:mm a')}`}
                </Typography>
              </Box>
            </Box>
          </Box>

          <Box sx={{ 
            display: 'flex', 
            gap: 1,
            justifyContent: isMobile ? 'center' : 'flex-end',
            flexWrap: 'wrap'
          }}>
            <Chip
              label={session.status.replace('_', ' ').toUpperCase()}
              color={isSessionActive ? 'success' : isSessionCompleted ? 'default' : 'warning'}
              variant="filled"
              size={isMobile ? "small" : "medium"}
              sx={{ 
                bgcolor: isSessionActive ? '#4caf50' : isSessionCompleted ? '#9e9e9e' : '#ff9800',
                color: 'white',
                fontSize: isMobile ? '0.7rem' : undefined
              }}
            />
            
            {session.session_type && (
              <Chip
                label={session.session_type.toUpperCase()}
                variant="outlined"
                size={isMobile ? "small" : "medium"}
                sx={{ 
                  borderColor: 'white', 
                  color: 'white',
                  fontSize: isMobile ? '0.7rem' : undefined
                }}
              />
            )}
          </Box>
        </Toolbar>
      </AppBar>

      {/* Navigation Tabs */}
      <Paper sx={{ borderRadius: 0 }}>
        <Box sx={{ 
          display: 'flex', 
          bgcolor: 'background.paper',
          flexDirection: isMobile ? 'column' : 'row'
        }}>
          {[
            { id: 'goals', label: isMobile ? 'Goals' : 'Goals & Objectives', icon: <Assignment /> },
            { id: 'notes', label: 'Session Notes', icon: <Save /> },
            ...(isSessionActive ? [{ id: 'summary', label: isMobile ? 'Complete' : 'Complete Session', icon: <Stop /> }] : [])
          ].map((tab) => (
            <Button
              key={tab.id}
              onClick={() => setCurrentView(tab.id as any)}
              startIcon={!isMobile ? tab.icon : undefined}
              variant={currentView === tab.id ? 'contained' : 'text'}
              size={isMobile ? "medium" : "large"}
              sx={{
                flex: 1,
                borderRadius: 0,
                py: isMobile ? 1.5 : 2,
                fontSize: isMobile ? '0.85rem' : undefined,
                ...(currentView === tab.id && {
                  bgcolor: '#40A8B6',
                  color: 'white',
                  '&:hover': { bgcolor: '#369aa6' }
                })
              }}
            >
              {isMobile && tab.icon}
              {isMobile && <Box sx={{ ml: 1 }}>{tab.label}</Box>}
              {!isMobile && tab.label}
            </Button>
          ))}
        </Box>
      </Paper>

      {/* Content Area */}
      <Box sx={{ 
        flex: 1, 
        overflow: 'auto', 
        p: isMobile ? 2 : 3 
      }}>
        {!isSessionActive && !isSessionCompleted && (
          <Alert severity="info" sx={{ mb: isMobile ? 2 : 3 }}>
            <Typography 
              variant="body2"
              sx={{ fontSize: isMobile ? '0.85rem' : undefined }}
            >
              Session is ready to start. Click the start button to begin therapy session.
            </Typography>
            <Button
              variant="contained"
              startIcon={<PlayArrow />}
              onClick={handleStartSession}
              disabled={updateSessionMutation.isPending}
              fullWidth={isMobile}
              size={isMobile ? "medium" : "large"}
              sx={{ 
                mt: isMobile ? 1.5 : 2,
                fontSize: isMobile ? '0.9rem' : undefined
              }}
            >
              {updateSessionMutation.isPending ? 'Starting...' : 'Start Session'}
            </Button>
          </Alert>
        )}

        {isSessionCompleted && (
          <Alert severity="success" sx={{ mb: isMobile ? 2 : 3 }}>
            <Typography 
              variant="body2"
              sx={{ fontSize: isMobile ? '0.85rem' : undefined }}
            >
              This therapy session has been completed.
              {session.end_time && ` Ended at ${format(new Date(session.end_time), 'h:mm a')}`}
            </Typography>
          </Alert>
        )}

        {/* Tab Content */}
        {currentView === 'goals' && (
          <TherapySessionGoalsAndObjectives
            session={session}
            studentGoals={studentGoals}
            disabled={!isSessionActive}
            onUpdateObjectiveProgress={async (objectiveId: number, updates: any) => {
              if (!sessionId) return;
              try {
                // Update the session objective using the proper API service
                await therapySessionsApi.updateSessionObjective(sessionId, objectiveId, updates);
                await refetchSession();
              } catch (error) {
                console.error('Failed to update objective progress:', error);
                alert('Failed to save objective progress. Please try again.');
              }
            }}
            onUpdateGoalProgress={async (goalId: number, updates: any) => {
              if (!sessionId) return;
              try {
                // Update the session goal data
                await updateSessionMutation.mutateAsync({
                  sessionId,
                  sessionData: {
                    session_notes: `Goal ${goalId} progress: ${JSON.stringify(updates)}`
                  }
                });
                await refetchSession();
              } catch (error) {
                console.error('Failed to update goal progress:', error);
              }
            }}
          />
        )}

        {currentView === 'notes' && (
          <SessionNotesForm
            session={session}
            onSave={(notes) => {
              if (sessionId) {
                updateSessionMutation.mutate({
                  sessionId,
                  sessionData: notes
                });
              }
            }}
            disabled={!isSessionActive}
          />
        )}

        {currentView === 'summary' && isSessionActive && (
          <SessionSummary
            session={session}
            studentGoals={studentGoals}
            onComplete={handleCompleteSession}
            loading={completeSessionMutation.isPending}
          />
        )}
      </Box>
    </Box>
  );
}
