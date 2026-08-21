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
  TablePagination,
  TableFooter,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { 
  Add, 
  Refresh, 
  MoreVert,
  Edit,
  PlayArrow,
  CalendarToday,
  Schedule,
  LocationOn,
  Person,
  Archive as ArchiveIcon,
} from '@mui/icons-material';
import { AppointmentSummary, schedulingApi } from '../../lib/api/scheduling';
import { useArchiveWithUndo, archiveMessage, archiveTitle } from '../../lib/archive';
import { ConfirmationModal } from '../ui/ConfirmationModal';

interface StudentAppointmentsProps {
  studentId: number;
  appointments: AppointmentSummary[];
  loading: boolean;
  onRefresh: () => void;
}

export function StudentAppointments({ studentId, appointments, loading, onRefresh }: StudentAppointmentsProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [actionMenuAnchor, setActionMenuAnchor] = useState<null | HTMLElement>(null);
  const [selectedAppointment, setSelectedAppointment] = useState<AppointmentSummary | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const archiveWithUndo = useArchiveWithUndo();
  const [archiveTarget, setArchiveTarget] = useState<AppointmentSummary | null>(null);
  const [archiving, setArchiving] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);

  const handleActionMenuOpen = (event: React.MouseEvent<HTMLElement>, appointment: AppointmentSummary) => {
    setActionMenuAnchor(event.currentTarget);
    setSelectedAppointment(appointment);
  };

  const handleActionMenuClose = () => {
    setActionMenuAnchor(null);
    setSelectedAppointment(null);
  };

  const formatDateTime = (dateString: string) => {
    const date = new Date(dateString);
    return {
      date: date.toLocaleDateString(),
      time: date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'scheduled':
        return 'primary';
      case 'completed':
        return 'success';
      case 'cancelled':
        return 'error';
      case 'no-show':
        return 'warning';
      case 'in-progress':
        return 'info';
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

  const handleStartSession = (appointment: AppointmentSummary) => {
    // TODO: Implement start therapy session
    console.log('Starting session for appointment:', appointment.id);
  };

  const handleEditAppointment = (appointment: AppointmentSummary) => {
    // TODO: Implement edit appointment
    console.log('Editing appointment:', appointment.id);
  };

  /** "3 Sep 2026 at 10:15" — `formatDateTime` returns the halves separately. */
  const appointmentLabel = (appointment: AppointmentSummary) => {
    const { date, time } = formatDateTime(appointment.start_datetime);
    return `${date} at ${time}`;
  };

  // Was a `window.confirm` over a `console.log`. Now it actually archives --
  // the route exists, answers with an archive event id, and the undo is free.
  const handleArchiveConfirm = async () => {
    if (!archiveTarget) return;
    const appointment = archiveTarget;
    setArchiving(true);
    setArchiveError(null);
    try {
      await archiveWithUndo({
        entity: 'appointment',
        name: appointmentLabel(appointment),
        archive: () => schedulingApi.deleteAppointment(appointment.id),
        invalidateKeys: [['appointments']],
        onChanged: () => onRefresh(),
      });
      setArchiveTarget(null);
    } catch (err) {
      // The server refuses an appointment whose session is completed or in
      // progress; that 400's message is the one worth showing.
      setArchiveError(
        err instanceof Error ? err.message : 'Failed to archive appointment. Please try again.'
      );
    } finally {
      setArchiving(false);
    }
  };

  // Sort appointments oldest to newest and apply pagination
  const sortedAndPaginatedAppointments = useMemo(() => {
    const sorted = [...appointments].sort((a, b) => 
      new Date(a.start_datetime).getTime() - new Date(b.start_datetime).getTime()
    );
    
    const startIndex = page * rowsPerPage;
    const endIndex = startIndex + rowsPerPage;
    
    return sorted.slice(startIndex, endIndex);
  }, [appointments, page, rowsPerPage]);

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  // Mobile card component for appointments
  const AppointmentCard = ({ appointment }: { appointment: AppointmentSummary }) => {
    const { date, time } = formatDateTime(appointment.start_datetime);
    const canStartSession = appointment.status === 'scheduled' && new Date(appointment.start_datetime) <= new Date();
    
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
                  {time}
                  {appointment.end_datetime && 
                    ` - ${formatDateTime(appointment.end_datetime).time}`
                  }
                </Typography>
              </Box>
              <IconButton
                size="small"
                onClick={(e) => handleActionMenuOpen(e, appointment)}
                sx={{ width: 32, height: 32 }}
              >
                <MoreVert fontSize="small" />
              </IconButton>
            </Box>

            {/* Status and Type chips */}
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Chip
                label={appointment.status}
                size="small"
                color={getStatusColor(appointment.status)}
                sx={{ fontSize: '0.7rem' }}
              />
              <Chip
                label={appointment.appointment_type}
                size="small"
                color={getTypeColor(appointment.appointment_type)}
                variant="outlined"
                sx={{ fontSize: '0.7rem' }}
              />
            </Box>

            {/* Location if available */}
            {appointment.location && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <LocationOn fontSize="small" color="action" />
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                  {appointment.location}
                </Typography>
              </Box>
            )}

            {/* Start Session button if applicable */}
            {canStartSession && (
              <Box sx={{ mt: 1 }}>
                <Button
                  variant="contained"
                  color="success"
                  size="small"
                  startIcon={<PlayArrow />}
                  onClick={() => handleStartSession(appointment)}
                  fullWidth
                  sx={{ fontSize: '0.75rem', py: 0.5 }}
                >
                  Start Session
                </Button>
              </Box>
            )}
          </Stack>
        </CardContent>
      </Card>
    );
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="300px">
        <CircularProgress />
      </Box>
    );
  }

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
            Appointments ({appointments.length})
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
              // TODO: Implement create appointment
              console.log('Creating appointment for student:', studentId);
            }}
            fullWidth={isMobile}
            size={isMobile ? 'medium' : 'large'}
          >
            Schedule Appointment
          </Button>
        </Stack>
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
            {appointments.length === 0 ? (
              <Typography color="text.secondary" textAlign="center" sx={{ py: 4 }}>
                No appointments found for this student. Click "Schedule Appointment" to create the first appointment.
              </Typography>
      ) : isMobile ? (
        // Mobile Card Layout
        <Box>
          {sortedAndPaginatedAppointments.map((appointment) => (
            <AppointmentCard key={appointment.id} appointment={appointment} />
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
              count={appointments.length}
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
                <TableCell>Date & Time</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Duration</TableCell>
                <TableCell>Teacher</TableCell>
                <TableCell>Location</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedAndPaginatedAppointments.map((appointment) => {
                  const { date, time } = formatDateTime(appointment.start_datetime);
                  const endTime = formatDateTime(appointment.end_datetime).time;
                  const canStartSession = appointment.status === 'scheduled' && !appointment.therapy_session_completed;
                  
                  return (
                    <TableRow key={appointment.id} hover>
                      <TableCell>
                        <Box>
                          <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <CalendarToday fontSize="small" color="action" />
                            {date}
                          </Typography>
                          <Typography variant="body2" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <Schedule fontSize="small" color="action" />
                            {time} - {endTime}
                          </Typography>
                        </Box>
                      </TableCell>
                      
                      <TableCell>
                        <Chip
                          label={appointment.appointment_type}
                          color={getTypeColor(appointment.appointment_type)}
                          size="small"
                          variant="outlined"
                        />
                      </TableCell>
                      
                      <TableCell>
                        <Chip
                          label={appointment.status}
                          color={getStatusColor(appointment.status)}
                          size="small"
                        />
                      </TableCell>
                      
                      <TableCell>
                        <Typography variant="body2">
                          {appointment.duration_minutes} min
                        </Typography>
                      </TableCell>
                      
                      <TableCell>
                        {appointment.teacher_name ? (
                          <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <Person fontSize="small" color="action" />
                            {appointment.teacher_name}
                          </Typography>
                        ) : (
                          <Typography variant="body2" color="text.secondary">
                            Not assigned
                          </Typography>
                        )}
                      </TableCell>
                      
                      <TableCell>
                        {appointment.location ? (
                          <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <LocationOn fontSize="small" color="action" />
                            {appointment.location}
                          </Typography>
                        ) : (
                          <Typography variant="body2" color="text.secondary">
                            Not specified
                          </Typography>
                        )}
                      </TableCell>
                      
                      <TableCell align="right">
                        <Stack direction="row" spacing={1} justifyContent="flex-end">
                          {canStartSession && (
                            <Tooltip title="Start Therapy Session">
                              <IconButton
                                size="small"
                                color="success"
                                onClick={() => handleStartSession(appointment)}
                              >
                                <PlayArrow />
                              </IconButton>
                            </Tooltip>
                          )}
                          <IconButton
                            size="small"
                            onClick={(e) => handleActionMenuOpen(e, appointment)}
                          >
                            <MoreVert />
                          </IconButton>
                        </Stack>
                      </TableCell>
                    </TableRow>
                  );
                })}
            </TableBody>
            <TableFooter>
              <TableRow>
                <TablePagination
                  rowsPerPageOptions={[5, 10, 25, 50]}
                  colSpan={7}
                  count={appointments.length}
                  rowsPerPage={rowsPerPage}
                  page={page}
                  onPageChange={handleChangePage}
                  onRowsPerPageChange={handleChangeRowsPerPage}
                  labelRowsPerPage="Appointments per page:"
                />
              </TableRow>
            </TableFooter>
          </Table>
        </TableContainer>
      )}

      {/* Action Menu */}
      <Menu
        anchorEl={actionMenuAnchor}
        open={Boolean(actionMenuAnchor)}
        onClose={handleActionMenuClose}
      >
        <MenuItem onClick={() => {
          if (selectedAppointment) handleEditAppointment(selectedAppointment);
          handleActionMenuClose();
        }}>
          <ListItemIcon>
            <Edit fontSize="small" />
          </ListItemIcon>
          <ListItemText>Edit Appointment</ListItemText>
        </MenuItem>
        
        {selectedAppointment?.status === 'scheduled' && !selectedAppointment.therapy_session_completed && (
          <MenuItem onClick={() => {
            if (selectedAppointment) handleStartSession(selectedAppointment);
            handleActionMenuClose();
          }}>
            <ListItemIcon>
              <PlayArrow fontSize="small" color="success" />
            </ListItemIcon>
            <ListItemText>Start Session</ListItemText>
          </MenuItem>
        )}
        
        <MenuItem
          onClick={() => {
            if (selectedAppointment) {
              setArchiveError(null);
              setArchiveTarget(selectedAppointment);
            }
            handleActionMenuClose();
          }}
          sx={{ color: 'warning.main' }}
        >
          <ListItemIcon>
            <ArchiveIcon fontSize="small" color="warning" />
          </ListItemIcon>
          <ListItemText>Archive Appointment</ListItemText>
        </MenuItem>
      </Menu>

      <ConfirmationModal
        open={Boolean(archiveTarget)}
        onClose={() => setArchiveTarget(null)}
        onConfirm={() => void handleArchiveConfirm()}
        title={archiveTitle('appointment')}
        message={
          archiveTarget
            ? [
                archiveMessage('appointment', appointmentLabel(archiveTarget)),
                ...(archiveError ? ['', `Last attempt failed: ${archiveError}`] : []),
              ].join('\n')
            : ''
        }
        confirmText="Archive"
        severity="warning"
        loading={archiving}
        loadingText="Archiving..."
      />
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}
