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
  CircularProgress,
  Paper
} from '@mui/material';
import {
  Close,
  CalendarToday,
  Info,
  TrendingFlat
} from '@mui/icons-material';
import { format, addDays, differenceInDays } from 'date-fns';
import { AppointmentSummary, schedulingApi } from '../../../lib/api/scheduling';

interface SeriesPatternDialogProps {
  open: boolean;
  onClose: () => void;
  appointment: AppointmentSummary;
  originalDate: Date;
  newDate: Date;
  offsetDays: number;
  dayOfWeekChanged: boolean;
  originalDayOfWeek: number;
  newDayOfWeek: number;
  onSingleUpdate: () => void;
  onOffsetUpdate: () => void;
  onDayAlignmentUpdate: () => void;
}

const DAYS_OF_WEEK = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

export function SeriesPatternDialog({
  open,
  onClose,
  appointment,
  originalDate,
  newDate,
  offsetDays,
  dayOfWeekChanged,
  originalDayOfWeek,
  newDayOfWeek,
  onSingleUpdate,
  onOffsetUpdate,
  onDayAlignmentUpdate
}: SeriesPatternDialogProps) {
  const [selectedOption, setSelectedOption] = useState<'single' | 'offset' | 'day_alignment'>('single');
  const [seriesInfo, setSeriesInfo] = useState<{ appointments: AppointmentSummary[]; totalCount: number; futureCount: number } | null>(null);
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
      const futureAppointments = appointments.filter(apt => 
        new Date(apt.start_datetime) >= now && 
        (!apt.therapy_session_status || !['completed', 'in_progress'].includes(apt.therapy_session_status))
      );

      setSeriesInfo({
        appointments,
        totalCount: appointments.length,
        futureCount: futureAppointments.length
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
      onSingleUpdate();
    } else if (selectedOption === 'offset') {
      onOffsetUpdate();
    } else {
      onDayAlignmentUpdate();
    }
    onClose();
  };

  const handleClose = () => {
    setSelectedOption('single');
    setSeriesInfo(null);
    setError(null);
    onClose();
  };

  // Calculate example dates for preview
  const getOffsetExample = () => {
    if (!seriesInfo) return '';
    
    const futureAppointments = seriesInfo.appointments
      .filter(apt => new Date(apt.start_datetime) > new Date())
      .slice(0, 2); // Show first 2 future appointments
    
    return futureAppointments.map(apt => {
      const currentDate = new Date(apt.start_datetime);
      const newDate = addDays(currentDate, offsetDays);
      return `${format(currentDate, 'MMM d')} → ${format(newDate, 'MMM d')}`;
    }).join(', ');
  };

  const getDayAlignmentExample = () => {
    if (!seriesInfo) return '';
    
    const futureAppointments = seriesInfo.appointments
      .filter(apt => new Date(apt.start_datetime) > new Date())
      .slice(0, 2); // Show first 2 future appointments
    
    return futureAppointments.map(apt => {
      const currentDate = new Date(apt.start_datetime);
      const offsetDate = addDays(currentDate, offsetDays);
      
      // Find the next occurrence of target day of week
      const dayDiff = newDayOfWeek - offsetDate.getDay();
      const alignedDate = addDays(offsetDate, dayDiff >= 0 ? dayDiff : dayDiff + 7);
      
      return `${format(currentDate, 'MMM d')} → ${format(alignedDate, 'MMM d')}`;
    }).join(', ');
  };

  return (
    <Dialog 
      open={open} 
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { minHeight: '500px' }
      }}
    >
      <DialogTitle sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        pb: 1
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CalendarToday color="primary" />
          <Typography variant="h6" component="div">
            Update Series Pattern
          </Typography>
        </Box>
        <IconButton onClick={handleClose} size="small">
          <Close />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
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
            {/* Change Summary */}
            <Paper sx={{ p: 2, bgcolor: 'info.50', border: '1px solid', borderColor: 'info.200' }}>
              <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
                Date Change Detected
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Chip size="small" label={format(originalDate, 'EEE, MMM d')} />
                <TrendingFlat />
                <Chip size="small" label={format(newDate, 'EEE, MMM d')} color="primary" />
              </Box>
              <Typography variant="body2" color="text.secondary">
                {offsetDays > 0 ? `+${offsetDays}` : offsetDays} days • {DAYS_OF_WEEK[originalDayOfWeek]} → {DAYS_OF_WEEK[newDayOfWeek]}
                {dayOfWeekChanged && ' (Day of week changed)'}
              </Typography>
            </Paper>

            {/* Series Information */}
            {seriesInfo && (
              <Box sx={{ 
                p: 2, 
                bgcolor: 'grey.50', 
                borderRadius: 1, 
                border: '1px solid',
                borderColor: 'grey.300'
              }}>
                <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
                  Series Information
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  <Chip size="small" label={`${seriesInfo.totalCount} Total`} color="default" />
                  <Chip size="small" label={`${seriesInfo.futureCount} Will Update`} color="primary" />
                </Box>
              </Box>
            )}

            <Typography variant="body1" color="text.secondary">
              How should future appointments in this series be updated?
            </Typography>

            {/* Update Options */}
            <RadioGroup
              value={selectedOption}
              onChange={(e) => setSelectedOption(e.target.value as 'single' | 'offset' | 'day_alignment')}
            >
              <FormControlLabel
                value="single"
                control={<Radio />}
                label={
                  <Box>
                    <Typography variant="body1" fontWeight={500}>
                      Edit this appointment only
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                      Only change this specific appointment on {format(newDate, 'MMM d, yyyy')}. Other appointments in the series remain unchanged.
                    </Typography>
                  </Box>
                }
                sx={{ mb: 2, alignItems: 'flex-start' }}
              />

              <FormControlLabel
                value="offset"
                control={<Radio />}
                label={
                  <Box>
                    <Typography variant="body1" fontWeight={500}>
                      Apply {offsetDays > 0 ? `+${offsetDays}` : offsetDays} day offset to all future appointments
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                      Each appointment moves by exactly {Math.abs(offsetDays)} day{Math.abs(offsetDays) !== 1 ? 's' : ''} {offsetDays > 0 ? 'forward' : 'backward'}
                    </Typography>
                    {seriesInfo && (
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5, fontStyle: 'italic' }}>
                        Example: {getOffsetExample()}
                      </Typography>
                    )}
                  </Box>
                }
                sx={{ mb: 2, alignItems: 'flex-start' }}
              />
              
              {dayOfWeekChanged && (
                <FormControlLabel
                  value="day_alignment"
                  control={<Radio />}
                  label={
                    <Box>
                      <Typography variant="body1" fontWeight={500}>
                        Move series to {DAYS_OF_WEEK[newDayOfWeek]} pattern
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                        Apply offset and align all future appointments to {DAYS_OF_WEEK[newDayOfWeek]}s
                      </Typography>
                      {seriesInfo && (
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5, fontStyle: 'italic' }}>
                          Example: {getDayAlignmentExample()}
                        </Typography>
                      )}
                    </Box>
                  }
                  sx={{ mb: 2, alignItems: 'flex-start' }}
                />
              )}
            </RadioGroup>

            {/* Info Alert */}
            <Alert severity="info" icon={<Info />}>
              <Typography variant="body2">
                Only future appointments will be updated. Completed appointments and in-progress therapy sessions will remain unchanged.
              </Typography>
            </Alert>
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
          disabled={loading || !seriesInfo}
          sx={{ minWidth: 120 }}
        >
          Update Series
        </Button>
      </DialogActions>
    </Dialog>
  );
}
