import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Stack,
  Alert,
  CircularProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  IconButton,
  Grid,
  Divider
} from '@mui/material';
import {
  Add,
  Edit,
  Delete,
  ExpandMore,
  TrackChanges,
  TrendingUp,
  CheckCircle,
  PlayCircle,
  PauseCircle,
  StopCircle
} from '@mui/icons-material';
import { useGoals } from '../lib/hooks/useGoals';
import type {
  IEPGoal,
  GoalObjective,
  CreateGoalRequest,
  UpdateGoalRequest,
  CreateObjectiveRequest,
  UpdateObjectiveRequest
} from '../lib/api';
import {
  GOAL_STATUS_OPTIONS,
  SCHEDULE_FREQUENCY_OPTIONS
} from '../lib/api/types/goals';

interface GoalManagementProps {
  studentId: number;
  studentName?: string;
}

export function GoalManagement({ studentId, studentName }: GoalManagementProps) {
  const {
    goals,
    goalCategories,
    loading,
    error,
    fetchStudentGoals,
    createGoal,
    updateGoal,
    deleteGoal,
    createObjective,
    updateObjective,
    deleteObjective,
    clearError
  } = useGoals();

  const [dialogState, setDialogState] = useState<{
    type: 'goal' | 'objective' | null;
    mode: 'create' | 'edit';
    data?: any;
    goalId?: number;
  }>({ type: null, mode: 'create' });

  const [expandedGoal, setExpandedGoal] = useState<number | null>(null);

  useEffect(() => {
    if (studentId) {
      fetchStudentGoals(studentId);
    }
  }, [studentId, fetchStudentGoals]);

  const handleCreateGoal = () => {
    setDialogState({ type: 'goal', mode: 'create' });
  };

  const handleEditGoal = (goal: IEPGoal) => {
    setDialogState({ type: 'goal', mode: 'edit', data: goal });
  };

  const handleDeleteGoal = async (goalId: number) => {
    if (window.confirm('Are you sure you want to delete this goal? This will also delete all objectives and progress entries.')) {
      try {
        await deleteGoal(goalId);
      } catch (error) {
        console.error('Failed to delete goal:', error);
      }
    }
  };

  const handleCreateObjective = (goalId: number) => {
    setDialogState({ type: 'objective', mode: 'create', goalId });
  };

  const handleEditObjective = (objective: GoalObjective, goalId: number) => {
    setDialogState({ type: 'objective', mode: 'edit', data: objective, goalId });
  };

  const handleDeleteObjective = async (objectiveId: number) => {
    if (window.confirm('Are you sure you want to delete this objective? This will also delete all progress entries.')) {
      try {
        await deleteObjective(objectiveId);
      } catch (error) {
        console.error('Failed to delete objective:', error);
      }
    }
  };

  const closeDialog = () => {
    setDialogState({ type: null, mode: 'create' });
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'active':
        return <PlayCircle color="success" />;
      case 'mastered':
        return <CheckCircle color="primary" />;
      case 'on hold':
        return <PauseCircle color="warning" />;
      case 'discontinued':
        return <StopCircle color="error" />;
      default:
        return <TrackChanges color="action" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'active':
        return 'success';
      case 'mastered':
        return 'primary';
      case 'on hold':
        return 'warning';
      case 'discontinued':
        return 'error';
      default:
        return 'default';
    }
  };

  if (loading && goals.length === 0) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box 
        display="flex" 
        justifyContent="space-between" 
        alignItems="center" 
        mb={3} 
        sx={{ 
          flexShrink: 0,
          bgcolor: 'white',
          p: 3,
          borderRadius: 2,
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          border: '1px solid #e0e0e0'
        }}
      >
        <Typography variant="h5" component="h2" sx={{ color: '#40A8B6', fontWeight: 600 }}>
          IEP Goals {studentName && `- ${studentName}`}
        </Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={handleCreateGoal}
          sx={{
            bgcolor: '#40A8B6',
            '&:hover': {
              bgcolor: '#369aa6'
            },
            textTransform: 'none',
            fontWeight: 500,
            px: 3,
            py: 1.5,
            borderRadius: 2,
            boxShadow: '0 2px 4px rgba(64,168,182,0.3)'
          }}
        >
          Add Goal
        </Button>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" onClose={clearError} sx={{ mb: 2, flexShrink: 0 }}>
          {error}
        </Alert>
      )}

      {/* Goals List - Scrollable */}
      <Box sx={{ flex: 1, overflow: 'auto', minHeight: 0, pb: 6 }}>
        {goals.length === 0 ? (
        <Card sx={{ 
          bgcolor: 'white', 
          borderRadius: 3, 
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          border: '1px solid #e0e0e0'
        }}>
          <CardContent sx={{ textAlign: 'center', py: 6 }}>
            <TrackChanges sx={{ fontSize: 64, color: '#40A8B6', mb: 2 }} />
            <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600, mb: 1 }}>
              No IEP Goals Yet
            </Typography>
            <Typography color="text.secondary" mb={4}>
              Start by creating the first goal for this student.
            </Typography>
            <Button 
              variant="contained" 
              startIcon={<Add />} 
              onClick={handleCreateGoal}
              sx={{
                bgcolor: '#40A8B6',
                '&:hover': {
                  bgcolor: '#369aa6'
                },
                textTransform: 'none',
                fontWeight: 500,
                px: 4,
                py: 1.5,
                borderRadius: 2,
                boxShadow: '0 3px 6px rgba(64,168,182,0.3)'
              }}
            >
              Create First Goal
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Stack spacing={3}>
          {goals.map((goal) => (
            <Accordion
              key={goal.id}
              expanded={expandedGoal === goal.id}
              onChange={(_, isExpanded) => setExpandedGoal(isExpanded ? goal.id : null)}
              sx={{
                bgcolor: 'white',
                borderRadius: '12px !important',
                boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                border: '1px solid #e0e0e0',
                mb: 2,
                '&:before': {
                  display: 'none'
                },
                '&.Mui-expanded': {
                  boxShadow: '0 4px 16px rgba(64,168,182,0.15)',
                  borderColor: '#40A8B6'
                }
              }}
            >
              <AccordionSummary 
                expandIcon={<ExpandMore sx={{ color: '#40A8B6' }} />}
                sx={{
                  '& .MuiAccordionSummary-content': {
                    my: 2
                  },
                  borderRadius: '12px',
                  '&:hover': {
                    bgcolor: '#f8fffe'
                  }
                }}
              >
                <Box display="flex" alignItems="center" width="100%" mr={2}>
                  <Box display="flex" alignItems="center" flex={1}>
                    {getStatusIcon(goal.goal_status)}
                    <Box ml={2} flex={1}>
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
                          color={getStatusColor(goal.goal_status) as any}
                          size="small"
                          sx={{ 
                            fontWeight: 500,
                            '&.MuiChip-colorPrimary': {
                              bgcolor: '#40A8B6',
                              color: 'white'
                            }
                          }}
                        />
                        {goal.goal_category_name && (
                          <Chip 
                            label={goal.goal_category_name} 
                            variant="outlined" 
                            size="small"
                            sx={{
                              borderColor: '#40A8B6',
                              color: '#40A8B6',
                              fontWeight: 500
                            }}
                          />
                        )}
                        <Chip
                          label={`${goal.objectives?.length || 0} objectives`}
                          variant="outlined"
                          size="small"
                          sx={{
                            bgcolor: '#f0f9fa',
                            borderColor: '#40A8B6',
                            color: '#40A8B6',
                            fontWeight: 500
                          }}
                        />
                      </Box>
                    </Box>
                  </Box>
                </Box>
              </AccordionSummary>
              <AccordionDetails sx={{ 
                bgcolor: '#fafbfc', 
                borderTop: '1px solid #e8f4f5',
                p: 3
              }}>
                <GoalDetails
                  goal={goal}
                  onEditGoal={() => handleEditGoal(goal)}
                  onDeleteGoal={() => handleDeleteGoal(goal.id)}
                  onCreateObjective={() => handleCreateObjective(goal.id)}
                  onEditObjective={(obj) => handleEditObjective(obj, goal.id)}
                  onDeleteObjective={handleDeleteObjective}
                />
              </AccordionDetails>
            </Accordion>
          ))}
        </Stack>
        )}
      </Box>

      {/* Goal Dialog */}
      <GoalDialog
        open={dialogState.type === 'goal'}
        mode={dialogState.mode}
        goal={dialogState.data}
        studentId={studentId}
        goalCategories={goalCategories}
        onClose={closeDialog}
        onCreate={createGoal}
        onUpdate={updateGoal}
      />

      {/* Objective Dialog */}
      <ObjectiveDialog
        open={dialogState.type === 'objective'}
        mode={dialogState.mode}
        objective={dialogState.data}
        goalId={dialogState.goalId || 0}
        currentGoal={goals.find(g => g.id === dialogState.goalId)}
        onClose={closeDialog}
        onCreate={createObjective}
        onUpdate={updateObjective}
      />
    </Box>
  );
}

