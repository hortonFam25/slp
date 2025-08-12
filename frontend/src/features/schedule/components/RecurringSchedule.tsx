import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Box,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  FormControlLabel,
  Checkbox,
  FormGroup,
  FormLabel,
  Alert,
  Chip,
  Divider
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { 
  format, 
  addDays, 
  addWeeks, 
  addMonths, 
  isBefore, 
  isAfter, 
  getDay,
  startOfWeek,
  endOfWeek
} from 'date-fns';
import { Repeat, CalendarToday } from '@mui/icons-material';

export interface RecurringConfig {
  isRecurring: boolean;
  frequency: 'weekly' | 'monthly';
  interval: number; // Every X weeks/months
  daysOfWeek: number[]; // 0 = Sunday, 1 = Monday, etc.
  endType: 'date' | 'occurrences';
  endDate?: Date;
  maxOccurrences?: number;
}

export interface RecurringScheduleProps {
  value: RecurringConfig;
  onChange: (config: RecurringConfig) => void;
  startDate: Date;
  disabled?: boolean;
  maxOccurrences?: number;
  maxEndDate?: Date;
}

const DAYS_OF_WEEK = [
  { value: 1, label: 'Monday', short: 'Mon' },
  { value: 2, label: 'Tuesday', short: 'Tue' },
  { value: 3, label: 'Wednesday', short: 'Wed' },
  { value: 4, label: 'Thursday', short: 'Thu' },
  { value: 5, label: 'Friday', short: 'Fri' },
  { value: 6, label: 'Saturday', short: 'Sat' },
  { value: 0, label: 'Sunday', short: 'Sun' }
];

