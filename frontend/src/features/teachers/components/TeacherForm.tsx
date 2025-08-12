import React, { useState, useEffect } from 'react';
import {
  Box,
  TextField,
  Button,
  Grid,
  FormControlLabel,
  Switch,
  Divider,
  Typography,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Autocomplete,
  Chip,
  IconButton,
  CircularProgress,
  Backdrop
} from '@mui/material';
import { Save, Cancel, Add, Delete } from '@mui/icons-material';
import { useSchools } from '../../../lib/hooks/useSchools';
import { useTeachers } from '../../../lib/hooks/useTeachers';
import type { Teacher, CreateTeacherRequest, UpdateTeacherRequest, ContactMethod } from '../../../lib/api/types/teachers';
import type { SchoolSummary } from '../../../lib/api/types/schools';

interface TeacherFormProps {
  teacher?: Teacher | null;
  onSubmit: (data: CreateTeacherRequest | UpdateTeacherRequest) => Promise<void>;
  onCancel: () => void;
}

interface SchoolAssignment {
  id?: number; // For existing assignments
  school: SchoolSummary;
  start_date: string;
  end_date?: string;
  is_primary: boolean;
  notes?: string;
  isNew?: boolean; // Flag to track new assignments
  isDeleted?: boolean; // Flag to track deleted assignments
}

