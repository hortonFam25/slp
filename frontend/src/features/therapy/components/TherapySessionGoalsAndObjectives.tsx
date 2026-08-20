import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Grid,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  LinearProgress,
  Divider,
  Paper,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Skeleton,
  Collapse,
  useMediaQuery,
  useTheme,
  ToggleButton,
  ToggleButtonGroup,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions
} from '@mui/material';
import {
  ExpandMore,
  Assignment,
  CheckCircle,
  PlayArrow,
  Timer,
  Save,
  Cancel,
  GpsFixed,
  ExpandLess,
  History,
  Close,
  ChevronLeft,
  ChevronRight,
  Notes,
  TrendingUp,
  CalendarToday,
  ViewList,
  GridView
} from '@mui/icons-material';
import { format } from 'date-fns';
import { therapySessionsApi, type TherapySession } from '../../../lib/api/therapySessions';
import type { IEPGoal, GoalObjective } from '../../../lib/api/types/goals';

interface TherapySessionGoalsAndObjectivesProps {
  session: TherapySession;
  studentGoals: IEPGoal[];
  disabled?: boolean;
  onUpdateGoalProgress?: (goalId: number, updates: any) => void;
  onUpdateObjectiveProgress?: (objectiveId: number, updates: any) => void;
}

interface GoalSessionData {
  planned: boolean;
  worked_on: boolean;
  goal_met?: boolean;
  difficulty_level?: string;
  student_response?: string;
  time_spent_minutes?: number;
  session_notes?: string;
  goal_progress_summary?: string;
}

interface ObjectiveSessionData {
  planned: boolean;
  worked_on: boolean;
  trials_attempted?: number;
  trials_correct?: number;
  accuracy_percentage?: number;
  independence_level?: string;
  objective_met?: boolean;
  progress_rating?: string;
  prompt_level?: string;
  time_spent_minutes?: number;
  student_engagement?: string;
  session_notes?: string;
  pre_session_notes?: string;
}

const DIFFICULTY_LEVELS = ['easy', 'appropriate', 'challenging', 'too_difficult'];
const STUDENT_RESPONSES = ['engaged', 'motivated', 'neutral', 'frustrated', 'resistant'];
const PROGRESS_RATINGS = ['no_progress', 'minimal', 'moderate', 'good', 'excellent'];
const INDEPENDENCE_LEVELS = ['independent', 'minimal_prompts', 'moderate_prompts', 'maximum_prompts', 'hand_over_hand'];
const PROMPT_LEVELS = ['none', 'verbal', 'gestural', 'visual', 'physical', 'full_physical'];

// Helper function to get school year date range
const getSchoolYearRange = () => {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth(); // 0-indexed, so August = 7
  
  // If we're in August-December, this is the start of the school year
  // If we're in January-July, we're in the second half of the school year
  const schoolYearStart = currentMonth >= 7 
    ? new Date(currentYear, 7, 1) // August 1st of current year
    : new Date(currentYear - 1, 7, 1); // August 1st of previous year
    
  const schoolYearEnd = currentMonth >= 7
    ? new Date(currentYear + 1, 5, 30) // June 30th of next year  
    : new Date(currentYear, 5, 30); // June 30th of current year
    
  return { start: schoolYearStart, end: schoolYearEnd };
};

export interface GridProgressViewProps {
  studentId: number;
  availableGoals: IEPGoal[];
  session: TherapySession;
  disabled?: boolean;
  onUpdateObjectiveProgress?: (objectiveId: number, updates: any) => void;
  showDateNavigator?: boolean;
}

