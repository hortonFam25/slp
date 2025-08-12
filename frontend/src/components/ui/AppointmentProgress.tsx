import React from 'react';
import {
  Dialog,
  DialogContent,
  Box,
  Typography,
  CircularProgress,
  Alert,
  Button,
  LinearProgress,
  Stack
} from '@mui/material';
import { CheckCircle, Error, Cancel } from '@mui/icons-material';

export interface AppointmentProgressState {
  isVisible: boolean;
  isLoading: boolean;
  isComplete: boolean;
  isError: boolean;
  message: string;
  progress?: number; // 0-100 for determinate progress
  details?: {
    totalAppointments?: number;
    createdAppointments?: number;
    conflicts?: string[];
    seriesId?: string;
  };
}

interface AppointmentProgressProps {
  state: AppointmentProgressState;
  onClose: () => void;
  onRetry?: () => void;
}

export function AppointmentProgress({ state, onClose, onRetry }: AppointmentProgressProps) {
  const {
    isVisible,
    isLoading,
    isComplete,
    isError,
    message,
    progress,
    details
  } = state;

  if (!isVisible) return null;

  const getIcon = () => {
    if (isLoading) {
      return <CircularProgress size={48} color="primary" />;
    }
    if (isComplete) {
      return <CheckCircle sx={{ fontSize: 48, color: 'success.main' }} />;
    }
    if (isError) {
      return <Error sx={{ fontSize: 48, color: 'error.main' }} />;
    }
    return null;
  };

  const getTitle = () => {
    if (isLoading) {
      return 'Creating Appointments...';
    }
    if (isComplete) {
      return 'Appointments Created Successfully!';
    }
    if (isError) {
      return 'Failed to Create Appointments';
    }
    return '';
  };

  const getSeverity = (): 'info' | 'success' | 'error' => {
    if (isComplete) return 'success';
    if (isError) return 'error';
    return 'info';
  };

  return (
    <Dialog
      open={isVisible}
      disableEscapeKeyDown={isLoading}
      PaperProps={{
        sx: { minWidth: 400, maxWidth: 600 }
      }}
    >
      <DialogContent>
        <Stack spacing={3} alignItems="center" sx={{ p: 2 }}>
          {/* Icon */}
          <Box display="flex" justifyContent="center">
            {getIcon()}
          </Box>

          {/* Title */}
          <Typography variant="h6" component="h2" align="center">
            {getTitle()}
          </Typography>

          {/* Progress Bar (if loading with progress) */}
          {isLoading && typeof progress === 'number' && (
            <Box sx={{ width: '100%' }}>
              <LinearProgress
                variant="determinate"
                value={progress}
                sx={{ height: 8, borderRadius: 4 }}
              />
              <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 1 }}>
                {Math.round(progress)}% complete
              </Typography>
            </Box>
          )}

          {/* Progress Bar (if loading without specific progress) */}
          {isLoading && typeof progress !== 'number' && (
            <Box sx={{ width: '100%' }}>
              <LinearProgress sx={{ height: 8, borderRadius: 4 }} />
            </Box>
          )}

          {/* Message */}
          <Alert severity={getSeverity()} sx={{ width: '100%' }}>
            <Typography variant="body1">
              {message}
            </Typography>
          </Alert>

          {/* Details for recurring appointments */}
          {details && (isComplete || isError) && (
            <Box sx={{ width: '100%' }}>
              {details.totalAppointments && (
                <Typography variant="body2" color="text.secondary">
                  Total appointments: {details.totalAppointments}
                </Typography>
              )}
              
              {details.createdAppointments !== undefined && (
                <Typography variant="body2" color="text.secondary">
                  Successfully created: {details.createdAppointments}
                </Typography>
              )}

              {details.conflicts && details.conflicts.length > 0 && (
                <Box sx={{ mt: 1 }}>
                  <Typography variant="body2" color="warning.main" sx={{ fontWeight: 'medium' }}>
                    ⚠️ Conflicts detected:
                  </Typography>
                  {details.conflicts.slice(0, 3).map((conflict, index) => (
                    <Typography key={index} variant="body2" color="text.secondary" sx={{ ml: 2 }}>
                      • {conflict}
                    </Typography>
                  ))}
                  {details.conflicts.length > 3 && (
                    <Typography variant="body2" color="text.secondary" sx={{ ml: 2 }}>
                      • And {details.conflicts.length - 3} more...
                    </Typography>
                  )}
                </Box>
              )}

              {details.seriesId && isComplete && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Series ID: {details.seriesId}
                </Typography>
              )}
            </Box>
          )}

          {/* Action Buttons */}
          <Stack direction="row" spacing={2}>
            {(isComplete || isError) && (
              <Button
                variant="contained"
                onClick={onClose}
                startIcon={isComplete ? <CheckCircle /> : undefined}
              >
                {isComplete ? 'Done' : 'Close'}
              </Button>
            )}

            {isError && onRetry && (
              <Button
                variant="outlined"
                onClick={onRetry}
                color="primary"
              >
                Retry
              </Button>
            )}

            {isLoading && (
              <Button
                variant="outlined"
                onClick={onClose}
                startIcon={<Cancel />}
                color="secondary"
              >
                Cancel
              </Button>
            )}
          </Stack>
        </Stack>
      </DialogContent>
    </Dialog>
  );
}

// Hook for managing appointment progress state
export function useAppointmentProgress() {
  const [state, setState] = React.useState<AppointmentProgressState>({
    isVisible: false,
    isLoading: false,
    isComplete: false,
    isError: false,
    message: ''
  });

  const showProgress = React.useCallback((message: string, progress?: number) => {
    setState({
      isVisible: true,
      isLoading: true,
      isComplete: false,
      isError: false,
      message,
      progress
    });
  }, []);

  const showSuccess = React.useCallback((message: string, details?: AppointmentProgressState['details']) => {
    setState({
      isVisible: true,
      isLoading: false,
      isComplete: true,
      isError: false,
      message,
      details
    });
  }, []);

  const showError = React.useCallback((message: string, details?: AppointmentProgressState['details']) => {
    setState({
      isVisible: true,
      isLoading: false,
      isComplete: false,
      isError: true,
      message,
      details
    });
  }, []);

  const updateProgress = React.useCallback((progress: number, message?: string) => {
    setState(prev => ({
      ...prev,
      progress,
      ...(message && { message })
    }));
  }, []);

  const hide = React.useCallback(() => {
    setState({
      isVisible: false,
      isLoading: false,
      isComplete: false,
      isError: false,
      message: ''
    });
  }, []);

  return {
    state,
    showProgress,
    showSuccess,
    showError,
    updateProgress,
    hide
  };
}
