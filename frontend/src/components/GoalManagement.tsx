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
  Alert,
  CircularProgress,
  IconButton,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow
} from '@mui/material';
import {
  Add,
  Edit,
  Delete,
  ExpandMore,
  TrackChanges
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

  const getGoalCategoryLabel = (goal: IEPGoal) => {
    if (goal.goal_category_name) return goal.goal_category_name;
    const matchedCategory = goalCategories.find((category) => category.id === goal.goal_category_id);
    return matchedCategory?.name || '-';
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
      {/* Error Alert */}
      {error && (
        <Alert severity="error" onClose={clearError} sx={{ mb: 2, flexShrink: 0 }}>
          {error}
        </Alert>
      )}

      {/* Goals Grid - Scrollable */}
      <Box sx={{ flex: 1, overflow: 'auto', minHeight: 0, pb: 2 }}>
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
        <Card sx={{ borderRadius: 2, border: '1px solid #e0e0e0', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', p: 1.5, borderBottom: '1px solid #e8f4f5' }}>
            <Typography variant="subtitle1" sx={{ color: '#40A8B6', fontWeight: 700 }}>
              Annual Goals {studentName && `- ${studentName}`}
            </Typography>
            <Button
              variant="contained"
              size="small"
              startIcon={<Add />}
              onClick={handleCreateGoal}
              sx={{ bgcolor: '#40A8B6', '&:hover': { bgcolor: '#369aa6' }, textTransform: 'none', fontWeight: 500 }}
            >
              Add Goal
            </Button>
          </Box>
          <TableContainer sx={{ maxHeight: 520 }}>
            <Table stickyHeader size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ width: 56 }} />
                  <TableCell sx={{ fontWeight: 700 }}>Annual Goal</TableCell>
                  <TableCell sx={{ fontWeight: 700, width: 160 }}>Category</TableCell>
                  <TableCell sx={{ fontWeight: 700, width: 110 }}>Objectives</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700, width: 170 }}>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {goals.map((goal) => (
                  <React.Fragment key={goal.id}>
                    <TableRow hover>
                      <TableCell>
                        <IconButton size="small" onClick={() => setExpandedGoal(expandedGoal === goal.id ? null : goal.id)}>
                          <ExpandMore
                            sx={{
                              color: '#40A8B6',
                              transform: expandedGoal === goal.id ? 'rotate(180deg)' : 'rotate(0deg)',
                              transition: 'transform 0.2s ease'
                            }}
                          />
                        </IconButton>
                      </TableCell>
                      <TableCell>
                        <Typography sx={{ fontWeight: 600 }}>
                          {goal.goal_number ? `Annual Goal ${goal.goal_number}: ` : ''}
                          {goal.goal_description.length > 115
                            ? `${goal.goal_description.substring(0, 115)}...`
                            : goal.goal_description}
                        </Typography>
                      </TableCell>
                      <TableCell>{getGoalCategoryLabel(goal)}</TableCell>
                      <TableCell>{goal.objectives?.length || 0}</TableCell>
                      <TableCell align="right">
                        <IconButton size="small" onClick={() => handleEditGoal(goal)} sx={{ color: '#40A8B6' }} title="Edit Goal">
                          <Edit fontSize="small" />
                        </IconButton>
                        <IconButton size="small" onClick={() => handleDeleteGoal(goal.id)} sx={{ color: '#f44336' }} title="Delete Goal">
                          <Delete fontSize="small" />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                    {expandedGoal === goal.id && (
                      <TableRow>
                        <TableCell colSpan={5} sx={{ bgcolor: '#fafbfc' }}>
                          <Box sx={{ py: 1 }}>
                            <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                              <Typography variant="subtitle2" sx={{ color: '#40A8B6', fontWeight: 700 }}>
                                Objectives
                              </Typography>
                              <Button
                                variant="outlined"
                                size="small"
                                startIcon={<Add />}
                                onClick={() => handleCreateObjective(goal.id)}
                                sx={{ borderColor: '#40A8B6', color: '#40A8B6', textTransform: 'none' }}
                              >
                                Add Objective
                              </Button>
                            </Box>
                            {!goal.objectives || goal.objectives.length === 0 ? (
                              <Typography color="text.secondary">No objectives yet for this annual goal.</Typography>
                            ) : (
                              <TableContainer sx={{ border: '1px solid #e8f4f5', borderRadius: 1, bgcolor: 'white' }}>
                                <Table size="small">
                                  <TableHead>
                                    <TableRow>
                                      <TableCell sx={{ fontWeight: 700, width: 90 }}>Obj #</TableCell>
                                      <TableCell sx={{ fontWeight: 700 }}>Objective Description</TableCell>
                                      <TableCell sx={{ fontWeight: 700, width: 140 }}>Frequency</TableCell>
                                      <TableCell sx={{ fontWeight: 700, width: 110 }}>Entries</TableCell>
                                      <TableCell align="right" sx={{ fontWeight: 700, width: 90 }}>Actions</TableCell>
                                    </TableRow>
                                  </TableHead>
                                  <TableBody>
                                    {goal.objectives.map((objective) => (
                                      <TableRow key={objective.id} hover>
                                        <TableCell>Objective {objective.objective_number}</TableCell>
                                        <TableCell>{objective.objective_description}</TableCell>
                                        <TableCell>{objective.schedule_frequency || '-'}</TableCell>
                                        <TableCell>{objective.progress_count}</TableCell>
                                        <TableCell align="right">
                                          <IconButton size="small" onClick={() => handleEditObjective(objective, goal.id)} sx={{ mr: 0.5, color: '#40A8B6' }}>
                                            <Edit fontSize="small" />
                                          </IconButton>
                                          <IconButton size="small" onClick={() => handleDeleteObjective(objective.id)} sx={{ color: '#f44336' }}>
                                            <Delete fontSize="small" />
                                          </IconButton>
                                        </TableCell>
                                      </TableRow>
                                    ))}
                                  </TableBody>
                                </Table>
                              </TableContainer>
                            )}
                          </Box>
                        </TableCell>
                      </TableRow>
                    )}
                  </React.Fragment>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Card>
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