export function GridProgressView({ 
  studentId, 
  availableGoals, 
  session, 
  disabled, 
  onUpdateObjectiveProgress,
  showDateNavigator = false
}: GridProgressViewProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  // Constants for tracking options
  const GRID_PROGRESS_RATINGS = ['no_progress', 'minimal', 'moderate', 'good', 'excellent'];
  const GRID_INDEPENDENCE_LEVELS = ['independent', 'minimal_prompts', 'moderate_prompts', 'maximum_prompts', 'hand_over_hand'];
  const GRID_PROMPT_LEVELS = ['none', 'verbal', 'gestural', 'visual', 'physical', 'full_physical'];
  const GRID_STUDENT_RESPONSES = ['engaged', 'motivated', 'neutral', 'frustrated', 'resistant'];
  const [allSessions, setAllSessions] = useState<TherapySession[]>([]);
  const [windowStartIndex, setWindowStartIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [editingCell, setEditingCell] = useState<{objectiveId: number, sessionId: number, objectiveTitle: string, sessionDate: string, preSessionNotes?: string} | null>(null);
  const [editingNotes, setEditingNotes] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [expandedTracking, setExpandedTracking] = useState(false);
  const [trackingData, setTrackingData] = useState({
    trials_attempted: undefined as number | undefined,
    trials_correct: undefined as number | undefined,
    accuracy_percentage: undefined as number | undefined,
    independence_level: ''
  });
  const SESSIONS_WINDOW_SIZE = 12;

  const getDefaultWindowStart = (sortedSessions: TherapySession[]) => {
    if (sortedSessions.length <= SESSIONS_WINDOW_SIZE) {
      return 0;
    }

    const maxStart = Math.max(0, sortedSessions.length - SESSIONS_WINDOW_SIZE);
    const sessionIndex = sortedSessions.findIndex((currentSession) => currentSession.id === session.id);

    if (sessionIndex >= 0) {
      return Math.min(maxStart, Math.max(0, sessionIndex - 7));
    }

    const todayStr = new Date().toISOString().split('T')[0];
    const todayIndex = sortedSessions.findIndex(
      (currentSession) => currentSession.session_date.split('T')[0] === todayStr
    );

    if (todayIndex >= 0) {
      return Math.min(maxStart, Math.max(0, todayIndex - 7));
    }

    return maxStart;
  };

  const visibleSessions = allSessions.slice(windowStartIndex, windowStartIndex + SESSIONS_WINDOW_SIZE);
  const maxWindowStart = Math.max(0, allSessions.length - SESSIONS_WINDOW_SIZE);
  const canShowOlder = windowStartIndex > 0;
  const canShowNewer = windowStartIndex < maxWindowStart;

  // Fetch school year sessions for this student
  useEffect(() => {
    const fetchSchoolYearSessions = async () => {
      try {
        setLoading(true);
        const { start, end } = getSchoolYearRange();
        const anchorDate = session.session_date
          ? new Date(session.session_date).toISOString().split('T')[0]
          : new Date().toISOString().split('T')[0];
        
        // Get a school-year window centered around the current session date.
        const fetchedSessions = await therapySessionsApi.getStudentSchoolYearSessions(
          studentId,
          start.toISOString().split('T')[0],
          end.toISOString().split('T')[0],
          75,
          anchorDate
        );
        
        // Always include the active session even when the historical fetch is capped.
        const sessionsForGrid = Array.from(
          new Map([...fetchedSessions, session].map((currentSession) => [currentSession.id, currentSession])).values()
        );

        // Sort sessions by date (oldest to newest)
        const sortedSessions = sessionsForGrid.sort((a: any, b: any) => 
          new Date(a.session_date).getTime() - new Date(b.session_date).getTime()
        );
        
        setAllSessions(sortedSessions);
        setWindowStartIndex(getDefaultWindowStart(sortedSessions));
      } catch (error) {
        console.error('Failed to fetch school year sessions:', error);
        setAllSessions([]);
        setWindowStartIndex(0);
      } finally {
        setLoading(false);
      }
    };

    if (studentId) {
      fetchSchoolYearSessions();
    }
  }, [studentId, session.id, session.session_date]);

  const handleCellClick = (objectiveId: number, sessionId: number, currentNotes: string, objectiveTitle: string, sessionDate: string, preSessionNotes?: string) => {
    if (disabled) return;
    
    // Find the session objective data to populate tracking fields
    const sessionData = allSessions.find(s => s.id === sessionId);
    const sessionObjective = sessionData?.session_objectives?.find(so => so.objective_id === objectiveId);
    
    setEditingCell({ objectiveId, sessionId, objectiveTitle, sessionDate, preSessionNotes });
    setEditingNotes(currentNotes || '');
    setTrackingData({
      trials_attempted: sessionObjective?.trials_attempted,
      trials_correct: sessionObjective?.trials_correct,
      accuracy_percentage: sessionObjective?.accuracy_percentage,
      independence_level: sessionObjective?.independence_level || ''
    });
    setExpandedTracking(false);
    setModalOpen(true);
  };

  const calculateGridAccuracy = (trialsAttempted?: number, trialsCorrect?: number) => {
    if (trialsAttempted && trialsCorrect !== undefined) {
      const accuracy = (trialsCorrect / trialsAttempted) * 100;
      setTrackingData(prev => ({ ...prev, accuracy_percentage: Math.round(accuracy) }));
    }
  };

  const handleSaveNotes = async () => {
    if (!editingCell) return;
    
    try {
      // Prepare the update payload with essential tracking data
      const updateData = {
        session_notes: editingNotes,
        trials_attempted: trackingData.trials_attempted,
        trials_correct: trackingData.trials_correct,
        accuracy_percentage: trackingData.accuracy_percentage,
        independence_level: trackingData.independence_level || undefined
      };

      await therapySessionsApi.updateSessionObjective(
        editingCell.sessionId,
        editingCell.objectiveId,
        updateData
      );
      
      // Update the local sessions state to reflect the new notes immediately
      setAllSessions(prevSessions => 
        prevSessions.map(sess => {
          if (sess.id !== editingCell.sessionId) return sess;
          
          const existingObjectiveIndex = sess.session_objectives?.findIndex(
            obj => obj.objective_id === editingCell.objectiveId
          ) ?? -1;
          
          if (existingObjectiveIndex >= 0) {
            // Update existing session objective
            return {
              ...sess,
              session_objectives: sess.session_objectives?.map(obj =>
                obj.objective_id === editingCell.objectiveId
                  ? { 
                      ...obj, 
                      session_notes: editingNotes,
                      trials_attempted: trackingData.trials_attempted,
                      trials_correct: trackingData.trials_correct,
                      accuracy_percentage: trackingData.accuracy_percentage,
                      independence_level: trackingData.independence_level
                    }
                  : obj
              ) || []
            };
          } else {
            // Add new session objective
            const newObjective = {
              id: Date.now(), // Temporary ID
              therapy_session_id: editingCell.sessionId,
              objective_id: editingCell.objectiveId,
              goal_id: 0, // Will be set by backend
              planned: false,
              worked_on: true,
              session_notes: editingNotes,
              trials_attempted: trackingData.trials_attempted,
              trials_correct: trackingData.trials_correct,
              accuracy_percentage: trackingData.accuracy_percentage,
              independence_level: trackingData.independence_level
            };
            
            return {
              ...sess,
              session_objectives: [...(sess.session_objectives || []), newObjective]
            };
          }
        })
      );
      
      setEditingCell(null);
      setEditingNotes('');
      setModalOpen(false);
    } catch (error) {
      console.error('Failed to save notes:', error);
      alert('Failed to save notes. Please try again.');
    }
  };

  const handleCancelEdit = () => {
    setEditingCell(null);
    setEditingNotes('');
    setTrackingData({
      trials_attempted: undefined,
      trials_correct: undefined,
      accuracy_percentage: undefined,
      independence_level: ''
    });
    setExpandedTracking(false);
    setModalOpen(false);
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <Typography>Loading school year progress...</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: 0, height: '100%', overflow: 'hidden' }}>
      {showDateNavigator && (
        <Box
          sx={{
            px: 1.5,
            py: 1,
            mb: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            border: 1,
            borderColor: 'grey.300',
            borderRadius: 2,
            backgroundColor: '#f8fffe'
          }}
        >
          <Button
            size="small"
            startIcon={<ChevronLeft />}
            onClick={() => setWindowStartIndex(prev => Math.max(0, prev - SESSIONS_WINDOW_SIZE))}
            disabled={!canShowOlder}
            sx={{ textTransform: 'none' }}
          >
            Previous 12
          </Button>
          <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
            {visibleSessions.length > 0
              ? `${format(new Date(visibleSessions[0].session_date), 'MMM d, yyyy')} - ${format(
                  new Date(visibleSessions[visibleSessions.length - 1].session_date),
                  'MMM d, yyyy'
                )}`
              : 'No sessions in this range'}
          </Typography>
          <Button
            size="small"
            endIcon={<ChevronRight />}
            onClick={() => setWindowStartIndex(prev => Math.min(maxWindowStart, prev + SESSIONS_WINDOW_SIZE))}
            disabled={!canShowNewer}
            sx={{ textTransform: 'none' }}
          >
            Next 12
          </Button>
        </Box>
      )}
      <TableContainer 
        component={Paper} 
        sx={{ 
          overflowX: 'auto',
          overflowY: 'auto',
          border: 1,
          borderColor: 'grey.300',
          borderRadius: 2,
          width: '100%',
          maxWidth: '100%',
          ...(showDateNavigator
            ? {
                flex: 1,
                minHeight: 0
              }
            : {
                height: isMobile ? 'calc(100vh - 200px)' : 'calc(100vh - 250px)'
              }),
          mb: 2,
          WebkitOverflowScrolling: 'touch'
        }}
      >
      <Table stickyHeader size="small">
        {/* Table Header */}
        <TableHead>
          <TableRow>
            <TableCell 
              sx={{ 
                backgroundColor: '#41AAB7',
                color: 'white',
                fontWeight: 600,
                minWidth: isMobile ? 200 : 300,
                position: 'sticky',
                top: 0,
                left: 0,
                zIndex: 11,
                boxShadow: '2px 0 4px rgba(0,0,0,0.1)',
                fontSize: isMobile ? '0.875rem' : '1rem'
              }}
            >
              {isMobile ? 'Goals & Obj.' : 'Goals & Objectives'}
            </TableCell>
            {visibleSessions.map((sess) => {
              const isCurrentSession = sess.id === session.id;
              return (
                <TableCell
                  key={sess.id}
                  align="center"
                  sx={{
                    backgroundColor: isCurrentSession ? '#2D7A85' : '#41AAB7',
                    color: 'white',
                    fontWeight: 600,
                    position: 'sticky',
                    top: 0,
                    zIndex: 10,
                    minWidth: isMobile ? 90 : 120,
                    maxWidth: isMobile ? 100 : 120,
                    fontSize: isMobile ? '0.75rem' : '0.9rem',
                    px: isMobile ? 0.5 : 1
                  }}
                >
                  {isMobile 
                    ? format(new Date(sess.session_date), 'M/d')
                    : format(new Date(sess.session_date), 'M/d/yy')
                  }
                </TableCell>
              );
            })}
          </TableRow>
        </TableHead>

        <TableBody>
          {availableGoals.map((goal) => (
            <React.Fragment key={goal.id}>
              {/* Goal Header Row */}
              <TableRow>
                <TableCell
                  colSpan={visibleSessions.length + 1}
                  sx={{
                    backgroundColor: '#E8F6F8', // Light teal background for goals
                    fontWeight: 600,
                    fontSize: '1rem',
                    py: 2.5,
                    borderBottom: 3,
                    borderColor: '#41AAB7',
                    borderLeft: 4,
                    borderLeftColor: '#41AAB7',
                    maxWidth: '75vw', // 3/4 of viewport width
                    width: '75vw',
                    wordWrap: 'break-word',
                    whiteSpace: 'normal',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <Typography 
                      variant="h6" 
                      component="span" 
                      sx={{ 
                        color: '#2D7A85', // Darker teal for goal titles
                        wordWrap: 'break-word',
                        whiteSpace: 'normal',
                        lineHeight: 1.2,
                        maxWidth: '70vw',
                        fontWeight: 700
                      }}
                    >
                      🎯 Goal {goal.goal_number}: {goal.goal_category_name || 'Goal'}
                    </Typography>
                  </Box>
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      color: '#5A6C7D', // Muted blue-grey for descriptions
                      wordWrap: 'break-word',
                      whiteSpace: 'normal',
                      lineHeight: 1.4,
                      maxWidth: '70vw',
                      fontStyle: 'italic'
                    }}
                  >
                    {goal.goal_description}
                  </Typography>
                </TableCell>
              </TableRow>

              {/* Objective Rows */}
              {goal.objectives?.map((objective, objIndex) => (
                <TableRow 
                  key={objective.id}
                  sx={{
                    '&:hover': { backgroundColor: '#F5F9FA' },
                    backgroundColor: objIndex % 2 === 0 ? '#FAFBFC' : '#F0F4F5', // Alternating light greys
                    borderLeft: 2,
                    borderLeftColor: '#D1E7EA' // Subtle left border for objectives
                  }}
                >
                  <TableCell
                    sx={{
                      fontWeight: 500,
                      borderRight: 2,
                      borderColor: '#E0E7E9',
                      position: 'sticky',
                      left: 0,
                      backgroundColor: 'inherit',
                      zIndex: 5,
                      maxWidth: isMobile ? 200 : 300,
                      wordWrap: 'break-word',
                      whiteSpace: 'normal',
                      boxShadow: '1px 0 2px rgba(0,0,0,0.05)',
                      fontSize: isMobile ? '0.75rem' : '0.875rem'
                    }}
                  >
                    <Box sx={{ pl: isMobile ? 1.5 : 3 }}>
                      <Typography 
                        variant="body2" 
                        sx={{ 
                          fontWeight: 600, 
                          mb: 0.5,
                          wordWrap: 'break-word',
                          whiteSpace: 'normal',
                          color: '#4A5D6B', // Darker grey for objective titles
                          fontSize: isMobile ? '0.75rem' : '0.875rem'
                        }}
                      >
                        📋 Objective {objective.objective_number}
                      </Typography>
                      <Typography 
                        variant="caption" 
                        sx={{
                          wordWrap: 'break-word',
                          whiteSpace: 'normal',
                          lineHeight: 1.3,
                          display: 'block',
                          color: '#6B7D8A', // Medium grey for objective descriptions
                          fontSize: isMobile ? '0.7rem' : '0.75rem'
                        }}
                      >
                        {objective.objective_description}
                      </Typography>
                    </Box>
                  </TableCell>

                  {visibleSessions.map((sess) => {
                    const sessionObjective = sess.session_objectives?.find(
                      so => so.objective_id === objective.id
                    );
                    const notes = sessionObjective?.session_notes || '';
                    const preSessionNotes = sessionObjective?.pre_session_notes || '';
                    const objectiveTitle = `Objective ${objective.objective_number}`;
                    const sessionDate = format(new Date(sess.session_date), 'MMM d, yyyy');
                    const isCurrentSession = sess.id === session.id;
                    
                    return (
                      <TableCell
                        key={sess.id}
                        sx={{
                          p: 0,
                          cursor: disabled ? 'default' : 'pointer',
                          position: 'relative',
                          verticalAlign: 'top',
                          minHeight: isMobile ? 120 : 100,
                          maxWidth: isMobile ? 100 : 120,
                          minWidth: isMobile ? 90 : 120,
                          borderRight: 1,
                          borderColor: '#E0E7E9',
                          ...(isCurrentSession && {
                            backgroundColor: '#E8F4F5'
                          })
                        }}
                        onClick={() => !disabled && handleCellClick(objective.id, sess.id, notes, objectiveTitle, sessionDate, preSessionNotes)}
                      >
                        <Box
                          sx={{
                            minHeight: isMobile ? 100 : 80,
                            height: 'calc(100% - 8px)',
                            display: 'flex',
                            alignItems: notes ? 'flex-start' : 'center',
                            justifyContent: notes ? 'flex-start' : 'center',
                            p: 1,
                            m: isMobile ? '2px' : '4px',
                            borderRadius: 1,
                            backgroundColor: notes ? '#E8F5E8' : 'transparent', // Light green for notes
                            border: notes ? 1 : 0,
                            borderColor: notes ? '#4CAF50' : 'transparent', // Green border for notes
                            '&:hover': disabled ? {} : {
                              backgroundColor: notes ? '#D4F4D4' : '#E8F6F8', // Green hover for notes, teal for empty
                              border: 1,
                              borderColor: notes ? '#4CAF50' : '#41AAB7'
                            },
                            transition: 'all 0.2s ease',
                            boxShadow: notes ? '0 1px 3px rgba(76, 175, 80, 0.2)' : 'none',
                            position: 'relative'
                          }}
                        >
                          {/* Pre-session notes indicator */}
                          {preSessionNotes && (
                            <Box
                              sx={{
                                position: 'absolute',
                                top: 4,
                                right: 4,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                width: 18,
                                height: 18,
                                borderRadius: '50%',
                                backgroundColor: '#41AAB7',
                                color: 'white',
                                fontSize: '10px',
                                zIndex: 1,
                                boxShadow: '0 1px 3px rgba(0,0,0,0.2)'
                              }}
                              title="Pre-session notes available"
                            >
                              <Notes sx={{ fontSize: 10 }} />
                            </Box>
                          )}
                          {notes ? (
                            <Tooltip title={`Full notes: ${notes}`} placement="top">
                              <Typography
                                variant="caption"
                                sx={{
                                  display: '-webkit-box',
                                  WebkitLineClamp: 10,
                                  WebkitBoxOrient: 'vertical',
                                  overflow: 'hidden',
                                  fontSize: isMobile ? '0.7rem' : '0.75rem',
                                  lineHeight: 1.2,
                                  wordBreak: 'break-word',
                                  cursor: 'pointer',
                                  height: '100%',
                                  width: '100%'
                                }}
                              >
                                {notes}
                              </Typography>
                            </Tooltip>
                          ) : (
                            !disabled && (
                              <Typography 
                                variant="caption" 
                                color="text.secondary"
                                sx={{ 
                                  fontSize: isMobile ? '0.65rem' : '0.7rem',
                                  fontWeight: isMobile ? 600 : 'normal',
                                  fontStyle: 'italic',
                                  textAlign: 'center'
                                }}
                              >
                                {isMobile ? '+ Add' : '+ Add notes'}
                              </Typography>
                            )
                          )}
                        </Box>
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </React.Fragment>
          ))}
        </TableBody>
      </Table>
      </TableContainer>

      {/* Notes Editing Modal */}
      <Dialog 
        open={modalOpen} 
        onClose={handleCancelEdit}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: {
            borderRadius: 2,
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12)'
          }
        }}
      >
        <DialogTitle sx={{ 
          pb: 1,
          borderBottom: 1,
          borderColor: 'grey.200',
          backgroundColor: '#F8FFFE'
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Notes color="primary" />
            <Box>
              <Typography variant="h6" component="div">
                Edit Session Notes
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {editingCell?.objectiveTitle} • {editingCell?.sessionDate}
              </Typography>
            </Box>
          </Box>
        </DialogTitle>
        
        <DialogContent sx={{ pt: 3 }}>
          {/* Pre-Session Notes Display (if available) */}
          {editingCell?.preSessionNotes && (
            <Box sx={{ 
              mb: 3, 
              p: 2, 
              bgcolor: '#F8FFFE', 
              borderRadius: 1, 
              border: '1px solid #E0F2F1' 
            }}>
              <Typography variant="subtitle2" sx={{ 
                mb: 1, 
                display: 'flex', 
                alignItems: 'center', 
                gap: 1,
                color: '#2D7A85',
                fontWeight: 600
              }}>
                <Notes fontSize="small" />
                Pre-Session Notes
              </Typography>
              <Typography variant="body2" sx={{ 
                fontStyle: 'italic',
                color: 'text.secondary',
                lineHeight: 1.5,
                p: 1,
                bgcolor: 'white',
                borderRadius: 0.5,
                border: '1px solid #E8F4F5'
              }}>
                {editingCell.preSessionNotes}
              </Typography>
            </Box>
          )}

          <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 600 }}>
            Session Notes
          </Typography>
          <TextField
            autoFocus
            fullWidth
            multiline
            rows={6}
            value={editingNotes}
            onChange={(e) => setEditingNotes(e.target.value)}
            placeholder="Enter your session notes for this objective..."
            variant="outlined"
            sx={{
              '& .MuiOutlinedInput-root': {
                fontSize: '1rem',
                lineHeight: 1.5
              }
            }}
          />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            Record what happened during this objective work, including student progress, challenges, and observations.
          </Typography>

          {/* Expandable Quick Tracking */}
          <Box sx={{ mt: 3 }}>
            <Button
              onClick={() => setExpandedTracking(!expandedTracking)}
              startIcon={expandedTracking ? <ExpandLess /> : <ExpandMore />}
              sx={{ mb: 2 }}
            >
              Quick Tracking
            </Button>
            
            <Collapse in={expandedTracking}>
              <Grid container spacing={2}>
                <Grid item xs={6} sm={3}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Trials Attempted"
                    value={trackingData.trials_attempted ?? ''}
                    onChange={(e) => {
                      const val = e.target.value === '' ? undefined : parseInt(e.target.value);
                      setTrackingData(prev => ({ ...prev, trials_attempted: val }));
                      if (val && trackingData.trials_correct !== undefined) {
                        calculateGridAccuracy(val, trackingData.trials_correct);
                      }
                    }}
                    size="small"
                    inputProps={{ min: 0 }}
                  />
                </Grid>
                <Grid item xs={6} sm={3}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Trials Correct"
                    value={trackingData.trials_correct ?? ''}
                    onChange={(e) => {
                      const val = e.target.value === '' ? undefined : parseInt(e.target.value);
                      setTrackingData(prev => ({ ...prev, trials_correct: val }));
                      if (trackingData.trials_attempted && val !== undefined) {
                        calculateGridAccuracy(trackingData.trials_attempted, val);
                      }
                    }}
                    size="small"
                    inputProps={{ min: 0 }}
                    error={trackingData.trials_correct !== undefined && trackingData.trials_attempted !== undefined && trackingData.trials_correct > trackingData.trials_attempted}
                    helperText={
                      trackingData.trials_correct !== undefined && trackingData.trials_attempted !== undefined && trackingData.trials_correct > trackingData.trials_attempted
                        ? 'Cannot exceed trials attempted'
                        : ''
                    }
                  />
                </Grid>
                <Grid item xs={6} sm={3}>
                  <TextField
                    fullWidth
                    label="Accuracy %"
                    value={trackingData.accuracy_percentage || ''}
                    disabled
                    size="small"
                  />
                </Grid>
                <Grid item xs={6} sm={3}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Independence Level</InputLabel>
                    <Select
                      value={trackingData.independence_level || ''}
                      onChange={(e) => setTrackingData(prev => ({ ...prev, independence_level: e.target.value }))}
                    >
                      <MenuItem value="">Select level</MenuItem>
                      {GRID_INDEPENDENCE_LEVELS.map(level => (
                        <MenuItem key={level} value={level}>
                          {level.replace('_', ' ').toUpperCase()}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
              </Grid>
            </Collapse>
          </Box>
        </DialogContent>
        
        <DialogActions sx={{ 
          px: 3, 
          pb: 3,
          gap: 1,
          backgroundColor: '#FAFBFC'
        }}>
          <Button 
            onClick={handleCancelEdit}
            color="inherit"
            sx={{ px: 3 }}
          >
            Cancel
          </Button>
          <Button 
            onClick={handleSaveNotes}
            variant="contained"
            sx={{ 
              px: 3,
              backgroundColor: '#41AAB7',
              '&:hover': {
                backgroundColor: '#2D7A85'
              }
            }}
          >
            Save Notes
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

// Historical data interfaces
interface HistoricalSessionData {
  session_date: string;
  session_notes?: string;
  trials_attempted?: number;
  trials_correct?: number;
  accuracy_percentage?: number;
  objective_met?: boolean;
  progress_rating?: string;
  independence_level?: string;
}

interface HistoricalData {
  type: 'goal' | 'objective';
  id: number;
  title: string;
  description: string;
  recent_sessions: HistoricalSessionData[];
  overall_progress?: string;
}

export function TherapySessionGoalsAndObjectives({
  session,
  studentGoals,
  disabled = false,
  onUpdateGoalProgress,
  onUpdateObjectiveProgress
}: TherapySessionGoalsAndObjectivesProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [expandedGoal, setExpandedGoal] = useState<number | null>(null);
  const [editingObjective, setEditingObjective] = useState<number | null>(null);
  const [expandedObjectiveDetails, setExpandedObjectiveDetails] = useState<Record<number, boolean>>({});
  const [goalData, setGoalData] = useState<Record<number, GoalSessionData>>({});
  const [objectiveData, setObjectiveData] = useState<Record<number, ObjectiveSessionData>>({});
  const [viewMode, setViewMode] = useState<'detailed' | 'grid'>('grid');
  
  // Initialize with detailed view on mobile for better usability
  useEffect(() => {
    if (isMobile && viewMode === 'grid') {
      setViewMode('detailed');
    }
  }, [isMobile]);
  
  // Historical sidebar state
  const [historicalSidebarOpen, setHistoricalSidebarOpen] = useState(false);
  const [selectedHistoricalData, setSelectedHistoricalData] = useState<HistoricalData | null>(null);
  const [loadingHistorical, setLoadingHistorical] = useState(false);

  // Get session data
  const sessionGoals = session.session_goals || [];
  const sessionObjectives = session.session_objectives || [];
  const plannedGoalIds = sessionGoals.filter(sg => sg.planned).map(sg => sg.goal_id);
  const plannedObjectiveIds = sessionObjectives.filter(so => so.planned).map(so => so.objective_id);
  const availableGoals = studentGoals.filter(goal => goal.goal_status === 'Active');

  const getGoalSessionData = (goalId: number): GoalSessionData => {
    const sessionGoal = sessionGoals.find(sg => sg.goal_id === goalId);
    return goalData[goalId] || {
      planned: sessionGoal?.planned || false,
      worked_on: sessionGoal?.worked_on || false,
      goal_met: sessionGoal?.goal_met,
      difficulty_level: sessionGoal?.difficulty_level,
      student_response: sessionGoal?.student_response,
      time_spent_minutes: sessionGoal?.time_spent_minutes,
      session_notes: sessionGoal?.session_notes,
      goal_progress_summary: sessionGoal?.goal_progress_summary
    };
  };

  const getObjectiveSessionData = (objectiveId: number): ObjectiveSessionData => {
    const sessionObjective = sessionObjectives.find(so => so.objective_id === objectiveId);
    return objectiveData[objectiveId] || {
      planned: sessionObjective?.planned || false,
      worked_on: sessionObjective?.worked_on || false,
      trials_attempted: sessionObjective?.trials_attempted,
      trials_correct: sessionObjective?.trials_correct,
      accuracy_percentage: sessionObjective?.accuracy_percentage,
      independence_level: sessionObjective?.independence_level,
      objective_met: sessionObjective?.objective_met,
      progress_rating: sessionObjective?.progress_rating,
      prompt_level: sessionObjective?.prompt_level,
      time_spent_minutes: sessionObjective?.time_spent_minutes,
      student_engagement: sessionObjective?.student_engagement,
      session_notes: sessionObjective?.session_notes,
      pre_session_notes: sessionObjective?.pre_session_notes
    };
  };

  const updateGoalData = (goalId: number, updates: Partial<GoalSessionData>) => {
    setGoalData(prev => ({
      ...prev,
      [goalId]: { ...getGoalSessionData(goalId), ...updates }
    }));
  };

  const updateObjectiveData = (objectiveId: number, updates: Partial<ObjectiveSessionData>) => {
    setObjectiveData(prev => ({
      ...prev,
      [objectiveId]: { ...getObjectiveSessionData(objectiveId), ...updates }
    }));
  };

  const handleStartWorkingOnObjective = (objective: GoalObjective) => {
    updateObjectiveData(objective.id, { worked_on: true });
    setEditingObjective(objective.id);
    setExpandedGoal(objective.goal_id);
    
    // Also mark the parent goal as being worked on
    updateGoalData(objective.goal_id, { worked_on: true });
  };

  const handleSaveObjective = (objectiveId: number) => {
    const data = getObjectiveSessionData(objectiveId);
    // Only require session_notes, all other fields are optional
    if (!data.session_notes || data.session_notes.trim() === '') {
      alert('Please add objective notes before saving.');
      return;
    }
    onUpdateObjectiveProgress?.(objectiveId, data);
    setEditingObjective(null);
  };

  const toggleObjectiveDetails = (objectiveId: number) => {
    setExpandedObjectiveDetails(prev => ({
      ...prev,
      [objectiveId]: !prev[objectiveId]
    }));
  };

  const handleViewGoalHistory = async (goal: IEPGoal) => {
    setLoadingHistorical(true);
    setHistoricalSidebarOpen(true);
    
    try {
      const data = await therapySessionsApi.getGoalHistory(goal.id);
      
      const sessionData = data.sessions.map((sessionObj: any) => ({
        session_date: sessionObj.therapy_session?.session_date || sessionObj.created_date,
        session_notes: sessionObj.session_notes,
        trials_attempted: sessionObj.trials_attempted,
        trials_correct: sessionObj.trials_correct,
        accuracy_percentage: sessionObj.accuracy_percentage,
        objective_met: sessionObj.objective_met,
        progress_rating: sessionObj.progress_rating,
        independence_level: sessionObj.independence_level
      }));

      setSelectedHistoricalData({
        type: 'goal',
        id: goal.id,
        title: `Goal ${goal.goal_number}: ${goal.goal_category_name || 'Goal'}`,
        description: goal.goal_description || '',
        recent_sessions: sessionData,
        overall_progress: goal.goal_status
      });
    } catch (error) {
      console.error('Failed to fetch goal history:', error);
      setSelectedHistoricalData({
        type: 'goal',
        id: goal.id,
        title: `Goal ${goal.goal_number}: ${goal.goal_category_name || 'Goal'}`,
        description: goal.goal_description || '',
        recent_sessions: [],
        overall_progress: goal.goal_status
      });
    }
    
    setLoadingHistorical(false);
  };

  const handleViewObjectiveHistory = async (objective: GoalObjective, goalNumber?: number) => {
    setLoadingHistorical(true);
    setHistoricalSidebarOpen(true);
    
    try {
      const data = await therapySessionsApi.getObjectiveHistory(objective.id);
      
      const sessionData = data.map((sessionObj: any) => ({
        session_date: sessionObj.therapy_session?.session_date || sessionObj.created_date,
        session_notes: sessionObj.session_notes,
        trials_attempted: sessionObj.trials_attempted,
        trials_correct: sessionObj.trials_correct,
        accuracy_percentage: sessionObj.accuracy_percentage,
        objective_met: sessionObj.objective_met,
        progress_rating: sessionObj.progress_rating,
        independence_level: sessionObj.independence_level
      }));

      setSelectedHistoricalData({
        type: 'objective',
        id: objective.id,
        title: `Objective ${objective.objective_number}${goalNumber ? ` (Goal ${goalNumber})` : ''}`,
        description: objective.objective_description || '',
        recent_sessions: sessionData,
        overall_progress: objective.progress_status
      });
    } catch (error) {
      console.error('Failed to fetch objective history:', error);
      setSelectedHistoricalData({
        type: 'objective',
        id: objective.id,
        title: `Objective ${objective.objective_number}${goalNumber ? ` (Goal ${goalNumber})` : ''}`,
        description: objective.objective_description || '',
        recent_sessions: [],
        overall_progress: objective.progress_status
      });
    }
    
    setLoadingHistorical(false);
  };

  const handleSaveGoal = (goalId: number) => {
    const data = getGoalSessionData(goalId);
    onUpdateGoalProgress?.(goalId, data);
  };

  const calculateAccuracy = (objectiveId: number, trialsAttempted?: number, trialsCorrect?: number) => {
    if (trialsAttempted && trialsCorrect !== undefined) {
      const accuracy = (trialsCorrect / trialsAttempted) * 100;
      updateObjectiveData(objectiveId, { accuracy_percentage: Math.round(accuracy) });
    }
  };

  const getGoalProgress = (goal: IEPGoal) => {
    if (!goal.objectives || goal.objectives.length === 0) return 0;
    
    const completedObjectives = goal.objectives.filter(obj => 
      obj.progress_status === 'Mastered' || obj.progress_status === 'Secure'
    ).length;
    
    return (completedObjectives / goal.objectives.length) * 100;
  };

  const getGoalObjectivesWorkedOn = (goalId: number) => {
    const goal = availableGoals.find(g => g.id === goalId);
    if (!goal?.objectives) return 0;
    
    return goal.objectives.filter(obj => getObjectiveSessionData(obj.id).worked_on).length;
  };

  return (
    <Box sx={{ position: 'relative', display: 'flex', flexDirection: 'column', minHeight: 0, height: '100%', overflow: 'hidden' }}>
      {/* Main Content */}
      <Box sx={{ 
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0,
        transition: 'margin-right 0.3s ease',
        marginRight: (historicalSidebarOpen && !isMobile) ? '400px' : 0 
      }}>
        <Box sx={{ 
          display: 'flex', 
          flexDirection: isMobile ? 'column' : 'row',
          justifyContent: 'space-between', 
          alignItems: isMobile ? 'stretch' : 'center', 
          mb: isMobile ? 2 : 3,
          gap: isMobile ? 1.5 : 0
        }}>
          <Typography 
            variant={isMobile ? "h6" : "h5"} 
            sx={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: 1,
              fontSize: isMobile ? '1.25rem' : undefined
            }}
          >
            <Assignment color="primary" sx={{ fontSize: isMobile ? 20 : 24 }} />
            {isMobile ? "IEP Goals" : "IEP Goals & Objectives"}
          </Typography>
          
          <Box sx={{ 
            display: 'flex', 
            gap: 1, 
            alignItems: 'center',
            flexWrap: 'wrap',
            justifyContent: isMobile ? 'center' : 'flex-end'
          }}>
            <Chip 
              label={isMobile ? `${plannedGoalIds.length} Goals` : `${plannedGoalIds.length} Goals Planned`}
              color="primary"
              variant="outlined"
              size="small"
              sx={{ fontSize: isMobile ? '0.7rem' : undefined }}
            />
            <Chip 
              label={isMobile ? `${plannedObjectiveIds.length} Obj.` : `${plannedObjectiveIds.length} Objectives Planned`}
              color="secondary"
              variant="outlined"
              size="small"
              sx={{ fontSize: isMobile ? '0.7rem' : undefined }}
            />
            {isMobile ? (
              <>
                <ToggleButtonGroup
                  value={viewMode}
                  exclusive
                  onChange={(_, newViewMode) => newViewMode && setViewMode(newViewMode)}
                  size="small"
                  sx={{ width: '100%', justifyContent: 'center' }}
                >
                  <ToggleButton value="detailed" aria-label="list view" sx={{ flex: 1 }}>
                    <ViewList fontSize="small" sx={{ mr: 0.5 }} />
                    <Typography variant="caption">List</Typography>
                  </ToggleButton>
                  <ToggleButton value="grid" aria-label="grid view" sx={{ flex: 1 }}>
                    <GridView fontSize="small" sx={{ mr: 0.5 }} />
                    <Typography variant="caption">Grid</Typography>
                  </ToggleButton>
                </ToggleButtonGroup>
              </>
            ) : (
              <>
                <ToggleButtonGroup
                  value={viewMode}
                  exclusive
                  onChange={(_, newViewMode) => newViewMode && setViewMode(newViewMode)}
                  size="small"
                  sx={{ ml: 1 }}
                >
                  <ToggleButton value="detailed" aria-label="detailed view">
                    <ViewList fontSize="small" />
                  </ToggleButton>
                  <ToggleButton value="grid" aria-label="grid view">
                    <GridView fontSize="small" />
                  </ToggleButton>
                </ToggleButtonGroup>
                <IconButton
                  onClick={() => setHistoricalSidebarOpen(!historicalSidebarOpen)}
                  color={historicalSidebarOpen ? "primary" : "default"}
                  size="small"
                  sx={{ ml: 1 }}
                >
                  <History />
                </IconButton>
              </>
            )}
          </Box>
        </Box>

      {availableGoals.length === 0 ? (
        <Alert severity="info" sx={{ fontSize: isMobile ? '0.85rem' : undefined }}>
          This student has no active IEP goals. Goals and objectives can be added in the IEP management section.
        </Alert>
      ) : viewMode === 'detailed' ? (
        <Grid container spacing={isMobile ? 1 : 2}>
          {availableGoals.map((goal) => {
            const goalSessionData = getGoalSessionData(goal.id);
            const isGoalPlanned = plannedGoalIds.includes(goal.id);
            const isGoalWorkedOn = goalSessionData.worked_on;
            const isExpanded = expandedGoal === goal.id;
            const progress = getGoalProgress(goal);
            const objectivesWorkedOn = getGoalObjectivesWorkedOn(goal.id);

            return (
              <Grid item xs={12} key={goal.id}>
                <Card 
                  sx={{ 
                    border: isGoalPlanned ? '2px solid #40A8B6' : '1px solid #e0e0e0',
                    bgcolor: isGoalWorkedOn ? '#f8fffe' : 'white'
                  }}
                >
                  <Accordion 
                    expanded={isExpanded}
                    onChange={() => setExpandedGoal(isExpanded ? null : goal.id)}
                  >
                    <AccordionSummary
                      expandIcon={<ExpandMore />}
                      sx={{
                        bgcolor: isGoalPlanned ? '#f0f9fa' : 'transparent',
                        '&:hover': { bgcolor: '#f5f5f5' },
                        py: isMobile ? 1 : undefined
                      }}
                    >
                      <Box sx={{ 
                        display: 'flex', 
                        alignItems: isMobile ? 'flex-start' : 'center', 
                        gap: isMobile ? 1 : 2, 
                        width: '100%',
                        flexDirection: isMobile ? 'column' : 'row'
                      }}>
                        <Box sx={{ flex: 1, width: '100%' }}>
                          <Typography 
                            variant={isMobile ? "subtitle1" : "h6"} 
                            sx={{ 
                              fontWeight: 600, 
                              mb: 1,
                              fontSize: isMobile ? '1.1rem' : undefined
                            }}
                          >
                            Goal {goal.goal_number}: {goal.goal_category_name || 'Goal'}
                          </Typography>
                          <Typography 
                            variant="body2" 
                            color="text.secondary" 
                            sx={{ 
                              mb: isMobile ? 1.5 : 2,
                              fontSize: isMobile ? '0.85rem' : undefined
                            }}
                          >
                            {goal.goal_description}
                          </Typography>
                          
                          <Box sx={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            gap: isMobile ? 2 : 3, 
                            flexWrap: 'wrap',
                            flexDirection: isMobile ? 'column' : 'row'
                          }}>
                            {progress > 0 && (
                              <Box sx={{ 
                                display: 'flex', 
                                alignItems: 'center', 
                                gap: 1, 
                                minWidth: isMobile ? '100%' : 200,
                                width: isMobile ? '100%' : 'auto'
                              }}>
                                <Typography 
                                  variant="caption"
                                  sx={{ fontSize: isMobile ? '0.7rem' : undefined }}
                                >
                                  Overall Progress:
                                </Typography>
                                <LinearProgress
                                  variant="determinate"
                                  value={progress}
                                  sx={{
                                    height: isMobile ? 4 : 6,
                                    borderRadius: 3,
                                    flex: 1,
                                    bgcolor: '#e0e0e0',
                                    '& .MuiLinearProgress-bar': {
                                      bgcolor: progress >= 80 ? '#4caf50' : progress >= 50 ? '#ff9800' : '#f44336'
                                    }
                                  }}
                                />
                                <Typography 
                                  variant="caption"
                                  sx={{ fontSize: isMobile ? '0.7rem' : undefined }}
                                >
                                  {Math.round(progress)}%
                                </Typography>
                              </Box>
                            )}
                            
                            <Box sx={{ 
                              display: 'flex', 
                              gap: isMobile ? 1 : 2,
                              flexWrap: 'wrap',
                              justifyContent: isMobile ? 'space-between' : 'flex-start',
                              width: isMobile ? '100%' : 'auto'
                            }}>
                              <Typography 
                                variant="caption" 
                                color="text.secondary"
                                sx={{ fontSize: isMobile ? '0.7rem' : undefined }}
                              >
                                {goal.objectives?.length || 0} objectives
                              </Typography>
                              
                              {objectivesWorkedOn > 0 && (
                                <Typography 
                                  variant="caption" 
                                  color="success.main"
                                  sx={{ fontSize: isMobile ? '0.7rem' : undefined }}
                                >
                                  {objectivesWorkedOn} worked on this session
                                </Typography>
                              )}
                            </Box>
                          </Box>
                        </Box>

                        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexDirection: 'column' }}>
                          <Box sx={{ display: 'flex', gap: 1 }}>
                            {isGoalPlanned && (
                              <Chip label="Planned" color="primary" size="small" variant="filled" />
                            )}
                            {isGoalWorkedOn && (
                              <Chip label="Worked On" color="success" size="small" variant="filled" />
                            )}
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleViewGoalHistory(goal);
                              }}
                              sx={{ 
                                color: '#666',
                                '&:hover': { color: '#40A8B6' }
                              }}
                            >
                              <History fontSize="small" />
                            </IconButton>
                          </Box>
                          {goalSessionData.goal_met && (
                            <Chip label="Goal Met" color="success" size="small" variant="outlined" />
                          )}
                        </Box>
                      </Box>
                    </AccordionSummary>

                    <AccordionDetails>
                      <Box sx={{ p: 2 }}>
                        {/* Goal-level tracking hidden for now */}

                        {/* Objectives Section */}
                        <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                          <GpsFixed color="secondary" />
                          Objectives ({goal.objectives?.length || 0})
                        </Typography>
                        
                        {/* Planned objectives indicator */}
                        {goal.objectives && goal.objectives.some(obj => plannedObjectiveIds.includes(obj.id)) && (
                          <Alert severity="info" sx={{ mb: 2 }}>
                            ⭐ {goal.objectives.filter(obj => plannedObjectiveIds.includes(obj.id)).length} objective(s) 
                            were planned for today's session
                          </Alert>
                        )}

                        {!goal.objectives || goal.objectives.length === 0 ? (
                          <Alert severity="info">
                            This goal has no objectives defined yet.
                          </Alert>
                        ) : (
                          <Grid container spacing={2}>
                            {goal.objectives
                              .sort((a, b) => {
                                // Sort planned objectives first
                                const aPlanned = plannedObjectiveIds.includes(a.id);
                                const bPlanned = plannedObjectiveIds.includes(b.id);
                                if (aPlanned && !bPlanned) return -1;
                                if (!aPlanned && bPlanned) return 1;
                                return a.objective_number - b.objective_number;
                              })
                              .map((objective) => {
                              const objData = getObjectiveSessionData(objective.id);
                              const isObjPlanned = plannedObjectiveIds.includes(objective.id);
                              const isObjWorkedOn = objData.worked_on;
                              const isEditing = editingObjective === objective.id;

                              return (
                                <Grid item xs={12} key={objective.id}>
                                  <Paper 
                                    sx={{ 
                                      p: 2,
                                      border: isObjPlanned ? '2px solid #2196f3' : '1px solid #e0e0e0',
                                      bgcolor: isObjWorkedOn ? '#fafafa' : (isObjPlanned ? '#f0f8ff' : 'white'),
                                      position: 'relative',
                                      ...(isObjPlanned && {
                                        boxShadow: '0 2px 8px rgba(33, 150, 243, 0.15)'
                                      })
                                    }}
                                  >
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                                      <Box sx={{ flex: 1 }}>
                                        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                                          Objective {objective.objective_number}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                          {objective.objective_description}
                                        </Typography>
                                      </Box>
                                      
                                      <Box sx={{ display: 'flex', gap: 1, ml: 2, alignItems: 'flex-start' }}>
                                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                                          {isObjPlanned && (
                                            <Chip 
                                              label="⭐ Planned for Today" 
                                              color="primary" 
                                              size="small" 
                                              variant="filled"
                                              sx={{ 
                                                bgcolor: '#2196f3',
                                                color: 'white',
                                                fontWeight: 600
                                              }}
                                            />
                                          )}
                                          {isObjWorkedOn && (
                                            <Chip label="Worked On" color="success" size="small" variant="filled" />
                                          )}
                                          {objData.objective_met && (
                                            <Chip label="Met" color="success" size="small" variant="outlined" />
                                          )}
                                        </Box>
                                        <IconButton
                                          size="small"
                                          onClick={() => handleViewObjectiveHistory(objective, parseInt(goal.goal_number))}
                                          sx={{ 
                                            color: '#666',
                                            '&:hover': { color: '#40A8B6' }
                                          }}
                                        >
                                          <History fontSize="small" />
                                        </IconButton>
                                      </Box>
                                    </Box>

                                    {/* Pre-Session Notes - Always show if they exist, or if objective is planned */}
                                    {(objData.pre_session_notes || isObjPlanned) && (
                                      <Box sx={{ mb: 2, p: 2, bgcolor: '#f8f9fa', borderRadius: 1, border: '1px solid #e9ecef' }}>
                                        <Typography variant="subtitle2" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                                          <Notes fontSize="small" color="primary" />
                                          Pre-Session Notes
                                        </Typography>
                                        {objData.pre_session_notes ? (
                                          <Box>
                                            <Typography variant="body2" sx={{ mb: 2, fontStyle: 'italic', color: 'text.secondary' }}>
                                              {objData.pre_session_notes}
                                            </Typography>
                                            {!disabled && (
                                              <TextField
                                                fullWidth
                                                multiline
                                                rows={2}
                                                size="small"
                                                label="Edit Pre-Session Notes"
                                                value={objData.pre_session_notes || ''}
                                                onChange={(e) => updateObjectiveData(objective.id, { pre_session_notes: e.target.value })}
                                                placeholder="Add preparation notes for this objective..."
                                                sx={{ 
                                                  '& .MuiOutlinedInput-root': {
                                                    bgcolor: 'white'
                                                  }
                                                }}
                                              />
                                            )}
                                          </Box>
                                        ) : (
                                          !disabled && (
                                            <TextField
                                              fullWidth
                                              multiline
                                              rows={2}
                                              size="small"
                                              label="Add Pre-Session Notes"
                                              value={objData.pre_session_notes || ''}
                                              onChange={(e) => updateObjectiveData(objective.id, { pre_session_notes: e.target.value })}
                                              placeholder="Add preparation notes for this objective..."
                                              sx={{ 
                                                '& .MuiOutlinedInput-root': {
                                                  bgcolor: 'white'
                                                }
                                              }}
                                            />
                                          )
                                        )}
                                      </Box>
                                    )}

                                    {!isObjWorkedOn && !disabled && (
                                      <Box sx={{ textAlign: 'center', py: 1 }}>
                                        <Button
                                          variant="contained"
                                          size="small"
                                          startIcon={<PlayArrow />}
                                          onClick={() => handleStartWorkingOnObjective(objective)}
                                          sx={{ bgcolor: '#9c27b0', '&:hover': { bgcolor: '#7b1fa2' } }}
                                        >
                                          Work on This Objective
                                        </Button>
                                      </Box>
                                    )}

                                    {(isObjWorkedOn || isEditing) && (
                                      <Box>
                                        {/* Primary Field: Objective Notes */}
                                        <Box sx={{ mb: 2 }}>
                                          <TextField
                                            fullWidth
                                            multiline
                                            rows={3}
                                            label="Objective Notes *"
                                            value={objData.session_notes || ''}
                                            onChange={(e) => updateObjectiveData(objective.id, { session_notes: e.target.value })}
                                            disabled={disabled}
                                            placeholder="Add notes about work on this objective..."
                                            required
                                            error={!objData.session_notes || objData.session_notes.trim() === ''}
                                            helperText={(!objData.session_notes || objData.session_notes.trim() === '') ? 'Notes are required' : ''}
                                          />
                                        </Box>

                                        {/* Optional Detailed Tracking */}
                                        <Box sx={{ mb: 2 }}>
                                          <Button
                                            variant="text"
                                            size="small"
                                            onClick={() => toggleObjectiveDetails(objective.id)}
                                            startIcon={expandedObjectiveDetails[objective.id] ? <ExpandLess /> : <ExpandMore />}
                                            sx={{ textTransform: 'none' }}
                                          >
                                            {expandedObjectiveDetails[objective.id] ? 'Hide' : 'Show'} Additional Tracking Data
                                          </Button>
                                        </Box>

                                        {expandedObjectiveDetails[objective.id] && (
                                          <Grid container spacing={2} sx={{ mb: 2 }}>
                                            <Grid item xs={6} sm={3}>
                                              <TextField
                                                fullWidth
                                                type="number"
                                                label="Trials Attempted"
                                                value={objData.trials_attempted ?? ''}
                                                onChange={(e) => {
                                                  const val = e.target.value === '' ? undefined : parseInt(e.target.value);
                                                  updateObjectiveData(objective.id, { trials_attempted: val });
                                                  // Calculate accuracy with current values
                                                  if (val && objData.trials_correct !== undefined) {
                                                    calculateAccuracy(objective.id, val, objData.trials_correct);
                                                  }
                                                }}
                                                disabled={disabled}
                                                size="small"
                                                inputProps={{ min: 0 }}
                                              />
                                            </Grid>

                                            <Grid item xs={6} sm={3}>
                                              <TextField
                                                fullWidth
                                                type="number"
                                                label="Trials Correct"
                                                value={objData.trials_correct ?? ''}
                                                onChange={(e) => {
                                                  const val = e.target.value === '' ? undefined : parseInt(e.target.value);
                                                  updateObjectiveData(objective.id, { trials_correct: val });
                                                  // Calculate accuracy with current values
                                                  if (objData.trials_attempted && val !== undefined) {
                                                    calculateAccuracy(objective.id, objData.trials_attempted, val);
                                                  }
                                                }}
                                                disabled={disabled}
                                                size="small"
                                                inputProps={{ min: 0 }}
                                                error={objData.trials_correct !== undefined && objData.trials_attempted !== undefined && objData.trials_correct > objData.trials_attempted}
                                                helperText={
                                                  objData.trials_correct !== undefined && objData.trials_attempted !== undefined && objData.trials_correct > objData.trials_attempted
                                                    ? 'Cannot exceed trials attempted'
                                                    : ''
                                                }
                                              />
                                            </Grid>

                                            <Grid item xs={6} sm={3}>
                                              <TextField
                                                fullWidth
                                                label="Accuracy %"
                                                value={objData.accuracy_percentage || ''}
                                                disabled
                                                size="small"
                                              />
                                            </Grid>

                                            <Grid item xs={6} sm={3}>
                                              <FormControl fullWidth size="small">
                                                <InputLabel>Objective Met</InputLabel>
                                                <Select
                                                  value={objData.objective_met === true ? 'met' : objData.objective_met === false ? 'not_met' : ''}
                                                  onChange={(e) => updateObjectiveData(objective.id, {
                                                    objective_met: e.target.value === 'met' ? true : e.target.value === 'not_met' ? false : undefined
                                                  })}
                                                  disabled={disabled}
                                                >
                                                  <MenuItem value="">Not assessed</MenuItem>
                                                  <MenuItem value="met">Met</MenuItem>
                                                  <MenuItem value="not_met">Not Met</MenuItem>
                                                </Select>
                                              </FormControl>
                                            </Grid>

                                            <Grid item xs={12} sm={6}>
                                              <FormControl fullWidth size="small">
                                                <InputLabel>Progress Rating</InputLabel>
                                                <Select
                                                  value={objData.progress_rating || ''}
                                                  onChange={(e) => updateObjectiveData(objective.id, { progress_rating: e.target.value })}
                                                  disabled={disabled}
                                                >
                                                  {PROGRESS_RATINGS.map(rating => (
                                                    <MenuItem key={rating} value={rating}>
                                                      {rating.replace('_', ' ').toUpperCase()}
                                                    </MenuItem>
                                                  ))}
                                                </Select>
                                              </FormControl>
                                            </Grid>

                                            <Grid item xs={12} sm={6}>
                                              <FormControl fullWidth size="small">
                                                <InputLabel>Independence Level</InputLabel>
                                                <Select
                                                  value={objData.independence_level || ''}
                                                  onChange={(e) => updateObjectiveData(objective.id, { independence_level: e.target.value })}
                                                  disabled={disabled}
                                                >
                                                  {INDEPENDENCE_LEVELS.map(level => (
                                                    <MenuItem key={level} value={level}>
                                                      {level.replace('_', ' ').toUpperCase()}
                                                    </MenuItem>
                                                  ))}
                                                </Select>
                                              </FormControl>
                                            </Grid>
                                          </Grid>
                                        )}

                                        {/* Save/Cancel Buttons */}
                                        {!disabled && (
                                          <Box sx={{ display: 'flex', gap: 1 }}>
                                            <Button
                                              variant="contained"
                                              size="small"
                                              startIcon={<Save />}
                                              onClick={() => handleSaveObjective(objective.id)}
                                              disabled={!objData.session_notes || objData.session_notes.trim() === ''}
                                            >
                                              Save Objective
                                            </Button>
                                            {isEditing && (
                                              <Button
                                                size="small"
                                                startIcon={<Cancel />}
                                                onClick={() => setEditingObjective(null)}
                                              >
                                                Cancel
                                              </Button>
                                            )}
                                          </Box>
                                        )}
                                      </Box>
                                    )}
                                  </Paper>
                                </Grid>
                              );
                            })}
                          </Grid>
                        )}
                      </Box>
                    </AccordionDetails>
                  </Accordion>
                </Card>
              </Grid>
            );
          })}
        </Grid>
      ) : (
        <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
          <GridProgressView 
            studentId={session.student_id}
            availableGoals={availableGoals}
            session={session}
            disabled={disabled}
            showDateNavigator
            onUpdateObjectiveProgress={onUpdateObjectiveProgress}
          />
        </Box>
      )}
      </Box>
      
      {/* Historical Data Sidebar */}
      <Box
        sx={{
          position: 'fixed',
          top: '180px', // Position below tabs and header
          right: historicalSidebarOpen ? 0 : -400,
          width: 400,
          height: 'calc(100vh - 180px)',
          backgroundColor: '#f8fffe',
          borderLeft: '1px solid #e8f4f5',
          transition: 'right 0.3s ease',
          overflowY: 'auto',
          zIndex: 1200,
          boxShadow: historicalSidebarOpen ? '-2px 0 8px rgba(0,0,0,0.1)' : 'none'
        }}
      >
        <Box sx={{ p: 2 }}>
          {/* Sidebar Header */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1, color: '#40A8B6' }}>
              <History />
              Historical Data
            </Typography>
            <IconButton size="small" onClick={() => setHistoricalSidebarOpen(false)}>
              <Close />
            </IconButton>
          </Box>

          {selectedHistoricalData && (
            <Box>
              {/* Item Details */}
              <Card sx={{ mb: 2, border: '1px solid #e8f4f5' }}>
                <CardContent>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600, color: '#40A8B6', mb: 1 }}>
                    {selectedHistoricalData.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    {selectedHistoricalData.description}
                  </Typography>
                  {selectedHistoricalData.overall_progress && (
                    <Chip 
                      label={`Status: ${selectedHistoricalData.overall_progress}`}
                      size="small"
                      color="primary"
                      variant="outlined"
                    />
                  )}
                </CardContent>
              </Card>

              {/* Recent Sessions */}
              <Typography variant="subtitle2" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                <CalendarToday fontSize="small" />
                Recent Sessions
              </Typography>

              {loadingHistorical ? (
                <Box>
                  {[1, 2, 3].map(i => (
                    <Skeleton key={i} variant="rectangular" height={80} sx={{ mb: 1, borderRadius: 1 }} />
                  ))}
                </Box>
              ) : selectedHistoricalData.recent_sessions.length > 0 ? (
                <List sx={{ p: 0 }}>
                  {selectedHistoricalData.recent_sessions.map((sessionData, index) => (
                    <Paper key={index} sx={{ mb: 1, p: 2 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {format(new Date(sessionData.session_date), 'MMM d, yyyy')}
                        </Typography>
                        {sessionData.objective_met !== undefined && (
                          <Chip 
                            label={sessionData.objective_met ? "Met" : "Not Met"}
                            size="small"
                            color={sessionData.objective_met ? "success" : "default"}
                            variant="outlined"
                          />
                        )}
                      </Box>
                      
                      {sessionData.trials_attempted && (
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                          {sessionData.trials_correct}/{sessionData.trials_attempted} trials 
                          {sessionData.accuracy_percentage && ` (${sessionData.accuracy_percentage}%)`}
                        </Typography>
                      )}
                      
                      {sessionData.progress_rating && (
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                          Progress: {sessionData.progress_rating.replace('_', ' ')}
                        </Typography>
                      )}
                      
                      {sessionData.session_notes && (
                        <Box sx={{ mt: 1, p: 1, bgcolor: '#f5f5f5', borderRadius: 1 }}>
                          <Typography variant="caption" sx={{ fontStyle: 'italic' }}>
                            <Notes fontSize="small" sx={{ mr: 0.5, verticalAlign: 'middle' }} />
                            {sessionData.session_notes}
                          </Typography>
                        </Box>
                      )}
                    </Paper>
                  ))}
                </List>
              ) : (
                <Alert severity="info" sx={{ mt: 1 }}>
                  No recent session data available for this {selectedHistoricalData.type}.
                </Alert>
              )}

              {/* Progress Trend */}
              <Typography variant="subtitle2" sx={{ mt: 3, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                <TrendingUp fontSize="small" />
                Progress Trend
              </Typography>
              
              <Alert severity="info" sx={{ mt: 1 }}>
                Progress visualization coming soon - this will show trends over time.
              </Alert>
            </Box>
          )}

          {!selectedHistoricalData && (
            <Alert severity="info">
              Click the <History fontSize="small" sx={{ mx: 0.5, verticalAlign: 'middle' }} /> icon next to any goal or objective to view its historical data.
            </Alert>
          )}
        </Box>
      </Box>
    </Box>
  );
}
