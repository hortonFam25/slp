import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Grid,
  Alert,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
  Paper
} from '@mui/material';
import {
  ExpandMore,
  Stop,
  Add,
  CheckCircle,
  Assignment,
  Timeline,
  Notes,
  Save
} from '@mui/icons-material';
import { useGoals } from '../../../lib/hooks/useGoals';
import { ProgressEntryForm } from './ProgressEntryForm';
import { SessionSummary } from './SessionSummary';
import type { Student } from '../../../lib/api/students';
import type { IEPGoal, GoalObjective } from '../../../lib/api/types/goals';

interface TherapySessionProps {
  student: Student;
  sessionDate: Date;
  onEndSession: () => void;
}

interface SessionProgress {
  objectiveId: number;
  progress: string;
  comments: string;
  sessionType: string;
}

export function TherapySession({ student, sessionDate, onEndSession }: TherapySessionProps) {
  const { goals, loading, error, fetchStudentGoals } = useGoals();
  const [expandedGoal, setExpandedGoal] = useState<number | null>(null);
  const [sessionProgress, setSessionProgress] = useState<SessionProgress[]>([]);
  const [showProgressForm, setShowProgressForm] = useState(false);
  const [selectedObjective, setSelectedObjective] = useState<GoalObjective | null>(null);
  const [showSummary, setShowSummary] = useState(false);

  useEffect(() => {
    if (student.id) {
      fetchStudentGoals(student.id);
    }
  }, [student.id, fetchStudentGoals]);

  const handleAddProgress = (objective: GoalObjective) => {
    setSelectedObjective(objective);
    setShowProgressForm(true);
  };

  const handleProgressSaved = (objectiveId: number, progress: string, comments: string, sessionType: string) => {
    setSessionProgress(prev => {
      const existing = prev.find(p => p.objectiveId === objectiveId);
      if (existing) {
        return prev.map(p => 
          p.objectiveId === objectiveId 
            ? { ...p, progress, comments, sessionType }
            : p
        );
      } else {
        return [...prev, { objectiveId, progress, comments, sessionType }];
      }
    });
    setShowProgressForm(false);
    setSelectedObjective(null);
  };

  const handleEndSession = () => {
    if (sessionProgress.length > 0) {
      setShowSummary(true);
    } else {
      onEndSession();
    }
  };

  const getObjectiveProgress = (objectiveId: number) => {
    return sessionProgress.find(p => p.objectiveId === objectiveId);
  };

  const activeGoals = goals?.filter(goal => goal.goal_status === 'Active') || [];

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
        <CircularProgress size={40} />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3, bgcolor: '#fafafa', minHeight: '100vh' }}>
      {/* Session Header */}
      <Paper elevation={2} sx={{ p: 3, mb: 3, bgcolor: 'white', borderRadius: 3 }}>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Box>
            <Typography variant="h4" sx={{ color: '#40A8B6', fontWeight: 600, mb: 1 }}>
              Therapy Session in Progress
            </Typography>
            <Typography variant="h6" color="text.secondary">
              {student.first} {student.last} • {sessionDate.toLocaleDateString()}
            </Typography>
          </Box>
          <Box display="flex" gap={2}>
            <Chip 
              icon={<Notes />} 
              label={`${sessionProgress.length} objectives tracked`} 
              color="primary"
              sx={{ 
                bgcolor: '#e8f4f5', 
                color: '#40A8B6',
                '& .MuiChip-icon': { color: '#40A8B6' }
              }}
            />
            <Button
              variant="contained"
              startIcon={<Stop />}
              onClick={handleEndSession}
              color="error"
              sx={{ textTransform: 'none', fontWeight: 500 }}
            >
              End Session
            </Button>
          </Box>
        </Box>
      </Paper>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Goals and Objectives */}
      <Box>
        <Typography 
          variant="h5" 
          sx={{ 
            mb: 3, 
            color: '#40A8B6', 
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center'
          }}
        >
          <Assignment sx={{ mr: 2 }} />
          Active Goals & Objectives
        </Typography>

        {activeGoals.length === 0 ? (
          <Card sx={{ bgcolor: 'white', borderRadius: 3, boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
            <CardContent sx={{ textAlign: 'center', py: 6 }}>
              <Assignment sx={{ fontSize: 64, color: '#40A8B6', mb: 2 }} />
              <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600, mb: 1 }}>
                No Active Goals Found
              </Typography>
              <Typography color="text.secondary">
                This student doesn't have any active IEP goals to work on.
              </Typography>
            </CardContent>
          </Card>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {activeGoals.map((goal) => (
              <Accordion
                key={goal.id}
                expanded={expandedGoal === goal.id}
                onChange={(_, isExpanded) => setExpandedGoal(isExpanded ? goal.id : null)}
                sx={{
                  bgcolor: 'white',
                  borderRadius: '12px !important',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                  border: '1px solid #e0e0e0',
                  '&:before': { display: 'none' },
                  '&.Mui-expanded': {
                    boxShadow: '0 4px 16px rgba(64,168,182,0.15)',
                    borderColor: '#40A8B6'
                  }
                }}
              >
                <AccordionSummary 
                  expandIcon={<ExpandMore sx={{ color: '#40A8B6' }} />}
                  sx={{
                    '& .MuiAccordionSummary-content': { my: 2 },
                    borderRadius: '12px',
                    '&:hover': { bgcolor: '#f8fffe' }
                  }}
                >
                  <Box display="flex" alignItems="center" width="100%" mr={2}>
                    <Box flex={1}>
                      <Typography variant="h6" sx={{ fontWeight: 600, color: '#333', mb: 1 }}>
                        {goal.goal_number && (
                          <span style={{ color: '#40A8B6', fontWeight: 700 }}>
                            Goal {goal.goal_number}: 
                          </span>
                        )} {goal.goal_description.length > 80
                          ? `${goal.goal_description.substring(0, 80)}...`
                          : goal.goal_description
                        }
                      </Typography>
                      <Box display="flex" gap={1} mt={1} flexWrap="wrap">
                        <Chip
                          label={goal.goal_status}
                          size="small"
                          sx={{ 
                            bgcolor: '#40A8B6',
                            color: 'white',
                            fontWeight: 500
                          }}
                        />
                        <Chip
                          label={`${goal.objectives?.length || 0} objectives`}
                          variant="outlined"
                          size="small"
                          sx={{
                            borderColor: '#40A8B6',
                            color: '#40A8B6',
                            fontWeight: 500
                          }}
                        />
                      </Box>
                    </Box>
                  </Box>
                </AccordionSummary>
                <AccordionDetails sx={{ 
                  bgcolor: '#fafbfc', 
                  borderTop: '1px solid #e8f4f5',
                  p: 3
                }}>
                  {!goal.objectives || goal.objectives.length === 0 ? (
                    <Box textAlign="center" py={3}>
                      <Typography color="text.secondary">
                        No objectives defined for this goal.
                      </Typography>
                    </Box>
                  ) : (
                    <Grid container spacing={2}>
                      {goal.objectives.map((objective) => {
                        const progress = getObjectiveProgress(objective.id);
                        return (
                          <Grid item xs={12} key={objective.id}>
                            <Card 
                              sx={{
                                bgcolor: 'white',
                                borderRadius: 2,
                                border: progress ? '2px solid #40A8B6' : '1px solid #e8f4f5',
                                boxShadow: progress ? '0 4px 8px rgba(64,168,182,0.15)' : '0 2px 4px rgba(0,0,0,0.05)',
                                '&:hover': {
                                  boxShadow: '0 4px 8px rgba(64,168,182,0.15)',
                                  borderColor: '#40A8B6'
                                }
                              }}
                            >
                              <CardContent sx={{ p: 3 }}>
                                <Box display="flex" justifyContent="space-between" alignItems="start">
                                  <Box flex={1}>
                                    <Typography 
                                      variant="subtitle1" 
                                      sx={{ 
                                        color: '#40A8B6', 
                                        fontWeight: 600, 
                                        mb: 1,
                                        display: 'flex',
                                        alignItems: 'center'
                                      }}
                                    >
                                      {progress && <CheckCircle sx={{ mr: 1, fontSize: 20 }} />}
                                      Objective {objective.objective_number}
                                    </Typography>
                                    <Typography variant="body2" sx={{ mb: 2, color: '#333' }}>
                                      {objective.objective_description}
                                    </Typography>
                                    
                                    {progress ? (
                                      <Box sx={{ 
                                        bgcolor: '#e8f4f5', 
                                        p: 2, 
                                        borderRadius: 2,
                                        border: '1px solid #d0e8ec'
                                      }}>
                                        <Typography variant="body2" sx={{ color: '#40A8B6', fontWeight: 600, mb: 1 }}>
                                          Progress Recorded:
                                        </Typography>
                                        <Typography variant="body2" sx={{ mb: 1 }}>
                                          <strong>Status:</strong> {progress.progress}
                                        </Typography>
                                        <Typography variant="body2" sx={{ mb: 1 }}>
                                          <strong>Session Type:</strong> {progress.sessionType}
                                        </Typography>
                                        {progress.comments && (
                                          <Typography variant="body2">
                                            <strong>Notes:</strong> {progress.comments}
                                          </Typography>
                                        )}
                                      </Box>
                                    ) : (
                                      <Box display="flex" gap={1} flexWrap="wrap">
                                        {objective.progress_status && (
                                          <Chip 
                                            label={objective.progress_status} 
                                            size="small"
                                            sx={{
                                              bgcolor: '#e8f4f5',
                                              color: '#40A8B6',
                                              fontWeight: 500
                                            }}
                                          />
                                        )}
                                        {objective.schedule_frequency && (
                                          <Chip 
                                            label={objective.schedule_frequency} 
                                            variant="outlined" 
                                            size="small"
                                            sx={{
                                              borderColor: '#40A8B6',
                                              color: '#40A8B6'
                                            }}
                                          />
                                        )}
                                      </Box>
                                    )}
                                  </Box>
                                  <Box>
                                    <Button
                                      variant={progress ? "outlined" : "contained"}
                                      size="small"
                                      startIcon={progress ? <Timeline /> : <Add />}
                                      onClick={() => handleAddProgress(objective)}
                                      sx={{
                                        bgcolor: progress ? 'transparent' : '#40A8B6',
                                        borderColor: '#40A8B6',
                                        color: progress ? '#40A8B6' : 'white',
                                        '&:hover': {
                                          bgcolor: progress ? 'rgba(64,168,182,0.05)' : '#369aa6'
                                        },
                                        textTransform: 'none',
                                        fontWeight: 500,
                                        minWidth: 120
                                      }}
                                    >
                                      {progress ? 'Update' : 'Track Progress'}
                                    </Button>
                                  </Box>
                                </Box>
                              </CardContent>
                            </Card>
                          </Grid>
                        );
                      })}
                    </Grid>
                  )}
                </AccordionDetails>
              </Accordion>
            ))}
          </Box>
        )}
      </Box>

      {/* Progress Entry Dialog */}
      <Dialog 
        open={showProgressForm} 
        onClose={() => setShowProgressForm(false)}
        maxWidth="sm" 
        fullWidth
      >
        <DialogTitle sx={{ bgcolor: '#40A8B6', color: 'white' }}>
          Track Progress - Objective {selectedObjective?.objective_number}
        </DialogTitle>
        <DialogContent sx={{ p: 0 }}>
          {selectedObjective && (
            <ProgressEntryForm
              objective={selectedObjective}
              sessionDate={sessionDate}
              existingProgress={getObjectiveProgress(selectedObjective.id)}
              onSave={handleProgressSaved}
              onCancel={() => setShowProgressForm(false)}
            />
          )}
        </DialogContent>
      </Dialog>

      {/* Session Summary Dialog */}
      <Dialog 
        open={showSummary} 
        onClose={() => setShowSummary(false)}
        maxWidth="md" 
        fullWidth
      >
        <DialogTitle sx={{ bgcolor: '#40A8B6', color: 'white' }}>
          Session Summary
        </DialogTitle>
        <DialogContent sx={{ p: 0 }}>
          <SessionSummary
            student={student}
            sessionDate={sessionDate}
            sessionProgress={sessionProgress}
            goals={activeGoals}
            onComplete={onEndSession}
            onCancel={() => setShowSummary(false)}
          />
        </DialogContent>
      </Dialog>
    </Box>
  );
}
