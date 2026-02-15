import React, { useState, useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  CircularProgress,
  Alert,
  Stack,
  Chip,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Tooltip,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  LinearProgress,
  Collapse,
  TablePagination,
  TableFooter,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { 
  Add, 
  Refresh, 
  MoreVert,
  Edit,
  Delete,
  PlayArrow,
  Stop,
  CalendarToday,
  Schedule,
  Psychology,
  TrackChanges,
  Assessment,
  ExpandMore,
  ExpandLess,
  Timer,
} from '@mui/icons-material';
import { TherapySessionSummary } from '../../lib/api/therapySessions';
import { useDeleteTherapySession, useUpdateTherapySession } from '../../lib/hooks/useTherapySessions';

interface StudentTherapySessionsProps {
  studentId: number;
  therapySessions: TherapySessionSummary[];
  loading: boolean;
  onRefresh: () => void;
}

interface ExpandedSessions {
  [key: number]: boolean;
}

export function StudentTherapySessions({ studentId, therapySessions, loading, onRefresh }: StudentTherapySessionsProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [actionMenuAnchor, setActionMenuAnchor] = useState<null | HTMLElement>(null);
  const [selectedSession, setSelectedSession] = useState<TherapySessionSummary | null>(null);
  const [expandedSessions, setExpandedSessions] = useState<ExpandedSessions>({});
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const deleteSessionMutation = useDeleteTherapySession();
  const updateSessionMutation = useUpdateTherapySession();
  const [durationDialogOpen, setDurationDialogOpen] = useState(false);
  const [durationSession, setDurationSession] = useState<TherapySessionSummary | null>(null);
  const [durationMinutes, setDurationMinutes] = useState<number>(0);

  const handleActionMenuOpen = (event: React.MouseEvent<HTMLElement>, session: TherapySessionSummary) => {
    setActionMenuAnchor(event.currentTarget);
    setSelectedSession(session);
  };

  const handleActionMenuClose = () => {
    setActionMenuAnchor(null);
    setSelectedSession(null);
  };

  const handleOpenAdjustDuration = (session: TherapySessionSummary) => {
    setDurationSession(session);
    setDurationMinutes(Math.max(0, session.duration_minutes || 0));
    setDurationDialogOpen(true);
  };

  const handleCloseAdjustDuration = () => {
    if (updateSessionMutation.isPending) return;
    setDurationDialogOpen(false);
    setDurationSession(null);
  };

  const handleSaveAdjustedDuration = async () => {
    if (!durationSession) return;
    const minutes = Number(durationMinutes);
    if (!Number.isFinite(minutes) || minutes <= 0) {
      alert('Please enter a duration greater than 0 minutes.');
      return;
    }

    try {
      const sessionData: any = {
        actual_duration_minutes: minutes,
      };

      // If we have an actual start time, also adjust actual_end_time so duration updates consistently.
      if (durationSession.actual_start_time) {
        const start = new Date(durationSession.actual_start_time);
        if (!Number.isNaN(start.getTime())) {
          const end = new Date(start.getTime() + minutes * 60 * 1000);
          sessionData.actual_end_time = end.toISOString();
        }
      }

      await updateSessionMutation.mutateAsync({
        sessionId: durationSession.id,
        sessionData,
      });
      onRefresh();
      handleCloseAdjustDuration();
    } catch (err) {
      console.error('Failed to update session duration:', err);
      alert('Failed to update session duration. Please try again.');
    }
  };

  const toggleSessionExpansion = (sessionId: number) => {
    setExpandedSessions(prev => ({
      ...prev,
      [sessionId]: !prev[sessionId]
    }));
  };

  const formatDateTime = (dateString: string) => {
    const date = new Date(dateString);
    return {
      date: date.toLocaleDateString(),
      time: date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
  };

  const getDisplayTimeRange = (session: TherapySessionSummary) => {
    const useActual = (session.status === 'in-progress' || session.status === 'completed') &&
      !!session.actual_start_time;
    const start = useActual ? session.actual_start_time : session.start_time;
    const end = useActual ? session.actual_end_time : session.end_time;
    return { start, end };
  };

  const formatDuration = (minutes: number) => {
    if (minutes < 60) {
      return `${minutes}m`;
    }
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'planned':
        return 'primary';
      case 'in-progress':
        return 'info';
      case 'completed':
        return 'success';
      case 'cancelled':
        return 'error';
      case 'no-show':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getTypeColor = (type: string) => {
    switch (type.toLowerCase()) {
      case 'individual':
        return 'primary';
      case 'group':
        return 'secondary';
      case 'assessment':
        return 'warning';
      case 'consultation':
        return 'info';
      default:
        return 'default';
    }
  };

  // Mobile card component for therapy sessions
  const TherapySessionCard = ({ session }: { session: TherapySessionSummary }) => {
    const { date, time } = formatDateTime(session.session_date);
    
    return (
      <Card variant="outlined" sx={{ mb: 1.5 }}>
        <CardContent sx={{ p: 2 }}>
          <Stack spacing={1.5}>
            {/* Header with date and actions */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '0.9rem' }}>
                  {date}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8rem' }}>
                  {time} • {formatDuration(session.duration_minutes || 0)}
                </Typography>
              </Box>
              <IconButton
                size="small"
                onClick={(e) => handleActionMenuOpen(e, session)}
                sx={{ width: 32, height: 32 }}
              >
                <MoreVert fontSize="small" />
              </IconButton>
            </Box>

            {/* Status and Type chips */}
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Chip
                label={session.status}
                size="small"
                color={getStatusColor(session.status)}
                sx={{ fontSize: '0.7rem' }}
              />
              <Chip
                label={session.session_type}
                size="small"
                color={getTypeColor(session.session_type)}
                variant="outlined"
                sx={{ fontSize: '0.7rem' }}
              />
            </Box>


          </Stack>
        </CardContent>
      </Card>
    );
  };

  const getQualityColor = (quality?: string) => {
    if (!quality) return 'default';
    switch (quality.toLowerCase()) {
      case 'excellent':
        return 'success';
      case 'good':
        return 'info';
      case 'fair':
        return 'warning';
      case 'poor':
        return 'error';
      default:
        return 'default';
    }
  };

  const handleStartSession = (session: TherapySessionSummary) => {
    // TODO: Implement start/resume session
    console.log('Starting session:', session.id);
  };

  const handleCompleteSession = (session: TherapySessionSummary) => {
    // TODO: Implement complete session
    console.log('Completing session:', session.id);
  };

  const handleEditSession = (session: TherapySessionSummary) => {
    // TODO: Implement edit session
    console.log('Editing session:', session.id);
  };

  const handleDeleteSession = async (session: TherapySessionSummary) => {
    if (window.confirm('Are you sure you want to delete this therapy session?')) {
      try {
        await deleteSessionMutation.mutateAsync(session.id);
        onRefresh();
      } catch (err) {
        console.error('Failed to delete therapy session:', err);
        alert('Failed to delete therapy session. Please try again.');
      }
    }
  };

  // Apply pagination (data already ordered oldest to newest from API)
  const sortedAndPaginatedSessions = useMemo(() => {
    const startIndex = page * rowsPerPage;
    const endIndex = startIndex + rowsPerPage;
    
    return therapySessions.slice(startIndex, endIndex);
  }, [therapySessions, page, rowsPerPage]);

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="300px">
        <CircularProgress />
      </Box>
    );
  }

  const activeSessions = therapySessions.filter(s => s.status === 'in-progress');
  const completedSessions = therapySessions.filter(s => s.status === 'completed');
  const plannedSessions = therapySessions.filter(s => s.status === 'planned');

  return (
    <Box sx={{ 
      height: 'calc(100vh - 300px)', // Account for dialog header, tabs, and buttons
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      mx: isMobile ? -2 : -3, // Counteract TabPanel padding
      mt: isMobile ? -2 : -3  // Counteract TabPanel padding
    }}>
      {/* Fixed Header Section */}
      <Box sx={{ 
        flexShrink: 0,
        backgroundColor: 'background.default',
        borderBottom: 1,
        borderColor: 'divider',
        p: isMobile ? 2 : 3,
        zIndex: 1
      }}>
        <Box sx={{ 
          display: 'flex', 
          flexDirection: isMobile ? 'column' : 'row',
          justifyContent: 'space-between', 
          alignItems: isMobile ? 'stretch' : 'center', 
          gap: isMobile ? 2 : 0
        }}>
          <Typography variant={isMobile ? "h6" : "h5"} sx={{ 
            textAlign: isMobile ? 'center' : 'left',
            fontSize: isMobile ? '1.2rem' : '1.5rem'
          }}>
            Therapy Sessions ({therapySessions.length})
          </Typography>
          <Stack 
            direction={isMobile ? 'column' : 'row'} 
            spacing={1}
            sx={{ width: isMobile ? '100%' : 'auto' }}
          >
            <Button
              variant="outlined"
              startIcon={<Refresh />}
              onClick={onRefresh}
              fullWidth={isMobile}
              size={isMobile ? 'medium' : 'large'}
            >
              Refresh
            </Button>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => {
              // TODO: Implement create session
              console.log('Creating session for student:', studentId);
            }}
            fullWidth={isMobile}
            size={isMobile ? 'medium' : 'large'}
          >
            Start New Session
          </Button>
        </Stack>

        {/* Active Sessions Alert */}
        {activeSessions.length > 0 && (
          <Alert severity="info" sx={{ mt: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Active Sessions ({activeSessions.length})
            </Typography>
            {activeSessions.map(session => (
              <Typography key={session.id} variant="body2">
                Session from {formatDateTime(session.session_date).date} - {formatDuration(session.duration_minutes)}
              </Typography>
            ))}
          </Alert>
        )}
        </Box>
      </Box>  
      {/* Scrollable Content Area */}
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
            {therapySessions.length === 0 ? (
              <Typography color="text.secondary" textAlign="center" sx={{ py: 4 }}>
                No therapy sessions found for this student. Click "Start New Session" to begin the first session.
              </Typography>
            ) : isMobile ? (
              // Mobile Card Layout
              <Box>
                {sortedAndPaginatedSessions.map((session) => (
                  <TherapySessionCard key={session.id} session={session} />
                ))}
                
                {/* Mobile Pagination */}
                <Box sx={{ 
                  display: 'flex', 
                  justifyContent: 'center', 
                  mt: 2,
                  px: 1
                }}>
                  <TablePagination
                    component="div"
                    count={therapySessions.length}
                    page={page}
                    onPageChange={handleChangePage}
                    rowsPerPage={rowsPerPage}
                    onRowsPerPageChange={handleChangeRowsPerPage}
                    rowsPerPageOptions={[5, 10, 25]}
                    labelRowsPerPage="Per page:"
                    labelDisplayedRows={({ from, to, count }) => 
                      `${from}-${to} of ${count}`
                    }
                    sx={{
                      '& .MuiTablePagination-select': {
                        fontSize: '0.8rem',
                      },
                      '& .MuiTablePagination-selectLabel': {
                        fontSize: '0.8rem',
                      },
                      '& .MuiTablePagination-displayedRows': {
                        fontSize: '0.8rem',
                      },
                    }}
                  />
                </Box>
              </Box>
            ) : (
              // Desktop Table Layout
              <TableContainer 
                component={Paper} 
                variant="outlined"
              >
                <Table stickyHeader>
                  <TableHead>
                    <TableRow>
                <TableCell width="40px"></TableCell>
                <TableCell>Date & Time</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Duration</TableCell>
                <TableCell>Goals</TableCell>
                <TableCell>Quality</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedAndPaginatedSessions.map((session) => {
                  const { date, time } = formatDateTime(session.session_date);
                  const canStart = session.status === 'planned';
                  const canComplete = session.status === 'in-progress';
                  const isExpanded = expandedSessions[session.id];
                  const { start, end } = getDisplayTimeRange(session);
                  
                  return (
                    <React.Fragment key={session.id}>
                      <TableRow hover>
                        <TableCell>
                          <IconButton
                            size="small"
                            onClick={() => toggleSessionExpansion(session.id)}
                          >
                            {isExpanded ? <ExpandLess /> : <ExpandMore />}
                          </IconButton>
                        </TableCell>
                        
                        <TableCell>
                          <Box>
                            <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                              <CalendarToday fontSize="small" color="action" />
                              {date}
                            </Typography>
                            {start && (
                              <Typography variant="body2" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <Schedule fontSize="small" color="action" />
                                {formatDateTime(start).time}
                                {end && ` - ${formatDateTime(end).time}`}
                              </Typography>
                            )}
                          </Box>
                        </TableCell>
                        
                        <TableCell>
                          <Chip
                            label={session.session_type}
                            color={getTypeColor(session.session_type)}
                            size="small"
                            variant="outlined"
                            icon={<Psychology />}
                          />
                        </TableCell>
                        
                        <TableCell>
                          <Chip
                            label={session.status}
                            color={getStatusColor(session.status)}
                            size="small"
                          />
                        </TableCell>
                        
                        <TableCell>
                          <Typography variant="body2">
                            {formatDuration(session.duration_minutes)}
                          </Typography>
                        </TableCell>
                        
                        <TableCell>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            {session.goals_addressed ? (
                              <Chip
                                label="Goals Addressed"
                                color="success"
                                size="small"
                                icon={<TrackChanges />}
                              />
                            ) : (
                              <Chip
                                label="No Goals"
                                color="default"
                                size="small"
                                variant="outlined"
                              />
                            )}
                          </Box>
                        </TableCell>
                        
                        <TableCell>
                          {session.session_quality ? (
                            <Chip
                              label={session.session_quality}
                              color={getQualityColor(session.session_quality)}
                              size="small"
                              variant="outlined"
                            />
                          ) : (
                            <Typography variant="body2" color="text.secondary">
                              Not rated
                            </Typography>
                          )}
                        </TableCell>
                        
                        <TableCell align="right">
                          <Stack direction="row" spacing={1} justifyContent="flex-end">
                            {canStart && (
                              <Tooltip title="Start Session">
                                <IconButton
                                  size="small"
                                  color="success"
                                  onClick={() => handleStartSession(session)}
                                >
                                  <PlayArrow />
                                </IconButton>
                              </Tooltip>
                            )}
                            {canComplete && (
                              <Tooltip title="Complete Session">
                                <IconButton
                                  size="small"
                                  color="primary"
                                  onClick={() => handleCompleteSession(session)}
                                >
                                  <Stop />
                                </IconButton>
                              </Tooltip>
                            )}
                            <IconButton
                              size="small"
                              onClick={(e) => handleActionMenuOpen(e, session)}
                            >
                              <MoreVert />
                            </IconButton>
                          </Stack>
                        </TableCell>
                      </TableRow>
                      
                      {/* Expanded Row with Session Details */}
                      <TableRow>
                        <TableCell colSpan={8} sx={{ py: 0 }}>
                          <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                            <Box sx={{ py: 2, px: 2, bgcolor: 'grey.50', borderRadius: 1, m: 1 }}>
                              <Typography variant="subtitle2" gutterBottom>
                                Session Details
                              </Typography>
                              <Stack spacing={2}>
                                {session.student_name && (
                                  <Typography variant="body2">
                                    <strong>Student:</strong> {session.student_name}
                                  </Typography>
                                )}
                                {session.is_scheduled && (
                                  <Typography variant="body2">
                                    <strong>Scheduled Session:</strong> Yes
                                  </Typography>
                                )}
                                <Typography variant="body2">
                                  <strong>Duration:</strong> {formatDuration(session.duration_minutes)}
                                </Typography>
                                <Typography variant="body2">
                                  <strong>Goals Addressed:</strong> {session.goals_addressed ? 'Yes' : 'No'}
                                </Typography>
                                {session.session_quality && (
                                  <Typography variant="body2">
                                    <strong>Session Quality:</strong> {session.session_quality}
                                  </Typography>
                                )}
                              </Stack>
                            </Box>
                          </Collapse>
                        </TableCell>
                      </TableRow>
                    </React.Fragment>
                  );
                })}
            </TableBody>
            <TableFooter>
              <TableRow>
                <TablePagination
                  rowsPerPageOptions={[5, 10, 25, 50]}
                  colSpan={8}
                  count={therapySessions.length}
                  rowsPerPage={rowsPerPage}
                  page={page}
                  onPageChange={handleChangePage}
                  onRowsPerPageChange={handleChangeRowsPerPage}
                  labelRowsPerPage="Sessions per page:"
                />
              </TableRow>
            </TableFooter>
                </Table>
              </TableContainer>
            )}
          </CardContent>
        </Card>
      </Box>

      {/* Action Menu */}
      <Menu
        anchorEl={actionMenuAnchor}
        open={Boolean(actionMenuAnchor)}
        onClose={handleActionMenuClose}
      >
        <MenuItem onClick={() => {
          if (selectedSession) handleEditSession(selectedSession);
          handleActionMenuClose();
        }}>
          <ListItemIcon>
            <Edit fontSize="small" />
          </ListItemIcon>
          <ListItemText>Edit Session</ListItemText>
        </MenuItem>

        <MenuItem onClick={() => {
          if (selectedSession) handleOpenAdjustDuration(selectedSession);
          handleActionMenuClose();
        }}>
          <ListItemIcon>
            <Timer fontSize="small" />
          </ListItemIcon>
          <ListItemText>Adjust Actual Duration</ListItemText>
        </MenuItem>
        
        {selectedSession?.status === 'planned' && (
          <MenuItem onClick={() => {
            if (selectedSession) handleStartSession(selectedSession);
            handleActionMenuClose();
          }}>
            <ListItemIcon>
              <PlayArrow fontSize="small" color="success" />
            </ListItemIcon>
            <ListItemText>Start Session</ListItemText>
          </MenuItem>
        )}
        
        {selectedSession?.status === 'in-progress' && (
          <MenuItem onClick={() => {
            if (selectedSession) handleCompleteSession(selectedSession);
            handleActionMenuClose();
          }}>
            <ListItemIcon>
              <Stop fontSize="small" color="primary" />
            </ListItemIcon>
            <ListItemText>Complete Session</ListItemText>
          </MenuItem>
        )}
        
        <MenuItem 
          onClick={() => {
            if (selectedSession) handleDeleteSession(selectedSession);
            handleActionMenuClose();
          }}
          sx={{ color: 'error.main' }}
        >
          <ListItemIcon>
            <Delete fontSize="small" color="error" />
          </ListItemIcon>
          <ListItemText>Delete Session</ListItemText>
        </MenuItem>
      </Menu>

      {/* Adjust Duration Dialog */}
      <Dialog open={durationDialogOpen} onClose={handleCloseAdjustDuration} maxWidth="xs" fullWidth>
        <DialogTitle>Adjust Actual Duration</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            type="number"
            label="Minutes"
            value={durationMinutes}
            onChange={(e) => setDurationMinutes(Number(e.target.value))}
            inputProps={{ min: 1, step: 1 }}
            sx={{ mt: 1 }}
            helperText="Sets actual therapy minutes. If actual start time exists, actual end time will be recalculated."
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseAdjustDuration} disabled={updateSessionMutation.isPending}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSaveAdjustedDuration}
            disabled={updateSessionMutation.isPending}
          >
            {updateSessionMutation.isPending ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
