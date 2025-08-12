import React, { useState, useMemo } from 'react';
import { Box, Typography, IconButton, Button, Chip, Tooltip, Badge, Popover, FormControl, InputLabel, Select, MenuItem, ButtonGroup, useMediaQuery, useTheme, Drawer } from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { DataGrid, GridColDef, GridRowsProp } from '@mui/x-data-grid';
import {
  ChevronLeft,
  ChevronRight,
  Add,
  Person,
  Group,
  PlayArrow,
  Weekend,
  WeekendOutlined,
  Visibility,
  VisibilityOff,
  People,
  Refresh,
  Schedule,
  AccessTime,
  PersonAdd,
  GroupAdd,
  ViewDay,
  Close
} from '@mui/icons-material';
import { format, startOfWeek, addDays, addWeeks, subWeeks, isSameDay } from 'date-fns';
import { AppointmentSummary, TimeBlockSummary } from '../../../lib/api/scheduling';
import { StudentScheduleView } from '../../../lib/api/schedulingStudents';
import { UnscheduledStudentsPanel } from './UnscheduledStudentsPanel';

interface WeeklyCalendarDataGridProps {
  appointments: AppointmentSummary[];
  timeBlocks: TimeBlockSummary[];
  selectedDate: Date;
  onDateChange: (date: Date) => void;
  onAppointmentClick?: (appointment: AppointmentSummary) => void;
  onTimeBlockClick?: (timeBlock: TimeBlockSummary) => void;
  onCreateAppointment?: (date: Date, hour: number) => void;
  onCreateTimeBlock?: (date: Date, hour: number) => void;
  showTimeBlocks?: boolean;
  loading?: boolean;
  // Students panel props
  showStudentsPanel?: boolean;
  studentScheduleData?: {
    all: Array<{ student: StudentScheduleView; hasAppointments: boolean; appointmentCount: number; appointments: any[] }>;
    scheduled: Array<{ student: StudentScheduleView; hasAppointments: boolean; appointmentCount: number; appointments: any[] }>;
    unscheduled: Array<{ student: StudentScheduleView; hasAppointments: boolean; appointmentCount: number; appointments: any[] }>;
    counts: { total: number; scheduled: number; unscheduled: number };
  };
  schools?: Array<{ id: number; name: string }>;
  teachers?: Array<{ id: number; full_name: string }>;
  onQuickSchedule?: (student: StudentScheduleView) => void;
  // Integrated controls
  onToggleTimeBlocks?: () => void;
  onToggleStudentsPanel?: () => void;
  onRefresh?: () => void;
  onScheduleStudent?: (date: Date, hour: number) => void;
  onCreateTherapyGroup?: (date: Date, hour: number) => void;
  onStartSession?: (appointment: AppointmentSummary) => void;
  onViewCellDetails?: (date: Date, hour: number) => void;
}

const ALL_HOURS = Array.from({ length: 24 }, (_, i) => i); // 0 to 23 (24-hour format)
const DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

// Time options for the dropdowns (in 24-hour format)
const TIME_OPTIONS = [
  { value: 0, label: '12:00 AM' },
  { value: 1, label: '1:00 AM' },
  { value: 2, label: '2:00 AM' },
  { value: 3, label: '3:00 AM' },
  { value: 4, label: '4:00 AM' },
  { value: 5, label: '5:00 AM' },
  { value: 6, label: '6:00 AM' },
  { value: 7, label: '7:00 AM' },
  { value: 8, label: '8:00 AM' },
  { value: 9, label: '9:00 AM' },
  { value: 10, label: '10:00 AM' },
  { value: 11, label: '11:00 AM' },
  { value: 12, label: '12:00 PM' },
  { value: 13, label: '1:00 PM' },
  { value: 14, label: '2:00 PM' },
  { value: 15, label: '3:00 PM' },
  { value: 16, label: '4:00 PM' },
  { value: 17, label: '5:00 PM' },
  { value: 18, label: '6:00 PM' },
  { value: 19, label: '7:00 PM' },
  { value: 20, label: '8:00 PM' },
  { value: 21, label: '9:00 PM' },
  { value: 22, label: '10:00 PM' },
  { value: 23, label: '11:00 PM' }
];

