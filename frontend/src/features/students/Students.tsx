import { useState } from 'react';
import { 
  Button, 
  Card, 
  CardContent, 
  Stack, 
  TextField, 
  Typography, 
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Grid,
  Chip,
  IconButton,
  Box,
  useMediaQuery,
  useTheme,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Autocomplete
} from '@mui/material';
import { Add, Edit, Refresh, FileUpload, FileDownload, Visibility, Archive, Timeline } from '@mui/icons-material';
import { UsersRound } from 'lucide-react';
import { useStudents } from '../../lib/hooks/useStudents';
import { UniversalCSVImport } from '../../components/UniversalCSVImport';
import { StudentDetailsDialog } from '../../components/StudentDetailsDialog';
import { StudentTherapyHistoryDialog } from '../../components/StudentTherapyHistoryDialog';
import { csvApi } from '../../lib/api/csv';
import { ConfirmationModal } from '../../components/ui/ConfirmationModal';
import { teachersApi } from '../../lib/api/teachers';
import { schoolsApi } from '../../lib/api/schools';
import type { TeacherSummary } from '../../lib/api/types/teachers';
import type { SchoolSummary } from '../../lib/api/types/schools';
import { useArchiveWithUndo, archiveMessage, archiveTitle } from '../../lib/archive';

