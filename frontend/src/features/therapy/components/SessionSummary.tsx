import React, { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Grid,
  Card,
  CardContent,
  Alert,
  CircularProgress,
  Divider,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Paper,
  useMediaQuery,
  useTheme
} from '@mui/material';
import { 
  Save, 
  Cancel, 
  CheckCircle, 
  Assignment,
  Person,
  CalendarToday,
  Notes,
  TrendingUp,
  Stop,
  Timer,
  GpsFixed,
  Psychology
} from '@mui/icons-material';
import { format } from 'date-fns';
import type { TherapySession } from '../../../lib/api/therapySessions';
import type { IEPGoal } from '../../../lib/api/types/goals';

interface SessionSummaryProps {
  session: TherapySession;
  studentGoals: IEPGoal[];
  onComplete: (sessionData: any) => void;
  loading?: boolean;
}

const SESSION_QUALITY_OPTIONS = ['excellent', 'good', 'fair', 'poor'];
const ENGAGEMENT_LEVELS = ['high', 'medium', 'low', 'variable'];

export function SessionSummary({ 
  session,
  studentGoals,
  onComplete,
  loading = false
}: SessionSummaryProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [completionData, setCompletionData] = useState({
    session_notes: session.session_notes || '',
    therapist_observations: session.therapist_observations || '',
    student_engagement: session.student_engagement || '',
    materials_used: session.materials_used || '',
    goals_addressed: true, // Default to true if any goals were worked on
    session_quality: session.session_quality || '',
    follow_up_needed: session.follow_up_needed || false,
    follow_up_notes: session.follow_up_notes || ''
  });

  const handleComplete = () => {
    onComplete(completionData);
  };

  // Get worked on goals and objectives
  const workedOnGoals = session.session_goals?.filter(sg => sg.worked_on) || [];
  const workedOnObjectives = session.session_objectives?.filter(so => so.worked_on) || [];
  
  // Calculate session duration
  const sessionDuration = (session.actual_start_time || session.start_time) ? 
    Math.round((new Date().getTime() - new Date((session.actual_start_time || session.start_time) as string).getTime()) / (1000 * 60)) : 
    session.planned_duration_minutes || 0;

  const getGoalDetails = (goalId: number) => {
    return studentGoals.find(g => g.id === goalId);
  };

  const getObjectiveDetails = (objectiveId: number) => {
    for (const goal of studentGoals) {
      const objective = goal.objectives?.find(obj => obj.id === objectiveId);
      if (objective) {
        return { goal, objective };
      }
    }
    return null;
  };

  return (
    <Box sx={{ p: isMobile ? 2 : 3 }}>
      {/* Session Header */}
      <Card sx={{ 
        mb: isMobile ? 2 : 3, 
        bgcolor: '#f8fffe', 
        border: '2px solid #40A8B6' 
      }}>
        <CardContent sx={{ p: isMobile ? 2 : 3 }}>
          <Typography 
            variant={isMobile ? "h5" : "h4"} 
            sx={{ 
              color: '#40A8B6', 
              fontWeight: 600, 
              mb: isMobile ? 1.5 : 2, 
              display: 'flex', 
              alignItems: 'center', 
              gap: isMobile ? 1 : 2,
              fontSize: isMobile ? '1.5rem' : undefined
            }}
          >
            <Stop sx={{ fontSize: isMobile ? 24 : 32 }} />
            {isMobile ? "Complete Session" : "Complete Therapy Session"}
          </Typography>
          
          <Grid container spacing={isMobile ? 2 : 3}>
            <Grid item xs={12} sm={6}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Person color="primary" sx={{ fontSize: isMobile ? 18 : 20 }} />
                <Typography 
                  variant="subtitle1" 
                  color="text.secondary"
                  sx={{ fontSize: isMobile ? '0.9rem' : undefined }}
                >
                  Student:
                </Typography>
              </Box>
              <Typography 
                variant={isMobile ? "subtitle1" : "h6"} 
                sx={{ 
                  fontWeight: 500,
                  fontSize: isMobile ? '1.1rem' : undefined
                }}
              >
                {session.student_name}
              </Typography>
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <CalendarToday color="primary" sx={{ fontSize: isMobile ? 18 : 20 }} />
                <Typography 
                  variant="subtitle1" 
                  color="text.secondary"
                  sx={{ fontSize: isMobile ? '0.9rem' : undefined }}
                >
                  Session Date:
                </Typography>
              </Box>
              <Typography 
                variant={isMobile ? "subtitle1" : "h6"} 
                sx={{ 
                  fontWeight: 500,
                  fontSize: isMobile ? '1.1rem' : undefined
                }}
              >
                {format(new Date(session.session_date), isMobile ? 'MMM d, yyyy' : 'EEEE, MMMM d, yyyy')}
              </Typography>
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Timer color="primary" />
                <Typography variant="subtitle1" color="text.secondary">Duration:</Typography>
              </Box>
              <Typography variant="h6" sx={{ fontWeight: 500 }}>
                {sessionDuration} minutes
              </Typography>
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Assignment color="primary" />
                <Typography variant="subtitle1" color="text.secondary">Goals Worked On:</Typography>
              </Box>
              <Typography variant="h6" sx={{ fontWeight: 500 }}>
                {workedOnGoals.length} of {session.session_goals?.length || 0} planned
              </Typography>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Progress Summary */}
      <Typography 
        variant={isMobile ? "h6" : "h5"} 
        sx={{ 
          mb: isMobile ? 2 : 3, 
          color: '#40A8B6', 
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          gap: isMobile ? 1 : 2,
          fontSize: isMobile ? '1.25rem' : undefined
        }}
      >
        <TrendingUp sx={{ fontSize: isMobile ? 20 : 24 }} />
        {isMobile ? "Progress Summary" : "Session Progress Summary"}
      </Typography>

      {/* Goals Summary */}
      {workedOnGoals.length > 0 && (
        <Card sx={{ mb: isMobile ? 2 : 3 }}>
          <CardContent sx={{ p: isMobile ? 2 : 3 }}>
            <Typography 
              variant={isMobile ? "subtitle1" : "h6"} 
              sx={{ 
                mb: isMobile ? 1.5 : 2, 
                display: 'flex', 
                alignItems: 'center', 
                gap: 1,
                fontSize: isMobile ? '1.1rem' : undefined
              }}
            >
              <Assignment color="primary" sx={{ fontSize: isMobile ? 18 : 20 }} />
              Goals Worked On ({workedOnGoals.length})
            </Typography>
            
            <List>
              {workedOnGoals.map((sessionGoal) => {
                const goal = getGoalDetails(sessionGoal.goal_id);
                if (!goal) return null;

                return (
                  <ListItem 
                    key={sessionGoal.goal_id}
                    sx={{ 
                      bgcolor: 'white',
                      borderRadius: 2,
                      border: '1px solid #e8f4f5',
                      mb: 2,
                      boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
                    }}
                  >
                    <ListItemIcon>
                      <CheckCircle sx={{ color: sessionGoal.goal_met ? '#4caf50' : '#40A8B6' }} />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Box>
                          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
                            Goal {goal.goal_number}: {goal.goal_category?.name}
                          </Typography>
                          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                            {goal.goal_description}
                          </Typography>
                          
                          <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                            {sessionGoal.goal_met && (
                              <Chip 
                                label="Goal Met" 
                                color="success"
                                size="small"
                                variant="filled"
                              />
                            )}
                            {sessionGoal.difficulty_level && (
                              <Chip 
                                label={`Difficulty: ${sessionGoal.difficulty_level.replace('_', ' ')}`}
                                size="small"
                                variant="outlined"
                              />
                            )}
                            {sessionGoal.time_spent_minutes && (
                              <Chip 
                                label={`${sessionGoal.time_spent_minutes} min`}
                                size="small"
                                variant="outlined"
                              />
                            )}
                          </Box>
                          
                          {sessionGoal.goal_progress_summary && (
                            <Paper sx={{ p: 2, bgcolor: '#f0f9fa', border: '1px solid #d0e8ec' }}>
                              <Typography variant="body2">
                                <strong>Progress Summary:</strong> {sessionGoal.goal_progress_summary}
                              </Typography>
                            </Paper>
                          )}
                        </Box>
                      }
                    />
                  </ListItem>
                );
              })}
            </List>
          </CardContent>
        </Card>
      )}

      {/* Objectives Summary */}
      {workedOnObjectives.length > 0 && (
        <Card sx={{ mb: isMobile ? 2 : 3 }}>
          <CardContent sx={{ p: isMobile ? 2 : 3 }}>
            <Typography 
              variant={isMobile ? "subtitle1" : "h6"} 
              sx={{ 
                mb: isMobile ? 1.5 : 2, 
                display: 'flex', 
                alignItems: 'center', 
                gap: 1,
                fontSize: isMobile ? '1.1rem' : undefined
              }}
            >
              <GpsFixed color="secondary" sx={{ fontSize: isMobile ? 18 : 20 }} />
              Objectives Worked On ({workedOnObjectives.length})
            </Typography>
            
            <List>
              {workedOnObjectives.map((sessionObjective) => {
                const details = getObjectiveDetails(sessionObjective.objective_id);
                if (!details) return null;

                return (
                  <ListItem 
                    key={sessionObjective.objective_id}
                    sx={{ 
                      bgcolor: 'white',
                      borderRadius: 2,
                      border: '1px solid #f3e5f5',
                      mb: 2,
                      boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
                    }}
                  >
                    <ListItemIcon>
                      <GpsFixed sx={{ color: sessionObjective.objective_met ? '#4caf50' : '#9c27b0' }} />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Box>
                          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
                            Goal {details.goal.goal_number} - Objective {details.objective.objective_number}
                          </Typography>
                          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                            {details.objective.objective_description}
                          </Typography>
                          
                          <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                            {sessionObjective.objective_met && (
                              <Chip 
                                label="Objective Met" 
                                color="success"
                                size="small"
                                variant="filled"
                              />
                            )}
                            {sessionObjective.accuracy_percentage !== undefined && (
                              <Chip 
                                label={`${sessionObjective.accuracy_percentage}% accuracy`}
                                color="primary"
                                size="small"
                                variant="outlined"
                              />
                            )}
                            {sessionObjective.trials_attempted && (
                              <Chip 
                                label={`${sessionObjective.trials_correct || 0}/${sessionObjective.trials_attempted} trials`}
                                size="small"
                                variant="outlined"
                              />
                            )}
                            {sessionObjective.progress_rating && (
                              <Chip 
                                label={sessionObjective.progress_rating.replace('_', ' ')}
                                size="small"
                                variant="outlined"
                              />
                            )}
                          </Box>
                          
                          {sessionObjective.session_notes && (
                            <Paper sx={{ p: 2, bgcolor: '#fafafa', border: '1px solid #e0e0e0' }}>
                              <Typography variant="body2">
                                <strong>Notes:</strong> {sessionObjective.session_notes}
                              </Typography>
                            </Paper>
                          )}
                        </Box>
                      }
                    />
                  </ListItem>
                );
              })}
            </List>
          </CardContent>
        </Card>
      )}

      {/* Session Completion Form */}
      <Card>
        <CardContent sx={{ p: isMobile ? 2 : 3 }}>
          <Typography 
            variant={isMobile ? "subtitle1" : "h6"} 
            sx={{ 
              mb: isMobile ? 2 : 3, 
              display: 'flex', 
              alignItems: 'center', 
              gap: 1,
              fontSize: isMobile ? '1.1rem' : undefined
            }}
          >
            <Psychology color="primary" sx={{ fontSize: isMobile ? 18 : 20 }} />
            Session Completion Details
          </Typography>
          
          <Grid container spacing={isMobile ? 2 : 3}>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Student Engagement</InputLabel>
                <Select
                  value={completionData.student_engagement}
                  onChange={(e) => setCompletionData(prev => ({ ...prev, student_engagement: e.target.value }))}
                  label="Student Engagement"
                >
                  {ENGAGEMENT_LEVELS.map(level => (
                    <MenuItem key={level} value={level}>
                      {level.toUpperCase()}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Session Quality</InputLabel>
                <Select
                  value={completionData.session_quality}
                  onChange={(e) => setCompletionData(prev => ({ ...prev, session_quality: e.target.value }))}
                  label="Session Quality"
                >
                  {SESSION_QUALITY_OPTIONS.map(quality => (
                    <MenuItem key={quality} value={quality}>
                      {quality.toUpperCase()}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={isMobile ? 3 : 4}
                label="Final Session Notes"
                value={completionData.session_notes}
                onChange={(e) => setCompletionData(prev => ({ ...prev, session_notes: e.target.value }))}
                placeholder="Final notes about the session, overall observations, significant events..."
              />
            </Grid>

            <Grid item xs={12}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Typography variant="body1">Follow-up needed?</Typography>
                <Select
                  value={completionData.follow_up_needed ? 'yes' : 'no'}
                  onChange={(e) => setCompletionData(prev => ({ ...prev, follow_up_needed: e.target.value === 'yes' }))}
                  size="small"
                  sx={{ minWidth: 100 }}
                >
                  <MenuItem value="no">No</MenuItem>
                  <MenuItem value="yes">Yes</MenuItem>
                </Select>
              </Box>

              {completionData.follow_up_needed && (
                <TextField
                  fullWidth
                  multiline
                  rows={isMobile ? 2 : 3}
                  label="Follow-up Notes"
                  value={completionData.follow_up_notes}
                  onChange={(e) => setCompletionData(prev => ({ ...prev, follow_up_notes: e.target.value }))}
                  placeholder="Describe what follow-up is needed..."
                />
              )}
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      <Divider sx={{ my: isMobile ? 2 : 3 }} />

      {/* Action Buttons */}
      <Box sx={{ 
        display: 'flex', 
        flexDirection: isMobile ? 'column' : 'row',
        justifyContent: isMobile ? 'stretch' : 'flex-end', 
        gap: isMobile ? 1.5 : 2
      }}>
        <Button
          startIcon={<Cancel />}
          disabled={loading}
          fullWidth={isMobile}
          size={isMobile ? 'medium' : 'small'}
          sx={{ 
            textTransform: 'none',
            fontWeight: 500,
            color: '#666',
            order: isMobile ? 2 : 1
          }}
        >
          Back to Session
        </Button>
        <Button
          onClick={handleComplete}
          variant="contained"
          startIcon={loading ? <CircularProgress size={16} /> : <Save />}
          disabled={loading}
          fullWidth={isMobile}
          size={isMobile ? 'medium' : 'small'}
          sx={{
            bgcolor: '#40A8B6',
            '&:hover': { bgcolor: '#369aa6' },
            '&:disabled': { bgcolor: '#e0e0e0' },
            textTransform: 'none',
            fontWeight: 500,
            px: isMobile ? 3 : 4,
            order: isMobile ? 1 : 2
          }}
        >
          {loading ? 'Completing Session...' : (isMobile ? 'Complete Session' : 'Complete & Save Session')}
        </Button>
      </Box>
    </Box>
  );
}