import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Alert,
  IconButton
} from '@mui/material';
import {
  Close,
  Lock,
  Warning
} from '@mui/icons-material';
import { format } from 'date-fns';
import { AppointmentSummary } from '../../../lib/api/scheduling';

interface ProtectedAppointmentModalProps {
  open: boolean;
  onClose: () => void;
  appointment: AppointmentSummary;
  action: 'edit' | 'delete';
  reason: string;
}

export function ProtectedAppointmentModal({
  open,
  onClose,
  appointment,
  action,
  reason
}: ProtectedAppointmentModalProps) {
  
  // The `'delete'` action name is the prop threaded down from CellDetailModal;
  // the route it names archives rather than deletes, so the copy says so.
  const getTitle = () => {
    return action === 'edit' ? 'Cannot Edit Appointment' : 'Cannot Archive Appointment';
  };

  const getDescription = () => {
    if (action === 'edit') {
      return 'This appointment cannot be modified because the therapy session is protected.';
    } else {
      return 'This appointment cannot be archived because the therapy session is protected.';
    }
  };

  const getStatusBadge = () => {
    if (appointment.therapy_session_status === 'completed') {
      return { color: 'success', label: 'Completed' };
    }
    if (appointment.therapy_session_status === 'in_progress') {
      return { color: 'warning', label: 'In Progress' };
    }
    return { color: 'default', label: 'Unknown' };
  };

  const statusBadge = getStatusBadge();

  return (
    <Dialog 
      open={open} 
      onClose={onClose}
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        pb: 1
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Lock color="warning" />
          <Typography variant="h6" component="div">
            {getTitle()}
          </Typography>
        </Box>
        <IconButton onClick={onClose} size="small">
          <Close />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Alert severity="warning" icon={<Warning />}>
          <Typography variant="subtitle2" fontWeight={600}>
            Protected Appointment
          </Typography>
          {getDescription()}
        </Alert>

        {/* Appointment Details */}
        <Box sx={{ 
          p: 2, 
          bgcolor: 'grey.50', 
          borderRadius: 1, 
          border: '1px solid',
          borderColor: 'grey.300'
        }}>
          <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
            Appointment Details
          </Typography>
          
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Typography variant="body2">
              <strong>Student:</strong> {appointment.student_name}
            </Typography>
            <Typography variant="body2">
              <strong>Date & Time:</strong> {format(new Date(appointment.start_datetime), 'MMM d, yyyy \'at\' h:mm a')} - {format(new Date(appointment.end_datetime), 'h:mm a')}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2">
                <strong>Therapy Session Status:</strong>
              </Typography>
              <Box
                sx={{
                  px: 1,
                  py: 0.5,
                  borderRadius: 1,
                  backgroundColor: statusBadge.color === 'success' ? 'success.100' : 'warning.100',
                  color: statusBadge.color === 'success' ? 'success.800' : 'warning.800',
                  fontSize: '0.75rem',
                  fontWeight: 600
                }}
              >
                {statusBadge.label}
              </Box>
            </Box>
          </Box>
        </Box>

        {/* Reason */}
        <Box sx={{ 
          p: 2, 
          bgcolor: 'info.50', 
          borderRadius: 1, 
          border: '1px solid',
          borderColor: 'info.200'
        }}>
          <Typography variant="body2" color="text.secondary">
            <strong>Reason:</strong> {reason}
          </Typography>
        </Box>

        {/* What can be done */}
        <Box sx={{ 
          p: 2, 
          bgcolor: 'primary.50', 
          borderRadius: 1, 
          border: '1px solid',
          borderColor: 'primary.200'
        }}>
          <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
            What you can do:
          </Typography>
          <Typography variant="body2" color="text.secondary">
            • View therapy session details and progress<br/>
            • Add notes to completed sessions<br/>
            • Create new appointments for future sessions<br/>
            {appointment.therapy_session_status === 'in_progress' && '• Wait for the session to complete before making changes'}
          </Typography>
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} variant="contained">
          Understood
        </Button>
      </DialogActions>
    </Dialog>
  );
}