// Goal Details Component
interface GoalDetailsProps {
  goal: IEPGoal;
  onEditGoal: () => void;
  onDeleteGoal: () => void;
  onCreateObjective: () => void;
  onEditObjective: (objective: GoalObjective) => void;
  onDeleteObjective: (objectiveId: number) => void;
}

function GoalDetails({
  goal,
  onEditGoal,
  onDeleteGoal,
  onCreateObjective,
  onEditObjective,
  onDeleteObjective
}: GoalDetailsProps) {
  return (
    <Box>
      {/* Goal Information */}
      <Box mb={3}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600 }}>
            Goal Details
          </Typography>
          <Box>
            <IconButton 
              onClick={onEditGoal} 
              size="small"
              sx={{
                mr: 1,
                color: '#40A8B6',
                '&:hover': {
                  bgcolor: 'rgba(64,168,182,0.1)'
                }
              }}
            >
              <Edit />
            </IconButton>
            <IconButton 
              onClick={onDeleteGoal} 
              size="small" 
              sx={{
                color: '#f44336',
                '&:hover': {
                  bgcolor: 'rgba(244,67,54,0.1)'
                }
              }}
            >
              <Delete />
            </IconButton>
          </Box>
        </Box>
        
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Box sx={{ 
              bgcolor: 'white', 
              p: 2, 
              borderRadius: 2, 
              border: '1px solid #e0e0e0',
              borderLeft: '4px solid #40A8B6'
            }}>
              <Typography variant="body2" sx={{ color: '#40A8B6', fontWeight: 600, mb: 1 }}>
                Description
              </Typography>
              <Typography variant="body1">{goal.goal_description}</Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={6}>
            <Box sx={{ 
              bgcolor: 'white', 
              p: 2, 
              borderRadius: 2, 
              border: '1px solid #e0e0e0',
              borderLeft: '4px solid #40A8B6'
            }}>
              <Typography variant="body2" sx={{ color: '#40A8B6', fontWeight: 600, mb: 1 }}>
                Target Criteria
              </Typography>
              <Typography variant="body1">{goal.target_criteria}</Typography>
            </Box>
          </Grid>
          {goal.target_behavior && (
            <Grid item xs={12} md={6}>
              <Box sx={{ 
                bgcolor: 'white', 
                p: 2, 
                borderRadius: 2, 
                border: '1px solid #e0e0e0',
                borderLeft: '4px solid #40A8B6'
              }}>
                <Typography variant="body2" sx={{ color: '#40A8B6', fontWeight: 600, mb: 1 }}>
                  Target Behavior
                </Typography>
                <Typography variant="body1">{goal.target_behavior}</Typography>
              </Box>
            </Grid>
          )}
          {goal.baseline_data && (
            <Grid item xs={12} md={6}>
              <Box sx={{ 
                bgcolor: 'white', 
                p: 2, 
                borderRadius: 2, 
                border: '1px solid #e0e0e0',
                borderLeft: '4px solid #40A8B6'
              }}>
                <Typography variant="body2" sx={{ color: '#40A8B6', fontWeight: 600, mb: 1 }}>
                  Baseline Data
                </Typography>
                <Typography variant="body1">{goal.baseline_data}</Typography>
              </Box>
            </Grid>
          )}
          <Grid item xs={12} md={6}>
            <Box sx={{ 
              bgcolor: '#f0f9fa', 
              p: 2, 
              borderRadius: 2, 
              border: '1px solid #d0e8ec',
              borderLeft: '4px solid #40A8B6'
            }}>
              <Typography variant="body2" sx={{ color: '#40A8B6', fontWeight: 600, mb: 1 }}>
                Start Date
              </Typography>
              <Typography variant="body1">{new Date(goal.start_date).toLocaleDateString()}</Typography>
            </Box>
          </Grid>
          {goal.end_date && (
            <Grid item xs={12} md={6}>
              <Box sx={{ 
                bgcolor: '#f0f9fa', 
                p: 2, 
                borderRadius: 2, 
                border: '1px solid #d0e8ec',
                borderLeft: '4px solid #40A8B6'
              }}>
                <Typography variant="body2" sx={{ color: '#40A8B6', fontWeight: 600, mb: 1 }}>
                  End Date
                </Typography>
                <Typography variant="body1">{new Date(goal.end_date).toLocaleDateString()}</Typography>
              </Box>
            </Grid>
          )}
        </Grid>
      </Box>

      <Divider sx={{ my: 4, borderColor: '#e8f4f5' }} />

      {/* Objectives Section */}
      <Box>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600 }}>
            Objectives
          </Typography>
          <Button
            variant="outlined"
            size="small"
            startIcon={<Add />}
            onClick={onCreateObjective}
            sx={{
              borderColor: '#40A8B6',
              color: '#40A8B6',
              '&:hover': {
                borderColor: '#369aa6',
                bgcolor: 'rgba(64,168,182,0.05)'
              },
              textTransform: 'none',
              fontWeight: 500
            }}
          >
            Add Objective
          </Button>
        </Box>

        {!goal.objectives || goal.objectives.length === 0 ? (
          <Box 
            textAlign="center" 
            py={5}
            sx={{
              bgcolor: 'white',
              borderRadius: 2,
              border: '2px dashed #d0e8ec',
              color: '#40A8B6'
            }}
          >
            <Add sx={{ fontSize: 48, color: '#40A8B6', mb: 2 }} />
            <Typography sx={{ color: '#40A8B6', fontWeight: 500, mb: 2 }}>
              No objectives yet for this goal.
            </Typography>
            <Button 
              variant="contained" 
              startIcon={<Add />} 
              onClick={onCreateObjective}
              sx={{
                bgcolor: '#40A8B6',
                '&:hover': {
                  bgcolor: '#369aa6'
                },
                textTransform: 'none',
                fontWeight: 500
              }}
            >
              Add First Objective
            </Button>
          </Box>
        ) : (
          <Box sx={{ maxHeight: '400px', overflow: 'auto' }}>
            <Stack spacing={2}>
              {goal.objectives.map((objective) => (
                <Card 
                  key={objective.id} 
                  sx={{
                    bgcolor: 'white',
                    borderRadius: 2,
                    border: '1px solid #e8f4f5',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
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
                            mb: 1 
                          }}
                        >
                          Objective {objective.objective_number}
                        </Typography>
                        <Typography variant="body2" sx={{ mb: 2, color: '#333' }}>
                          {objective.objective_description}
                        </Typography>
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
                          <Chip
                            label={`${objective.progress_count} entries`}
                            variant="outlined"
                            size="small"
                            icon={<TrendingUp sx={{ color: '#40A8B6' }} />}
                            sx={{
                              borderColor: '#40A8B6',
                              color: '#40A8B6'
                            }}
                          />
                        </Box>
                      </Box>
                      <Box>
                        <IconButton 
                          onClick={() => onEditObjective(objective)} 
                          size="small"
                          sx={{
                            mr: 1,
                            color: '#40A8B6',
                            '&:hover': {
                              bgcolor: 'rgba(64,168,182,0.1)'
                            }
                          }}
                        >
                          <Edit />
                        </IconButton>
                        <IconButton
                          onClick={() => onDeleteObjective(objective.id)}
                          size="small"
                          sx={{
                            color: '#f44336',
                            '&:hover': {
                              bgcolor: 'rgba(244,67,54,0.1)'
                            }
                          }}
                        >
                          <Delete />
                        </IconButton>
                      </Box>
                    </Box>
                  </CardContent>
                </Card>
              ))}
            </Stack>
          </Box>
        )}
      </Box>
    </Box>
  );
}

