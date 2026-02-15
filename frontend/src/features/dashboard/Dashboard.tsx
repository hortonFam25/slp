import React, { useState } from 'react';
import { Card, CardContent, Grid, Typography, Box, useMediaQuery, useTheme, Drawer, IconButton } from '@mui/material';
import { Close } from '@mui/icons-material';
import { LayoutDashboard } from 'lucide-react';
import { AppointmentSummary } from '../../lib/api/scheduling';
import { DailyScheduleView } from './components/DailyScheduleView';
import { AppointmentPreSessionPlanner } from './components/AppointmentPreSessionPlanner';

export default function Dashboard() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [selectedAppointment, setSelectedAppointment] = useState<AppointmentSummary | null>(null);

  return (
    <Box sx={{ 
      flex: 1, 
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    }}>
      {/* Page Header */}
      <Box sx={{ 
        p: 3, 
        pb: 2,
        backgroundColor: 'background.default',
        borderBottom: '1px solid',
        borderColor: 'divider'
      }}>
        <Typography variant="h4" sx={{ 
          fontWeight: 700, 
          color: '#41AAB7',
          display: 'flex',
          alignItems: 'center',
          gap: 2
        }}>
          <LayoutDashboard size={32} />
          Dashboard
        </Typography>
      </Box>

      {/* Main Content */}
      <Box sx={{ flex: 1, overflow: 'hidden' }}>
        {isMobile ? (
          // Mobile Layout - Full width calendar with drawer overlay
          <Box sx={{ height: '100%', p: 3, pt: 2 }}>
            <DailyScheduleView onAppointmentSelect={setSelectedAppointment} />
            
            {/* Mobile Drawer Overlay */}
            <Drawer
              anchor="right"
              open={!!selectedAppointment}
              onClose={() => setSelectedAppointment(null)}
              variant="temporary"
              sx={{
                '& .MuiDrawer-paper': {
                  width: '100vw',
                  maxWidth: '100vw',
                  height: '100vh',
                  boxSizing: 'border-box',
                  display: 'flex',
                  flexDirection: 'column'
                },
                '& .MuiBackdrop-root': {
                  backgroundColor: 'rgba(0, 0, 0, 0.3)',
                },
              }}
              SlideProps={{
                direction: 'left'
              }}
            >
              {/* Mobile Header */}
              <Box sx={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between',
                p: 2,
                borderBottom: '1px solid',
                borderColor: 'divider',
                backgroundColor: 'background.default'
              }}>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  Session Planning
                </Typography>
                <IconButton 
                  onClick={() => setSelectedAppointment(null)}
                  size="small"
                  sx={{ 
                    backgroundColor: 'action.hover',
                    '&:hover': { backgroundColor: 'action.selected' }
                  }}
                >
                  <Close />
                </IconButton>
              </Box>
              
              {/* Mobile Content */}
              <Box sx={{ 
                flex: 1, 
                overflow: 'auto',
                p: 2,
                '&::-webkit-scrollbar': {
                  width: '6px',
                },
                '&::-webkit-scrollbar-track': {
                  background: '#f1f1f1',
                  borderRadius: '3px',
                },
                '&::-webkit-scrollbar-thumb': {
                  background: '#c1c1c1',
                  borderRadius: '3px',
                  '&:hover': {
                    background: '#a8a8a8',
                  },
                },
              }}>
                <AppointmentPreSessionPlanner
                  selectedAppointment={selectedAppointment}
                  onClear={() => setSelectedAppointment(null)}
                />
              </Box>
            </Drawer>
          </Box>
        ) : (
          // Desktop Layout - Side by side
          <Grid container spacing={3} sx={{ height: '100%', p: 3, pt: 2 }}>
            {/* Daily Calendar */}
            <Grid item xs={12} lg={6} sx={{ height: '100%' }}>
              <DailyScheduleView onAppointmentSelect={setSelectedAppointment} />
            </Grid>
            
            {/* Session Planning Panel */}
            <Grid item xs={12} lg={6} sx={{ height: '100%' }}>
              <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardContent sx={{ p: 3, pb: 1, flexShrink: 0 }}>
                  <Typography variant="h6" sx={{ mb: 0 }}>
                    {selectedAppointment ? 'Session Planning' : 'Quick Actions'}
                  </Typography>
                </CardContent>
                
                <Box sx={{
                  flex: 1,
                  overflow: 'auto',
                  px: 3,
                  pt: 0,
                  pb: 3,
                  '&::-webkit-scrollbar': {
                    width: '6px',
                  },
                  '&::-webkit-scrollbar-track': {
                    background: '#f1f1f1',
                    borderRadius: '3px',
                  },
                  '&::-webkit-scrollbar-thumb': {
                    background: '#c1c1c1',
                    borderRadius: '3px',
                    '&:hover': {
                      background: '#a8a8a8',
                    },
                  },
                }}>
                  <AppointmentPreSessionPlanner
                    selectedAppointment={selectedAppointment}
                    onClear={() => setSelectedAppointment(null)}
                  />
                </Box>
              </Card>
            </Grid>
          </Grid>
        )}
      </Box>
    </Box>
  );
}