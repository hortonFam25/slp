import React from 'react';
import { Card, CardContent, Grid, Typography, Box, CircularProgress, useMediaQuery, useTheme } from '@mui/material';
import { 
  UsersRound, 
  Calendar, 
  CheckCircle 
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { studentsApi } from '../../lib/api/students';
import { schedulingApi } from '../../lib/api/scheduling';
import { therapySessionsApi } from '../../lib/api/therapySessions';
import { BarChart3 } from 'lucide-react';

interface KPICardProps {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  loading?: boolean;
  subtitle?: string;
  color?: string;
}

function KPICard({ title, value, icon, loading, subtitle, color = '#40A8B6' }: KPICardProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  return (
    <Card sx={{
      bgcolor: 'white',
      borderRadius: 1.5,
      boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
      border: '1px solid #e0e0e0',
      height: '100%',
      minHeight: isMobile ? '70px' : '80px',
      '&:hover': {
        boxShadow: '0 2px 6px rgba(64,168,182,0.12)',
        borderColor: '#40A8B6'
      },
      transition: 'all 0.2s ease-in-out'
    }}>
      <CardContent sx={{ 
        p: isMobile ? 1.25 : 1.5, 
        '&:last-child': { pb: isMobile ? 1.25 : 1.5 } 
      }}>
        <Box display="flex" alignItems="center" justifyContent="between">
          <Box flex={1} sx={{ minWidth: 0 }}>
            <Typography variant="caption" color="text.secondary" sx={{ 
              fontWeight: 500, 
              fontSize: isMobile ? '0.6rem' : '0.65rem',
              mb: isMobile ? 0.15 : 0.25, 
              display: 'block',
              textTransform: 'uppercase',
              letterSpacing: '0.5px'
            }}>
              {title}
            </Typography>
            {loading ? (
              <CircularProgress size={isMobile ? 14 : 16} sx={{ color }} />
            ) : (
              <Typography variant="h6" sx={{ 
                fontWeight: 700, 
                color: '#333', 
                lineHeight: 1,
                fontSize: isMobile ? '1.25rem' : '1.5rem'
              }}>
                {value}
              </Typography>
            )}
            {subtitle && (
              <Typography variant="caption" color="text.secondary" sx={{ 
                fontSize: isMobile ? '0.55rem' : '0.6rem',
                lineHeight: 1,
                mt: isMobile ? 0.15 : 0.25,
                display: 'block'
              }}>
                {subtitle}
              </Typography>
            )}
          </Box>
          <Box sx={{ 
            color,
            display: 'flex',
            alignItems: 'center',
            ml: 1
          }}>
            {React.cloneElement(icon as React.ReactElement, { 
              size: isMobile ? 16 : 20 
            })}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

export default function Analytics() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  
  // Fetch data for KPIs
  const { data: students = [], isLoading: studentsLoading } = useQuery({
    queryKey: ['students'],
    queryFn: studentsApi.getStudents
  });

  const today = new Date().toISOString().split('T')[0];
  
  const { data: todayAppointments = [], isLoading: appointmentsLoading } = useQuery({
    queryKey: ['appointments', today],
    queryFn: () => schedulingApi.getAppointments({
      startDate: today,
      endDate: today
    })
  });

  const { data: recentSessions = [], isLoading: sessionsLoading } = useQuery({
    queryKey: ['recent-sessions'],
    queryFn: () => therapySessionsApi.getTherapySessions({
      limit: 50,
      orderBy: 'desc'
    })
  });

  const activeStudents = students.filter(student => !student.is_archived);
  const completedSessionsToday = recentSessions.filter(session => 
    session.session_date === today && session.status === 'completed'
  );

  return (
    <Box sx={{ 
      flex: 1, 
      p: 3,
      bgcolor: '#fafafa',
      minHeight: '100vh'
    }}>
      {/* Page Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" sx={{ 
          fontWeight: 700, 
          color: '#41AAB7',
          display: 'flex',
          alignItems: 'center',
          gap: 2
        }}>
          <BarChart3 size={32} />
          Analytics
        </Typography>
      </Box>

      {/* KPI Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={4}>
          <KPICard
            title="Active Students"
            value={activeStudents.length}
            icon={<UsersRound />}
            loading={studentsLoading}
            subtitle={`${students.length} total students`}
            color="#40A8B6"
          />
        </Grid>
        
        <Grid item xs={12} sm={6} md={4}>
          <KPICard
            title="Today's Sessions"
            value={todayAppointments.length}
            icon={<Calendar />}
            loading={appointmentsLoading}
            subtitle="Scheduled appointments"
            color="#66BB6A"
          />
        </Grid>
        
        <Grid item xs={12} sm={6} md={4}>
          <KPICard
            title="Completed Today"
            value={completedSessionsToday.length}
            icon={<CheckCircle />}
            loading={sessionsLoading}
            subtitle="Therapy sessions"
            color="#42A5F5"
          />
        </Grid>
      </Grid>

      {/* Placeholder for future analytics */}
      <Card sx={{ mt: 3 }}>
        <CardContent sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary" sx={{ mb: 2 }}>
            More Analytics Coming Soon
          </Typography>
          <Typography variant="body2" color="text.secondary">
            This page will be expanded with charts, reports, and detailed analytics.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
}
