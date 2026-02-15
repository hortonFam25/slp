import { useState, useCallback } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  FormControlLabel,
  Checkbox,
  Stack,
  IconButton,
  Collapse,
  ToggleButton,
  ToggleButtonGroup,
  Divider,
} from '@mui/material';
import { 
  CloudUpload, 
  Download, 
  CheckCircle, 
  Error, 
  Warning,
  ExpandMore,
  ExpandLess,
  People,
  TrackChanges
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import { csvApi, CSVPreviewResult, CSVImportResult } from '../lib/api/csv';
import { goalsCSVApi, GoalPreviewResult, GoalImportResult } from '../lib/api/goals-csv';

interface UniversalCSVImportProps {
  open: boolean;
  onClose: () => void;
  onImportComplete?: (result: CSVImportResult | GoalImportResult) => void;
  defaultImportType?: 'students' | 'goals';
}

type ImportType = 'students' | 'goals';

export function UniversalCSVImport({ 
  open, 
  onClose, 
  onImportComplete,
  defaultImportType = 'students' 
}: UniversalCSVImportProps) {
  const [importType, setImportType] = useState<ImportType>(defaultImportType);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<CSVPreviewResult | GoalPreviewResult | null>(null);
  const [importResult, setImportResult] = useState<CSVImportResult | GoalImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<'upload' | 'preview' | 'complete'>('upload');
  
  // Import options
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [updateExisting, setUpdateExisting] = useState(false);
  const [showErrors, setShowErrors] = useState(false);

  // Import type configuration
  const importConfig = {
    students: {
      title: 'Import Students from CSV',
      icon: <People />,
      apiEndpoint: '/api/csv',
      templateEndpoint: '/api/csv/template',
      guidelines: [
        'Use UTF-8 encoding',
        'Required fields: first, last',
        'Optional fields: uic, grade_level, teacher_name, case_manager, enrollment_status, date_of_birth',
        'Date format: YYYY-MM-DD',
        'Enrollment status options: Active, Inactive, Transferred'
      ],
      duplicateLabel: 'Skip students with duplicate UICs',
      updateLabel: 'Update existing students when UIC matches',
      previewColumns: ['Row', 'Status', 'Name', 'UIC', 'Grade', 'Case Manager', 'Notes']
    },
    goals: {
      title: 'Import Goals & Objectives from CSV',
      icon: <TrackChanges />,
      apiEndpoint: '/api/goals-csv',
      templateEndpoint: '/api/goals-csv/template',
      guidelines: [
        'Use UTF-8 encoding',
        'Required fields: ID (student UIC), Goal',
        'Supports up to 5 objectives per goal',
        'Date format: M/D/YYYY (will be converted)',
        'Progress comments and dates will be imported'
      ],
      duplicateLabel: 'Skip goals for students that already have active goals',
      updateLabel: 'Update existing goals if student already has goals',
      previewColumns: ['Row', 'Status', 'Student', 'Goal', 'Objectives', 'Progress', 'Notes']
    }
  };

  const currentConfig = importConfig[importType];

  // Dropzone configuration
  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const selectedFile = acceptedFiles[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setLoading(true);

    try {
      let previewResult: CSVPreviewResult | GoalPreviewResult;
      
      if (importType === 'students') {
        previewResult = await csvApi.previewImport(selectedFile, { max_rows: 10 });
      } else {
        previewResult = await goalsCSVApi.previewImport(selectedFile, { max_rows: 10 });
      }
      
      setPreview(previewResult);
      setStep('preview');
    } catch (error: any) {
      console.error('Preview error:', error);
      const errorMessage = error?.message || error?.toString() || 'Unknown error';
      alert(`Error previewing file: ${errorMessage}`);
    } finally {
      setLoading(false);
    }
  }, [importType]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.ms-excel': ['.csv'],
    },
    maxFiles: 1,
  });

  const handleImport = async () => {
    if (!file) return;

    setLoading(true);
    try {
      let result: CSVImportResult | GoalImportResult;
      
      if (importType === 'students') {
        result = await csvApi.importFromFile(file, {
          skip_duplicates: skipDuplicates,
          update_existing: updateExisting,
        });
      } else {
        result = await goalsCSVApi.importFromFile(file, {
          skip_duplicates: skipDuplicates,
          update_existing: updateExisting,
          default_goal_category: 'Speech/Language'
        });
      }
      
      setImportResult(result);
      setStep('complete');
      onImportComplete?.(result);
    } catch (error: any) {
      console.error('Import error:', error);
      const errorMessage = error?.message || error?.toString() || 'Unknown error';
      alert(`Error importing file: ${errorMessage}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      if (importType === 'students') {
        await csvApi.downloadTemplateFile();
      } else {
        await goalsCSVApi.downloadTemplateFile();
      }
    } catch (error: any) {
      console.error('Download error:', error);
      const errorMessage = error?.message || error?.toString() || 'Unknown error';
      alert(`Error downloading template: ${errorMessage}`);
    }
  };

  const handleClose = () => {
    setFile(null);
    setPreview(null);
    setImportResult(null);
    setStep('upload');
    setShowErrors(false);
    onClose();
  };

  const handleImportTypeChange = (
    event: React.MouseEvent<HTMLElement>,
    newImportType: ImportType | null,
  ) => {
    if (newImportType !== null) {
      setImportType(newImportType);
      // Reset when switching types
      setFile(null);
      setPreview(null);
      setImportResult(null);
      setStep('upload');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'create': return 'success';
      case 'update': return 'warning';
      case 'error': return 'error';
      default: return 'default';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'create': return 'New';
      case 'update': return 'Update';
      case 'error': return 'Error';
      default: return status;
    }
  };

  const renderPreviewRow = (row: any, index: number) => {
    if (importType === 'students') {
      return (
        <TableRow key={index}>
          <TableCell>{row.row_number}</TableCell>
          <TableCell>
            <Chip
              label={getStatusLabel(row.status)}
              color={getStatusColor(row.status)}
              size="small"
            />
          </TableCell>
          <TableCell>
            {row.data?.first} {row.data?.last}
          </TableCell>
          <TableCell>{row.data?.uic || '-'}</TableCell>
          <TableCell>{row.data?.grade_level || '-'}</TableCell>
          <TableCell>{row.data?.case_manager || '-'}</TableCell>
          <TableCell>
            {row.status === 'update' && row.existing_student && (
              <Typography variant="caption" color="text.secondary">
                Will update: {row.existing_student.name}
              </Typography>
            )}
            {row.error && (
              <Typography variant="caption" color="error">
                {row.error}
              </Typography>
            )}
          </TableCell>
        </TableRow>
      );
    } else {
      // Goals preview row
      return (
        <TableRow key={index}>
          <TableCell>{row.row_number}</TableCell>
          <TableCell>
            <Chip
              label={getStatusLabel(row.status)}
              color={getStatusColor(row.status)}
              size="small"
            />
          </TableCell>
          <TableCell>{row.data?.student_uic || row.data?.id || 'Unknown'}</TableCell>
          <TableCell>
            <Typography variant="caption" sx={{ maxWidth: 200, display: 'block' }}>
              {row.data?.goal_description || row.data?.goal || '-'}
            </Typography>
          </TableCell>
          <TableCell>{row.data?.objectives_count || row.data?.objectives?.length || 0}</TableCell>
          <TableCell>
            <Chip 
              label={row.data?.has_progress_data ? 'Yes' : 'No'} 
              color={row.data?.has_progress_data ? 'success' : 'default'}
              size="small"
            />
          </TableCell>
          <TableCell>
            {row.existing_goals_count > 0 && (
              <Typography variant="caption" color="text.secondary">
                {row.existing_goals_count} existing goals
              </Typography>
            )}
            {row.error && (
              <Typography variant="caption" color="error">
                {row.error}
              </Typography>
            )}
          </TableCell>
        </TableRow>
      );
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        {currentConfig.title}
        {loading && <LinearProgress sx={{ mt: 1 }} />}
      </DialogTitle>
      
      <DialogContent>
        {step === 'upload' && (
          <Stack spacing={3}>
            {/* Import Type Selection */}
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" gutterBottom>Select Import Type</Typography>
                <ToggleButtonGroup
                  value={importType}
                  exclusive
                  onChange={handleImportTypeChange}
                  aria-label="import type"
                  fullWidth
                >
                  <ToggleButton value="students" aria-label="students">
                    <People sx={{ mr: 1 }} />
                    Students
                  </ToggleButton>
                  <ToggleButton value="goals" aria-label="goals">
                    <TrackChanges sx={{ mr: 1 }} />
                    Goals & Objectives
                  </ToggleButton>
                </ToggleButtonGroup>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  {importType === 'students' 
                    ? 'Import student information, demographics, and IEP dates'
                    : 'Import IEP goals, objectives, and progress tracking data'
                  }
                </Typography>
              </CardContent>
            </Card>

            {/* Download Template Section */}
            <Card variant="outlined">
              <CardContent>
                <Stack direction="row" alignItems="center" spacing={2}>
                  <Download />
                  <Box flex={1}>
                    <Typography variant="h6">Download Template</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Start with our CSV template to ensure proper formatting
                    </Typography>
                  </Box>
                  <Button
                    variant="outlined"
                    startIcon={<Download />}
                    onClick={handleDownloadTemplate}
                  >
                    Download Template
                  </Button>
                </Stack>
              </CardContent>
            </Card>

            {/* File Upload Section */}
            <Card variant="outlined">
              <CardContent>
                <Box
                  {...getRootProps()}
                  sx={{
                    border: '2px dashed',
                    borderColor: isDragActive ? 'primary.main' : 'grey.300',
                    borderRadius: 2,
                    p: 4,
                    textAlign: 'center',
                    cursor: 'pointer',
                    bgcolor: isDragActive ? 'action.hover' : 'transparent',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <input {...getInputProps()} />
                  <CloudUpload sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                  <Typography variant="h6" gutterBottom>
                    {isDragActive ? 'Drop the CSV file here' : 'Drag & drop a CSV file here'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    or click to browse files
                  </Typography>
                  <Button variant="contained" sx={{ mt: 2 }}>
                    Choose File
                  </Button>
                </Box>
              </CardContent>
            </Card>

            {/* Format Guidelines */}
            <Alert severity="info">
              <Typography variant="subtitle2" gutterBottom>CSV Format Guidelines:</Typography>
              <ul style={{ margin: 0, paddingLeft: '20px' }}>
                {currentConfig.guidelines.map((guideline, index) => (
                  <li key={index}>{guideline}</li>
                ))}
              </ul>
            </Alert>
          </Stack>
        )}

        {step === 'preview' && preview && (
          <Stack spacing={3}>
            {/* Preview Summary */}
            <Alert severity={preview.valid ? 'success' : 'error'}>
              <Typography variant="subtitle2">
                File: {preview.filename} ({Math.round(preview.file_size / 1024)} KB)
              </Typography>
              <Typography variant="body2">
                {preview.total_rows} total rows • {preview.validation_errors.length} errors
                {preview.has_more_rows && ' • Showing first 10 rows'}
              </Typography>
            </Alert>

            {/* Import Options */}
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" gutterBottom>Import Options</Typography>
                <Stack spacing={1}>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={skipDuplicates}
                        onChange={(e) => setSkipDuplicates(e.target.checked)}
                      />
                    }
                    label={currentConfig.duplicateLabel}
                  />
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={updateExisting}
                        onChange={(e) => setUpdateExisting(e.target.checked)}
                      />
                    }
                    label={currentConfig.updateLabel}
                  />
                </Stack>
              </CardContent>
            </Card>

            {/* Preview Table */}
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    {currentConfig.previewColumns.map((column) => (
                      <TableCell key={column}>{column}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {preview.preview_rows.map((row, index) => renderPreviewRow(row, index))}
                </TableBody>
              </Table>
            </TableContainer>

            {/* Validation Errors */}
            {preview.validation_errors.length > 0 && (
              <Card variant="outlined">
                <CardContent>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <Error color="error" />
                    <Typography variant="h6" color="error">
                      Validation Errors ({preview.validation_errors.length})
                    </Typography>
                    <IconButton size="small" onClick={() => setShowErrors(!showErrors)}>
                      {showErrors ? <ExpandLess /> : <ExpandMore />}
                    </IconButton>
                  </Stack>
                  <Collapse in={showErrors}>
                    <Box mt={2}>
                      {preview.validation_errors.map((error, index) => (
                        <Alert key={index} severity="error" sx={{ mt: 1 }}>
                          <Typography variant="subtitle2">Row {error.row}: {error.error}</Typography>
                        </Alert>
                      ))}
                    </Box>
                  </Collapse>
                </CardContent>
              </Card>
            )}
          </Stack>
        )}

        {step === 'complete' && importResult && (
          <Stack spacing={3}>
            {/* Results Summary */}
            <Card variant="outlined">
              <CardContent>
                <Stack direction="row" alignItems="center" spacing={2} mb={2}>
                  <CheckCircle color="success" />
                  <Typography variant="h6">Import Complete</Typography>
                </Stack>
                
                <Stack spacing={1}>
                  <Typography>
                    <strong>Total Rows:</strong> {importResult.total_rows}
                  </Typography>
                  <Typography color="success.main">
                    <strong>Successfully Imported:</strong> {importResult.successful_imports}
                  </Typography>
                  {importResult.updated_existing > 0 && (
                    <Typography color="warning.main">
                      <strong>Updated Existing:</strong> {importResult.updated_existing}
                    </Typography>
                  )}
                  {importResult.skipped_duplicates > 0 && (
                    <Typography color="info.main">
                      <strong>Skipped Duplicates:</strong> {importResult.skipped_duplicates}
                    </Typography>
                  )}
                  {importResult.failed_imports > 0 && (
                    <Typography color="error.main">
                      <strong>Failed:</strong> {importResult.failed_imports}
                    </Typography>
                  )}
                  
                  {/* Goals-specific stats */}
                  {importType === 'goals' && 'goals_created' in importResult && (
                    <>
                      <Divider sx={{ my: 1 }} />
                      <Typography color="success.main">
                        <strong>Goals Created:</strong> {(importResult as GoalImportResult).goals_created}
                      </Typography>
                      <Typography color="success.main">
                        <strong>Objectives Created:</strong> {(importResult as GoalImportResult).objectives_created}
                      </Typography>
                      <Typography color="success.main">
                        <strong>Progress Entries:</strong> {(importResult as GoalImportResult).progress_entries_created}
                      </Typography>
                    </>
                  )}
                </Stack>
              </CardContent>
            </Card>

            {/* Import Errors */}
            {importResult.errors.length > 0 && (
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="h6" color="error" gutterBottom>
                    Import Errors ({importResult.errors.length})
                  </Typography>
                  {importResult.errors.map((error, index) => (
                    <Alert key={index} severity="error" sx={{ mt: 1 }}>
                      Row {error.row}: {error.error}
                    </Alert>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Imported Items */}
            {((importType === 'students' && 'imported_students' in importResult && importResult.imported_students?.length > 0) || 
              (importType === 'goals' && 'imported_goals' in importResult && importResult.imported_goals?.length > 0)) && (
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Imported {importType === 'students' ? 'Students' : 'Goals'} ({
                      importType === 'students' 
                        ? ('imported_students' in importResult ? importResult.imported_students?.length || 0 : 0)
                        : ('imported_goals' in importResult ? (importResult as GoalImportResult).imported_goals?.length || 0 : 0)
                    })
                  </Typography>
                  <Stack spacing={1}>
                    {importType === 'students' && 'imported_students' in importResult
                      ? importResult.imported_students?.slice(0, 10).map((student, index) => (
                          <Box key={index} display="flex" alignItems="center" gap={1}>
                            <Chip
                              label={student.action}
                              color={student.action === 'created' ? 'success' : 'warning'}
                              size="small"
                            />
                            <Typography>{student.name}</Typography>
                            {student.uic && (
                              <Typography variant="caption" color="text.secondary">
                                ({student.uic})
                              </Typography>
                            )}
                          </Box>
                        ))
                      : importType === 'goals' && 'imported_goals' in importResult
                        ? (importResult as GoalImportResult).imported_goals?.slice(0, 10).map((goal, index) => (
                            <Box key={index} display="flex" alignItems="center" gap={1}>
                              <Chip
                                label={goal.action}
                                color={goal.action === 'created' ? 'success' : 'warning'}
                                size="small"
                              />
                              <Typography>{goal.student_name}</Typography>
                              <Typography variant="caption" color="text.secondary">
                                ({goal.objectives_count} objectives)
                              </Typography>
                            </Box>
                          ))
                        : null
                    }
                    {((importType === 'students' && 'imported_students' in importResult ? importResult.imported_students?.length : 
                       importType === 'goals' && 'imported_goals' in importResult ? (importResult as GoalImportResult).imported_goals?.length : 0) || 0) > 10 && (
                      <Typography variant="caption" color="text.secondary">
                        ... and {(importType === 'students' && 'imported_students' in importResult ? importResult.imported_students?.length : 
                                 importType === 'goals' && 'imported_goals' in importResult ? (importResult as GoalImportResult).imported_goals?.length : 0) - 10} more
                      </Typography>
                    )}
                  </Stack>
                </CardContent>
              </Card>
            )}
          </Stack>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={handleClose}>
          {step === 'complete' ? 'Close' : 'Cancel'}
        </Button>
        
        {step === 'preview' && (
          <Button
            onClick={handleImport}
            variant="contained"
            disabled={loading || !preview?.valid}
            startIcon={loading ? undefined : <CloudUpload />}
          >
            {loading ? 'Importing...' : `Import ${importType === 'students' ? 'Students' : 'Goals'}`}
          </Button>
        )}
        
        {step === 'upload' && (
          <Button
            onClick={handleDownloadTemplate}
            variant="outlined"
            startIcon={<Download />}
          >
            Download Template
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