export function RecurringSchedule({
  value,
  onChange,
  startDate,
  disabled = false,
  maxOccurrences = 50,
  maxEndDate
}: RecurringScheduleProps) {
  // Debug: Only log when endDate changes
  React.useEffect(() => {
    if (value.endDate) {
      console.log('🔍 RecurringSchedule endDate updated:', value.endDate.toString());
    }
  }, [value.endDate]);

  const preview = useMemo(() => generatePreviewDates(startDate, value, 5), [startDate, value]);

  const handleRecurringToggle = useCallback((checked: boolean) => {
    const newConfig: RecurringConfig = {
      ...value,
      isRecurring: checked
    };

    // Set default values when enabling recurring
    if (checked && !value.isRecurring) {
      const currentDayOfWeek = getDay(startDate);
      newConfig.frequency = 'weekly';
      newConfig.interval = 1;
      newConfig.daysOfWeek = [currentDayOfWeek];
      newConfig.endType = 'occurrences';
      newConfig.maxOccurrences = 10;
    }

    onChange(newConfig);
  }, [value, startDate, onChange]);

  const handleFrequencyChange = useCallback((frequency: 'weekly' | 'monthly') => {
    const currentDayOfWeek = getDay(startDate);
    onChange({
      ...value,
      frequency,
      daysOfWeek: [currentDayOfWeek] // Reset to current day when changing frequency
    });
  }, [value, startDate, onChange]);

  const handleDaysOfWeekChange = useCallback((day: number, checked: boolean) => {
    const newDays = checked 
      ? [...value.daysOfWeek, day]
      : value.daysOfWeek.filter(d => d !== day);
    
    onChange({
      ...value,
      daysOfWeek: newDays.sort()
    });
  }, [value, onChange]);

  const handleEndTypeChange = useCallback((endType: 'date' | 'occurrences') => {
    const newConfig: RecurringConfig = {
      ...value,
      endType
    };

    // Set default values ONLY if we're switching to date type AND there's no existing endDate AND endType is actually changing
    if (endType === 'date' && !value.endDate && value.endType !== 'date') {
      // Calculate June 1st of the following year
      const currentYear = startDate.getFullYear();
      const targetYear = currentYear + 1; // Always use the following year
      console.log('🗓️ Creating default date:', { 
        startDate: startDate.toString(), 
        currentYear, 
        targetYear,
        existingEndDate: value.endDate 
      });
      
      // Create a simple date without time components for DatePicker
      const defaultDate = new Date(targetYear, 5, 1); // June 1st (month 5 = June)
      console.log('🗓️ Default date created:', defaultDate.toString());
      console.log('🗓️ Default date year check:', defaultDate.getFullYear());
      newConfig.endDate = defaultDate;
    } else if (endType === 'occurrences' && !value.maxOccurrences) {
      newConfig.maxOccurrences = 10; // Default 10 occurrences
    }

    onChange(newConfig);
  }, [value, startDate, onChange]);

  const handleEndDateChange = useCallback((date: Date | null) => {
    // Create a new config object to avoid mutation issues
    const newConfig = {
      ...value,
      endDate: date ? new Date(date.getTime()) : undefined // Use getTime() to ensure new object
    };
    onChange(newConfig);
  }, [value, onChange]);

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box>
        <Typography variant="subtitle1" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Repeat color="primary" />
          Recurring Appointment
        </Typography>

        <FormControlLabel
          control={
            <Checkbox
              checked={value.isRecurring}
              onChange={(e) => handleRecurringToggle(e.target.checked)}
              disabled={disabled}
            />
          }
          label="Make this a recurring appointment"
        />

        {value.isRecurring && (
          <Box sx={{ mt: 2, p: 2, border: 1, borderColor: 'divider', borderRadius: 1, bgcolor: 'grey.50' }}>
            {/* Frequency Selection */}
            <Box sx={{ mb: 3 }}>
              <Typography variant="subtitle2" gutterBottom>
                Repeat Frequency
              </Typography>
              <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                <FormControl size="small" sx={{ minWidth: 120 }}>
                  <InputLabel>Frequency</InputLabel>
                  <Select
                    value={value.frequency}
                    label="Frequency"
                    onChange={(e) => handleFrequencyChange(e.target.value as 'weekly' | 'monthly')}
                    disabled={disabled}
                  >
                    <MenuItem value="weekly">Weekly</MenuItem>
                    <MenuItem value="monthly">Monthly</MenuItem>
                  </Select>
                </FormControl>

                <TextField
                  label={`Every X ${value.frequency === 'weekly' ? 'weeks' : 'months'}`}
                  type="number"
                  size="small"
                  value={value.interval}
                  onChange={(e) => onChange({ ...value, interval: Math.max(1, parseInt(e.target.value) || 1) })}
                  inputProps={{ min: 1, max: value.frequency === 'weekly' ? 12 : 6 }}
                  sx={{ width: 100 }}
                  disabled={disabled}
                />
              </Box>
            </Box>

            {/* Days of Week Selection */}
            {value.frequency === 'weekly' && (
              <Box sx={{ mb: 3 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Days of the Week
                </Typography>
                <FormGroup row>
                  {DAYS_OF_WEEK.map((day) => (
                    <FormControlLabel
                      key={day.value}
                      control={
                        <Checkbox
                          checked={value.daysOfWeek.includes(day.value)}
                          onChange={(e) => handleDaysOfWeekChange(day.value, e.target.checked)}
                          disabled={disabled}
                          size="small"
                        />
                      }
                      label={day.short}
                      sx={{ mr: 1 }}
                    />
                  ))}
                </FormGroup>
                {value.daysOfWeek.length === 0 && (
                  <Alert severity="warning" sx={{ mt: 1 }}>
                    Please select at least one day of the week
                  </Alert>
                )}
              </Box>
            )}

            {value.frequency === 'monthly' && (
              <Box sx={{ mb: 3 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Monthly Schedule
                </Typography>
                <Alert severity="info" sx={{ mb: 2 }}>
                  Monthly appointments will occur on the same day of the week ({DAYS_OF_WEEK.find(d => d.value === getDay(startDate))?.label}) 
                  every {value.interval} month{value.interval > 1 ? 's' : ''}.
                </Alert>
                <FormGroup row>
                  {DAYS_OF_WEEK.map((day) => (
                    <FormControlLabel
                      key={day.value}
                      control={
                        <Checkbox
                          checked={value.daysOfWeek.includes(day.value)}
                          onChange={(e) => handleDaysOfWeekChange(day.value, e.target.checked)}
                          disabled={disabled}
                          size="small"
                        />
                      }
                      label={day.short}
                      sx={{ mr: 1 }}
                    />
                  ))}
                </FormGroup>
              </Box>
            )}

            {/* End Condition */}
            <Box sx={{ mb: 3 }}>
              <Typography variant="subtitle2" gutterBottom>
                End Condition
              </Typography>
              <FormControl size="small" sx={{ mb: 2, minWidth: 150 }}>
                <InputLabel>End Type</InputLabel>
                <Select
                  value={value.endType}
                  label="End Type"
                  onChange={(e) => handleEndTypeChange(e.target.value as 'date' | 'occurrences')}
                  disabled={disabled}
                >
                  <MenuItem value="occurrences">After X appointments</MenuItem>
                  <MenuItem value="date">On specific date</MenuItem>
                </Select>
              </FormControl>

              {value.endType === 'occurrences' && (
                <TextField
                  label="Number of appointments"
                  type="number"
                  size="small"
                  value={value.maxOccurrences || ''}
                  onChange={(e) => onChange({ 
                    ...value, 
                    maxOccurrences: Math.min(maxOccurrences, Math.max(1, parseInt(e.target.value) || 1))
                  })}
                  inputProps={{ min: 1, max: maxOccurrences }}
                  sx={{ width: 160 }}
                  disabled={disabled}
                />
              )}

              {value.endType === 'date' && (
                <Box>
                  <DatePicker
                    key={`date-picker-${value.endDate?.getTime() || 'null'}`}
                    label="End date"
                    value={value.endDate ? new Date(value.endDate) : null}
                    onChange={handleEndDateChange}
                    minDate={addDays(startDate, 1)}
                    maxDate={maxEndDate || addMonths(startDate, 12)}
                    disabled={disabled}
                    format="MM/dd/yyyy"
                    closeOnSelect={true}
                    shouldDisableDate={() => false}
                    slotProps={{
                      textField: {
                        size: 'small',
                        sx: { width: 160 },
                        variant: 'outlined'
                      },
                      actionBar: {
                        actions: ['clear', 'cancel', 'accept']
                      }
                    }}
                  />
                  {/* Debug info */}
                  {process.env.NODE_ENV === 'development' && (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                      Debug: {value.endDate?.toString() || 'null'} | Start: {startDate.getFullYear()}
                    </Typography>
                  )}
                </Box>
              )}
            </Box>

            {/* Preview */}
            {preview.length > 0 && (
              <Box>
                <Divider sx={{ mb: 2 }} />
                <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CalendarToday color="primary" />
                  Preview (First 5 appointments)
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  {preview.map((date, index) => (
                    <Chip
                      key={index}
                      label={format(date, 'MMM d, yyyy (EEE)')}
                      size="small"
                      variant="outlined"
                      color="primary"
                    />
                  ))}
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                  Total appointments: {value.endType === 'occurrences' ? value.maxOccurrences : 'Until end date'}
                </Typography>
              </Box>
            )}
          </Box>
        )}
      </Box>
    </LocalizationProvider>
  );
}

// Simple preview function - generates just a few dates for UI display
// The actual date generation is now handled by the backend
function generatePreviewDates(startDate: Date, config: RecurringConfig, limit: number = 5): Date[] {
  if (!config.isRecurring) return [];
  
  const dates: Date[] = [];
  let currentDate = new Date(startDate);
  
  // Always include start date
  dates.push(new Date(currentDate));
  
  // Generate a few more dates for preview only
  for (let i = 1; i < limit && dates.length < limit; i++) {
    if (config.frequency === 'weekly') {
      currentDate = addWeeks(currentDate, config.interval);
    } else if (config.frequency === 'monthly') {
      currentDate = addMonths(currentDate, config.interval);
    }
    
    // Simple preview - don't worry about day-of-week logic here
    // The backend will handle the proper logic
    dates.push(new Date(currentDate));
  }
  
  return dates;
}
