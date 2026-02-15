import React, { useState, useMemo, useRef, useEffect } from 'react';
import { 
  Dialog, 
  DialogTitle, 
  DialogContent, 
  DialogActions, 
  Button, 
  Box, 
  Typography, 
  Chip, 
  IconButton, 
  Tooltip,
  Badge,
  Paper,
  Grid,
  useMediaQuery,
  useTheme
} from '@mui/material';
import {
  Close, 
  Person, 
  Group, 
  PlayArrow, 
  Edit, 
  Repeat,
  AccessTime,
  School,
  PersonOutline,
  Delete,
  Lock
} from '@mui/icons-material';
import { format, addMinutes, isSameDay, startOfDay, setHours, setMinutes, differenceInMinutes } from 'date-fns';
import { useNavigate } from 'react-router-dom';
import { AppointmentSummary, TimeBlockSummary } from '../../../lib/api/scheduling';
import { StudentScheduleView } from '../../../lib/api/schedulingStudents';
import { useStartTherapySession } from '../../../lib/hooks/useTherapySessions';
import { StartSessionRequest } from '../../../lib/api/therapySessions';
import { EditAppointmentModal } from './EditAppointmentModal';
import { EditTimeBlockModal } from './EditTimeBlockModal';
import { SeriesActionDialog } from './SeriesActionDialog';
import { ProtectedAppointmentModal } from './ProtectedAppointmentModal';
import { ConfirmationModal } from '../../../components/ui/ConfirmationModal';

// Helper function to check if appointment can be modified
const canModifyAppointment = (appointment: AppointmentSummary): { canModify: boolean; reason?: string } => {
  // Primary check: therapy session status
  if (appointment.therapy_session_status) {
    if (appointment.therapy_session_status === 'completed') {
      return { canModify: false, reason: "This therapy session has been completed" };
    }
    if (appointment.therapy_session_status === 'in_progress') {
      return { canModify: false, reason: "This therapy session is currently in progress" };
    }
  }
  
  // Secondary check: appointment timing
  const now = new Date();
  const appointmentStart = new Date(appointment.start_datetime);
  
  if (appointmentStart < now && !appointment.therapy_session_status) {
    return { canModify: false, reason: "This appointment has already started" };
  }
  
  return { canModify: true };
};

interface CellDetailModalProps {
  open: boolean;
  onClose: () => void;
  date: Date;
  hour: number;
  appointments: AppointmentSummary[];
  timeBlocks: TimeBlockSummary[];
  students: StudentScheduleView[];
  onEditAppointment?: (appointment: AppointmentSummary) => void;
  onStartTherapySession?: (appointment: AppointmentSummary) => void;
  onEditTimeBlock?: (timeBlock: TimeBlockSummary) => void;
  onDeleteAppointment?: (appointment: AppointmentSummary) => void;
  onDeleteTimeBlock?: (timeBlock: TimeBlockSummary) => void;
  onUpdateAppointment?: (appointmentData: any) => void;
  onSeriesUpdate?: () => Promise<void>; // New callback for series updates
  onUpdateTimeBlock?: (timeBlockData: any) => void;
  onLoadTherapySession?: (appointmentId: number) => Promise<{
    goals: Array<{ goal_id: number; goal_text: string; planned: boolean; worked_on: boolean }>;
    objectives: Array<{ objective_id: number; goal_id: number; objective_text: string; planned: boolean; worked_on: boolean }>;
  }>;
}

interface TimeSlot {
  time: string;
  timeValue: Date;
  hour: number;
  minute: number;
  isSelectedHour: boolean;
  slotIndex: number;
}

interface AppointmentBlock {
  appointment: AppointmentSummary;
  startSlotIndex: number;
  durationSlots: number;
  isSelected: boolean;
}

interface TimeBlockBlock {
  timeBlock: TimeBlockSummary;
  startSlotIndex: number;
  durationSlots: number;
  isSelected: boolean;
}

