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
} from '@mui/material';
import { 
  CloudUpload, 
  Download, 
  CheckCircle, 
  Error, 
  Warning,
  ExpandMore,
  ExpandLess
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import { csvApi, CSVPreviewResult, CSVImportResult } from '../lib/api/csv';

interface CSVImportProps {
  open: boolean;
  onClose: () => void;
  onImportComplete?: (result: CSVImportResult) => void;
}

export function CSVImport({ open, onClose, onImportComplete }: CSVImportProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<CSVPreviewResult | null>(null);
  const [importResult, setImportResult] = useState<CSVImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<'upload' | 'preview' | 'complete'>('upload');
  
  // Import options
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [updateExisting, setUpdateExisting] = useState(false);
  const [showErrors, setShowErrors] = useState(false);

  // Dropzone configuration
  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const selectedFile = acceptedFiles[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setLoading(true);

    try {
      const previewResult = await csvApi.previewImport(selectedFile, { max_rows: 10 });
      setPreview(previewResult);
      setStep('preview');
    } catch (error) {
      console.error('Preview error:', error);
      alert(`Error previewing file: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  }, []);

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
      const result = await csvApi.importFromFile(file, {
        skip_duplicates: skipDuplicates,
        update_existing: updateExisting,
      });
      
      setImportResult(result);
      setStep('complete');
      onImportComplete?.(result);
    } catch (error) {
      console.error('Import error:', error);
      alert(`Error importing file: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      await csvApi.downloadTemplateFile();
    } catch (error) {
      console.error('Download error:', error);
      alert(`Error downloading template: ${error instanceof Error ? error.message : 'Unknown error'}`);
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

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        Import Students from CSV
        {loading && <LinearProgress sx={{ mt: 1 }} />}
      </DialogTitle>
      
      <DialogContent>
        {step === 'upload' && (
          <Stack spacing={3}>
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
                <li>Use UTF-8 encoding</li>
                <li>Required fields: first, last</li>
                <li>Optional fields: uic, grade_level, teacher_name, case_manager, enrollment_status, date_of_birth</li>
                <li>Date format: YYYY-MM-DD</li>
                <li>Enrollment status options: Active, Inactive, Transferred</li>
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
                    label="Skip students with duplicate UICs"
                  />
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={updateExisting}
                        onChange={(e) => setUpdateExisting(e.target.checked)}
                      />
                    }
                    label="Update existing students when UIC matches"
                  />
                </Stack>
              </CardContent>
            </Card>

            {/* Preview Table */}
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Row</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Name</TableCell>
                    <TableCell>UIC</TableCell>
                    <TableCell>Grade</TableCell>
                    <TableCell>Case Manager</TableCell>
                    <TableCell>Notes</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {preview.preview_rows.map((row, index) => (
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
                        {row.data.first} {row.data.last}
                      </TableCell>
                      <TableCell>{row.data.uic || '-'}</TableCell>
                      <TableCell>{row.data.grade_level || '-'}</TableCell>
                      <TableCell>{row.data.case_manager || '-'}</TableCell>
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
                  ))}
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
                  <Typography color="warning.main">
                    <strong>Updated Existing:</strong> {importResult.updated_existing}
                  </Typography>
                  <Typography color="info.main">
                    <strong>Skipped Duplicates:</strong> {importResult.skipped_duplicates}
                  </Typography>
                  <Typography color="error.main">
                    <strong>Failed:</strong> {importResult.failed_imports}
                  </Typography>
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

            {/* Imported Students */}
            {importResult.imported_students.length > 0 && (
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Imported Students ({importResult.imported_students.length})
                  </Typography>
                  <Stack spacing={1}>
                    {importResult.imported_students.slice(0, 10).map((student, index) => (
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
                    ))}
                    {importResult.imported_students.length > 10 && (
                      <Typography variant="caption" color="text.secondary">
                        ... and {importResult.imported_students.length - 10} more
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
            {loading ? 'Importing...' : 'Import Students'}
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
