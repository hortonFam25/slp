import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Grid,
  CircularProgress,
  Alert,
  Stack,
  Chip,
  Divider,
  MenuItem,
  FormControl,
  InputLabel,
  Select,
  FormHelperText,
  FormControlLabel,
  Checkbox,
  IconButton,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { Save, Edit, Cancel, Archive, Unarchive, Add, Delete } from '@mui/icons-material';
import { Student, studentsApi, UpdateStudentRequest, StudentEligibility, EligibilityCategory } from '../../lib/api/students';
import { teachersApi, TeacherSummary } from '../../lib/api/teachers';
import { eligibilitiesApi, CreateStudentEligibilityRequest } from '../../lib/api/eligibilities';

interface StudentBasicInfoProps {
  student: Student | null;
  loading: boolean;
  onUpdate: (student: Student) => void;
}

export function StudentBasicInfo({ student, loading, onUpdate }: StudentBasicInfoProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState<UpdateStudentRequest>({});
  const [teachers, setTeachers] = useState<TeacherSummary[]>([]);
  const [teachersLoading, setTeachersLoading] = useState(false);
  
  // Eligibility management state
  const [eligibilityCategories, setEligibilityCategories] = useState<EligibilityCategory[]>([]);
  const [showAddEligibility, setShowAddEligibility] = useState(false);
  const [eligibilityForm, setEligibilityForm] = useState({
    eligibility_category_id: '',
    start_date: new Date().toISOString().split('T')[0],
    end_date: '',
    is_primary: false,
    notes: ''
  });

  // Initialize form data when student changes
  useEffect(() => {
    if (student) {
      setFormData({
        first: student.first,
        last: student.last,
        uic: student.uic || '',
        grade_level: student.grade_level || '',
        teacher_name: student.teacher_name || '',
        case_manager: student.case_manager || '',
        enrollment_status: student.enrollment_status,
        date_of_birth: student.date_of_birth || '',
        // IEP and Evaluation dates
        iep_date: student.iep_date || '',
        annual_review_due_date: student.annual_review_due_date || '',
        reevaluation_due_date: student.reevaluation_due_date || '',
        iep_meeting_date: student.iep_meeting_date || '',
        initial_evaluation_date: student.initial_evaluation_date || '',
        eligibility_determination_date: student.eligibility_determination_date || '',
        school_id: student.school_id,
        is_archived: student.is_archived,
      });
    }
  }, [student]);

  const loadTeachers = async () => {
    try {
      setTeachersLoading(true);
      const teacherData = await teachersApi.getTeachersSummary(true); // Get active teachers only
      setTeachers(teacherData);
    } catch (err) {
      console.error('Failed to load teachers:', err);
      setError('Failed to load teachers list');
    } finally {
      setTeachersLoading(false);
    }
  };

  const loadEligibilityCategories = async () => {
    try {
      const categories = await eligibilitiesApi.getEligibilityCategories(true);
      setEligibilityCategories(categories);
    } catch (err) {
      console.error('Failed to load eligibility categories:', err);
      setError('Failed to load eligibility categories');
    }
  };

  const handleEdit = async () => {
    setIsEditing(true);
    setError(null);
    await loadTeachers();
    await loadEligibilityCategories();
  };

  const handleCancel = () => {
    setIsEditing(false);
    setError(null);
    // Reset form data to original values
    if (student) {
      setFormData({
        first: student.first,
        last: student.last,
        uic: student.uic || '',
        grade_level: student.grade_level || '',
        teacher_name: student.teacher_name || '',
        case_manager: student.case_manager || '',
        enrollment_status: student.enrollment_status,
        date_of_birth: student.date_of_birth || '',
        // IEP and Evaluation dates
        iep_date: student.iep_date || '',
        annual_review_due_date: student.annual_review_due_date || '',
        reevaluation_due_date: student.reevaluation_due_date || '',
        iep_meeting_date: student.iep_meeting_date || '',
        initial_evaluation_date: student.initial_evaluation_date || '',
        eligibility_determination_date: student.eligibility_determination_date || '',
        school_id: student.school_id,
        is_archived: student.is_archived,
      });
    }
  };

  const handleSave = async () => {
    if (!student) return;

    try {
      setSaving(true);
      setError(null);

      // Process form data to handle empty date strings
      const processedFormData = { ...formData };
      
      // Convert empty date strings to undefined (becomes null in JSON)
      const dateFields = [
        'date_of_birth',
        'iep_date', 
        'annual_review_due_date',
        'reevaluation_due_date',
        'iep_meeting_date',
        'initial_evaluation_date',
        'eligibility_determination_date'
      ];
      
      dateFields.forEach(field => {
        if (processedFormData[field] === '') {
          processedFormData[field] = undefined;
        }
      });

      const updatedStudent = await studentsApi.updateStudent(student.id, processedFormData);
      onUpdate(updatedStudent);
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update student');
    } finally {
      setSaving(false);
    }
  };

  const updateFormField = (field: keyof UpdateStudentRequest, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleArchive = async () => {
    if (!student) return;
    
    const confirmMessage = student.is_archived 
      ? 'Are you sure you want to unarchive this student? They will appear in active student lists again.'
      : 'Are you sure you want to archive this student? They will be hidden from active student lists but their data will be preserved.';
    
    if (window.confirm(confirmMessage)) {
      try {
        setSaving(true);
        setError(null);
        
        const updatedStudent = student.is_archived 
          ? await studentsApi.unarchiveStudent(student.id)
          : await studentsApi.archiveStudent(student.id);
          
        onUpdate(updatedStudent);
      } catch (err) {
        setError(err instanceof Error ? err.message : `Failed to ${student.is_archived ? 'unarchive' : 'archive'} student`);
      } finally {
        setSaving(false);
      }
    }
  };

  const handleAddEligibility = async () => {
    if (!student || !eligibilityForm.eligibility_category_id) return;

    try {
      setSaving(true);
      setError(null);

      const payload: CreateStudentEligibilityRequest = {
        student_id: student.id,
        eligibility_category_id: parseInt(eligibilityForm.eligibility_category_id),
        start_date: eligibilityForm.start_date,
        end_date: eligibilityForm.end_date || undefined,
        is_primary: eligibilityForm.is_primary,
        notes: eligibilityForm.notes || undefined
      };

      await eligibilitiesApi.createStudentEligibility(payload);
      
      // Refresh student data to show new eligibility
      const updatedStudent = await studentsApi.getStudent(student.id);
      onUpdate(updatedStudent);
      
      // Reset form and hide add section
      setEligibilityForm({
        eligibility_category_id: '',
        start_date: new Date().toISOString().split('T')[0],
        end_date: '',
        is_primary: false,
        notes: ''
      });
      setShowAddEligibility(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add eligibility');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteEligibility = async (eligibilityId: number) => {
    if (!student) return;

    if (window.confirm('Are you sure you want to remove this eligibility? This action cannot be undone.')) {
      try {
        setSaving(true);
        setError(null);

        await eligibilitiesApi.deleteStudentEligibility(eligibilityId);
        
        // Refresh student data to remove eligibility
        const updatedStudent = await studentsApi.getStudent(student.id);
        onUpdate(updatedStudent);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to remove eligibility');
      } finally {
        setSaving(false);
      }
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="300px">
        <CircularProgress />
      </Box>
    );
  }

  if (!student) {
    return (
      <Alert severity="error">
        Student information could not be loaded.
      </Alert>
    );
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Not provided';
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <Box sx={{ 
      height: 'calc(100vh - 300px)', // Account for dialog header, tabs, and buttons
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      mx: isMobile ? -2 : -3, // Counteract TabPanel padding
      mt: isMobile ? -2 : -3  // Counteract TabPanel padding
    }}>
      {/* Fixed Header Section - Completely Outside Scrollable Area */}
      <Box sx={{ 
        flexShrink: 0,
        backgroundColor: 'background.default',
        borderBottom: 1,
        borderColor: 'divider',
        p: isMobile ? 2 : 3,
        zIndex: 1
      }}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Box sx={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: isMobile ? 'flex-start' : 'center',
          flexDirection: isMobile ? 'column' : 'row',
          gap: isMobile ? 2 : 0
        }}>
          <Box>
            <Typography 
              variant={isMobile ? "h6" : "h5"}
              sx={{ fontSize: isMobile ? '1.2rem' : '1.5rem' }}
            >
              Basic Information
            </Typography>
            {student?.is_archived && (
              <Chip 
                label="ARCHIVED" 
                color="warning" 
                size="small" 
                sx={{ mt: 1 }}
              />
            )}
          </Box>
          {!isEditing ? (
            <Stack direction={isMobile ? "column" : "row"} spacing={1} sx={{ width: isMobile ? '100%' : 'auto' }}>
              <Button
                variant="outlined"
                color={student?.is_archived ? "success" : "warning"}
                startIcon={student?.is_archived ? <Unarchive /> : <Archive />}
                onClick={handleArchive}
                disabled={saving}
                fullWidth={isMobile}
                size={isMobile ? "medium" : "large"}
              >
                {student?.is_archived ? 'Unarchive' : 'Archive'}
              </Button>
              <Button
                variant="outlined"
                startIcon={<Edit />}
                onClick={handleEdit}
                fullWidth={isMobile}
                size={isMobile ? "medium" : "large"}
              >
                Edit
              </Button>
            </Stack>
          ) : (
            <Stack direction={isMobile ? "column" : "row"} spacing={1} sx={{ width: isMobile ? '100%' : 'auto' }}>
              <Button
                variant="outlined"
                startIcon={<Cancel />}
                onClick={handleCancel}
                fullWidth={isMobile}
                size={isMobile ? "medium" : "large"}
                disabled={saving}
              >
                Cancel
              </Button>
              <Button
                variant="contained"
                startIcon={<Save />}
                onClick={handleSave}
                disabled={saving || !formData.first?.trim() || !formData.last?.trim()}
                fullWidth={isMobile}
                size={isMobile ? "medium" : "large"}
              >
                {saving ? 'Saving...' : 'Save'}
              </Button>
            </Stack>
          )}
        </Box>
      </Box>

      {/* Content Area - Fixed Height Card */}
      <Box sx={{ 
        flex: 1, 
        overflow: 'hidden',
        p: isMobile ? 2 : 3
      }}>
        <Card sx={{ 
          height: '100%',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <CardContent sx={{
            flex: 1,
            overflow: 'auto',
            '&::-webkit-scrollbar': {
              width: '8px',
            },
            '&::-webkit-scrollbar-track': {
              background: '#f1f1f1',
            },
            '&::-webkit-scrollbar-thumb': {
              background: '#c1c1c1',
              borderRadius: '4px',
            },
            '&::-webkit-scrollbar-thumb:hover': {
              background: '#a1a1a1',
            },
          }}>
            <Grid container spacing={3}>
            <Grid item xs={12} sm={6}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="First Name"
                  required
                  value={formData.first || ''}
                  onChange={(e) => updateFormField('first', e.target.value)}
                  disabled={saving}
                />
              ) : (
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    First Name
                  </Typography>
                  <Typography variant="body1">
                    {student.first}
                  </Typography>
                </Box>
              )}
            </Grid>

            <Grid item xs={12} sm={6}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="Last Name"
                  required
                  value={formData.last || ''}
                  onChange={(e) => updateFormField('last', e.target.value)}
                  disabled={saving}
                />
              ) : (
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Last Name
                  </Typography>
                  <Typography variant="body1">
                    {student.last}
                  </Typography>
                </Box>
              )}
            </Grid>

            <Grid item xs={12} sm={6}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="UIC (Legacy System ID)"
                  value={formData.uic || ''}
                  onChange={(e) => updateFormField('uic', e.target.value)}
                  disabled={saving}
                  helperText="Optional: For mapping to legacy IEP system"
                />
              ) : (
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    UIC (Legacy System ID)
                  </Typography>
                  <Typography variant="body1">
                    {student.uic || 'Not provided'}
                  </Typography>
                </Box>
              )}
            </Grid>

            <Grid item xs={12} sm={6}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="Grade Level"
                  value={formData.grade_level || ''}
                  onChange={(e) => updateFormField('grade_level', e.target.value)}
                  disabled={saving}
                  placeholder="e.g., K, 1, 2, 3..."
                />
              ) : (
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Grade Level
                  </Typography>
                  <Typography variant="body1">
                    {student.grade_level || 'Not provided'}
                  </Typography>
                </Box>
              )}
            </Grid>

            <Grid item xs={12} sm={6}>
              {isEditing ? (
                <FormControl fullWidth disabled={saving || teachersLoading}>
                  <InputLabel>Teacher</InputLabel>
                  <Select
                    value={formData.teacher_name || ''}
                    onChange={(e) => updateFormField('teacher_name', e.target.value)}
                    label="Teacher"
                  >
                    <MenuItem value="">
                      <em>-- Select Teacher --</em>
                    </MenuItem>
                    {teachers.map((teacher) => (
                      <MenuItem key={teacher.id} value={teacher.display_name}>
                        {teacher.display_name}
                        {teacher.title ? ` (${teacher.title})` : ''}
                      </MenuItem>
                    ))}
                  </Select>
                  <FormHelperText>
                    {teachersLoading ? 'Loading teachers...' : 'Select a teacher from the list'}
                  </FormHelperText>
                </FormControl>
              ) : (
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Teacher
                  </Typography>
                  <Typography variant="body1">
                    {student.teacher_name || 'Not assigned'}
                  </Typography>
                </Box>
              )}
            </Grid>

            <Grid item xs={12} sm={6}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="Case Manager"
                  value={formData.case_manager || ''}
                  onChange={(e) => updateFormField('case_manager', e.target.value)}
                  disabled={saving}
                />
              ) : (
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Case Manager
                  </Typography>
                  <Typography variant="body1">
                    {student.case_manager || 'Not provided'}
                  </Typography>
                </Box>
              )}
            </Grid>

            <Grid item xs={12} sm={6}>
              {isEditing ? (
                <TextField
                  fullWidth
                  select
                  label="Enrollment Status"
                  value={formData.enrollment_status || 'Active'}
                  onChange={(e) => updateFormField('enrollment_status', e.target.value)}
                  disabled={saving}
                  SelectProps={{ native: true }}
                >
                  <option value="Active">Active</option>
                  <option value="Inactive">Inactive</option>
                  <option value="Transferred">Transferred</option>
                </TextField>
              ) : (
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Enrollment Status
                  </Typography>
                  <Chip
                    label={student.enrollment_status}
                    color={student.enrollment_status === 'Active' ? 'success' : 'default'}
                    size="small"
                  />
                </Box>
              )}
            </Grid>

            <Grid item xs={12} sm={6}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="Date of Birth"
                  type="date"
                  value={formData.date_of_birth || ''}
                  onChange={(e) => updateFormField('date_of_birth', e.target.value)}
                  disabled={saving}
                  InputLabelProps={{ shrink: true }}
                />
              ) : (
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Date of Birth
                  </Typography>
                  <Typography variant="body1">
                    {formatDate(student.date_of_birth)}
                  </Typography>
                </Box>
              )}
            </Grid>
          </Grid>

          <Divider sx={{ my: 3 }} />

          <Typography variant="subtitle1" gutterBottom>
            IEP & Evaluation Dates
          </Typography>
          
          <Grid container spacing={3}>
            <Grid item xs={12} sm={6}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="IEP Date"
                  type="date"
                  value={formData.iep_date || ''}
                  onChange={(e) => updateFormField('iep_date', e.target.value)}
                  disabled={saving}
                  InputLabelProps={{ shrink: true }}
                  helperText="Current IEP effective date"
                />
              ) : (
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    IEP Date
                  </Typography>
                  <Typography variant="body1">
                    {formatDate(student.iep_date)}
                  </Typography>
                </Box>
              )}
            </Grid>

            <Grid item xs={12} sm={6}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="Annual Review Due Date"
                  type="date"
                  value={formData.annual_review_due_date || ''}
                  onChange={(e) => updateFormField('annual_review_due_date', e.target.value)}
                  disabled={saving}
                  InputLabelProps={{ shrink: true }}
                  helperText="Next annual IEP review due"
                />
              ) : (
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Annual Review Due Date
                  </Typography>
                  <Typography variant="body1">
                    {formatDate(student.annual_review_due_date)}
                  </Typography>
                </Box>
              )}
            </Grid>

            <Grid item xs={12} sm={6}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="Reevaluation Due Date"
                  type="date"
                  value={formData.reevaluation_due_date || ''}
                  onChange={(e) => updateFormField('reevaluation_due_date', e.target.value)}
                  disabled={saving}
                  InputLabelProps={{ shrink: true }}
                  helperText="Next reevaluation due"
                />
              ) : (
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Reevaluation Due Date
                  </Typography>
                  <Typography variant="body1">
                    {formatDate(student.reevaluation_due_date)}
                  </Typography>
                </Box>
              )}
            </Grid>

            <Grid item xs={12} sm={6}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="IEP Meeting Date"
                  type="date"
                  value={formData.iep_meeting_date || ''}
                  onChange={(e) => updateFormField('iep_meeting_date', e.target.value)}
                  disabled={saving}
                  InputLabelProps={{ shrink: true }}
                  helperText="Last or next IEP meeting"
                />
              ) : (
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    IEP Meeting Date
                  </Typography>
                  <Typography variant="body1">
                    {formatDate(student.iep_meeting_date)}
                  </Typography>
                </Box>
              )}
            </Grid>

            <Grid item xs={12} sm={6}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="Initial Evaluation Date"
                  type="date"
                  value={formData.initial_evaluation_date || ''}
                  onChange={(e) => updateFormField('initial_evaluation_date', e.target.value)}
                  disabled={saving}
                  InputLabelProps={{ shrink: true }}
                  helperText="Date of first evaluation"
                />
              ) : (
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Initial Evaluation Date
                  </Typography>
                  <Typography variant="body1">
                    {formatDate(student.initial_evaluation_date)}
                  </Typography>
                </Box>
              )}
            </Grid>

            <Grid item xs={12} sm={6}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="Eligibility Determination Date"
                  type="date"
                  value={formData.eligibility_determination_date || ''}
                  onChange={(e) => updateFormField('eligibility_determination_date', e.target.value)}
                  disabled={saving}
                  InputLabelProps={{ shrink: true }}
                  helperText="Date eligibility was determined"
                />
              ) : (
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Eligibility Determination Date
                  </Typography>
                  <Typography variant="body1">
                    {formatDate(student.eligibility_determination_date)}
                  </Typography>
                </Box>
              )}
            </Grid>
          </Grid>

          <Divider sx={{ my: 3 }} />

          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            System Information
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <Typography variant="body2" color="text.secondary">
                Student ID: <strong>{student.id}</strong>
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6}>
              <Typography variant="body2" color="text.secondary">
                Created: {formatDate(student.created_date)}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6}>
              <Typography variant="body2" color="text.secondary">
                Last Modified: {formatDate(student.modified_date)}
              </Typography>
            </Grid>
          </Grid>

          <Divider sx={{ my: 3 }} />

          {/* Eligibility Information */}
          <Box sx={{ mb: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                Eligibility Information
              </Typography>
              {isEditing && (
                <Button
                  variant="outlined"
                  startIcon={<Add />}
                  onClick={() => setShowAddEligibility(true)}
                  disabled={saving || showAddEligibility}
                  size="small"
                >
                  Add Eligibility
                </Button>
              )}
            </Box>

          {/* Add Eligibility Form */}
          {showAddEligibility && isEditing && (
            <Card variant="outlined" sx={{ mb: 3, p: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Add New Eligibility
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Eligibility Category</InputLabel>
                    <Select
                      value={eligibilityForm.eligibility_category_id}
                      onChange={(e) => setEligibilityForm(prev => ({ ...prev, eligibility_category_id: e.target.value }))}
                      label="Eligibility Category"
                      disabled={saving}
                    >
                      <MenuItem value="">
                        <em>-- Select Category --</em>
                      </MenuItem>
                      {eligibilityCategories.map((category) => (
                        <MenuItem key={category.id} value={category.id.toString()}>
                          {category.name}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} sm={3}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Start Date"
                    type="date"
                    value={eligibilityForm.start_date}
                    onChange={(e) => setEligibilityForm(prev => ({ ...prev, start_date: e.target.value }))}
                    disabled={saving}
                    InputLabelProps={{ shrink: true }}
                  />
                </Grid>
                <Grid item xs={12} sm={3}>
                  <TextField
                    fullWidth
                    size="small"
                    label="End Date"
                    type="date"
                    value={eligibilityForm.end_date}
                    onChange={(e) => setEligibilityForm(prev => ({ ...prev, end_date: e.target.value }))}
                    disabled={saving}
                    InputLabelProps={{ shrink: true }}
                    helperText="Leave blank if ongoing"
                  />
                </Grid>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Notes"
                    multiline
                    rows={2}
                    value={eligibilityForm.notes}
                    onChange={(e) => setEligibilityForm(prev => ({ ...prev, notes: e.target.value }))}
                    disabled={saving}
                    placeholder="Optional notes about this eligibility..."
                  />
                </Grid>
                <Grid item xs={12}>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    <FormControl>
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={eligibilityForm.is_primary}
                            onChange={(e) => setEligibilityForm(prev => ({ ...prev, is_primary: e.target.checked }))}
                            disabled={saving}
                          />
                        }
                        label="Primary eligibility"
                      />
                    </FormControl>
                    <Box sx={{ flexGrow: 1 }} />
                    <Button
                      variant="outlined"
                      onClick={() => setShowAddEligibility(false)}
                      disabled={saving}
                      size="small"
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="contained"
                      onClick={handleAddEligibility}
                      disabled={saving || !eligibilityForm.eligibility_category_id}
                      size="small"
                    >
                      {saving ? 'Adding...' : 'Add'}
                    </Button>
                  </Box>
                </Grid>
              </Grid>
            </Card>
          )}
          
          {student?.eligibilities && student.eligibilities.length > 0 ? (
            <Grid container spacing={2}>
              {student.eligibilities.map((eligibility: StudentEligibility) => (
                <Grid item xs={12} sm={6} md={4} key={eligibility.id}>
                  <Card variant="outlined" sx={{ height: '100%' }}>
                    <CardContent>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                        <Typography variant="subtitle1" fontWeight="bold">
                          {eligibility.eligibility_category.name}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                          {eligibility.is_primary && (
                            <Chip label="Primary" color="primary" size="small" />
                          )}
                          <Chip 
                            label={eligibility.is_active ? "Active" : "Ended"} 
                            color={eligibility.is_active ? "success" : "default"} 
                            size="small" 
                          />
                          {isEditing && (
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => handleDeleteEligibility(eligibility.id)}
                              disabled={saving}
                              title="Remove eligibility"
                            >
                              <Delete fontSize="small" />
                            </IconButton>
                          )}
                        </Box>
                      </Box>
                      
                      {eligibility.eligibility_category.code && (
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                          Code: {eligibility.eligibility_category.code}
                        </Typography>
                      )}
                      
                      <Typography variant="body2" sx={{ mt: 1 }}>
                        <strong>Start Date:</strong> {new Date(eligibility.start_date).toLocaleDateString()}
                      </Typography>
                      
                      {eligibility.end_date && (
                        <Typography variant="body2">
                          <strong>End Date:</strong> {new Date(eligibility.end_date).toLocaleDateString()}
                        </Typography>
                      )}
                      
                      {eligibility.notes && (
                        <Typography variant="body2" sx={{ mt: 1 }}>
                          <strong>Notes:</strong> {eligibility.notes}
                        </Typography>
                      )}
                      
                      {eligibility.eligibility_category.description && (
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1, fontStyle: 'italic' }}>
                          {eligibility.eligibility_category.description}
                        </Typography>
                      )}
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          ) : (
            <Typography color="text.secondary" textAlign="center" sx={{ py: 3 }}>
              No eligibility information found for this student.
              {isEditing && (
                <>
                  <br />
                  <Button
                    variant="text"
                    startIcon={<Add />}
                    onClick={() => setShowAddEligibility(true)}
                    disabled={saving}
                    sx={{ mt: 1 }}
                  >
                    Add First Eligibility
                  </Button>
                </>
              )}
            </Typography>
          )}
          </Box>
        </CardContent>
      </Card>
      </Box>
    </Box>
  );
}