export function CellDetailModal({
  open,
  onClose,
  date,
  hour,
  appointments,
  timeBlocks,
  students,
  onEditAppointment,
  onStartTherapySession,
  onEditTimeBlock,
  onDeleteAppointment,
  onDeleteTimeBlock,
  onUpdateAppointment,
  onSeriesUpdate,
  onUpdateTimeBlock,
  onLoadTherapySession
}: CellDetailModalProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const eventsScrollRef = useRef<HTMLDivElement>(null);
  
  // API hooks for direct therapy session creation
  const startSessionMutation = useStartTherapySession();
  const navigate = useNavigate();
  
  // State for edit modals
  const [editAppointmentModalOpen, setEditAppointmentModalOpen] = useState(false);
  const [editTimeBlockModalOpen, setEditTimeBlockModalOpen] = useState(false);
  const [selectedAppointmentForEdit, setSelectedAppointmentForEdit] = useState<AppointmentSummary | null>(null);
  const [selectedTimeBlockForEdit, setSelectedTimeBlockForEdit] = useState<TimeBlockSummary | null>(null);
  
  // State for delete confirmation modal
  const [deleteConfirmationOpen, setDeleteConfirmationOpen] = useState(false);
  const [itemToDelete, setItemToDelete] = useState<{
    type: 'appointment' | 'timeBlock';
    item: AppointmentSummary | TimeBlockSummary;
  } | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  
  // State for series action dialog
  const [seriesActionDialogOpen, setSeriesActionDialogOpen] = useState(false);
  const [appointmentForSeriesAction, setAppointmentForSeriesAction] = useState<AppointmentSummary | null>(null);
  const [seriesActionType, setSeriesActionType] = useState<'edit' | 'delete'>('delete');
  
  // State for protected appointment modal
  const [protectedModalOpen, setProtectedModalOpen] = useState(false);
  const [protectedAppointment, setProtectedAppointment] = useState<AppointmentSummary | null>(null);
  const [protectedAction, setProtectedAction] = useState<'edit' | 'delete'>('edit');
  const [protectedReason, setProtectedReason] = useState('');
  
  // State for time block detail data
  const [timeBlockDetails, setTimeBlockDetails] = useState<{[key: number]: any}>({});
  
  // Load time block details when needed
  const loadTimeBlockDetails = async (timeBlockId: number) => {
    if (timeBlockDetails[timeBlockId]) {
      return timeBlockDetails[timeBlockId]; // Already loaded
    }
    
    try {
      const { schedulingApi } = await import('../../../lib/api/scheduling');
      const [detailedData, appointmentsData] = await Promise.all([
        schedulingApi.getTimeBlockDetailed(timeBlockId),
        schedulingApi.getTimeBlockAppointments(timeBlockId)
      ]);
      
      const details = {
        ...detailedData,
        appointments: appointmentsData
      };
      
      setTimeBlockDetails(prev => ({
        ...prev,
        [timeBlockId]: details
      }));
      
      return details;
    } catch (error) {
      console.error(`Failed to load time block ${timeBlockId} details:`, error);
      return null;
    }
  };
  
  // Generate time slots from 8 AM to 4 PM in 5-minute intervals
  const timeSlots = useMemo<TimeSlot[]>(() => {
    const slots: TimeSlot[] = [];
    const startHour = 8; // 8:00 AM
    const endHour = 16; // 4:00 PM
    const totalMinutes = (endHour - startHour) * 60; // 8 hours = 480 minutes
    const intervalMinutes = 5;
    
    for (let i = 0; i < totalMinutes / intervalMinutes; i++) {
      const slotMinutes = i * intervalMinutes;
      const slotHour = startHour + Math.floor(slotMinutes / 60);
      const slotMinute = slotMinutes % 60;
      
      // Create the time for this slot using the provided date
      const slotTime = new Date(date);
      slotTime.setHours(slotHour, slotMinute, 0, 0);
      
      const timeString = format(slotTime, 'h:mm a');
      
      // Check if this slot is in the selected hour
      const isSelectedHour = slotHour === hour;
      
      slots.push({
        time: timeString,
        timeValue: slotTime,
        hour: slotHour,
        minute: slotMinute,
        isSelectedHour,
        slotIndex: i
      });
    }
    
    return slots;
  }, [date, hour]);

  // Process appointments into continuous blocks
  const appointmentBlocks = useMemo<AppointmentBlock[]>(() => {
    const startHour = 8;
    const intervalMinutes = 5;
    
    return appointments
      .filter(apt => {
        if (!apt.start_datetime || !apt.end_datetime) return false;
        const aptDate = new Date(apt.start_datetime);
        return isSameDay(aptDate, date);
      })
      .map(apt => {
        const startTime = new Date(apt.start_datetime!);
        const endTime = new Date(apt.end_datetime!);
        
        // Calculate slot indices
        const startMinutesFromBase = (startTime.getHours() - startHour) * 60 + startTime.getMinutes();
        const endMinutesFromBase = (endTime.getHours() - startHour) * 60 + endTime.getMinutes();
        
        const startSlotIndex = Math.floor(startMinutesFromBase / intervalMinutes);
        const endSlotIndex = Math.ceil(endMinutesFromBase / intervalMinutes);
        const durationSlots = Math.max(1, endSlotIndex - startSlotIndex);
        
        // Check if this appointment overlaps with the selected hour
        const isSelected = startTime.getHours() <= hour && endTime.getHours() >= hour;
        
        return {
          appointment: apt,
          startSlotIndex,
          durationSlots,
          isSelected
        };
      })
      .filter(block => block.startSlotIndex >= 0 && block.startSlotIndex < timeSlots.length);
  }, [appointments, date, hour, timeSlots.length]);

  // Process time blocks into continuous blocks
  const timeBlockBlocks = useMemo<TimeBlockBlock[]>(() => {
    const startHour = 8;
    const intervalMinutes = 5;
    
    return timeBlocks
      .filter(block => {
        if (!block.start_datetime || !block.end_datetime) return false;
        const blockDate = new Date(block.start_datetime);
        return isSameDay(blockDate, date);
      })
      .map(block => {
        const startTime = new Date(block.start_datetime!);
        const endTime = new Date(block.end_datetime!);
        
        // Calculate slot indices
        const startMinutesFromBase = (startTime.getHours() - startHour) * 60 + startTime.getMinutes();
        const endMinutesFromBase = (endTime.getHours() - startHour) * 60 + endTime.getMinutes();
        
        const startSlotIndex = Math.floor(startMinutesFromBase / intervalMinutes);
        const endSlotIndex = Math.ceil(endMinutesFromBase / intervalMinutes);
        const durationSlots = Math.max(1, endSlotIndex - startSlotIndex);
        
        // Check if this time block overlaps with the selected hour
        const isSelected = startTime.getHours() <= hour && endTime.getHours() >= hour;
        
        return {
          timeBlock: block,
          startSlotIndex,
          durationSlots,
          isSelected
        };
      })
      .filter(block => block.startSlotIndex >= 0 && block.startSlotIndex < timeSlots.length);
  }, [timeBlocks, date, hour, timeSlots.length]);

  // Sync scroll between time column and events column
  const handleTimeScroll = (e: React.UIEvent<HTMLDivElement>) => {
    if (eventsScrollRef.current) {
      eventsScrollRef.current.scrollTop = e.currentTarget.scrollTop;
    }
  };

  const handleEventsScroll = (e: React.UIEvent<HTMLDivElement>) => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = e.currentTarget.scrollTop;
    }
  };

  // Auto-scroll to selected hour when modal opens
  useEffect(() => {
    if (open && scrollContainerRef.current && eventsScrollRef.current) {
      const selectedSlotIndex = timeSlots.findIndex(slot => slot.isSelectedHour);
      if (selectedSlotIndex >= 0) {
        const slotHeight = 35; // Height of each time slot
        const scrollPosition = selectedSlotIndex * slotHeight - 200; // Offset to center in view
        
        // Small delay to ensure DOM is rendered
        setTimeout(() => {
          if (scrollContainerRef.current && eventsScrollRef.current) {
            const targetScroll = Math.max(0, scrollPosition);
            scrollContainerRef.current.scrollTo({
              top: targetScroll,
              behavior: 'smooth'
            });
            eventsScrollRef.current.scrollTo({
              top: targetScroll,
              behavior: 'smooth'
            });
          }
        }, 150);
      }
    }
  }, [open, timeSlots]);
  
  const formatDateHeader = (date: Date, hour: number) => {
    return format(date, 'EEEE, MMM d, yyyy') + ' - Detailed Schedule (8:00 AM - 4:00 PM)';
  };
  
  const handleAppointmentClick = (appointment: AppointmentSummary) => {
    const modificationCheck = canModifyAppointment(appointment);
    
    if (!modificationCheck.canModify) {
      setProtectedAppointment(appointment);
      setProtectedAction('edit');
      setProtectedReason(modificationCheck.reason || 'Unknown reason');
      setProtectedModalOpen(true);
    } else {
      setSelectedAppointmentForEdit(appointment);
      setEditAppointmentModalOpen(true);
    }
  };
  
  const handleStartSession = async (appointment: AppointmentSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    
    try {
      // Create therapy session directly from appointment
      const request: StartSessionRequest = {
        student_id: appointment.student_id,
        session_type: 'link_existing',
        appointment_id: appointment.id,
        create_appointment: false, // Already linked to existing appointment
        planned_duration_minutes: appointment.duration_minutes || 30,
        planned_goals: [], // TODO: Get planned goals from appointment
        planned_objectives: [] // TODO: Get planned objectives from appointment
      };

      const newSession = await startSessionMutation.mutateAsync(request);
      
      // Navigate directly to therapy session interface
      navigate(`/therapy/session/${newSession.id}`);
      
      // Close the modal
      onClose();
    } catch (error) {
      console.error('Failed to start therapy session from appointment:', error);
      // Show error to user - no fallback needed since this should always work
      alert(`Failed to start therapy session: ${error instanceof Error ? error.message : 'Unknown error'}\n\nPlease try again or contact support if the issue persists.`);
    }
  };
  
  const handleTimeBlockClick = (timeBlock: TimeBlockSummary) => {
    setSelectedTimeBlockForEdit(timeBlock);
    setEditTimeBlockModalOpen(true);
  };

  // Handle edit modal close
  const handleEditAppointmentClose = () => {
    setEditAppointmentModalOpen(false);
    setSelectedAppointmentForEdit(null);
  };

  const handleEditTimeBlockClose = () => {
    setEditTimeBlockModalOpen(false);
    setSelectedTimeBlockForEdit(null);
  };

  // Handle update callbacks
  const handleUpdateAppointment = async (appointmentData: any) => {
    if (onUpdateAppointment) {
      await onUpdateAppointment(appointmentData);
    }
    handleEditAppointmentClose();
  };

  const handleUpdateTimeBlock = async (timeBlockData: any) => {
    if (onUpdateTimeBlock) {
      await onUpdateTimeBlock(timeBlockData);
    }
    handleEditTimeBlockClose();
  };

  // Handle delete with confirmation modal
  const handleDeleteAppointment = (appointment: AppointmentSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    
    const modificationCheck = canModifyAppointment(appointment);
    
    if (!modificationCheck.canModify) {
      setProtectedAppointment(appointment);
      setProtectedAction('delete');
      setProtectedReason(modificationCheck.reason || 'Unknown reason');
      setProtectedModalOpen(true);
      return;
    }
    
    // Check if this appointment is part of a series
    if (appointment.series_id) {
      setAppointmentForSeriesAction(appointment);
      setSeriesActionType('delete');
      setSeriesActionDialogOpen(true);
    } else {
      setItemToDelete({ type: 'appointment', item: appointment });
      setDeleteConfirmationOpen(true);
    }
  };

  const handleDeleteTimeBlock = (timeBlock: TimeBlockSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    setItemToDelete({ type: 'timeBlock', item: timeBlock });
    setDeleteConfirmationOpen(true);
  };

  // Handle confirmation modal close
  const handleDeleteCancel = () => {
    setDeleteConfirmationOpen(false);
    setItemToDelete(null);
    setDeleteLoading(false);
  };

  // Handle confirmed deletion
  const handleDeleteConfirm = async () => {
    if (!itemToDelete) return;

    setDeleteLoading(true);
    try {
      if (itemToDelete.type === 'appointment') {
        await onDeleteAppointment?.(itemToDelete.item as AppointmentSummary);
      } else {
        await onDeleteTimeBlock?.(itemToDelete.item as TimeBlockSummary);
      }
      
      // Close confirmation modal but keep detail modal open
      handleDeleteCancel();
      
      // Note: The parent handlers will refresh the data, so the modal will re-render
      // with updated data automatically
    } catch (error) {
      console.error('Delete failed:', error);
      setDeleteLoading(false);
      // Keep the confirmation modal open to show the error or let user retry
    }
  };

  // Handle series action dialog
  const handleSeriesActionClose = () => {
    setSeriesActionDialogOpen(false);
    setAppointmentForSeriesAction(null);
  };

  const handleSingleAppointmentDelete = async () => {
    if (!appointmentForSeriesAction) return;
    
    try {
      await onDeleteAppointment?.(appointmentForSeriesAction);
      handleSeriesActionClose();
    } catch (error) {
      console.error('Failed to delete single appointment:', error);
    }
  };

  const handleSeriesDelete = async () => {
    if (!appointmentForSeriesAction?.series_id) return;
    
    try {
      const { schedulingApi } = await import('../../../lib/api/scheduling');
      await schedulingApi.deleteAppointmentSeries(appointmentForSeriesAction.series_id);
      console.log('✅ Series deleted successfully');
      
      // Trigger data refresh without individual appointment deletion
      if (onSeriesUpdate) {
        await onSeriesUpdate();
      }
      
      handleSeriesActionClose();
    } catch (error) {
      console.error('Failed to delete appointment series:', error);
    }
  };
  
  return (
    <>
    <Dialog 
      open={open} 
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      fullScreen={isMobile}
      PaperProps={{
        sx: { 
          height: isMobile ? '100vh' : '85vh', 
          maxHeight: isMobile ? '100vh' : '85vh' 
        }
      }}
    >
      <DialogTitle sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        pb: 1,
        px: isMobile ? 2 : 3,
        py: isMobile ? 1.5 : 2
      }}>
        <Box>
          <Typography 
            variant={isMobile ? "subtitle1" : "h6"} 
            component="div"
            sx={{ fontSize: isMobile ? '1.1rem' : undefined }}
          >
            {isMobile ? "Schedule Details" : "Daily Schedule Details"}
          </Typography>
          <Typography 
            variant={isMobile ? "body2" : "subtitle2"} 
            color="text.secondary"
            sx={{ fontSize: isMobile ? '0.8rem' : undefined }}
          >
            {formatDateHeader(date, hour)} • Focused on {format(setHours(setMinutes(new Date(date), 0), hour), 'h:00 a')}
          </Typography>
        </Box>
        <IconButton onClick={onClose} size={isMobile ? "medium" : "small"}>
          <Close />
        </IconButton>
      </DialogTitle>
      
      <DialogContent dividers sx={{ 
        p: 0, 
        height: isMobile ? 'calc(100vh - 120px)' : 'calc(85vh - 120px)', 
        overflow: 'hidden' 
      }}>
        <Box sx={{ height: '100%', display: 'flex' }}>
          {/* Custom Grid Layout */}
          <Grid container sx={{ height: '100%', overflow: 'hidden', flexWrap: 'nowrap' }}>
            {/* Time Column */}
            <Grid item xs={2} sx={{ 
              borderRight: '1px solid #e0e0e0',
              backgroundColor: '#f8f9fa'
            }}>
              {/* Header */}
              <Box sx={{ 
                height: 56,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderBottom: '2px solid #e0e0e0',
                fontWeight: 600,
                backgroundColor: '#f8f9fa'
              }}>
                <Typography variant="subtitle2" fontWeight={600}>
                  Time
                </Typography>
              </Box>
              
              {/* Time slots */}
              <Box sx={{ 
                height: 'calc(100% - 56px)', 
                overflow: 'auto',
                overflowX: 'hidden',
                /* Hide scrollbar but keep functionality */
                scrollbarWidth: 'none', /* Firefox */
                msOverflowStyle: 'none', /* IE and Edge */
                '&::-webkit-scrollbar': {
                  display: 'none' /* Chrome, Safari, Opera */
                }
              }} ref={scrollContainerRef} onScroll={handleTimeScroll}>
                <Box sx={{ minHeight: `${timeSlots.length * 35}px` }}>
                  {timeSlots.map((slot, index) => (
                    <Box 
                      key={index}
                      sx={{ 
                        height: 35,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderBottom: '1px solid #e8e8e8',
                        backgroundColor: slot.isSelectedHour ? 'primary.50' : 'transparent',
                        fontWeight: slot.isSelectedHour ? 600 : 400,
                        color: slot.isSelectedHour ? 'primary.main' : 'text.secondary'
                      }}
                    >
                      <Typography variant="caption" sx={{ fontSize: '0.75rem' }}>
                        {slot.time}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              </Box>
            </Grid>
            
            {/* Events Column */}
            <Grid item xs={10} sx={{ position: 'relative' }}>
              {/* Header */}
              <Box sx={{ 
                height: 56,
                display: 'flex',
                alignItems: 'center',
                paddingLeft: 2,
                borderBottom: '2px solid #e0e0e0',
                backgroundColor: '#f8f9fa'
              }}>
                <Typography variant="subtitle2" fontWeight={600}>
                  Scheduled Events
                </Typography>
              </Box>
              
              {/* Events area with continuous blocks */}
              <Box sx={{ 
                height: 'calc(100% - 56px)', 
                position: 'relative',
                overflow: 'auto',
                overflowX: 'hidden'
              }} ref={eventsScrollRef} onScroll={handleEventsScroll}>
                {/* Content container with proper height */}
                <Box sx={{ 
                  position: 'relative',
                  minHeight: `${timeSlots.length * 35}px`,
                  height: `${timeSlots.length * 35}px`
                }}>
                  {/* Background grid lines */}
                  {timeSlots.map((slot, index) => (
                    <Box 
                      key={`bg-${index}`}
                      sx={{ 
                        position: 'absolute',
                        top: index * 35,
                        left: 0,
                        right: 0,
                        height: 35,
                        borderBottom: '1px solid #e8e8e8',
                        backgroundColor: slot.isSelectedHour ? 'primary.25' : 'transparent',
                        opacity: 0.3
                      }}
                    />
                  ))}
                
                {/* Appointment Blocks */}
                {appointmentBlocks.map((block, index) => {
                  const topPosition = block.startSlotIndex * 35;
                  const height = block.durationSlots * 35 - 2; // Subtract 2px for border spacing
                  const modificationCheck = canModifyAppointment(block.appointment);
                  const canModify = modificationCheck.canModify;
                  
                  return (
                    <Paper
                      key={`apt-${index}`}
                      elevation={2}
                      sx={{
                        position: 'absolute',
                        top: topPosition + 1,
                        left: 8,
                        right: 8,
                        height: height,
                        backgroundColor: !canModify 
                          ? (block.appointment.therapy_session_status === 'completed' 
                              ? (block.isSelected ? '#2E7A85' : '#41AAB7') 
                              : (block.isSelected ? 'grey.700' : 'grey.600'))
                          : (block.isSelected ? 'primary.main' : 'primary.light'),
                        color: !canModify 
                          ? 'white'
                          : (block.isSelected ? 'white' : 'primary.contrastText'),
                        border: '1px solid',
                        borderColor: !canModify 
                          ? (block.appointment.therapy_session_status === 'completed' ? '#41AAB7' : 'grey.600')
                          : (block.isSelected ? 'primary.dark' : 'primary.main'),
                        cursor: 'pointer',
                        p: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        overflow: 'hidden',
                        opacity: !canModify ? 0.8 : 1,
                        '&:hover': {
                          backgroundColor: !canModify 
                            ? (block.appointment.therapy_session_status === 'completed' 
                                ? (block.isSelected ? '#2E7A85' : '#358A96') 
                                : (block.isSelected ? 'grey.800' : 'grey.700'))
                            : (block.isSelected ? 'primary.dark' : 'primary.main'),
                          borderColor: !canModify 
                            ? (block.appointment.therapy_session_status === 'completed' ? '#358A96' : 'grey.700')
                            : 'primary.dark'
                        },
                        zIndex: block.isSelected ? 10 : 5
                      }}
                      onClick={() => handleAppointmentClick(block.appointment)}
                    >
                      <Box sx={{ flex: 1, overflow: 'hidden' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                          <Person fontSize="small" />
                          <Typography variant="subtitle2" fontWeight={600} noWrap>
                            {block.appointment.student_name || 'Unknown'}
                          </Typography>
                          {block.appointment.series_id && (
                            <Repeat fontSize="small" />
                          )}
                          {!canModify && (
                            <Lock fontSize="small" sx={{ opacity: 0.7 }} />
                          )}
                        </Box>
                        
                        <Typography variant="caption" sx={{ opacity: 0.9 }}>
                          {format(new Date(block.appointment.start_datetime!), 'h:mm a')} - {format(new Date(block.appointment.end_datetime!), 'h:mm a')}
                        </Typography>
                        
                        {block.appointment.location && (
                          <Typography variant="caption" sx={{ display: 'block', opacity: 0.8 }}>
                            {block.appointment.location}
                          </Typography>
                        )}
                      </Box>
                      
                      <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
                        <Tooltip title={canModify ? "Edit Appointment" : `Cannot edit: ${modificationCheck.reason}`}>
                          <IconButton 
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAppointmentClick(block.appointment);
                            }}
                            sx={{ 
                              color: 'inherit',
                              backgroundColor: !canModify 
                                ? 'rgba(128,128,128,0.6)'
                                : 'rgba(255,255,255,0.2)',
                              '&:hover': { 
                                backgroundColor: !canModify 
                                  ? 'rgba(128,128,128,0.8)'
                                  : 'rgba(255,255,255,0.3)' 
                              }
                            }}
                          >
                            {!canModify ? <Lock fontSize="small" /> : <Edit fontSize="small" />}
                          </IconButton>
                        </Tooltip>
                        
                        <Tooltip title={canModify ? "Delete Appointment" : `Cannot delete: ${modificationCheck.reason}`}>
                          <IconButton 
                            size="small"
                            onClick={(e) => handleDeleteAppointment(block.appointment, e)}
                            sx={{ 
                              color: 'inherit',
                              backgroundColor: !canModify 
                                ? 'rgba(128,128,128,0.6)'
                                : 'rgba(244,67,54,0.8)',
                              '&:hover': { 
                                backgroundColor: !canModify 
                                  ? 'rgba(128,128,128,0.8)'
                                  : 'rgba(244,67,54,1)' 
                              }
                            }}
                          >
                            {!canModify ? <Lock fontSize="small" /> : <Delete fontSize="small" />}
                          </IconButton>
                        </Tooltip>
                        
                        <Tooltip title="Start Therapy Session">
                          <IconButton 
                            size="small"
                            onClick={(e) => handleStartSession(block.appointment, e)}
                            sx={{ 
                              color: 'inherit',
                              backgroundColor: 'rgba(76,175,80,0.8)',
                              '&:hover': { backgroundColor: 'rgba(76,175,80,1)' }
                            }}
                          >
                            <PlayArrow fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </Paper>
                  );
                })}
                
                  {/* Time Block Blocks */}
                  {timeBlockBlocks.map((block, index) => {
                  const topPosition = block.startSlotIndex * 35;
                  const height = block.durationSlots * 35 - 2;
                  
                  return (
                    <Paper
                      key={`block-${index}`}
                      elevation={2}
                      sx={{
                        position: 'absolute',
                        top: topPosition + 1,
                        left: 8,
                        right: 8,
                        height: height,
                        backgroundColor: block.isSelected ? 'secondary.main' : 'secondary.light',
                        color: block.isSelected ? 'white' : 'secondary.contrastText',
                        border: '1px solid',
                        borderColor: block.isSelected ? 'secondary.dark' : 'secondary.main',
                        cursor: 'pointer',
                        p: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        overflow: 'hidden',
                        '&:hover': {
                          backgroundColor: block.isSelected ? 'secondary.dark' : 'secondary.main',
                          borderColor: 'secondary.dark'
                        },
                        zIndex: block.isSelected ? 10 : 5
                      }}
                      onClick={() => handleTimeBlockClick(block.timeBlock)}
                    >
                      <Box sx={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', gap: 1, p: 0.5 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Group fontSize="medium" />
                          <Typography variant="subtitle1" fontWeight={600} sx={{ 
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            flex: 1,
                            minWidth: 0,
                            fontSize: '1rem'
                          }}>
                            {block.timeBlock.title || 'Group Therapy'}
                          </Typography>
                          <Badge badgeContent={block.timeBlock.current_student_count || 0} color="secondary" max={99} />
                        </Box>
                        
                        <Typography variant="body2" sx={{ opacity: 0.95, fontWeight: 600, fontSize: '0.875rem' }}>
                          {format(new Date(block.timeBlock.start_datetime!), 'h:mm a')} - {format(new Date(block.timeBlock.end_datetime!), 'h:mm a')}
                        </Typography>
                        
                        {block.timeBlock.teacher_name && (
                          <Typography variant="body2" sx={{ opacity: 0.9, fontStyle: 'italic', fontSize: '0.8rem' }}>
                            👨‍🏫 {block.timeBlock.teacher_name}
                          </Typography>
                        )}
                        
                        {block.timeBlock.location && (
                          <Typography variant="body2" sx={{ opacity: 0.9, fontSize: '0.8rem' }}>
                            📍 {block.timeBlock.location}
                          </Typography>
                        )}
                        
                        {/* Activities Section */}
                        {block.timeBlock.current_student_count && block.timeBlock.current_student_count > 0 && (
                          <Box sx={{ mt: 1, maxHeight: height - 120, overflow: 'auto' }}>
                            {/* Load and display activities for this time block */}
                            <TimeBlockActivitiesDisplay timeBlockId={block.timeBlock.id} />
                            
                            {/* Time Allocation Section */}
                            <Box sx={{ mt: 1, pt: 1, borderTop: '1px solid rgba(255,255,255,0.2)' }}>
                              <Typography variant="caption" sx={{ fontSize: '0.7rem', fontWeight: 'bold', opacity: 0.8, mb: 0.5, display: 'block' }}>
                                TIME ALLOCATION
                              </Typography>
                              {/* Get actual student names from appointments for this time block */}
                              {(() => {
                              const startTime = new Date(block.timeBlock.start_datetime!);
                              const endTime = new Date(block.timeBlock.end_datetime!);
                              const totalMinutes = differenceInMinutes(endTime, startTime);
                              
                              // First try to use cached time block details
                              const details = timeBlockDetails[block.timeBlock.id];
                              let timeBlockAppointments: any[] = [];
                              
                              if (details && details.appointments) {
                                timeBlockAppointments = details.appointments.filter((apt: any) => 
                                  isSameDay(new Date(apt.start_datetime), date)
                                ).sort((a: any, b: any) => new Date(a.start_datetime).getTime() - new Date(b.start_datetime).getTime());
                                console.log(`🔍 Using cached time block ${block.timeBlock.id} appointments:`, timeBlockAppointments.length);
                              } else {
                                // Fallback to general appointments array
                                timeBlockAppointments = appointments.filter(apt => 
                                  (apt as any).time_block_id === block.timeBlock.id && 
                                  isSameDay(new Date(apt.start_datetime!), date)
                                ).sort((a, b) => new Date(a.start_datetime!).getTime() - new Date(b.start_datetime!).getTime());
                                
                                console.log(`🔍 Time block ${block.timeBlock.id} appointments from general array:`, timeBlockAppointments.length);
                                
                                // If no appointments found, try to load details
                                if (timeBlockAppointments.length === 0) {
                                  loadTimeBlockDetails(block.timeBlock.id);
                                }
                              }
                              
                              // Prioritize assigned_students data if available (most reliable)
                              const timeBlockWithStudents = block.timeBlock as any;
                              if (timeBlockWithStudents.assigned_students && timeBlockWithStudents.assigned_students.length > 0) {
                                console.log(`🔍 Using time block assigned_students:`, timeBlockWithStudents.assigned_students);
                                
                                const studentCount = timeBlockWithStudents.assigned_students.length;
                                const minutesPerStudent = Math.floor(totalMinutes / studentCount / 5) * 5;
                                
                                return timeBlockWithStudents.assigned_students.map((student: any, i: number) => {
                                  const slotStart = addMinutes(startTime, i * minutesPerStudent);
                                  const slotEnd = addMinutes(slotStart, minutesPerStudent);
                                  
                                  return {
                                    index: i + 1,
                                    name: `${student.first} ${student.last}`,
                                    startTime: slotStart,
                                    endTime: slotEnd,
                                    duration: minutesPerStudent
                                  };
                                });
                              }
                              
                              if (timeBlockAppointments.length === 0) {
                                
                                // Final fallback: calculate generic slots
                                const studentCount = block.timeBlock.current_student_count || 1;
                                const minutesPerStudent = Math.floor(totalMinutes / studentCount / 5) * 5;
                                
                                const studentSlots = [];
                                for (let i = 0; i < studentCount; i++) {
                                  const slotStart = addMinutes(startTime, i * minutesPerStudent);
                                  const slotEnd = addMinutes(slotStart, minutesPerStudent);
                                  
                                  studentSlots.push({
                                    index: i + 1,
                                    name: `Student ${i + 1}`,
                                    startTime: slotStart,
                                    endTime: slotEnd,
                                    duration: minutesPerStudent
                                  });
                                }
                                return studentSlots;
                              }
                              
                              // Use actual appointment data for student names and times
                              return timeBlockAppointments.map((apt, index) => ({
                                index: index + 1,
                                name: apt.student_name || `Student ${index + 1}`,
                                startTime: new Date(apt.start_datetime!),
                                endTime: new Date(apt.end_datetime!),
                                duration: differenceInMinutes(new Date(apt.end_datetime!), new Date(apt.start_datetime!))
                              }));
                            })().map((slot, index) => (
                              <Box key={index} sx={{ 
                                display: 'flex', 
                                alignItems: 'center', 
                                gap: 1,
                                mb: 0.5,
                                opacity: 0.95,
                                backgroundColor: 'rgba(255,255,255,0.1)',
                                borderRadius: 1,
                                p: 0.5
                              }}>
                                <Box sx={{ 
                                  minWidth: 20,
                                  height: 20,
                                  borderRadius: '50%',
                                  backgroundColor: 'rgba(255,255,255,0.4)',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  fontSize: '0.75rem',
                                  fontWeight: 'bold',
                                  color: 'secondary.main'
                                }}>
                                  {slot.index}
                                </Box>
                                <Typography variant="body2" sx={{ fontSize: '0.8rem', fontWeight: 500 }}>
                                  {slot.name}: {format(slot.startTime, 'h:mm')} - {format(slot.endTime, 'h:mm')} ({slot.duration}m)
                                </Typography>
                              </Box>
                            ))}
                            </Box>
                          </Box>
                        )}
                      </Box>
                      
                      <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
                        <Tooltip title="Edit Time Block">
                          <IconButton 
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleTimeBlockClick(block.timeBlock);
                            }}
                            sx={{ 
                              color: 'inherit',
                              backgroundColor: 'rgba(255,255,255,0.2)',
                              '&:hover': { backgroundColor: 'rgba(255,255,255,0.3)' }
                            }}
                          >
                            <Edit fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        
                        <Tooltip title="Delete Time Block">
                          <IconButton 
                            size="small"
                            onClick={(e) => handleDeleteTimeBlock(block.timeBlock, e)}
                            sx={{ 
                              color: 'inherit',
                              backgroundColor: 'rgba(244,67,54,0.8)',
                              '&:hover': { backgroundColor: 'rgba(244,67,54,1)' }
                            }}
                          >
                            <Delete fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </Paper>
                  );
                  })}
                </Box>
              </Box>
            </Grid>
          </Grid>
        </Box>
      </DialogContent>
      
      <DialogActions sx={{ 
        px: isMobile ? 2 : 3, 
        py: isMobile ? 1.5 : 2,
        flexDirection: isMobile ? 'column' : 'row',
        alignItems: isMobile ? 'stretch' : 'center'
      }}>
        <Typography 
          variant="caption" 
          color="text.secondary" 
          sx={{ 
            flex: 1,
            fontSize: isMobile ? '0.7rem' : undefined,
            textAlign: isMobile ? 'center' : 'left',
            mb: isMobile ? 1 : 0
          }}
        >
          {isMobile 
            ? "Tap blocks to edit or start sessions" 
            : "🕐 5-minute increments • 🎯 Blue highlighting shows your selected hour • Click blocks to edit or start sessions"
          }
        </Typography>
        <Button 
          onClick={onClose} 
          variant="outlined"
          fullWidth={isMobile}
          size={isMobile ? 'medium' : 'small'}
        >
          Close
        </Button>
      </DialogActions>
    </Dialog>

    {/* Edit Appointment Modal */}
    {selectedAppointmentForEdit && (
      <EditAppointmentModal
        open={editAppointmentModalOpen}
        onClose={handleEditAppointmentClose}
        appointment={selectedAppointmentForEdit}
        students={students}
        existingAppointments={appointments}
        onUpdateAppointment={handleUpdateAppointment}
        onSeriesUpdate={onSeriesUpdate}
        onLoadTherapySession={onLoadTherapySession}
      />
    )}

    {/* Edit Time Block Modal */}
    {selectedTimeBlockForEdit && (
      <EditTimeBlockModal
        open={editTimeBlockModalOpen}
        onClose={handleEditTimeBlockClose}
        timeBlock={selectedTimeBlockForEdit}
        students={students}
        onUpdateTimeBlock={handleUpdateTimeBlock}
      />
    )}

    {/* Delete Confirmation Modal */}
    <ConfirmationModal
      open={deleteConfirmationOpen}
      onClose={handleDeleteCancel}
      onConfirm={handleDeleteConfirm}
      title={itemToDelete?.type === 'appointment' ? 'Delete Appointment' : 'Delete Time Block'}
      message={
        itemToDelete?.type === 'appointment'
          ? `Are you sure you want to delete this appointment for ${(itemToDelete.item as AppointmentSummary).student_name}?\n\nThis will also delete the associated therapy session and all planned goals/objectives.`
          : `Are you sure you want to delete the time block "${(itemToDelete?.item as TimeBlockSummary)?.title}"?\n\nThis will delete ALL appointments in the time block and their therapy sessions.`
      }
      confirmText="Delete"
      cancelText="Cancel"
      severity="error"
      loading={deleteLoading}
    />

    {/* Series Action Dialog */}
    {appointmentForSeriesAction && (
      <SeriesActionDialog
        open={seriesActionDialogOpen}
        onClose={handleSeriesActionClose}
        appointment={appointmentForSeriesAction}
        action={seriesActionType}
        onSingleAction={handleSingleAppointmentDelete}
        onSeriesAction={handleSeriesDelete}
      />
    )}

    {/* Protected Appointment Modal */}
    {protectedAppointment && (
      <ProtectedAppointmentModal
        open={protectedModalOpen}
        onClose={() => setProtectedModalOpen(false)}
        appointment={protectedAppointment}
        action={protectedAction}
        reason={protectedReason}
      />
    )}
  </>
  );
}

