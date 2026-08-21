import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  RadioGroup,
  FormControlLabel,
  Radio,
  Alert,
  Chip,
  Divider,
  IconButton,
  CircularProgress
} from '@mui/material';
import {
  Close,
  Repeat,
  CalendarToday,
  Warning,
  Info
} from '@mui/icons-material';
import { format } from 'date-fns';
import { AppointmentSummary, schedulingApi } from '../../../lib/api/scheduling';
import { ARCHIVE_REASSURANCE } from '../../../lib/archive';

interface SeriesActionDialogProps {
  open: boolean;
  onClose: () => void;
  appointment: AppointmentSummary;
  action: 'edit' | 'delete';
  onSingleAction: () => void;
  onSeriesAction: () => void;
}

interface SeriesInfo {
  appointments: AppointmentSummary[];
  totalCount: number;
  nextAppointment?: AppointmentSummary;
  completedCount: number;
  upcomingCount: number;
}

export function SeriesActionDialog({
  open,
  onClose,
  appointment,
  action,
  onSingleAction,
  onSeriesAction
}: SeriesActionDialogProps) {
  const [selectedOption, setSelectedOption] = useState<'single' | 'series'>('single');
  const [seriesInfo, setSeriesInfo] = useState<SeriesInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load series information when dialog opens
  useEffect(() => {
    if (open && appointment.series_id) {
      loadSeriesInfo();
    }
  }, [open, appointment.series_id]);

  const loadSeriesInfo = async () => {
    if (!appointment.series_id) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const appointments = await schedulingApi.getAppointmentSeries(appointment.series_id);
      
      const now = new Date();
      const completed = appointments.filter(apt => 
        apt.status === 'completed' || new Date(apt.start_datetime) < now
      );
      const upcoming = appointments.filter(apt => 
        apt.status !== 'completed' && new Date(apt.start_datetime) >= now
      );
      const currentAndFuture = appointments.filter(apt => 
        apt.status !== 'completed' && new Date(apt.start_datetime) >= now
      );
      
      const nextAppointment = upcoming
        .sort((a, b) => new Date(a.start_datetime).getTime() - new Date(b.start_datetime).getTime())[0];

      setSeriesInfo({
        appointments,
        totalCount: appointments.length,
        nextAppointment,
        completedCount: completed.length,
        upcomingCount: currentAndFuture.length
      });
    } catch (err) {
      console.error('Failed to load series info:', err);
      setError('Failed to load series information');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = () => {
    if (selectedOption === 'single') {
      onSingleAction();
    } else {
      onSeriesAction();
    }
    onClose();
  };

  const handleClose = () => {
    setSelectedOption('single');
    setSeriesInfo(null);
    setError(null);
    onClose();
  };

  // The `action === 'delete'` discriminator keeps its name -- the route is
  // still a DELETE and the prop is threaded through three components -- but
  // everything a therapist READS now says archive, because that is what
  // happens. See backend/app/routers/scheduling.py.
  const getActionTitle = () => {
    return action === 'edit' ? 'Edit Recurring Series' : 'Archive Recurring Series';
  };

  const getActionDescription = () => {
    if (action === 'edit') {
      return 'This appointment is part of a recurring series. What would you like to edit?';
    } else {
      return 'This appointment is part of a recurring series. What would you like to archive?';
    }
  };

  const getSingleOptionLabel = () => {
    return action === 'edit' ? 'Edit this appointment only' : 'Archive this appointment only';
  };

  const getSeriesOptionLabel = () => {
    const totalCount = seriesInfo?.totalCount || 0;
    const upcomingCount = seriesInfo?.upcomingCount || 0;
    if (action === 'edit') {
      return `Edit series (${upcomingCount} of ${totalCount} appointment${totalCount !== 1 ? 's' : ''})`;
    } else {
      return `Archive series (${upcomingCount} of ${totalCount} appointment${totalCount !== 1 ? 's' : ''})`;
    }
  };

  const getConfirmButtonText = () => {
    if (selectedOption === 'single') {
      return action === 'edit' ? 'Edit Appointment' : 'Archive Appointment';
    } else {
      return action === 'edit' ? 'Edit Series' : 'Archive Series';
    }
  };

  const getConfirmButtonColor = () => {
    if (action === 'delete') {
      return 'warning' as const;
    }
    return 'primary' as const;
  };

  return (
    <Dialog 
      open={open} 
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: { minHeight: '400px' }
      }}
    >
      <DialogTitle sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        pb: 1
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Repeat color="primary" />
          <Typography variant="h6" component="div">
            {getActionTitle()}
          </Typography>
        </Box>
        <IconButton onClick={handleClose} size="small">
          <Close />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {error && (
          <Alert severity="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : (
          <>
            <Typography variant="body1" color="text.secondary">
              {getActionDescription()}
            </Typography>

            {/* Series Information */}
            {seriesInfo && (
              <Box sx={{ 
                p: 2, 
                bgcolor: 'info.50', 
                borderRadius: 1, 
                border: '1px solid',
                borderColor: 'info.200'
              }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <Info color="info" fontSize="small" />
                  <Typography variant="subtitle2" fontWeight={600}>
                    Series Information
                  </Typography>
                </Box>
                
                <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                  <Chip 
                    size="small" 
                    label={`${seriesInfo.totalCount} Total`}
                    color="default"
                  />
                  <Chip 
                    size="small" 
                    label={`${seriesInfo.completedCount} Completed`}
                    color="success"
                    variant={seriesInfo.completedCount > 0 ? "filled" : "outlined"}
                  />
                  <Chip 
                    size="small" 
                    label={`${seriesInfo.upcomingCount} Editable`}
                    color="primary"
                    variant={seriesInfo.upcomingCount > 0 ? "filled" : "outlined"}
                  />
                </Box>

                {seriesInfo.nextAppointment && (
                  <Typography variant="body2" color="text.secondary">
                    Next: {format(new Date(seriesInfo.nextAppointment.start_datetime), 'MMM d, yyyy \'at\' h:mm a')}
                  </Typography>
                )}
              </Box>
            )}

            <Divider />

            {/* Action Options */}
            <RadioGroup
              value={selectedOption}
              onChange={(e) => setSelectedOption(e.target.value as 'single' | 'series')}
            >
              <FormControlLabel
                value="single"
                control={<Radio />}
                label={
                  <Box>
                    <Typography variant="body1" fontWeight={500}>
                      {getSingleOptionLabel()}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Only affects this specific appointment on {format(new Date(appointment.start_datetime), 'MMM d, yyyy')}
                    </Typography>
                  </Box>
                }
              />
              
              <FormControlLabel
                value="series"
                control={<Radio />}
                label={
                  <Box>
                    <Typography variant="body1" fontWeight={500}>
                      {getSeriesOptionLabel()}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {action === 'edit'
                        ? 'Applies changes to all appointments in the recurring series'
                        : 'Archives all current and future appointments in the recurring series'
                      }
                    </Typography>
                  </Box>
                }
              />
            </RadioGroup>

            {/* Warning for series actions */}
            {selectedOption === 'series' && (
              <Alert 
                severity={action === 'delete' ? 'warning' : 'info'} 
                icon={action === 'delete' ? <Warning /> : <Info />}
              >
                {action === 'delete'
                  ? `All current and future appointments in the series are archived under one entry, so one undo brings the whole series back. Completed appointments and in-progress therapy sessions are not affected. ${ARCHIVE_REASSURANCE}`
                  : 'Changes will be applied to all current and future appointments in the series. Completed appointments and in-progress therapy sessions will not be affected.'
                }
              </Alert>
            )}
          </>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          color={getConfirmButtonColor()}
          disabled={loading || !seriesInfo}
          sx={{ minWidth: 120 }}
        >
          {getConfirmButtonText()}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
