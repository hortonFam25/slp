import React, { useState, useMemo } from 'react';
import {
  Box,
  Typography,
  Paper,
  TextField,
  InputAdornment,
  Chip,
  Card,
  CardContent,
  IconButton,
  Tooltip,
  Button,
  Badge,
  Collapse,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction
} from '@mui/material';
import {
  Search,
  Person,
  School,
  PersonOutline,
  Add,
  CheckCircle,
  RadioButtonUnchecked,
  ExpandMore,
  ExpandLess
} from '@mui/icons-material';
import { StudentScheduleView } from '../../../lib/api/schedulingStudents';

interface StudentScheduleStatus {
  student: StudentScheduleView;
  hasAppointments: boolean;
  appointmentCount: number;
  appointments: any[];
}

interface UnscheduledStudentsPanelProps {
  studentScheduleData: {
    all: StudentScheduleStatus[];
    scheduled: StudentScheduleStatus[];
    unscheduled: StudentScheduleStatus[];
    counts: {
      total: number;
      scheduled: number;
      unscheduled: number;
    };
  };
  schools?: Array<{ id: number; name: string }>;
  teachers?: Array<{ id: number; full_name: string }>;
  onQuickSchedule: (student: StudentScheduleView) => void;
  loading?: boolean;
}

type FilterMode = 'unscheduled' | 'all' | 'scheduled';

