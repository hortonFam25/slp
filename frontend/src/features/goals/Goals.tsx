import React, { useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  Grid,
  Alert,
  Tabs,
  Tab,
  Paper,
  useMediaQuery,
  useTheme,
  Stack,
  IconButton
} from '@mui/material';
import { Search, TrackChanges, Category, Person, FileUpload, Refresh } from '@mui/icons-material';
import { Target } from 'lucide-react';
import { GoalManagement } from '../../components/GoalManagement';
import { useStudents } from '../../lib/hooks/useStudents';
import { GoalCategoriesManagement } from './components/GoalCategoriesManagement';
import { UniversalCSVImport } from '../../components/UniversalCSVImport';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`goals-tabpanel-${index}`}
      aria-labelledby={`goals-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ pt: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

export default function Goals() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [tabValue, setTabValue] = useState(0);
  const { students, loading, error, refetch } = useStudents();
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [isCSVImportOpen, setIsCSVImportOpen] = useState(false);

  // Filter students based on search term
  const filteredStudents = students.filter(student =>
    `${student.first} ${student.last}`.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (student.uic && student.uic.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const selectedStudent = students.find(s => s.id === selectedStudentId);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleCSVImportComplete = (result: any) => {
    setIsCSVImportOpen(false);
    refetch(); // Refresh the students list to pick up any new data
  };

  return (
    <Box sx={{ 
      p: isMobile ? 2 : 3,
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    }}>
      {/* Header */}
      <Box sx={{ flexShrink: 0, mb: 2 }}>
        <Box sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: isMobile ? 'flex-start' : 'center',
          flexDirection: isMobile ? 'column' : 'row',
          gap: isMobile ? 2 : 0,
          mb: 2
        }}>
          <Typography 
            variant={isMobile ? "h5" : "h4"} 
            component="h1" 
            sx={{ 
              display: 'flex', 
              alignItems: 'center',
              fontSize: isMobile ? '1.5rem' : undefined,
              color: '#41AAB7',
              fontWeight: 700,
              gap: 2
            }}
          >
            <Target size={isMobile ? 24 : 32} />
            Goals
          </Typography>
          
          <Stack direction="row" spacing={1}>
            <IconButton onClick={refetch} disabled={loading}>
              <Refresh />
            </IconButton>
            <Button 
              variant="outlined" 
              startIcon={<FileUpload />}
              onClick={() => setIsCSVImportOpen(true)}
              size={isMobile ? "small" : "medium"}
            >
              Import Goals
            </Button>
          </Stack>
        </Box>

        {/* Navigation Tabs */}
        <Paper elevation={1} sx={{ flexShrink: 0 }}>
          <Tabs 
            value={tabValue} 
            onChange={handleTabChange}
            variant={isMobile ? "fullWidth" : "standard"}
            sx={{ 
              borderBottom: 1, 
              borderColor: 'divider',
              minHeight: isMobile ? 42 : 48
            }}
          >
            <Tab 
              label={isMobile ? "Student Goals" : "Student Goal Management"} 
              icon={!isMobile ? <Person /> : undefined}
              iconPosition="start"
              sx={{ 
                minHeight: isMobile ? 42 : 48,
                fontSize: isMobile ? '0.85rem' : undefined
              }}
            />
            <Tab 
              label={isMobile ? "Categories" : "Goal Categories"} 
              icon={!isMobile ? <Category /> : undefined}
              iconPosition="start"
              sx={{ 
                minHeight: isMobile ? 42 : 48,
                fontSize: isMobile ? '0.85rem' : undefined
              }}
            />
          </Tabs>
        </Paper>
      </Box>

      {/* Tab Content - Scrollable */}
      <Box sx={{ 
        flex: 1,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column'
      }}>

        {/* Tab Panel 0: Student Goal Management */}
        <TabPanel value={tabValue} index={0}>
          <Box sx={{ 
            height: '70vh',
            display: 'flex',
            flexDirection: 'column'
          }}>
            {/* Sticky Header Section */}
            <Box sx={{ 
              position: 'sticky',
              top: 0,
              zIndex: 10,
              backgroundColor: 'background.default',
              borderBottom: 1,
              borderColor: 'divider',
              pb: 1,
              mb: 2,
              flexShrink: 0
            }}>
              {/* Compact Student Selection */}
              <Box sx={{ 
                display: 'flex', 
                gap: 2, 
                alignItems: 'center',
                flexWrap: isMobile ? 'wrap' : 'nowrap'
              }}>
                <TextField
                  size="small"
                  label="Search Students"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Search by name or UIC..."
                  sx={{ 
                    minWidth: 200,
                    flex: isMobile ? '1 1 100%' : '1 1 auto'
                  }}
                  InputProps={{
                    startAdornment: <Search sx={{ mr: 1, color: 'text.secondary', fontSize: 18 }} />
                  }}
                />
                <FormControl 
                  size="small" 
                  sx={{ 
                    minWidth: 250,
                    flex: isMobile ? '1 1 100%' : '1 1 auto'
                  }}
                >
                  <InputLabel>Select Student</InputLabel>
                  <Select
                    value={selectedStudentId || ''}
                    onChange={(e) => setSelectedStudentId(Number(e.target.value) || null)}
                    label="Select Student"
                    disabled={loading}
                  >
                    <MenuItem value="">Choose a student...</MenuItem>
                    {filteredStudents.map((student) => (
                      <MenuItem key={student.id} value={student.id}>
                        {student.first} {student.last}
                        {student.uic && ` (${student.uic})`}
                        {student.grade_level && ` - Grade ${student.grade_level}`}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Box>

              {/* Error Alert */}
              {error && (
                <Alert severity="error" sx={{ mt: 1, py: 0.5 }}>
                  {error}
                </Alert>
              )}

              {/* Search Results Alert */}
              {filteredStudents.length === 0 && searchTerm && (
                <Alert severity="info" sx={{ mt: 1, py: 0.5 }}>
                  No students found matching "{searchTerm}"
                </Alert>
              )}
            </Box>

            {/* Goal Content */}
            <Box sx={{ 
              flex: 1,
              minHeight: 0,
              overflow: 'hidden'
            }}>
              {selectedStudentId ? (
                <GoalManagement 
                  studentId={selectedStudentId} 
                  studentName={selectedStudent?.first + ' ' + selectedStudent?.last}
                />
              ) : (
                <Card>
                  <CardContent sx={{ textAlign: 'center', py: 6 }}>
                    <TrackChanges sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                    <Typography variant="h6" color="text.secondary" sx={{ mb: 1 }}>
                      No Student Selected
                    </Typography>
                    <Typography color="text.secondary" sx={{ mb: 3 }}>
                      Please select a student to view and manage their IEP goals.
                    </Typography>
                    <Button
                      variant="outlined"
                      onClick={() => {
                        const firstStudent = filteredStudents[0];
                        if (firstStudent) {
                          setSelectedStudentId(firstStudent.id);
                        }
                      }}
                      disabled={filteredStudents.length === 0}
                    >
                      {filteredStudents.length > 0 ? 'Select First Student' : 'No Students Available'}
                    </Button>
                  </CardContent>
                </Card>
              )}
            </Box>
          </Box>
        </TabPanel>

        {/* Tab Panel 1: Goal Categories Management */}
        <TabPanel value={tabValue} index={1}>
          <Box sx={{ 
            height: '100%',
            overflow: 'auto'
          }}>
            <GoalCategoriesManagement />
          </Box>
        </TabPanel>
      </Box>

      {/* CSV Import Dialog */}
      <UniversalCSVImport
        open={isCSVImportOpen}
        onClose={() => setIsCSVImportOpen(false)}
        onImportComplete={handleCSVImportComplete}
        defaultImportType="goals"
      />
    </Box>
  );
}