export default function Students() {
  const { students, loading, error, createStudent, archiveStudent, unarchiveStudent, refetch } = useStudents();
  const archiveWithUndo = useArchiveWithUndo();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isCSVImportOpen, setIsCSVImportOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [teachers, setTeachers] = useState<TeacherSummary[]>([]);
  const [teachersLoading, setTeachersLoading] = useState(false);
  const [schools, setSchools] = useState<SchoolSummary[]>([]);
  const [schoolsLoading, setSchoolsLoading] = useState(false);
  const [detailsDialogState, setDetailsDialogState] = useState<{
    open: boolean;
    studentId: number | null;
    studentName: string;
  }>({ open: false, studentId: null, studentName: '' });
  
  const [therapyHistoryDialogState, setTherapyHistoryDialogState] = useState<{
    open: boolean;
    studentId: number | null;
    studentName: string;
  }>({ open: false, studentId: null, studentName: '' });
  
  const [archiveConfirmState, setArchiveConfirmState] = useState<{
    open: boolean;
    studentId: number | null;
    studentName: string;
    loading: boolean;
  }>({ open: false, studentId: null, studentName: '', loading: false });
  
  // Form state
  const [formData, setFormData] = useState({
    first: '',
    last: '',
    uic: '',
    grade_level: '',
    teacher_id: null as number | null,
    case_manager_id: null as number | null,
    school_id: null as number | null,
    enrollment_status: 'Active',
    date_of_birth: '',
  });

  const handleCreateStudent = async () => {
    if (!formData.first.trim() || !formData.last.trim()) {
      return;
    }

    try {
      setIsSubmitting(true);
      await createStudent({
        first: formData.first.trim(),
        last: formData.last.trim(),
        uic: formData.uic.trim() || undefined,
        grade_level: formData.grade_level.trim() || undefined,
        teacher_id: formData.teacher_id || undefined,
        case_manager_id: formData.case_manager_id || undefined,
        school_id: formData.school_id || undefined,
        enrollment_status: formData.enrollment_status,
        date_of_birth: formData.date_of_birth || undefined,
      });
      
      // Reset form and close dialog
      setFormData({
        first: '',
        last: '',
        uic: '',
        grade_level: '',
        teacher_id: null,
        case_manager_id: null,
        school_id: null,
        enrollment_status: 'Active',
        date_of_birth: '',
      });
      setIsCreateDialogOpen(false);
    } catch (err) {
      // Error is handled by the hook
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOpenDetails = (studentId: number, studentName: string) => {
    setDetailsDialogState({
      open: true,
      studentId,
      studentName
    });
  };

  const handleCloseDetails = () => {
    setDetailsDialogState({
      open: false,
      studentId: null,
      studentName: ''
    });
  };

  const handleOpenTherapyHistory = (studentId: number, studentName: string) => {
    setTherapyHistoryDialogState({
      open: true,
      studentId,
      studentName
    });
  };

  const handleCloseTherapyHistory = () => {
    setTherapyHistoryDialogState({
      open: false,
      studentId: null,
      studentName: ''
    });
  };

  const handleArchiveClick = (studentId: number, studentName: string) => {
    setArchiveConfirmState({
      open: true,
      studentId,
      studentName,
      loading: false
    });
  };

  const handleArchiveConfirm = async () => {
    const studentId = archiveConfirmState.studentId;
    if (!studentId) return;

    try {
      setArchiveConfirmState(prev => ({ ...prev, loading: true }));
      await archiveWithUndo({
        entity: 'student',
        name: archiveConfirmState.studentName,
        archive: () => archiveStudent(studentId),
        // `PUT /students/{id}/archive` answers with the student, not with an
        // archive event id -- so the undo is the matching unarchive route,
        // which restores the very same event server-side.
        undo: () => unarchiveStudent(studentId),
        onChanged: () => refetch(),
      });
      setArchiveConfirmState({ open: false, studentId: null, studentName: '', loading: false });
    } catch (err) {
      // Error is handled by the hook
      setArchiveConfirmState(prev => ({ ...prev, loading: false }));
    }
  };

  const handleArchiveCancel = () => {
    setArchiveConfirmState({ open: false, studentId: null, studentName: '', loading: false });
  };

  const updateFormField = (field: string, value: string | number | null) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const fetchTeachers = async () => {
    try {
      setTeachersLoading(true);
      const teachersList = await teachersApi.getTeachersSummary(true); // Get active teachers only
      setTeachers(teachersList);
    } catch (error) {
      console.error('Failed to fetch teachers:', error);
      setTeachers([]);
    } finally {
      setTeachersLoading(false);
    }
  };

  const fetchSchools = async () => {
    try {
      setSchoolsLoading(true);
      const schoolsList = await schoolsApi.getSchoolsSummary(true); // Get active schools only
      setSchools(schoolsList);
    } catch (error) {
      console.error('Failed to fetch schools:', error);
      setSchools([]);
    } finally {
      setSchoolsLoading(false);
    }
  };

  const handleOpenCreateDialog = () => {
    setIsCreateDialogOpen(true);
    fetchTeachers(); // Load teachers when dialog opens
    fetchSchools(); // Load schools when dialog opens
  };

  const handleCSVImportComplete = () => {
    setIsCSVImportOpen(false);
    refetch(); // Refresh the students list
  };

  const handleExportCSV = async () => {
    try {
      await csvApi.exportAndDownloadStudents();
    } catch (error) {
      console.error('Export error:', error);
      alert(`Error exporting students: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <CircularProgress />
      </Box>
    );
  }

  // Calculate active students count
  const activeStudentsCount = students.filter(student => 
    student.enrollment_status === 'Active' && !student.is_archived
  ).length;

  return (
    <Stack
      spacing={2}
      sx={{ p: { xs: 1.5, sm: 2 }, height: '100%', minHeight: 0, overflow: 'hidden' }}
    >
      <Box sx={{
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        gap: isMobile ? 2 : 3,
        justifyContent: 'space-between',
        alignItems: isMobile ? 'stretch' : 'center',
        position: 'sticky',
        top: 0,
        zIndex: 2,
        bgcolor: 'background.default',
        pt: 0.25,
      }}>
        <Box sx={{ 
          display: 'flex', 
          flexDirection: isMobile ? 'column' : 'row',
          alignItems: isMobile ? 'center' : 'center',
          gap: isMobile ? 2 : 3
        }}>
          <Typography
            component="h1"
            sx={{
              textAlign: isMobile ? 'center' : 'left',
              color: '#41AAB7',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: 1.25,
              justifyContent: isMobile ? 'center' : 'flex-start',
              fontSize: { xs: '1.35rem', sm: '1.5rem' },
              lineHeight: 1.2,
            }}
          >
            <UsersRound size={24} />
            Students
          </Typography>
          
          {/* Active Students Count Card */}
          <Card sx={{ 
            minWidth: isMobile ? 'auto' : 140,
            bgcolor: '#f8fffe',
            border: '1px solid #41AAB7',
            boxShadow: '0 2px 4px rgba(65,170,183,0.1)'
          }}>
            <CardContent sx={{ 
              p: isMobile ? 1.5 : 2, 
              '&:last-child': { pb: isMobile ? 1.5 : 2 },
              textAlign: 'center'
            }}>
              <Typography 
                variant="h6" 
                component="div" 
                sx={{ 
                  color: '#41AAB7', 
                  fontWeight: 700,
                  fontSize: isMobile ? '1.25rem' : '1.5rem',
                  lineHeight: 1
                }}
              >
                {activeStudentsCount}
              </Typography>
              <Typography 
                variant="caption" 
                sx={{ 
                  color: '#41AAB7', 
                  fontWeight: 500,
                  fontSize: isMobile ? '0.7rem' : '0.75rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px'
                }}
              >
                Active Students
              </Typography>
            </CardContent>
          </Card>
        </Box>
        
        {isMobile ? (
          // Mobile: Stacked buttons
          <Stack spacing={1}>
            <Stack direction="row" spacing={1} justifyContent="center">
              <IconButton onClick={refetch} disabled={loading}>
                <Refresh />
              </IconButton>
              <Button 
                variant="outlined" 
                startIcon={<FileDownload />}
                onClick={handleExportCSV}
                size="small"
              >
                Export
              </Button>
              <Button 
                variant="outlined" 
                startIcon={<FileUpload />}
                onClick={() => setIsCSVImportOpen(true)}
                size="small"
              >
                Import
              </Button>
            </Stack>
            <Button 
              variant="contained" 
              startIcon={<Add />}
              onClick={handleOpenCreateDialog}
              fullWidth
            >
              Add Student
            </Button>
          </Stack>
        ) : (
          // Desktop: Horizontal row
          <Stack direction="row" spacing={1}>
            <IconButton onClick={refetch} disabled={loading}>
              <Refresh />
            </IconButton>
            <Button 
              variant="outlined" 
              startIcon={<FileDownload />}
              onClick={handleExportCSV}
            >
              Export CSV
            </Button>
            <Button 
              variant="outlined" 
              startIcon={<FileUpload />}
              onClick={() => setIsCSVImportOpen(true)}
            >
              Import CSV
            </Button>
            <Button 
              variant="contained" 
              startIcon={<Add />}
              onClick={handleOpenCreateDialog}
            >
              Add Student
            </Button>
          </Stack>
        )}
      </Box>

      {error && (
        <Alert severity="error" onClose={() => window.location.reload()}>
          {error}
        </Alert>
      )}

      <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        <Stack spacing={isMobile ? 1.5 : 2}>
          {students.map((student) => (
          <Card key={student.id} variant="outlined" sx={{ 
            border: isMobile ? '1px solid #e0e0e0' : undefined,
            boxShadow: isMobile ? '0 1px 3px rgba(0,0,0,0.1)' : undefined
          }}>
            <CardContent sx={{ p: isMobile ? 2 : 3 }}>
              <Stack 
                direction={isMobile ? 'column' : 'row'} 
                justifyContent="space-between" 
                alignItems={isMobile ? 'stretch' : 'start'}
                spacing={isMobile ? 2 : 0}
              >
                <Box sx={{ flex: 1 }}>
                  <Typography variant={isMobile ? 'subtitle1' : 'h6'} sx={{ 
                    fontWeight: 600,
                    fontSize: isMobile ? '1rem' : '1.25rem'
                  }}>
                    {student.last}, {student.first}
                  </Typography>
                  <Stack 
                    direction={isMobile ? 'column' : 'row'} 
                    spacing={isMobile ? 0.5 : 1} 
                    sx={{ mt: 1 }}
                    flexWrap="wrap"
                  >
                    <Stack direction="row" spacing={0.5} flexWrap="wrap">
                      {student.grade_level && (
                        <Chip 
                          label={`Grade ${student.grade_level}`} 
                          size="small" 
                          variant="outlined"
                          sx={{ fontSize: isMobile ? '0.7rem' : '0.75rem' }}
                        />
                      )}
                      {(() => {
                        // Handle both legacy string and new TeacherSummary object
                        let caseManagerName = '';
                        if (typeof student.case_manager === 'string') {
                          caseManagerName = student.case_manager;
                        } else if (student.case_manager?.display_name) {
                          caseManagerName = student.case_manager.display_name;
                        } else if (student.teacher?.display_name && student.case_manager_id === student.teacher_id) {
                          // If case manager ID matches teacher ID, use teacher name
                          caseManagerName = student.teacher.display_name;
                        }
                        
                        return caseManagerName ? (
                          <Chip 
                            label={`CM: ${caseManagerName}`} 
                            size="small" 
                            color="primary" 
                            variant="outlined"
                            sx={{ fontSize: isMobile ? '0.7rem' : '0.75rem' }}
                          />
                        ) : null;
                      })()}
                    </Stack>
                    <Stack direction="row" spacing={0.5} flexWrap="wrap">
                      <Chip 
                        label={student.enrollment_status} 
                        size="small" 
                        color={student.enrollment_status === 'Active' ? 'success' : 'default'}
                        sx={{ fontSize: isMobile ? '0.7rem' : '0.75rem' }}
                      />
                      {student.is_archived && (
                        <Chip 
                          label="ARCHIVED" 
                          size="small" 
                          color="warning"
                          sx={{ fontSize: isMobile ? '0.7rem' : '0.75rem' }}
                        />
                      )}
                    </Stack>
                    {/* IEP Status Indicators */}
                    {(student.annual_review_due_date || student.reevaluation_due_date) && (
                      <Stack direction="row" spacing={0.5} flexWrap="wrap">
                        {student.annual_review_due_date && (
                          <Chip 
                            label={`Review: ${new Date(student.annual_review_due_date).toLocaleDateString()}`}
                            size="small" 
                            color={new Date(student.annual_review_due_date) <= new Date() ? 'error' : 'info'}
                            variant="outlined"
                            sx={{ fontSize: isMobile ? '0.7rem' : '0.75rem' }}
                          />
                        )}
                        {student.reevaluation_due_date && (
                          <Chip 
                            label={`Re-eval: ${new Date(student.reevaluation_due_date).toLocaleDateString()}`}
                            size="small" 
                            color={new Date(student.reevaluation_due_date) <= new Date() ? 'error' : 'secondary'}
                            variant="outlined"
                            sx={{ fontSize: isMobile ? '0.7rem' : '0.75rem' }}
                          />
                        )}
                      </Stack>
                    )}
                  </Stack>
                </Box>
                
                <Stack 
                  direction="row" 
                  spacing={isMobile ? 0.5 : 1}
                  justifyContent={isMobile ? 'center' : 'flex-end'}
                  alignItems="center"
                >
                  <IconButton 
                    size="small" 
                    color="primary"
                    onClick={() => handleOpenDetails(student.id, `${student.first} ${student.last}`)}
                    title="View/Edit Details"
                    sx={{ 
                      width: isMobile ? 36 : 40,
                      height: isMobile ? 36 : 40
                    }}
                  >
                    <Visibility fontSize={isMobile ? 'small' : 'medium'} />
                  </IconButton>
                  <IconButton 
                    size="small" 
                    color="secondary"
                    onClick={() => handleOpenTherapyHistory(student.id, `${student.first} ${student.last}`)}
                    title="View Therapy History"
                    sx={{ 
                      width: isMobile ? 36 : 40,
                      height: isMobile ? 36 : 40
                    }}
                  >
                    <Timeline fontSize={isMobile ? 'small' : 'medium'} />
                  </IconButton>
                  {/* There used to be a red "Delete Student" button beside this
                      one. It is gone: `DELETE /api/students/{id}` now archives
                      exactly what this button archives, so the pair were two
                      controls doing one thing, and the red one was the one
                      lying about it. */}
                  {!student.is_archived && (
                    <IconButton
                      size="small"
                      color="warning"
                      onClick={() => handleArchiveClick(student.id, `${student.first} ${student.last}`)}
                      title="Archive Student"
                      aria-label={`Archive ${student.first} ${student.last}`}
                      sx={{
                        width: isMobile ? 36 : 40,
                        height: isMobile ? 36 : 40
                      }}
                    >
                      <Archive fontSize={isMobile ? 'small' : 'medium'} />
                    </IconButton>
                  )}
                </Stack>
              </Stack>
            </CardContent>
          </Card>
          ))}
          
          {students.length === 0 && !loading && (
            <Card variant="outlined">
              <CardContent>
                <Typography color="text.secondary" textAlign="center">
                  No students found. Click "Add Student" to get started.
                </Typography>
              </CardContent>
            </Card>
          )}
        </Stack>
      </Box>

      {/* Create Student Dialog */}
      <Dialog 
        open={isCreateDialogOpen} 
        onClose={() => setIsCreateDialogOpen(false)} 
        maxWidth="md" 
        fullWidth
        fullScreen={isMobile}
      >
        <DialogTitle sx={{ 
          fontSize: isMobile ? '1.25rem' : '1.5rem',
          p: isMobile ? 2 : 3
        }}>
          Add New Student
        </DialogTitle>
        <DialogContent sx={{ p: isMobile ? 2 : 3 }}>
          <Grid container spacing={isMobile ? 1.5 : 2} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="First Name"
                required
                value={formData.first}
                onChange={(e) => updateFormField('first', e.target.value)}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Last Name"
                required
                value={formData.last}
                onChange={(e) => updateFormField('last', e.target.value)}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="UIC (Legacy System ID)"
                value={formData.uic}
                onChange={(e) => updateFormField('uic', e.target.value)}
                helperText="Optional: For mapping to legacy IEP system"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Grade Level</InputLabel>
                <Select
                  value={formData.grade_level}
                  onChange={(e) => updateFormField('grade_level', e.target.value)}
                  label="Grade Level"
                >
                  <MenuItem value="">Select grade</MenuItem>
                  <MenuItem value="Pre-K">Pre-K</MenuItem>
                  <MenuItem value="K">Kindergarten</MenuItem>
                  <MenuItem value="1">1st Grade</MenuItem>
                  <MenuItem value="2">2nd Grade</MenuItem>
                  <MenuItem value="3">3rd Grade</MenuItem>
                  <MenuItem value="4">4th Grade</MenuItem>
                  <MenuItem value="5">5th Grade</MenuItem>
                  <MenuItem value="6">6th Grade</MenuItem>
                  <MenuItem value="7">7th Grade</MenuItem>
                  <MenuItem value="8">8th Grade</MenuItem>
                  <MenuItem value="9">9th Grade</MenuItem>
                  <MenuItem value="10">10th Grade</MenuItem>
                  <MenuItem value="11">11th Grade</MenuItem>
                  <MenuItem value="12">12th Grade</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6}>
              <Autocomplete
                fullWidth
                options={teachers}
                getOptionLabel={(option) => option.display_name}
                value={teachers.find(t => t.id === formData.teacher_id) || null}
                onChange={(_, newValue) => updateFormField('teacher_id', newValue?.id || null)}
                loading={teachersLoading}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Teacher"
                    placeholder="Select a teacher"
                    InputProps={{
                      ...params.InputProps,
                      endAdornment: (
                        <>
                          {teachersLoading ? <CircularProgress color="inherit" size={20} /> : null}
                          {params.InputProps.endAdornment}
                        </>
                      ),
                    }}
                  />
                )}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <Autocomplete
                fullWidth
                options={teachers}
                getOptionLabel={(option) => option.display_name}
                value={teachers.find(t => t.id === formData.case_manager_id) || null}
                onChange={(_, newValue) => updateFormField('case_manager_id', newValue?.id || null)}
                loading={teachersLoading}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Case Manager"
                    placeholder="Select a case manager"
                    InputProps={{
                      ...params.InputProps,
                      endAdornment: (
                        <>
                          {teachersLoading ? <CircularProgress color="inherit" size={20} /> : null}
                          {params.InputProps.endAdornment}
                        </>
                      ),
                    }}
                  />
                )}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <Autocomplete
                fullWidth
                options={schools}
                getOptionLabel={(option) => option.name}
                value={schools.find(s => s.id === formData.school_id) || null}
                onChange={(_, newValue) => updateFormField('school_id', newValue?.id || null)}
                loading={schoolsLoading}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="School"
                    placeholder="Select a school"
                    InputProps={{
                      ...params.InputProps,
                      endAdornment: (
                        <>
                          {schoolsLoading ? <CircularProgress color="inherit" size={20} /> : null}
                          {params.InputProps.endAdornment}
                        </>
                      ),
                    }}
                  />
                )}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Date of Birth"
                type="date"
                value={formData.date_of_birth}
                onChange={(e) => updateFormField('date_of_birth', e.target.value)}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                select
                label="Enrollment Status"
                value={formData.enrollment_status}
                onChange={(e) => updateFormField('enrollment_status', e.target.value)}
                SelectProps={{ native: true }}
              >
                <option value="Active">Active</option>
                <option value="Inactive">Inactive</option>
                <option value="Transferred">Transferred</option>
              </TextField>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ 
          p: isMobile ? 2 : 3,
          flexDirection: isMobile ? 'column' : 'row',
          gap: isMobile ? 1 : 0
        }}>
          <Button 
            onClick={() => setIsCreateDialogOpen(false)}
            fullWidth={isMobile}
            sx={{ order: isMobile ? 2 : 1 }}
          >
            Cancel
          </Button>
          <Button 
            onClick={handleCreateStudent} 
            variant="contained" 
            disabled={!formData.first.trim() || !formData.last.trim() || isSubmitting}
            fullWidth={isMobile}
            sx={{ order: isMobile ? 1 : 2 }}
          >
            {isSubmitting ? 'Creating...' : 'Create Student'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* CSV Import Dialog */}
      <UniversalCSVImport
        open={isCSVImportOpen}
        onClose={() => setIsCSVImportOpen(false)}
        onImportComplete={handleCSVImportComplete}
        defaultImportType="students"
      />

      {/* Student Details Dialog */}
      {detailsDialogState.open && detailsDialogState.studentId && (
        <StudentDetailsDialog
          open={detailsDialogState.open}
          onClose={handleCloseDetails}
          studentId={detailsDialogState.studentId}
          studentName={detailsDialogState.studentName}
        />
      )}

      {/* Therapy History Dialog */}
      {therapyHistoryDialogState.open && therapyHistoryDialogState.studentId && (
        <StudentTherapyHistoryDialog
          open={therapyHistoryDialogState.open}
          onClose={handleCloseTherapyHistory}
          studentId={therapyHistoryDialogState.studentId}
          studentName={therapyHistoryDialogState.studentName}
        />
      )}

      {/* Archive Confirmation Modal */}
      <ConfirmationModal
        open={archiveConfirmState.open}
        onClose={handleArchiveCancel}
        onConfirm={handleArchiveConfirm}
        title={archiveTitle('student')}
        message={archiveMessage('student', archiveConfirmState.studentName)}
        confirmText="Archive"
        severity="warning"
        loading={archiveConfirmState.loading}
        loadingText="Archiving..."
      />
    </Stack>
  );
}


