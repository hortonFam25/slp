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
  useTheme
} from '@mui/material';
import { Add, Delete, Edit, Refresh, FileUpload, FileDownload, Visibility, Archive } from '@mui/icons-material';
import { useStudents } from '../../lib/hooks/useStudents';
import { CSVImport } from '../../components/CSVImport';
import { StudentDetailsDialog } from '../../components/StudentDetailsDialog';
import { csvApi } from '../../lib/api/csv';
import { ConfirmationModal } from '../../components/ui/ConfirmationModal';

export default function Students() {
  const { students, loading, error, createStudent, deleteStudent, archiveStudent, refetch } = useStudents();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isCSVImportOpen, setIsCSVImportOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [detailsDialogState, setDetailsDialogState] = useState<{
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
    teacher_name: '',
    case_manager: '',
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
        teacher_name: formData.teacher_name.trim() || undefined,
        case_manager: formData.case_manager.trim() || undefined,
        enrollment_status: formData.enrollment_status,
        date_of_birth: formData.date_of_birth || undefined,
      });
      
      // Reset form and close dialog
      setFormData({
        first: '',
        last: '',
        uic: '',
        grade_level: '',
        teacher_name: '',
        case_manager: '',
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

  const handleDeleteStudent = async (id: number, name: string) => {
    if (window.confirm(`Are you sure you want to delete ${name}?`)) {
      try {
        await deleteStudent(id);
      } catch (err) {
        // Error is handled by the hook
      }
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

  const handleArchiveClick = (studentId: number, studentName: string) => {
    setArchiveConfirmState({
      open: true,
      studentId,
      studentName,
      loading: false
    });
  };

  const handleArchiveConfirm = async () => {
    if (!archiveConfirmState.studentId) return;

    try {
      setArchiveConfirmState(prev => ({ ...prev, loading: true }));
      await archiveStudent(archiveConfirmState.studentId);
      setArchiveConfirmState({ open: false, studentId: null, studentName: '', loading: false });
    } catch (err) {
      // Error is handled by the hook
      setArchiveConfirmState(prev => ({ ...prev, loading: false }));
    }
  };

  const handleArchiveCancel = () => {
    setArchiveConfirmState({ open: false, studentId: null, studentName: '', loading: false });
  };

  const updateFormField = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
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

  return (
    <Stack spacing={isMobile ? 2 : 3} sx={{ p: isMobile ? 2 : 0 }}>
      <Box sx={{
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        gap: isMobile ? 2 : 0,
        justifyContent: 'space-between',
        alignItems: isMobile ? 'stretch' : 'center'
      }}>
        <Typography 
          variant={isMobile ? 'h5' : 'h4'} 
          component="h1" 
          className="font-semibold"
          sx={{ textAlign: isMobile ? 'center' : 'left' }}
        >
          Students
        </Typography>
        
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
              onClick={() => setIsCreateDialogOpen(true)}
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
              onClick={() => setIsCreateDialogOpen(true)}
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
                      {student.case_manager && (
                        <Chip 
                          label={`CM: ${student.case_manager}`} 
                          size="small" 
                          color="primary" 
                          variant="outlined"
                          sx={{ fontSize: isMobile ? '0.7rem' : '0.75rem' }}
                        />
                      )}
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
                  {!student.is_archived && (
                    <IconButton 
                      size="small" 
                      color="warning"
                      onClick={() => handleArchiveClick(student.id, `${student.first} ${student.last}`)}
                      title="Archive Student"
                      sx={{ 
                        width: isMobile ? 36 : 40,
                        height: isMobile ? 36 : 40
                      }}
                    >
                      <Archive fontSize={isMobile ? 'small' : 'medium'} />
                    </IconButton>
                  )}
                  <IconButton 
                    size="small" 
                    color="error"
                    onClick={() => handleDeleteStudent(student.id, `${student.first} ${student.last}`)}
                    title="Delete Student"
                    sx={{ 
                      width: isMobile ? 36 : 40,
                      height: isMobile ? 36 : 40
                    }}
                  >
                    <Delete fontSize={isMobile ? 'small' : 'medium'} />
                  </IconButton>
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
              <TextField
                fullWidth
                label="Grade Level"
                value={formData.grade_level}
                onChange={(e) => updateFormField('grade_level', e.target.value)}
                placeholder="e.g., K, 1, 2, 3..."
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Teacher Name"
                value={formData.teacher_name}
                onChange={(e) => updateFormField('teacher_name', e.target.value)}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Case Manager"
                value={formData.case_manager}
                onChange={(e) => updateFormField('case_manager', e.target.value)}
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
      <CSVImport
        open={isCSVImportOpen}
        onClose={() => setIsCSVImportOpen(false)}
        onImportComplete={handleCSVImportComplete}
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

      {/* Archive Confirmation Modal */}
      <ConfirmationModal
        open={archiveConfirmState.open}
        onClose={handleArchiveCancel}
        onConfirm={handleArchiveConfirm}
        title="Archive Student"
        message={`Are you sure you want to archive ${archiveConfirmState.studentName}?\n\nThe student will be hidden from active student lists but their data will be preserved. You can unarchive them later if needed.`}
        confirmText="Archive"
        severity="warning"
        loading={archiveConfirmState.loading}
      />
    </Stack>
  );
}