export function TeacherForm({ teacher, onSubmit, onCancel }: TeacherFormProps) {
  const { schoolsSummary, fetchSchoolsSummary } = useSchools();
  const { 
    getTeacherSchoolAssignments, 
    createTeacherSchoolAssignment, 
    updateTeacherSchoolAssignment, 
    deleteTeacherSchoolAssignment 
  } = useTeachers();
  
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    title: '',
    department: '',
    room_number: '',
    preferred_contact_method: '' as ContactMethod | '',
    notes: '',
    is_active: true
  });

  const [schoolAssignments, setSchoolAssignments] = useState<SchoolAssignment[]>([]);
  const [originalAssignments, setOriginalAssignments] = useState<SchoolAssignment[]>([]);
  const [selectedSchool, setSelectedSchool] = useState<SchoolSummary | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>('');

  const [showAddAssignment, setShowAddAssignment] = useState(false);
  const [initializing, setInitializing] = useState(false);

  // Single effect to coordinate all initialization
  useEffect(() => {
    const initializeForm = async () => {
      if (teacher) {
        setInitializing(true);
        setError('');
        
        try {
          // Set form data immediately
          setFormData({
            first_name: teacher.first_name || '',
            last_name: teacher.last_name || '',
            email: teacher.email || '',
            phone: teacher.phone || '',
            title: teacher.title || '',
            department: teacher.department || '',
            room_number: teacher.room_number || '',
            preferred_contact_method: (teacher.preferred_contact_method as ContactMethod) || '',
            notes: teacher.notes || '',
            is_active: teacher.is_active ?? true
          });
          
          // Load all required data in parallel
          await Promise.all([
            fetchSchoolsSummary(true),
            loadTeacherSchoolAssignments(teacher.id)
          ]);
          
        } catch (error) {
          console.error('Failed to initialize teacher form:', error);
          setError('Failed to load teacher data');
        } finally {
          setInitializing(false);
        }
      } else {
        // New teacher - just load schools
        setInitializing(true);
        try {
          await fetchSchoolsSummary(true);
          setSchoolAssignments([]);
          setOriginalAssignments([]);
          setShowAddAssignment(false);
        } catch (error) {
          console.error('Failed to load schools:', error);
          setError('Failed to load schools data');
        } finally {
          setInitializing(false);
        }
      }
    };

    initializeForm();
  }, [teacher, fetchSchoolsSummary]);

  const loadTeacherSchoolAssignments = async (teacherId: number) => {
    try {
      const assignments = await getTeacherSchoolAssignments(teacherId);
      
      // Convert API assignments to local format
      const formattedAssignments: SchoolAssignment[] = assignments.map(assignment => {
        // Find the school from schoolsSummary
        const school = schoolsSummary.find(s => s.id === assignment.school_id);
        
        return {
          id: assignment.id,
          school: school || { id: assignment.school_id, name: `School ${assignment.school_id}`, district: '', is_active: true }, // Fallback
          start_date: assignment.start_date || new Date().toISOString().split('T')[0],
          end_date: assignment.end_date || undefined,
          is_primary: assignment.is_primary || false,
          notes: assignment.notes || ''
        };
      });
      
      setSchoolAssignments(formattedAssignments);
      setOriginalAssignments([...formattedAssignments]); // Deep copy for comparison
    } catch (error) {
      console.error('Failed to load teacher school assignments:', error);
      throw error; // Re-throw so the parent can handle it
    }
  };

  const saveSchoolAssignments = async (teacherId: number) => {
    try {
      // Process new assignments
      const newAssignments = schoolAssignments.filter(a => a.isNew && !a.isDeleted);
      console.log(`Processing ${newAssignments.length} new assignments`);
      
      for (const assignment of newAssignments) {
        const assignmentData = {
          teacher_id: teacherId,
          school_id: assignment.school.id,
          start_date: assignment.start_date,
          end_date: assignment.end_date,
          is_primary: assignment.is_primary,
          notes: assignment.notes
        };
        console.log('Creating assignment:', assignmentData);
        const result = await createTeacherSchoolAssignment(assignmentData);
        console.log('Assignment created:', result);
      }

      // Process updated assignments
      for (const assignment of schoolAssignments.filter(a => !a.isNew && !a.isDeleted && a.id)) {
        const original = originalAssignments.find(o => o.id === assignment.id);
        if (original && (
          original.start_date !== assignment.start_date ||
          original.end_date !== assignment.end_date ||
          original.is_primary !== assignment.is_primary ||
          original.notes !== assignment.notes
        )) {
          await updateTeacherSchoolAssignment(assignment.id!, {
            teacher_id: teacherId,
            school_id: assignment.school.id,
            start_date: assignment.start_date,
            end_date: assignment.end_date,
            is_primary: assignment.is_primary,
            notes: assignment.notes
          });
        }
      }

      // Process deleted assignments
      const deletedAssignments = schoolAssignments.filter(a => a.isDeleted && a.id);
      console.log(`Processing ${deletedAssignments.length} deleted assignments`);
      
      for (const assignment of deletedAssignments) {
        console.log('Deleting assignment:', assignment.id);
        await deleteTeacherSchoolAssignment(assignment.id!);
        console.log('Assignment deleted successfully');
      }
    } catch (error) {
      console.error('Failed to save school assignments:', error);
      throw new Error('Failed to save school assignments');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.first_name.trim() || !formData.last_name.trim()) {
      setError('First name and last name are required');
      return;
    }

    setSubmitting(true);
    setError('');

    try {
      // Filter out empty preferred_contact_method
      const submitData = {
        ...formData,
        preferred_contact_method: formData.preferred_contact_method || undefined
      };
      
      // First, save the teacher data
      let savedTeacher: any;
      let teacherId: number;
      
      if (teacher) {
        // For updates, onSubmit returns the updated teacher
        savedTeacher = await onSubmit(submitData);
        teacherId = teacher.id;
      } else {
        // For creates, onSubmit should return the created teacher
        savedTeacher = await onSubmit(submitData);
        teacherId = savedTeacher?.id;
      }
      
      if (teacherId && schoolAssignments.length > 0) {
        // Then save school assignments
        console.log('Saving school assignments for teacher ID:', teacherId);
        await saveSchoolAssignments(teacherId);
        console.log('School assignments saved successfully');
      }
      
      // Close the form on success
      onCancel(); // This will close the modal
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save teacher');
    } finally {
      setSubmitting(false);
    }
  };

  const handleChange = (field: string) => (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSelectChange = (field: string) => (event: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: event.target.value
    }));
  };

  const addSchoolAssignment = () => {
    if (!selectedSchool) return;
    
    // Check if school is already assigned
    if (schoolAssignments.some(assignment => assignment.school.id === selectedSchool.id && !assignment.isDeleted)) {
      setError('This school is already assigned to the teacher');
      return;
    }

    const newAssignment: SchoolAssignment = {
      school: selectedSchool,
      start_date: new Date().toISOString().split('T')[0], // Today's date
      is_primary: schoolAssignments.filter(a => !a.isDeleted).length === 0, // First active assignment is primary
      notes: '',
      isNew: true // Mark as new assignment
    };

    setSchoolAssignments(prev => [...prev, newAssignment]);
    setSelectedSchool(null);
    setShowAddAssignment(false);
    setError('');
  };

  const removeSchoolAssignment = (index: number) => {
    setSchoolAssignments(prev => {
      const assignmentToRemove = prev[index];
      console.log('Removing assignment at index:', index, assignmentToRemove);
      
      // If it's a new assignment, just remove it from the array
      if (assignmentToRemove.isNew) {
        console.log('Removing new assignment from array');
        const updated = prev.filter((_, i) => i !== index);
        // If we removed the primary assignment, make the first one primary
        if (updated.length > 0 && !updated.some(a => a.is_primary && !a.isDeleted)) {
          const firstActive = updated.find(a => !a.isDeleted);
          if (firstActive) firstActive.is_primary = true;
        }
        return updated;
      } else {
        // If it's an existing assignment, mark it as deleted
        console.log('Marking existing assignment as deleted');
        const updated = prev.map((assignment, i) => 
          i === index ? { ...assignment, isDeleted: true } : assignment
        );
        
        // If we deleted the primary assignment, make the first active one primary
        const activeAssignments = updated.filter(a => !a.isDeleted);
        if (activeAssignments.length > 0 && !activeAssignments.some(a => a.is_primary)) {
          activeAssignments[0].is_primary = true;
        }
        
        return updated;
      }
    });
  };

  const updateSchoolAssignment = (index: number, field: keyof SchoolAssignment, value: any) => {
    setSchoolAssignments(prev => prev.map((assignment, i) => {
      if (i === index) {
        // If setting this as primary, unset others
        if (field === 'is_primary' && value) {
          const updated = prev.map(a => ({ ...a, is_primary: false }));
          updated[index] = { ...assignment, [field]: value };
          return updated[index];
        }
        return { ...assignment, [field]: value };
      }
      return assignment;
    }));
  };

  // Show loading screen until all data is ready
  if (initializing) {
    return (
      <Box sx={{ p: 3, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 400 }}>
        <CircularProgress sx={{ color: '#40A8B6', mb: 2 }} size={40} />
        <Typography variant="body1" color="#40A8B6" sx={{ fontWeight: 500 }}>
          {teacher ? 'Loading teacher data...' : 'Loading schools...'}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Please wait while we prepare the form
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3, position: 'relative' }}>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit}>
        <Grid container spacing={3}>
          {/* Basic Information */}
          <Grid item xs={12}>
            <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600, mb: 2 }}>
              Basic Information
            </Typography>
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              required
              label="First Name"
              value={formData.first_name}
              onChange={handleChange('first_name')}
              placeholder="Enter first name"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              required
              label="Last Name"
              value={formData.last_name}
              onChange={handleChange('last_name')}
              placeholder="Enter last name"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Title/Position"
              value={formData.title}
              onChange={handleChange('title')}
              placeholder="e.g., General Education Teacher, Special Education Teacher"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Department"
              value={formData.department}
              onChange={handleChange('department')}
              placeholder="e.g., Elementary, Math, Science, Special Education"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          {/* Contact Information */}
          <Grid item xs={12}>
            <Divider sx={{ my: 2, borderColor: '#e8f4f5' }} />
            <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600, mb: 2 }}>
              Contact Information
            </Typography>
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Email Address"
              type="email"
              value={formData.email}
              onChange={handleChange('email')}
              placeholder="teacher@school.edu"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Phone Number"
              value={formData.phone}
              onChange={handleChange('phone')}
              placeholder="(555) 123-4567"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Room Number"
              value={formData.room_number}
              onChange={handleChange('room_number')}
              placeholder="e.g., 101, A-204, Library"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>Preferred Contact Method</InputLabel>
              <Select
                value={formData.preferred_contact_method}
                onChange={handleSelectChange('preferred_contact_method')}
                label="Preferred Contact Method"
                sx={{
                  '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                    borderColor: '#40A8B6'
                  }
                }}
              >
                <MenuItem value="">No Preference</MenuItem>
                <MenuItem value="email">Email</MenuItem>
                <MenuItem value="phone">Phone Call</MenuItem>
                <MenuItem value="text">Text Message</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          {/* School Assignments */}
          <Grid item xs={12}>
            <Divider sx={{ my: 2, borderColor: '#e8f4f5' }} />
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600 }}>
                School Assignments
                {schoolAssignments.filter(a => !a.isDeleted).length > 0 && (
                  <Chip 
                    label={`${schoolAssignments.filter(a => !a.isDeleted).length} assigned`}
                    size="small"
                    sx={{ ml: 2, bgcolor: '#40A8B6', color: 'white' }}
                  />
                )}
              </Typography>
              {schoolAssignments.filter(a => !a.isDeleted).length > 0 && !showAddAssignment && (
                <Button
                  onClick={() => setShowAddAssignment(true)}
                  variant="outlined"
                  startIcon={<Add />}
                  size="small"
                  sx={{
                    borderColor: '#40A8B6',
                    color: '#40A8B6',
                    '&:hover': {
                      borderColor: '#369aa6',
                      bgcolor: 'rgba(64,168,182,0.1)'
                    },
                    textTransform: 'none',
                    fontWeight: 500
                  }}
                >
                  Add Another
                </Button>
              )}
            </Box>
          </Grid>

          {/* Show dropdown only when adding assignments or no assignments exist */}
          {(showAddAssignment || schoolAssignments.filter(a => !a.isDeleted).length === 0) && (
            <>
              <Grid item xs={12} md={8}>
                <Autocomplete
                  options={schoolsSummary}
                  getOptionLabel={(option) => option.name}
                  value={selectedSchool}
                  onChange={(_, newValue) => setSelectedSchool(newValue)}
                  renderInput={(params) => (
                    <TextField 
                      {...params} 
                      label="Add School Assignment" 
                      placeholder="Select a school to assign..."
                      sx={{
                        '& .MuiOutlinedInput-root': {
                          '&.Mui-focused fieldset': {
                            borderColor: '#40A8B6'
                          }
                        }
                      }}
                    />
                  )}
                  isOptionEqualToValue={(option, value) => option.id === value.id}
                />
              </Grid>

              <Grid item xs={12} md={4}>
                <Box display="flex" gap={1}>
                  <Button
                    onClick={addSchoolAssignment}
                    variant="contained"
                    startIcon={<Add />}
                    disabled={!selectedSchool}
                    sx={{
                      height: '56px',
                      bgcolor: '#40A8B6',
                      '&:hover': {
                        bgcolor: '#369aa6'
                      },
                      textTransform: 'none',
                      fontWeight: 500
                    }}
                  >
                    Add
                  </Button>
                  {showAddAssignment && (
                    <Button
                      onClick={() => {
                        setShowAddAssignment(false);
                        setSelectedSchool(null);
                      }}
                      variant="outlined"
                      sx={{
                        height: '56px',
                        textTransform: 'none',
                        fontWeight: 500
                      }}
                    >
                      Cancel
                    </Button>
                  )}
                </Box>
              </Grid>
            </>
          )}

          {/* Display Current School Assignments */}
          {schoolAssignments.filter(a => !a.isDeleted).length > 0 && (
            <Grid item xs={12}>
              <Typography variant="subtitle2" sx={{ mb: 2, color: '#666' }}>
                Current School Assignments ({schoolAssignments.filter(a => !a.isDeleted).length})
              </Typography>
              
              {schoolAssignments.filter(a => !a.isDeleted).map((assignment, index) => {
                const actualIndex = schoolAssignments.indexOf(assignment);
                return (
                <Box
                  key={index}
                  sx={{
                    p: 2,
                    mb: 2,
                    bgcolor: '#f8f9fa',
                    borderRadius: 2,
                    border: '1px solid #e0e0e0'
                  }}
                >
                  <Grid container spacing={2} alignItems="center">
                    <Grid item xs={12} md={4}>
                      <Box display="flex" alignItems="center" gap={1}>
                        <Typography variant="body1" sx={{ fontWeight: 500 }}>
                          {assignment.school.name}
                        </Typography>
                        {assignment.is_primary && (
                          <Chip 
                            label="Primary" 
                            size="small" 
                            sx={{ 
                              bgcolor: '#40A8B6', 
                              color: 'white',
                              fontSize: '0.75rem'
                            }} 
                          />
                        )}
                      </Box>
                      {assignment.school.district && (
                        <Typography variant="caption" color="text.secondary">
                          {assignment.school.district}
                        </Typography>
                      )}
                    </Grid>
                    
                    <Grid item xs={12} md={3}>
                      <TextField
                        fullWidth
                        label="Start Date"
                        type="date"
                        size="small"
                        value={assignment.start_date}
                        onChange={(e) => updateSchoolAssignment(actualIndex, 'start_date', e.target.value)}
                        InputLabelProps={{ shrink: true }}
                        sx={{
                          '& .MuiOutlinedInput-root': {
                            '&.Mui-focused fieldset': {
                              borderColor: '#40A8B6'
                            }
                          }
                        }}
                      />
                    </Grid>
                    
                    <Grid item xs={12} md={2}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={assignment.is_primary}
                            onChange={(e) => updateSchoolAssignment(actualIndex, 'is_primary', e.target.checked)}
                            size="small"
                            sx={{
                              '& .MuiSwitch-switchBase.Mui-checked': {
                                color: '#40A8B6'
                              },
                              '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                                backgroundColor: '#40A8B6'
                              }
                            }}
                          />
                        }
                        label="Primary"
                        labelPlacement="top"
                        sx={{ m: 0 }}
                      />
                    </Grid>
                    
                    <Grid item xs={12} md={2}>
                      <IconButton
                        onClick={() => removeSchoolAssignment(actualIndex)}
                        size="small"
                        sx={{
                          color: '#f44336',
                          '&:hover': {
                            bgcolor: 'rgba(244,67,54,0.1)'
                          }
                        }}
                        title="Remove Assignment"
                      >
                        <Delete />
                      </IconButton>
                    </Grid>
                    
                    <Grid item xs={12}>
                      <TextField
                        fullWidth
                        label="Assignment Notes"
                        size="small"
                        value={assignment.notes || ''}
                        onChange={(e) => updateSchoolAssignment(actualIndex, 'notes', e.target.value)}
                        placeholder="Optional notes about this assignment..."
                        multiline
                        rows={1}
                        sx={{
                          '& .MuiOutlinedInput-root': {
                            '&.Mui-focused fieldset': {
                              borderColor: '#40A8B6'
                            }
                          }
                        }}
                      />
                    </Grid>
                  </Grid>
                </Box>
                );
              })}
            </Grid>
          )}

          {/* Additional Information */}
          <Grid item xs={12}>
            <Divider sx={{ my: 2, borderColor: '#e8f4f5' }} />
            <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600, mb: 2 }}>
              Additional Information
            </Typography>
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Notes"
              value={formData.notes}
              onChange={handleChange('notes')}
              placeholder="Add any additional notes about the teacher..."
              multiline
              rows={3}
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Switch
                  checked={formData.is_active}
                  onChange={handleChange('is_active')}
                  sx={{
                    '& .MuiSwitch-switchBase.Mui-checked': {
                      color: '#40A8B6'
                    },
                    '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                      backgroundColor: '#40A8B6'
                    }
                  }}
                />
              }
              label="Teacher is active"
            />
          </Grid>
        </Grid>

        <Divider sx={{ my: 3, borderColor: '#e8f4f5' }} />

        {/* Action Buttons */}
        <Box display="flex" justifyContent="flex-end" gap={2}>
          <Button
            onClick={onCancel}
            startIcon={<Cancel />}
            disabled={submitting}
            sx={{ 
              textTransform: 'none',
              fontWeight: 500,
              color: '#666'
            }}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            startIcon={<Save />}
            disabled={submitting || !formData.first_name.trim() || !formData.last_name.trim()}
            sx={{
              bgcolor: '#40A8B6',
              '&:hover': {
                bgcolor: '#369aa6'
              },
              '&:disabled': {
                bgcolor: '#e0e0e0'
              },
              textTransform: 'none',
              fontWeight: 500,
              px: 3
            }}
          >
            {submitting ? 'Saving...' : teacher ? 'Update Teacher' : 'Create Teacher'}
          </Button>
        </Box>
      </form>
    </Box>
  );
}