export function WeeklyCalendarDataGrid({
  appointments,
  timeBlocks,
  selectedDate,
  onDateChange,
  onAppointmentClick,
  onTimeBlockClick,
  onCreateAppointment,
  onCreateTimeBlock,
  showTimeBlocks = true,
  loading = false,
  showStudentsPanel = false,
  studentScheduleData,
  schools = [],
  teachers = [],
  onQuickSchedule,
  onToggleTimeBlocks,
  onToggleStudentsPanel,
  onRefresh,
  onScheduleStudent,
  onCreateTherapyGroup,
  onStartSession,
  onViewCellDetails
}: WeeklyCalendarDataGridProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  // State for showing weekends
  const [showWeekends, setShowWeekends] = useState(false);
  
  // State for time range filter
  const [startHour, setStartHour] = useState(8); // 8:00 AM default
  const [endHour, setEndHour] = useState(15); // 3:00 PM default (last visible row)
  const [timeRangeAnchorEl, setTimeRangeAnchorEl] = useState<HTMLButtonElement | null>(null);
  
  // State for mobile students drawer
  const [mobileStudentsDrawerOpen, setMobileStudentsDrawerOpen] = useState(false);
  
  // State for mobile cell selection
  const [selectedCell, setSelectedCell] = useState<{date: Date, hour: number} | null>(null);
  const isTimeRangeOpen = Boolean(timeRangeAnchorEl);

  const handleTimeRangeClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setTimeRangeAnchorEl(event.currentTarget);
  };

  const handleTimeRangeClose = () => {
    setTimeRangeAnchorEl(null);
  };


  
  // Calculate current week
  const currentWeek = startOfWeek(selectedDate, { weekStartsOn: 1 }); // Monday = 1
  const allWeekDates = Array.from({ length: 7 }, (_, i) => addDays(currentWeek, i));
  
  // Filter dates based on weekend visibility
  const weekDates = useMemo(() => {
    return showWeekends ? allWeekDates : allWeekDates.slice(0, 5); // Monday-Friday only
  }, [allWeekDates, showWeekends]);

  // Generate hours based on selected time range
  const visibleHours = useMemo(() => {
    const hours = [];
    for (let hour = startHour; hour <= endHour; hour++) {
      hours.push(hour);
    }
    return hours;
  }, [startHour, endHour]);

  // Navigation functions
  const goToPreviousWeek = () => onDateChange(subWeeks(selectedDate, 1));
  const goToNextWeek = () => onDateChange(addWeeks(selectedDate, 1));
  const goToToday = () => onDateChange(new Date());

  // Check for weekend appointments when weekends are hidden
  const weekendAppointments = useMemo(() => {
    if (showWeekends) return 0;
    
    const saturdayDate = allWeekDates[5]; // Saturday
    const sundayDate = allWeekDates[6]; // Sunday
    
    return appointments.filter(apt => {
      if (!apt.appointment_time) return false;
      const aptDate = new Date(apt.appointment_time);
      return isSameDay(aptDate, saturdayDate) || isSameDay(aptDate, sundayDate);
    }).length;
  }, [showWeekends, allWeekDates, appointments]);

  const weekendTimeBlocks = useMemo(() => {
    if (showWeekends) return 0;
    
    const saturdayDate = allWeekDates[5]; // Saturday
    const sundayDate = allWeekDates[6]; // Sunday
    
    return timeBlocks.filter(block => {
      if (!block.start_time) return false;
      const blockDate = new Date(block.start_time);
      return isSameDay(blockDate, saturdayDate) || isSameDay(blockDate, sundayDate);
    }).length;
  }, [showWeekends, allWeekDates, timeBlocks]);

  // Create columns: Time + 7 days with responsive widths
  const columns: GridColDef[] = useMemo(() => {
    const timeColumnWidth = 100;
    const numberOfDays = weekDates.length;
    
    const cols: GridColDef[] = [
      {
        field: 'time',
        headerName: 'Time',
        width: timeColumnWidth,
        sortable: false,
        filterable: false,
        disableColumnMenu: true,
        resizable: false,
        renderCell: (params) => (
          <Typography 
            variant="body2" 
            color="text.secondary"
            sx={{ 
              fontWeight: 500,
              fontSize: '0.875rem',
              textAlign: 'center'
            }}
          >
            {params.value}
          </Typography>
        ),
      }
    ];

    // Add columns for each day of the week with flexible width
    weekDates.forEach((date, index) => {
      const isToday = isSameDay(date, new Date());
      const dayOfWeekIndex = (date.getDay() + 6) % 7; // Convert Sunday=0 to Monday=0 system
      cols.push({
        field: `day_${index}`,
        headerName: DAYS_OF_WEEK[dayOfWeekIndex],
        flex: 1, // This makes columns take equal remaining space
        minWidth: 120, // Minimum width to ensure readability
        sortable: false,
        filterable: false,
        disableColumnMenu: true,
        resizable: false,
        headerAlign: 'center',
        align: 'center',
        renderHeader: () => (
          <Box sx={{ textAlign: 'center', width: '100%' }}>
            <Typography 
              variant="subtitle2" 
              sx={{ 
                fontWeight: 600,
                color: isToday ? '#2196f3' : 'text.primary'
              }}
            >
              {DAYS_OF_WEEK[dayOfWeekIndex]}
            </Typography>
            <Typography 
              variant="h6" 
              sx={{ 
                color: isToday ? '#2196f3' : 'text.primary',
                fontWeight: isToday ? 700 : 400,
                fontSize: '1rem'
              }}
            >
              {format(date, 'd')}
            </Typography>
          </Box>
        ),
        renderCell: (params) => {
          const hour = params.row.hourValue; // Use the stored numeric hour value
          const cellDate = date; // Use the actual date from the iteration
          
          return (
            <Box 
              sx={{ 
                width: '100%', 
                height: '100%',
                minHeight: 60,
                display: 'flex',
                flexDirection: 'column',
                gap: 0.5,
                p: 0.5,
                position: 'relative',
                cursor: isMobile ? 'pointer' : 'default',
                '&:hover .schedule-overlay': {
                  opacity: 1
                },
                // Show selection highlight on mobile
                ...(isMobile && selectedCell && 
                    isSameDay(selectedCell.date, cellDate) && 
                    selectedCell.hour === hour && {
                  backgroundColor: 'rgba(25, 118, 210, 0.1)',
                  border: '2px solid #1976d2'
                })
              }}
              onClick={isMobile ? (e) => {
                e.stopPropagation();
                
                // Check if this cell is already selected
                const isCurrentlySelected = selectedCell && 
                  isSameDay(selectedCell.date, cellDate) && 
                  selectedCell.hour === hour;
                
                if (isCurrentlySelected) {
                  // Second tap - check if there are existing appointments/blocks
                  const cellAppointments = appointments.filter(appt => {
                    const apptDate = new Date(appt.start_datetime);
                    return isSameDay(apptDate, cellDate) && apptDate.getHours() === hour;
                  });
                  
                  const cellTimeBlocks = timeBlocks.filter(block => {
                    if (!block.start_time) return false;
                    const blockDate = new Date(block.start_time);
                    return isSameDay(blockDate, cellDate) && blockDate.getHours() === hour;
                  });
                  
                  // If there are existing items, show details
                  if (cellAppointments.length > 0 || cellTimeBlocks.length > 0) {
                    onViewCellDetails?.(cellDate, hour);
                  } else {
                    // For empty cells, default to schedule student (most common action)
                    onScheduleStudent?.(cellDate, hour);
                  }
                  
                  // Clear selection after action
                  setSelectedCell(null);
                } else {
                  // First tap - select the cell
                  setSelectedCell({ date: cellDate, hour });
                }
              } : undefined}
            >
              {/* Appointments Content - stacks from top */}
              <Box 
                className="appointments-content" 
                sx={{ 
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 0.5,
                  alignItems: 'flex-start',
                  width: '100%',
                  zIndex: 1
                }}
              >
              {(() => {
                const cellAppointments = appointments.filter(apt => {
                  if (!apt.start_datetime) return false;
                  const aptDate = new Date(apt.start_datetime);
                  return isSameDay(aptDate, cellDate) && aptDate.getHours() === hour;
                });

                // Check for overlapping appointments (appointments that extend beyond this hour)
                const overlappingAppointments = appointments.filter(apt => {
                  if (!apt.start_datetime || !apt.end_datetime) return false;
                  const startDate = new Date(apt.start_datetime);
                  const endDate = new Date(apt.end_datetime);
                  
                  // Check if appointment starts before this hour and ends in this hour (or after)
                  return isSameDay(startDate, cellDate) && 
                         startDate.getHours() < hour && 
                         endDate.getHours() >= hour;
                });

                if (cellAppointments.length === 0 && overlappingAppointments.length === 0) return null;

                // Calculate total items to determine display strategy
                const totalItems = overlappingAppointments.length + cellAppointments.length;
                const shouldShowIndividualAppointments = cellAppointments.length <= 2 && totalItems <= 3;

                return (
                  <>
                    {/* Always show overlap indicators first (at top of cell) */}
                    {overlappingAppointments.map(appointment => (
                      <Chip
                        key={`overlap-${appointment.id}`}
                        label={`↳ ${appointment.student_name || 'Unknown'} (cont.)`}
                        size="small"
                        variant="outlined"
                        onClick={(e) => {
                          e.stopPropagation();
                          onAppointmentClick?.(appointment);
                        }}
                        sx={{ 
                          fontSize: '0.7rem',
                          height: 20,
                          width: '100%',
                          backgroundColor: 'rgba(255, 193, 7, 0.1)',
                          borderColor: 'warning.main',
                          color: 'warning.dark',
                          borderStyle: 'dashed',
                          borderWidth: '1.5px',
                          fontWeight: 500,
                          '& .MuiChip-label': { 
                            px: 1.5,
                            py: 0,
                            fontWeight: 500
                          },
                          '&:hover': {
                            backgroundColor: 'rgba(255, 193, 7, 0.2)',
                            borderColor: 'warning.dark',
                            transform: 'translateY(-1px)',
                            boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                          },
                          transition: 'all 0.2s ease-in-out'
                        }}
                      />
                    ))}
                    
                    {/* Show individual appointments or count bubble for current hour appointments */}
                    {shouldShowIndividualAppointments ? (
                      // Show individual appointments
                      cellAppointments.map(appointment => (
                        <Chip
                          key={appointment.id}
                          label={appointment.student_name || 'Unknown'}
                          size="small"
                          color="primary"
                          icon={<Person />}
                          onClick={(e) => {
                            e.stopPropagation();
                            onAppointmentClick?.(appointment);
                          }}
                          sx={{ 
                            fontSize: isMobile ? '0.75rem' : '0.7rem',
                            height: isMobile ? 24 : 20,
                            width: '100%',
                            '& .MuiChip-label': { px: 1 },
                            '& .MuiChip-icon': { fontSize: isMobile ? 14 : 12 }
                          }}
                        />
                      ))
                    ) : cellAppointments.length > 0 ? (
                      // Show count bubble if there are appointments in this hour
                      <Chip
                        label={`${cellAppointments.length} Appointments`}
                        size="small"
                        color="primary"
                        icon={<Person />}
                        onClick={(e) => {
                          e.stopPropagation();
                          // Could show a popup with all appointments, or just click the first one
                          onAppointmentClick?.(cellAppointments[0]);
                        }}
                        sx={{ 
                          fontSize: isMobile ? '0.75rem' : '0.7rem',
                          height: isMobile ? 24 : 20,
                          width: '100%',
                          '& .MuiChip-label': { px: 1 },
                          '& .MuiChip-icon': { fontSize: isMobile ? 14 : 12 },
                          bgcolor: 'primary.main',
                          color: 'white',
                          fontWeight: 600
                        }}
                      />
                    ) : null}
                  </>
                );
              })()}

                {/* Render time blocks for this time slot */}
                {showTimeBlocks && timeBlocks
                  .filter(block => {
                    if (!block.start_time) return false;
                    const blockDate = new Date(block.start_time);
                    return isSameDay(blockDate, cellDate) && blockDate.getHours() === hour;
                  })
                  .map(timeBlock => (
                    <Chip
                      key={timeBlock.id}
                      label={`Group (${timeBlock.student_count || 0})`}
                      size="small"
                      color="secondary"
                      icon={<Group />}
                      onClick={(e) => {
                        e.stopPropagation();
                        onTimeBlockClick?.(timeBlock);
                      }}
                      sx={{ 
                        fontSize: '0.7rem',
                        height: 20,
                        width: '100%',
                        '& .MuiChip-label': { px: 1 },
                        '& .MuiChip-icon': { fontSize: 12 }
                      }}
                    />
                  ))
                }
              </Box>

              {/* Schedule Overlay - appears on hover (desktop) or when selected (mobile) */}
              <Box 
                className="schedule-overlay"
                sx={{ 
                  opacity: (() => {
                    if (isMobile) {
                      // On mobile, only show when this specific cell is selected
                      return selectedCell && 
                        isSameDay(selectedCell.date, cellDate) && 
                        selectedCell.hour === hour ? 1 : 0;
                    } else {
                      // On desktop, show on hover
                      return 0;
                    }
                  })(), 
                  // CRITICAL: Hide completely on mobile when not selected to prevent click interference
                  display: (() => {
                    if (isMobile) {
                      return selectedCell && 
                        isSameDay(selectedCell.date, cellDate) && 
                        selectedCell.hour === hour ? 'flex' : 'none';
                    } else {
                      return 'flex';
                    }
                  })(),
                  transition: 'opacity 0.2s ease',
                  position: 'absolute',
                  top: isMobile ? '-4px' : '-8px',
                  left: isMobile ? '-4px' : '-8px',
                  right: isMobile ? '-4px' : '-8px',
                  bottom: isMobile ? '-4px' : '-8px',
                  alignItems: 'center',
                  justifyContent: 'center',
                  backgroundColor: 'white',
                  borderRadius: isMobile ? 1 : 0,
                  border: isMobile ? '2px solid #1976d2' : 'none',
                  boxShadow: isMobile ? '0 2px 8px rgba(0,0,0,0.15)' : 'none',
                  zIndex: 10
                }}
              >
                {/* Centered Button Row - Responsive Size */}
                <Box sx={{ 
                  display: 'flex', 
                  gap: isMobile ? 1 : 0.5,
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <Tooltip title="Schedule Student" arrow>
                    <IconButton 
                      size={isMobile ? "medium" : "small"}
                      onClick={(e) => {
                        e.stopPropagation();
                        onScheduleStudent?.(cellDate, hour);
                      }}
                      sx={{ 
                        minWidth: 'auto',
                        width: isMobile ? 32 : 24,
                        height: isMobile ? 32 : 24,
                        bgcolor: 'primary.light',
                        color: 'white',
                        '&:hover': {
                          bgcolor: 'primary.main'
                        }
                      }}
                    >
                      <PersonAdd fontSize={isMobile ? "medium" : "small"} />
                    </IconButton>
                  </Tooltip>
                  
                  <Tooltip title="Create Therapy Group" arrow>
                    <IconButton 
                      size={isMobile ? "medium" : "small"}
                      onClick={(e) => {
                        e.stopPropagation();
                        onCreateTherapyGroup?.(cellDate, hour);
                      }}
                      sx={{ 
                        minWidth: 'auto',
                        width: isMobile ? 32 : 24,
                        height: isMobile ? 32 : 24,
                        bgcolor: 'secondary.light',
                        color: 'white',
                        '&:hover': {
                          bgcolor: 'secondary.main'
                        }
                      }}
                    >
                      <GroupAdd fontSize={isMobile ? "medium" : "small"} />
                    </IconButton>
                  </Tooltip>
                  
                  <Tooltip title="View Cell Details" arrow>
                    <IconButton 
                      size={isMobile ? "medium" : "small"}
                      onClick={(e) => {
                        e.stopPropagation();
                        onViewCellDetails?.(cellDate, hour);
                      }}
                      sx={{ 
                        minWidth: 'auto',
                        width: isMobile ? 32 : 24,
                        height: isMobile ? 32 : 24,
                        bgcolor: 'info.light',
                        color: 'white',
                        '&:hover': {
                          bgcolor: 'info.main'
                        }
                      }}
                    >
                      <ViewDay fontSize={isMobile ? "medium" : "small"} />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Box>
            </Box>
          );
        }
      });
    });

    return cols;
  }, [weekDates, appointments, timeBlocks, showTimeBlocks, onAppointmentClick, onTimeBlockClick, onCreateAppointment, currentWeek]);

  // Helper function to format time in 12-hour format
  const formatTimeDisplay = (hour: number) => {
    if (hour === 0) return '12:00 AM';
    if (hour === 12) return '12:00 PM';
    if (hour < 12) return `${hour}:00 AM`;
    return `${hour - 12}:00 PM`;
  };

  // Create rows: one for each visible hour
  const rows: GridRowsProp = useMemo(() => {
    return visibleHours.map((hour, index) => {
      const timeString = formatTimeDisplay(hour);
      const row: any = {
        id: index,
        time: timeString,
        hourValue: hour, // Keep the numeric hour for calculations
      };

      // Add empty data for each day column
      weekDates.forEach((_, dayIndex) => {
        row[`day_${dayIndex}`] = ''; // Empty cell data
      });

      return row;
    });
  }, [weekDates, visibleHours]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <Typography>Loading calendar...</Typography>
      </Box>
    );
  }

  return (
    <Box 
      sx={{ 
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      }}
      onClick={isMobile ? (e) => {
        // Clear cell selection when clicking outside of cells
        if (e.target === e.currentTarget) {
          setSelectedCell(null);
        }
      } : undefined}
    >
      {/* Integrated Calendar Header with All Controls */}
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between', 
        mb: 1,
        flexShrink: 0,
        py: isMobile ? 1 : 1.5,
        px: 1,
        borderBottom: '1px solid #e0e0e0',
        flexWrap: 'wrap',
        gap: isMobile ? 1 : 2
      }}>
        {/* Left Side: Week Navigation with Date Picker */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 'fit-content' }}>
          <DatePicker
            label={isMobile ? "Week" : "Week of"}
            value={selectedDate}
            onChange={(newValue) => newValue && onDateChange(newValue)}
            slotProps={{
              textField: {
                size: 'small',
                sx: { width: isMobile ? 100 : 140 }
              }
            }}
          />
          <IconButton onClick={goToPreviousWeek} size="small">
            <ChevronLeft />
          </IconButton>
          <Typography 
            variant="subtitle1" 
            sx={{ 
              minWidth: isMobile ? 120 : 160, 
              textAlign: 'center', 
              fontWeight: 600, 
              fontSize: isMobile ? '0.85rem' : '0.95rem'
            }}
          >
            {isMobile 
              ? `${format(currentWeek, 'MMM d')} - ${format(addDays(currentWeek, 6), 'MMM d')}`
              : `${format(currentWeek, 'MMM d')} - ${format(addDays(currentWeek, 6), 'MMM d, yyyy')}`
            }
          </Typography>
          <IconButton onClick={goToNextWeek} size="small">
            <ChevronRight />
          </IconButton>
        </Box>

        {/* Right Side: All Action Controls */}
        <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center', flexWrap: 'wrap' }}>
          {/* View Controls */}
          {onToggleTimeBlocks && (
            <Tooltip title={`${showTimeBlocks ? 'Hide' : 'Show'} Time Blocks`}>
              <IconButton
                onClick={onToggleTimeBlocks}
                color={showTimeBlocks ? 'primary' : 'default'}
                size="small"
              >
                {showTimeBlocks ? <Visibility fontSize="small" /> : <VisibilityOff fontSize="small" />}
              </IconButton>
            </Tooltip>
          )}
          
          {onToggleStudentsPanel && (
            <Tooltip title={isMobile ? "View Students" : "Toggle Students Panel"}>
              <IconButton
                onClick={() => {
                  if (isMobile) {
                    setMobileStudentsDrawerOpen(true);
                  } else {
                    onToggleStudentsPanel();
                  }
                }}
                color={showStudentsPanel ? 'primary' : 'default'}
                size="small"
              >
                <People fontSize="small" />
              </IconButton>
            </Tooltip>
          )}

          {/* Weekend Toggle */}
          <Tooltip title={
            showWeekends 
              ? "Hide weekends" 
              : weekendAppointments + weekendTimeBlocks > 0 
                ? `Show weekends (${weekendAppointments + weekendTimeBlocks} events)`
                : "Show weekends"
          }>
            <Badge 
              badgeContent={!showWeekends && (weekendAppointments + weekendTimeBlocks) > 0 ? weekendAppointments + weekendTimeBlocks : 0}
              color="warning"
              max={99}
            >
              <IconButton
                color={showWeekends ? 'primary' : 'default'}
                onClick={() => setShowWeekends(!showWeekends)}
                size="small"
              >
                {showWeekends ? <Weekend fontSize="small" /> : <WeekendOutlined fontSize="small" />}
              </IconButton>
            </Badge>
          </Tooltip>

          {/* Time Range Filter */}
          <Tooltip title="Set Time Range">
            <IconButton
              onClick={handleTimeRangeClick}
              size="small"
              color={isTimeRangeOpen ? 'primary' : 'default'}
            >
              <AccessTime fontSize="small" />
            </IconButton>
          </Tooltip>

          {/* Action Buttons */}
          {onRefresh && (
            <Tooltip title="Refresh">
              <IconButton onClick={onRefresh} size="small">
                <Refresh fontSize="small" />
              </IconButton>
            </Tooltip>
          )}

          <Button variant="outlined" onClick={goToToday} size="small">
            Today
          </Button>

          <Button variant="contained" startIcon={<Add />} size="small">
            NEW
          </Button>
        </Box>
      </Box>

      {/* Mobile interaction hint */}
      {isMobile && (
        <Box sx={{ 
          px: 1, 
          py: 0.5, 
          borderBottom: '1px solid #e0e0e0',
          backgroundColor: 'rgba(25, 118, 210, 0.05)'
        }}>
          <Typography 
            variant="caption" 
            color="text.secondary" 
            sx={{ 
              fontSize: '0.7rem',
              fontStyle: 'italic'
            }}
          >
            {selectedCell 
              ? "Tap again to schedule appointment or view details" 
              : "Tap a time slot to select, then tap again to schedule"
            }
          </Typography>
        </Box>
      )}

      {/* Calendar Grid with Students Panel Layout */}
      <Box sx={{ 
        display: 'flex', 
        gap: isMobile ? 0 : 2,
        flex: 1,
        overflow: 'hidden',
        minHeight: 0,
        position: 'relative'
      }}>
        {/* DataGrid Calendar */}
        <Box sx={{ 
          flex: 1, 
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column'
        }}>
          <DataGrid
            rows={rows}
            columns={columns}
            hideFooter
            disableRowSelectionOnClick
            disableColumnSelector
            disableColumnFilter
            disableColumnSorting
            disableDensitySelector
            disableColumnResize
            rowHeight={isMobile ? 60 : 80}
            autoHeight={false}
            sx={{
              border: 1,
              borderColor: 'divider',
              '& .MuiDataGrid-columnHeaders': {
                backgroundColor: '#f5f5f5',
                borderBottom: '2px solid #e0e0e0',
                fontSize: isMobile ? '0.75rem' : undefined
              },
              '& .MuiDataGrid-columnHeaderTitle': {
                fontWeight: 600,
                fontSize: isMobile ? '0.75rem' : undefined
              },
              '& .MuiDataGrid-cell': {
                border: '1px solid #e0e0e0',
                borderTop: 'none',
                borderLeft: 'none',
                fontSize: isMobile ? '0.75rem' : undefined,
                padding: isMobile ? '4px' : undefined,
                '&:last-child': {
                  borderRight: 'none'
                }
              },
              '& .MuiDataGrid-row': {
                borderBottom: '1px solid #e0e0e0',
                '&:last-child': {
                  borderBottom: 'none'
                }
              },
              '& .MuiDataGrid-virtualScroller': {
                // Allow horizontal scrolling on mobile if needed
                overflowX: isMobile ? 'auto' : 'hidden'
              },
              '& .MuiDataGrid-main': {
                // Allow horizontal scrolling on mobile if needed
                overflowX: isMobile ? 'auto' : 'hidden'
              }
            }}
          />
        </Box>

        {/* Students Panel - Hidden on mobile by default */}
        {showStudentsPanel && studentScheduleData && onQuickSchedule && (
          <Box sx={{ 
            flexShrink: 0,
            display: isMobile ? 'none' : 'block',
            width: isMobile ? 0 : 'auto'
          }}>
            <UnscheduledStudentsPanel
              studentScheduleData={studentScheduleData}
              schools={schools}
              teachers={teachers}
              onQuickSchedule={onQuickSchedule}
              loading={loading}
            />
          </Box>
        )}
      </Box>

      {/* Time Range Selection Popover */}
      <Popover
        open={isTimeRangeOpen}
        anchorEl={timeRangeAnchorEl}
        onClose={handleTimeRangeClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'center',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'center',
        }}
      >
        <Box sx={{ p: 3, minWidth: 300 }}>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <AccessTime />
            Time Range
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Set the visible hours in the calendar grid
          </Typography>
          
          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Start Time</InputLabel>
              <Select
                value={startHour}
                label="Start Time"
                onChange={(e) => setStartHour(e.target.value as number)}
              >
                {TIME_OPTIONS.filter(option => option.value < endHour).map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>End Time</InputLabel>
              <Select
                value={endHour}
                label="End Time"
                onChange={(e) => setEndHour(e.target.value as number)}
              >
                {TIME_OPTIONS.filter(option => option.value > startHour).map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>

          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="caption" color="text.secondary">
              Showing {visibleHours.length} hours ({formatTimeDisplay(startHour)} - {formatTimeDisplay(endHour)})
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                size="small"
                onClick={() => {
                  setStartHour(8);
                  setEndHour(15);
                }}
              >
                Reset
              </Button>
              <Button
                variant="contained"
                size="small"
                onClick={handleTimeRangeClose}
              >
                Apply
              </Button>
            </Box>
          </Box>
        </Box>
      </Popover>

      {/* Mobile Students Drawer */}
      {isMobile && (
        <Drawer
          anchor="right"
          open={mobileStudentsDrawerOpen}
          onClose={() => setMobileStudentsDrawerOpen(false)}
          PaperProps={{
            sx: {
              width: '85%',
              maxWidth: 400
            }
          }}
        >
          <Box sx={{ p: 2, height: '100%', overflow: 'auto' }}>
            <Box sx={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              mb: 2,
              pb: 1,
              borderBottom: '1px solid',
              borderColor: 'divider'
            }}>
              <Typography variant="h6" sx={{ fontSize: '1.1rem' }}>
                Students
              </Typography>
              <IconButton 
                onClick={() => setMobileStudentsDrawerOpen(false)}
                size="small"
              >
                <Close />
              </IconButton>
            </Box>
            
            {showStudentsPanel && studentScheduleData && onQuickSchedule && (
              <UnscheduledStudentsPanel
                studentScheduleData={studentScheduleData}
                schools={schools}
                teachers={teachers}
                onQuickSchedule={onQuickSchedule}
                loading={loading}
              />
            )}
          </Box>
        </Drawer>
      )}
    </Box>
  );
}