// Component to display activities for a time block
interface TimeBlockActivitiesDisplayProps {
  timeBlockId: number;
}

function TimeBlockActivitiesDisplay({ timeBlockId }: TimeBlockActivitiesDisplayProps) {
  const [activities, setActivities] = React.useState<any[]>([]);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    const loadActivities = async () => {
      setLoading(true);
      try {
        const { schedulingApi } = await import('../../../lib/api/scheduling');
        const activitiesData = await schedulingApi.getTimeBlockActivities(timeBlockId);
        setActivities(activitiesData);
      } catch (error) {
        console.error(`Failed to load activities for time block ${timeBlockId}:`, error);
        setActivities([]);
      } finally {
        setLoading(false);
      }
    };

    if (timeBlockId) {
      loadActivities();
    }
  }, [timeBlockId]);

  if (loading) {
    return (
      <Typography variant="caption" sx={{ fontSize: '0.7rem', opacity: 0.8 }}>
        Loading activities...
      </Typography>
    );
  }

  if (activities.length === 0) {
    return (
      <Typography variant="caption" sx={{ fontSize: '0.7rem', opacity: 0.6, fontStyle: 'italic' }}>
        No activities planned
      </Typography>
    );
  }

  return (
    <Box sx={{ mb: 1 }}>
      <Typography variant="caption" sx={{ fontSize: '0.7rem', fontWeight: 'bold', opacity: 0.8, mb: 0.5, display: 'block' }}>
        ACTIVITIES
      </Typography>
      {activities.map((activity, index) => (
        <Box key={activity.id || index} sx={{ 
          mb: 0.5,
          p: 0.5,
          backgroundColor: 'rgba(255,255,255,0.1)',
          borderRadius: 1,
          border: '1px solid rgba(255,255,255,0.2)'
        }}>
          <Typography variant="caption" sx={{ fontSize: '0.75rem', fontWeight: 'bold', display: 'block' }}>
            🎯 {activity.activity_name}
          </Typography>
          <Typography variant="caption" sx={{ fontSize: '0.7rem', opacity: 0.9, display: 'block' }}>
            {activity.start_datetime && activity.end_datetime ? (
              `${format(new Date(activity.start_datetime), 'h:mm')} - ${format(new Date(activity.end_datetime), 'h:mm')} (${activity.duration_minutes}m)`
            ) : (
              `${activity.start_minute}m - ${activity.start_minute + activity.duration_minutes}m (${activity.duration_minutes}m)`
            )}
          </Typography>
          {activity.assigned_students && activity.assigned_students.length > 0 && (
            <Typography variant="caption" sx={{ fontSize: '0.65rem', opacity: 0.8, display: 'block', mt: 0.25 }}>
              👥 {activity.assigned_students.map((student: any) => student.full_name).join(', ')}
            </Typography>
          )}
        </Box>
      ))}
    </Box>
  );
}
