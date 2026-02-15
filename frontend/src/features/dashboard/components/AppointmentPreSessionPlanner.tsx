import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  Chip,
  Alert,
  Paper,
  IconButton,
  LinearProgress
} from '@mui/material';
import {
  Save,
  Clear,
  Person,
  Assignment,
  Schedule,
  CheckCircle
} from '@mui/icons-material';
import { format } from 'date-fns';
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query';
import { AppointmentSummary, schedulingApi } from '../../../lib/api/scheduling';
import { useStudentActiveGoals } from '../../../lib/hooks/useStudentGoals';
import { IEPGoalWithObjectives } from '../../../lib/api/types/goals';

interface AppointmentPreSessionPlannerProps {
  selectedAppointment: AppointmentSummary | null;
  onClear: () => void;
}

interface ObjectiveWithNotes {
  objective_id: number;
  goal_id: number;
  objective_description: string;
  goal_description: string;
  pre_session_notes: string;
  planned: boolean;
}

export function AppointmentPreSessionPlanner({
  selectedAppointment,
  onClear
}: AppointmentPreSessionPlannerProps) {
  const [objectivesWithNotes, setObjectivesWithNotes] = useState<ObjectiveWithNotes[]>([]);
  const [hasChanges, setHasChanges] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const loadedAppointmentRef = useRef<number | null>(null);

  const queryClient = useQueryClient();

  // Fetch student goals when appointment is selected
  const { data: studentGoals = [], isLoading: goalsLoading, error: goalsError } = useStudentActiveGoals(
    selectedAppointment?.student_id || 0,
    !!selectedAppointment
  );

  // Fetch existing therapy session data for this appointment
  const { data: existingSessionData, isLoading: sessionLoading } = useQuery({
    queryKey: ['appointment-therapy-session', selectedAppointment?.id],
    queryFn: async () => {
      if (!selectedAppointment?.id) return null;
      try {
        // Get therapy session goals/objectives for this appointment
        const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
        const response = await fetch(`${baseUrl}/api/therapy-sessions/by-appointment/${selectedAppointment.id}`);
        if (response.ok) {
          return await response.json();
        }
        return null;
      } catch (error) {
        console.log('No existing session data found for appointment:', selectedAppointment.id);
        return null;
      }
    },
    enabled: !!selectedAppointment?.id,
    staleTime: 0, // Always fetch fresh data when switching appointments
  });

  // Mutation for saving pre-session notes to therapy session objectives
  const savePreSessionNotesMutation = useMutation({
    mutationFn: async (data: { 
      appointmentId: number; 
      planned_objectives: Array<{
        objective_id: number;
        goal_id: number;
        planned: boolean;
        worked_on: boolean;
        priority: number;
        pre_session_notes?: string;
      }>;
    }) => {
      // Update therapy session objectives directly
      const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/api/therapy-sessions/by-appointment/${data.appointmentId}/objectives`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          objectives: data.planned_objectives
        }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to save pre-session notes');
      }
      
      return response.json();
    },
    onSuccess: () => {
      setSaveStatus('saved');
      setHasChanges(false);
      // Refresh therapy session data
      queryClient.invalidateQueries({ queryKey: ['appointment-therapy-session', selectedAppointment?.id] });
      setTimeout(() => setSaveStatus('idle'), 3000);
    },
    onError: (error) => {
      console.error('Failed to save pre-session notes:', error);
      setSaveStatus('error');
      setTimeout(() => setSaveStatus('idle'), 5000);
    }
  });

  // Load data when appointment changes
  useEffect(() => {
    const appointmentId = selectedAppointment?.id;
    
    // Clear data when no appointment
    if (!appointmentId) {
      setObjectivesWithNotes([]);
      loadedAppointmentRef.current = null;
      setHasChanges(false);
      setSaveStatus('idle');
      return;
    }
    
    // Reset when appointment changes
    if (loadedAppointmentRef.current !== appointmentId) {
      setObjectivesWithNotes([]);
      setHasChanges(false);
      setSaveStatus('idle');
      loadedAppointmentRef.current = appointmentId;
    }
  }, [selectedAppointment?.id]);

  // Load objectives when goals are ready
  useEffect(() => {
    const appointmentId = selectedAppointment?.id;
    
    if (
      appointmentId && 
      studentGoals.length > 0 && 
      !goalsLoading && 
      objectivesWithNotes.length === 0 // Only load if we don't have objectives yet
    ) {
      const allObjectives: ObjectiveWithNotes[] = [];
      
      studentGoals.forEach(goal => {
        if (goal.objectives) {
          goal.objectives.forEach(objective => {
            allObjectives.push({
              objective_id: objective.id,
              goal_id: goal.id,
              objective_description: objective.objective_description,
              goal_description: goal.goal_description,
              pre_session_notes: '',
              planned: false
            });
          });
        }
      });
      
      setObjectivesWithNotes(allObjectives);
    }
  }, [selectedAppointment?.id, studentGoals, goalsLoading, objectivesWithNotes.length]);

  // Update with session data when available
  useEffect(() => {
    if (
      !sessionLoading && 
      existingSessionData?.objectives && 
      objectivesWithNotes.length > 0 &&
      selectedAppointment?.id === loadedAppointmentRef.current
    ) {
      // Always load session data when it becomes available - don't check for existing notes
      // since we reset objectives when switching appointments
      setObjectivesWithNotes(prev => 
        prev.map(obj => {
          const existingObjective = existingSessionData.objectives?.find(
            (sessionObj: any) => sessionObj.objective_id === obj.objective_id
          );
          
          if (existingObjective?.pre_session_notes) {
            return {
              ...obj,
              pre_session_notes: existingObjective.pre_session_notes,
              planned: true
            };
          }
          return obj;
        })
      );
    }
  }, [sessionLoading, existingSessionData, selectedAppointment?.id, objectivesWithNotes.length]);

  const updateObjectiveNotes = (objectiveId: number, notes: string) => {
    setObjectivesWithNotes(prev => 
      prev.map(obj => 
        obj.objective_id === objectiveId 
          ? { 
              ...obj, 
              pre_session_notes: notes,
              planned: notes.trim().length > 0 // Automatically set planned based on notes
            }
          : obj
      )
    );
    setHasChanges(true);
    setSaveStatus('idle');
  };





  const handleSave = () => {
    if (!selectedAppointment || !hasChanges) return;

    setSaveStatus('saving');
    
    const plannedObjectives = objectivesWithNotes
      .filter(obj => obj.pre_session_notes.trim().length > 0) // Only include objectives with notes
      .map(obj => ({
        objective_id: obj.objective_id,
        goal_id: obj.goal_id,
        planned: true, // Always true since we're filtering by notes
        worked_on: false,
        priority: 1,
        pre_session_notes: obj.pre_session_notes.trim()
      }));

    savePreSessionNotesMutation.mutate({
      appointmentId: selectedAppointment.id,
      planned_objectives: plannedObjectives
    });
  };

  const handleClear = () => {
    setObjectivesWithNotes([]);
    setHasChanges(false);
    setSaveStatus('idle');
    onClear();
  };

  // Reset state when appointment changes
  useEffect(() => {
    if (selectedAppointment) {
      setHasChanges(false);
      setSaveStatus('idle');
    }
  }, [selectedAppointment?.id]);

  // Color palette for objective grouping - grays and green tones based on #41AAB7
  const objectiveColors = [
    { bg: '#f0f8f9', border: '#41AAB7', text: '#2d7a85' }, // Primary teal
    { bg: '#f5f5f5', border: '#757575', text: '#424242' }, // Medium gray
    { bg: '#e8f5e8', border: '#66BB6A', text: '#388E3C' }, // Light green
    { bg: '#fafafa', border: '#9E9E9E', text: '#616161' }, // Light gray
    { bg: '#e0f2e6', border: '#4CAF50', text: '#2E7D32' }, // Green
    { bg: '#f3f3f3', border: '#8D8D8D', text: '#525252' }, // Gray
    { bg: '#e6f3f7', border: '#26A69A', text: '#00695C' }, // Teal variant
    { bg: '#f7f7f7', border: '#BDBDBD', text: '#757575' }, // Lighter gray
  ];

  // Create flat list of objectives with colors and goal info
  const allObjectivesWithColors = useMemo(() => {
    const allObjectives: (ObjectiveWithNotes & { 
      goal_description: string; 
      goal_number?: string;
      color: { bg: string; border: string; text: string };
      objectiveIndex: number;
    })[] = [];
    
    // Sort goals by goal_number in ascending order
    const sortedGoals = [...studentGoals].sort((a, b) => {
      const goalNumA = a.goal_number ? parseInt(a.goal_number) : 0;
      const goalNumB = b.goal_number ? parseInt(b.goal_number) : 0;
      return goalNumA - goalNumB;
    });
    
    sortedGoals.forEach((goal, goalIndex) => {
      const goalColor = objectiveColors[goalIndex % objectiveColors.length];
      
      if (goal.objectives) {
        goal.objectives.forEach((_, objIndex) => {
          const objectiveData = objectivesWithNotes.find(obj => 
            obj.goal_id === goal.id && obj.objective_description === goal.objectives![objIndex].objective_description
          );
          if (objectiveData) {
            allObjectives.push({
              ...objectiveData,
              goal_description: goal.goal_description,
              goal_number: goal.goal_number,
              color: goalColor, // Same color for all objectives in this goal
              objectiveIndex: objIndex + 1
            });
          }
        });
      }
    });
    
    return allObjectives;
  }, [objectivesWithNotes, studentGoals, objectiveColors]);

  if (!selectedAppointment) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <Assignment sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
        <Typography variant="body1" color="text.secondary" gutterBottom>
          Select an appointment from the calendar
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Click on any appointment to plan pre-session notes for objectives
        </Typography>
      </Box>
    );
  }

      return (
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* Compact Sticky Header */}
        <Box sx={{ 
          position: 'sticky', 
          top: 0, 
          zIndex: 10, 
          bgcolor: 'background.default',
          borderBottom: '1px solid',
          borderColor: 'divider',
          p: 1.5,
          mb: 1
        }}>
          {/* Single Row with all info */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1, minWidth: 0 }}>
              <Person sx={{ color: 'primary.main', fontSize: 20 }} />
              <Typography variant="body2" fontWeight="600" sx={{ flexShrink: 0 }}>
                {selectedAppointment.student_name}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ 
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                minWidth: 0
              }}>
                {format(new Date(selectedAppointment.start_datetime), 'MMM d • h:mm a')} • {selectedAppointment.duration_minutes}min
              </Typography>
            </Box>
            
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexShrink: 0 }}>
              {saveStatus === 'saved' && (
                <Chip
                  icon={<CheckCircle />}
                  label="Saved"
                  color="success"
                  size="small"
                  sx={{ fontSize: '0.7rem', height: 24 }}
                />
              )}
              
              {hasChanges && saveStatus === 'idle' && (
                <Typography variant="caption" color="warning.main" sx={{ fontSize: '0.7rem' }}>
                  Unsaved
                </Typography>
              )}
              
              <Button
                variant="contained"
                size="small"
                startIcon={<Save />}
                onClick={handleSave}
                disabled={!hasChanges || saveStatus === 'saving'}
                sx={{ 
                  minWidth: 'auto', 
                  px: 1.5,
                  fontSize: '0.75rem',
                  height: 28
                }}
              >
                {saveStatus === 'saving' ? 'Saving...' : 'Save'}
              </Button>
              
              <IconButton size="small" onClick={handleClear}>
                <Clear fontSize="small" />
              </IconButton>
            </Box>
          </Box>

          {/* Progress bar and errors - compact */}
          {saveStatus === 'saving' && <LinearProgress sx={{ height: 2 }} />}
          
          {goalsError && (
            <Alert severity="error" sx={{ py: 0.5, fontSize: '0.75rem' }}>
              Failed to load goals
            </Alert>
          )}

          {saveStatus === 'error' && (
            <Alert severity="error" sx={{ py: 0.5, fontSize: '0.75rem' }}>
              Failed to save notes
            </Alert>
          )}

          {/* Loading State - compact */}
          {(goalsLoading || sessionLoading) && (
            <Box sx={{ textAlign: 'center', py: 1 }}>
              <LinearProgress sx={{ height: 2, mb: 1 }} />
              <Typography variant="caption" color="text.secondary">
                {goalsLoading ? 'Loading goals...' : 'Loading session data...'}
              </Typography>
            </Box>
          )}
        </Box>

        {/* Scrollable Objectives Section */}
        <Box sx={{ 
          flex: 1, 
          overflow: 'auto',
          '&::-webkit-scrollbar': {
            width: '8px',
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
          {/* Individual Objective Cards */}
          {!goalsLoading && !sessionLoading && allObjectivesWithColors.length === 0 && (
            <Alert severity="info">
              No active IEP goals found for this student.
            </Alert>
          )}

          {!goalsLoading && !sessionLoading && allObjectivesWithColors.length > 0 && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pr: 1, pt: 1 }}>
              {allObjectivesWithColors.map((objective) => (
                <Paper 
                  key={objective.objective_id} 
                  variant="outlined" 
                  sx={{ 
                    p: 2.5,
                    bgcolor: objective.color.bg,
                    border: `1px solid ${objective.color.border}`,
                    borderLeft: `4px solid ${objective.color.border}`,
                    borderRadius: 2,
                    transition: 'all 0.2s ease',
                    '&:hover': {
                      boxShadow: 2,
                      transform: 'translateY(-1px)'
                    }
                  }}
                >
                  {/* Goal Row */}
                  <Box sx={{ 
                    mb: 1.5,
                    overflow: 'hidden'
                  }}>
                    <Typography variant="body2" sx={{ 
                      color: objective.color.text,
                      fontWeight: 400,
                      fontSize: '0.95rem',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      lineHeight: 1.2
                    }}>
                      <span style={{ fontWeight: 700 }}>Goal {objective.goal_number || '?'}</span>: <span style={{ fontStyle: 'italic' }}>{objective.goal_description}</span>
                    </Typography>
                  </Box>

                  {/* Header Row */}
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1.5, mb: 2, ml: 1.5 }}>
                    {/* Objective Description */}
                    <Typography variant="body2" sx={{ 
                      flex: 1,
                      color: objective.color.text,
                      fontWeight: 400,
                      lineHeight: 1.4,
                      fontSize: '0.9rem'
                    }}>
                      <span style={{ fontWeight: 700 }}>Objective {objective.objectiveIndex}</span>: {objective.objective_description}
                    </Typography>
                    
                    {/* Planned Indicator */}
                    {objective.planned && (
                      <Chip
                        label="Planned"
                        size="small"
                        color="primary"
                        sx={{ 
                          fontSize: '0.7rem',
                          height: 24,
                          flexShrink: 0
                        }}
                      />
                    )}
                  </Box>
                  
                  {/* Notes Field */}
                  <Box sx={{ ml: 1.5 }}>
                    <TextField
                      fullWidth
                      multiline
                      rows={2}
                      size="small"
                      placeholder="Add pre-session notes for this objective..."
                      value={objective.pre_session_notes}
                      onChange={(e) => updateObjectiveNotes(objective.objective_id, e.target.value)}
                      sx={{ 
                        '& .MuiOutlinedInput-root': {
                          bgcolor: 'rgba(255, 255, 255, 0.8)',
                          '&:hover .MuiOutlinedInput-notchedOutline': {
                            borderColor: objective.color.border,
                          },
                          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                            borderColor: objective.color.border,
                          },
                        }
                      }}
                    />
                  </Box>
                </Paper>
              ))}
            </Box>
          )}
        </Box>
      </Box>
    );
}