// Goal Dialog Component (Create/Edit Goal)
interface GoalDialogProps {
  open: boolean;
  mode: 'create' | 'edit';
  goal?: IEPGoal;
  studentId: number;
  goalCategories: any[];
  onClose: () => void;
  onCreate: (goal: CreateGoalRequest) => Promise<IEPGoal>;
  onUpdate: (goalId: number, updates: UpdateGoalRequest) => Promise<IEPGoal>;
}

function GoalDialog({
  open,
  mode,
  goal,
  studentId,
  goalCategories,
  onClose,
  onCreate,
  onUpdate
}: GoalDialogProps) {
  const [formData, setFormData] = useState({
    goal_category_id: goal?.goal_category_id || '',
    goal_number: goal?.goal_number || '',
    goal_description: goal?.goal_description || '',
    target_behavior: goal?.target_behavior || '',
    baseline_data: goal?.baseline_data || '',
    target_criteria: goal?.target_criteria || '',
    goal_status: goal?.goal_status || 'Active',
    start_date: goal?.start_date || new Date().toISOString().split('T')[0],
    end_date: goal?.end_date || '',
    mastery_date: goal?.mastery_date || ''
  });

  const [submitting, setSubmitting] = useState(false);

  // Update form data when goal prop changes (for edit mode)
  useEffect(() => {
    if (open) {
      setFormData({
        goal_category_id: goal?.goal_category_id || '',
        goal_number: goal?.goal_number || '',
        goal_description: goal?.goal_description || '',
        target_behavior: goal?.target_behavior || '',
        baseline_data: goal?.baseline_data || '',
        target_criteria: goal?.target_criteria || '',
        goal_status: goal?.goal_status || 'Active',
        start_date: goal?.start_date || new Date().toISOString().split('T')[0],
        end_date: goal?.end_date || '',
        mastery_date: goal?.mastery_date || ''
      });
    }
  }, [open, goal]);

  const handleSubmit = async () => {
    try {
      setSubmitting(true);
      
      const goalData = {
        ...formData,
        goal_category_id: Number(formData.goal_category_id),
        end_date: formData.end_date || undefined,
        mastery_date: formData.mastery_date || undefined
      };

      if (mode === 'create') {
        await onCreate({ ...goalData, student_id: studentId } as CreateGoalRequest);
      } else if (goal) {
        await onUpdate(goal.id, goalData as UpdateGoalRequest);
      }
      
      onClose();
    } catch (error) {
      console.error('Failed to save goal:', error);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        {mode === 'create' ? 'Create New Goal' : 'Edit Goal'}
      </DialogTitle>
      <DialogContent>
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>Goal Category</InputLabel>
              <Select
                value={formData.goal_category_id}
                onChange={(e) => setFormData({ ...formData, goal_category_id: e.target.value })}
                label="Goal Category"
              >
                {goalCategories.map((category) => (
                  <MenuItem key={category.id} value={category.id}>
                    {category.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Goal Number"
              value={formData.goal_number}
              onChange={(e) => setFormData({ ...formData, goal_number: e.target.value })}
              placeholder="e.g., 1, 2A, etc."
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              multiline
              rows={3}
              label="Goal Description"
              value={formData.goal_description}
              onChange={(e) => setFormData({ ...formData, goal_description: e.target.value })}
              required
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              multiline
              rows={2}
              label="Target Criteria"
              value={formData.target_criteria}
              onChange={(e) => setFormData({ ...formData, target_criteria: e.target.value })}
              required
              placeholder="e.g., 80% accuracy across 3 consecutive sessions"
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              multiline
              rows={2}
              label="Target Behavior (Optional)"
              value={formData.target_behavior}
              onChange={(e) => setFormData({ ...formData, target_behavior: e.target.value })}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              multiline
              rows={2}
              label="Baseline Data (Optional)"
              value={formData.baseline_data}
              onChange={(e) => setFormData({ ...formData, baseline_data: e.target.value })}
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={formData.goal_status}
                onChange={(e) => setFormData({ ...formData, goal_status: e.target.value })}
                label="Status"
              >
                {GOAL_STATUS_OPTIONS.map((status) => (
                  <MenuItem key={status} value={status}>
                    {status}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              type="date"
              label="Start Date"
              value={formData.start_date}
              onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
              InputLabelProps={{ shrink: true }}
              required
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              type="date"
              label="End Date (Optional)"
              value={formData.end_date}
              onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
          {formData.goal_status === 'Mastered' && (
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                type="date"
                label="Mastery Date"
                value={formData.mastery_date}
                onChange={(e) => setFormData({ ...formData, mastery_date: e.target.value })}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
          )}
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={submitting || !formData.goal_description || !formData.target_criteria}
        >
          {submitting ? <CircularProgress size={20} /> : mode === 'create' ? 'Create' : 'Update'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// Objective Dialog Component (Create/Edit Objective)
interface ObjectiveDialogProps {
  open: boolean;
  mode: 'create' | 'edit';
  objective?: GoalObjective;
  goalId: number;
  currentGoal?: IEPGoal;
  onClose: () => void;
  onCreate: (objective: CreateObjectiveRequest) => Promise<GoalObjective>;
  onUpdate: (objectiveId: number, updates: UpdateObjectiveRequest) => Promise<GoalObjective>;
}

function ObjectiveDialog({
  open,
  mode,
  objective,
  goalId,
  currentGoal,
  onClose,
  onCreate,
  onUpdate
}: ObjectiveDialogProps) {
  const [formData, setFormData] = useState({
    objective_number: objective?.objective_number || 1,
    objective_description: objective?.objective_description || '',
    progress_status: objective?.progress_status || '',
    schedule_frequency: objective?.schedule_frequency || ''
  });

  const [submitting, setSubmitting] = useState(false);

  // Calculate available objective numbers (1-10) that aren't already used
  const getAvailableObjectiveNumbers = () => {
    const allNumbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    
    if (!currentGoal?.objectives) {
      return allNumbers;
    }

    const usedNumbers = currentGoal.objectives
      .filter(obj => mode === 'edit' ? obj.id !== objective?.id : true) // Exclude current objective if editing
      .map(obj => obj.objective_number);

    return allNumbers.filter(num => !usedNumbers.includes(num));
  };

  const availableNumbers = getAvailableObjectiveNumbers();

  // Update form data when objective prop changes (for edit mode)
  useEffect(() => {
    if (open) {
      setFormData({
        objective_number: objective?.objective_number || 1,
        objective_description: objective?.objective_description || '',
        progress_status: objective?.progress_status || '',
        schedule_frequency: objective?.schedule_frequency || ''
      });
    }
  }, [open, objective]);

  // Auto-select first available number if current selection is not available
  useEffect(() => {
    if (mode === 'create' && !availableNumbers.includes(formData.objective_number)) {
      setFormData(prev => ({ 
        ...prev, 
        objective_number: availableNumbers[0] || 1 
      }));
    }
  }, [mode, availableNumbers, formData.objective_number]);

  const handleSubmit = async () => {
    try {
      setSubmitting(true);
      
      if (mode === 'create') {
        await onCreate({ ...formData, goal_id: goalId });
      } else if (objective) {
        await onUpdate(objective.id, formData);
      }
      
      onClose();
    } catch (error) {
      console.error('Failed to save objective:', error);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {mode === 'create' ? 'Create New Objective' : 'Edit Objective'}
      </DialogTitle>
      <DialogContent>
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>Objective Number</InputLabel>
              <Select
                value={formData.objective_number}
                onChange={(e) => setFormData({ ...formData, objective_number: Number(e.target.value) })}
                label="Objective Number"
                disabled={availableNumbers.length === 0}
              >
                {availableNumbers.map((num) => (
                  <MenuItem key={num} value={num}>
                    Objective {num}
                  </MenuItem>
                ))}
              </Select>
              {availableNumbers.length === 0 && (
                <Typography variant="caption" color="error" sx={{ mt: 1 }}>
                  All objective numbers (1-10) are already used for this goal.
                </Typography>
              )}
            </FormControl>
          </Grid>
          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>Schedule Frequency</InputLabel>
              <Select
                value={formData.schedule_frequency}
                onChange={(e) => setFormData({ ...formData, schedule_frequency: e.target.value })}
                label="Schedule Frequency"
              >
                <MenuItem value="">None</MenuItem>
                {SCHEDULE_FREQUENCY_OPTIONS.map((freq) => (
                  <MenuItem key={freq} value={freq}>
                    {freq}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              multiline
              rows={3}
              label="Objective Description"
              value={formData.objective_description}
              onChange={(e) => setFormData({ ...formData, objective_description: e.target.value })}
              required
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Progress Status (Optional)"
              value={formData.progress_status}
              onChange={(e) => setFormData({ ...formData, progress_status: e.target.value })}
              placeholder="e.g., In Progress, Emerging, etc."
            />
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={submitting || !formData.objective_description || (mode === 'create' && availableNumbers.length === 0)}
        >
          {submitting ? <CircularProgress size={20} /> : mode === 'create' ? 'Create' : 'Update'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
