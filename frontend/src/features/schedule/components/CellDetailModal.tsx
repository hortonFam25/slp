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
  Delete
} from '@mui/icons-material';
import { format, addMinutes, isSameDay, startOfDay, setHours, setMinutes, differenceInMinutes } from 'date-fns';
import { useNavigate } from 'react-router-dom';
import { AppointmentSummary, TimeBlockSummary } from '../../../lib/api/scheduling';
import { StudentScheduleView } from '../../../lib/api/schedulingStudents';
import { useStartTherapySession } from '../../../lib/hooks/useTherapySessions';
import { StartSessionRequest } from '../../../lib/api/therapySessions';
import { EditAppointmentModal } from './EditAppointmentModal';
import { EditTimeBlockModal } from './EditTimeBlockModal';
import { ConfirmationModal } from '../../../components/ui/ConfirmationModal';

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
    setSelectedAppointmentForEdit(appointment);
    setEditAppointmentModalOpen(true);
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
    setItemToDelete({ type: 'appointment', item: appointment });
    setDeleteConfirmationOpen(true);
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
                        backgroundColor: block.isSelected ? 'primary.main' : 'primary.light',
                        color: block.isSelected ? 'white' : 'primary.contrastText',
                        border: '1px solid',
                        borderColor: block.isSelected ? 'primary.dark' : 'primary.main',
                        cursor: 'pointer',
                        p: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        overflow: 'hidden',
                        '&:hover': {
                          backgroundColor: block.isSelected ? 'primary.dark' : 'primary.main',
                          borderColor: 'primary.dark'
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
                        <Tooltip title="Edit Appointment">
                          <IconButton 
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAppointmentClick(block.appointment);
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
                        
                        <Tooltip title="Delete Appointment">
                          <IconButton 
                            size="small"
                            onClick={(e) => handleDeleteAppointment(block.appointment, e)}
                            sx={{ 
                              color: 'inherit',
                              backgroundColor: 'rgba(244,67,54,0.8)',
                              '&:hover': { backgroundColor: 'rgba(244,67,54,1)' }
                            }}
                          >
                            <Delete fontSize="small" />
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
                      <Box sx={{ flex: 1, overflow: 'hidden' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                          <Group fontSize="small" />
                          <Typography variant="subtitle2" fontWeight={600} noWrap>
                            {block.timeBlock.title || 'Group'}
                          </Typography>
                          <Badge badgeContent={block.timeBlock.current_student_count || 0} color="secondary" max={99} />
                        </Box>
                        
                        <Typography variant="caption" sx={{ opacity: 0.9 }}>
                          {format(new Date(block.timeBlock.start_datetime!), 'h:mm a')} - {format(new Date(block.timeBlock.end_datetime!), 'h:mm a')}
                        </Typography>
                        
                        {block.timeBlock.location && (
                          <Typography variant="caption" sx={{ display: 'block', opacity: 0.8 }}>
                            {block.timeBlock.location}
                          </Typography>
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
  </>
  );
}