export function UnscheduledStudentsPanel({
  studentScheduleData,
  schools = [],
  teachers = [],
  onQuickSchedule,
  loading = false
}: UnscheduledStudentsPanelProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterMode, setFilterMode] = useState<FilterMode>('unscheduled');
  const [isExpanded, setIsExpanded] = useState(true);

  // Get current student list based on filter mode
  const currentStudents = useMemo(() => {
    let students: StudentScheduleStatus[] = [];
    
    switch (filterMode) {
      case 'scheduled':
        students = studentScheduleData.scheduled;
        break;
      case 'unscheduled':
        students = studentScheduleData.unscheduled;
        break;
      case 'all':
      default:
        students = studentScheduleData.all;
        break;
    }

    // Apply search filter
    if (searchTerm.trim()) {
      const searchLower = searchTerm.toLowerCase();
      students = students.filter(status => {
        const fullName = `${status.student.first?.trim() || ''} ${status.student.last?.trim() || ''}`.trim();
        return fullName.toLowerCase().includes(searchLower) ||
               status.student.uic?.toLowerCase().includes(searchLower);
      });
    }

    return students;
  }, [studentScheduleData, filterMode, searchTerm]);

  // Helper to get school name (now using computed property from StudentScheduleView)
  const getSchoolName = (student: StudentScheduleView) => {
    return student.school_name || 'No School Assigned';
  };

  // Helper to get primary teacher name (now using computed property from StudentScheduleView)
  const getPrimaryTeacher = (student: StudentScheduleView) => {
    return student.primary_teacher_name || 'No Teacher Assigned';
  };

  return (
    <Paper 
      elevation={1} 
      sx={{ 
        width: 300, 
        height: '100%', // Take full available height
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden' // Prevent the Paper itself from scrolling
      }}
    >
      {/* Sticky Header */}
      <Box sx={{ 
        p: 2, 
        borderBottom: '1px solid #e0e0e0',
        flexShrink: 0 // Prevent header from shrinking
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Person color="primary" />
            Students
          </Typography>
          <IconButton 
            size="small" 
            onClick={() => setIsExpanded(!isExpanded)}
            color="primary"
          >
            {isExpanded ? <ExpandLess /> : <ExpandMore />}
          </IconButton>
        </Box>

        <Collapse in={isExpanded}>
          {/* Search */}
          <TextField
            fullWidth
            size="small"
            placeholder="Search students..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search fontSize="small" />
                </InputAdornment>
              )
            }}
            sx={{ mb: 2 }}
          />

          {/* Filter Chips */}
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Chip
              icon={<Person />}
              label={`All (${studentScheduleData.counts.total})`}
              onClick={() => setFilterMode('all')}
              color={filterMode === 'all' ? 'primary' : 'default'}
              variant={filterMode === 'all' ? 'filled' : 'outlined'}
              size="small"
            />
            <Chip
              icon={<RadioButtonUnchecked />}
              label={`Unscheduled (${studentScheduleData.counts.unscheduled})`}
              onClick={() => setFilterMode('unscheduled')}
              color={filterMode === 'unscheduled' ? 'error' : 'default'}
              variant={filterMode === 'unscheduled' ? 'filled' : 'outlined'}
              size="small"
            />
            <Chip
              icon={<CheckCircle />}
              label={`Scheduled (${studentScheduleData.counts.scheduled})`}
              onClick={() => setFilterMode('scheduled')}
              color={filterMode === 'scheduled' ? 'success' : 'default'}
              variant={filterMode === 'scheduled' ? 'filled' : 'outlined'}
              size="small"
            />
          </Box>
        </Collapse>
      </Box>

      {/* Scrollable Student List */}
      {isExpanded && (
        <Box sx={{ 
          flex: 1, 
          overflow: 'auto',
          minHeight: 0, // Important: allows the box to shrink below content size
          display: 'flex',
          flexDirection: 'column'
        }}>
          {loading ? (
            <Box sx={{ p: 2, textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary">
                Loading students...
              </Typography>
            </Box>
          ) : currentStudents.length === 0 ? (
            <Box sx={{ p: 2, textAlign: 'center' }}>
              <PersonOutline sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
              <Typography variant="body2" color="text.secondary">
                {searchTerm.trim() ? 'No students found matching your search' : 
                 filterMode === 'unscheduled' ? 'All students are scheduled!' :
                 filterMode === 'scheduled' ? 'No students are scheduled yet' :
                 'No students found'}
              </Typography>
            </Box>
          ) : (
            <List dense sx={{ p: 0 }}>
              {currentStudents.map((status, index) => (
                <React.Fragment key={status.student.id}>
                  <ListItem sx={{ py: 0.5, px: 1.5 }}>
                    <Box sx={{ width: '100%' }}>
                      {/* Student Name and Status - more compact */}
                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.25 }}>
                        <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
                          {`${status.student.first?.trim() || ''} ${status.student.last?.trim() || ''}`.trim()}
                        </Typography>
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          {status.hasAppointments ? (
                            <Tooltip title={`${status.appointmentCount} appointment${status.appointmentCount !== 1 ? 's' : ''}`}>
                              <Badge badgeContent={status.appointmentCount} color="success" size="small">
                                <CheckCircle color="success" sx={{ fontSize: 16 }} />
                              </Badge>
                            </Tooltip>
                          ) : (
                            <Tooltip title="No appointments scheduled">
                              <RadioButtonUnchecked color="error" sx={{ fontSize: 16 }} />
                            </Tooltip>
                          )}
                        </Box>
                      </Box>

                      {/* Student Details - more compact */}
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.125, mb: 0.5 }}>
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.25, fontSize: '0.75rem' }}>
                          <School sx={{ fontSize: 10 }} />
                          {getSchoolName(status.student)}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.25, fontSize: '0.75rem' }}>
                          <Person sx={{ fontSize: 10 }} />
                          {getPrimaryTeacher(status.student)}
                        </Typography>
                      </Box>

                      {/* Quick Schedule Button - smaller */}
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<Add sx={{ fontSize: 14 }} />}
                        onClick={() => onQuickSchedule(status.student)}
                        fullWidth
                        sx={{ 
                          minHeight: 28,
                          fontSize: '0.75rem',
                          borderColor: status.hasAppointments ? '#4caf50' : '#f44336',
                          color: status.hasAppointments ? '#4caf50' : '#f44336',
                          '&:hover': {
                            borderColor: status.hasAppointments ? '#45a049' : '#e53935',
                            backgroundColor: status.hasAppointments ? '#e8f5e8' : '#ffebee'
                          }
                        }}
                      >
                        {status.hasAppointments ? 'Add Another' : 'Quick Schedule'}
                      </Button>
                    </Box>
                  </ListItem>
                  {index < currentStudents.length - 1 && <Divider sx={{ borderColor: '#f0f0f0' }} />}
                </React.Fragment>
              ))}
            </List>
          )}
        </Box>
      )}
    </Paper>
  );
}
