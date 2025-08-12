import React, { useMemo } from 'react';
import { Route, Routes, Navigate } from 'react-router-dom';
import { CssBaseline, ThemeProvider, createTheme, CircularProgress, Box } from '@mui/material';
import { AppShell } from './components/AppShell';
import { useThemeStore } from './lib/stores/themeStore';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import { InteractionStatus } from '@azure/msal-browser';

// Import components directly (no lazy loading to eliminate timing issues)
import Dashboard from './features/dashboard/Dashboard';
import Analytics from './features/analytics/Analytics';
import Students from './features/students/Students';
import Goals from './features/goals/Goals';
import Therapy from './features/therapy/Therapy';
import { TherapySessionInterface } from './features/therapy/TherapySessionInterface';
import Schedule from './features/schedule/Schedule';
import Schools from './features/schools/Schools';
import Teachers from './features/teachers/Teachers';
import Settings from './features/settings/Settings';
import Login from './features/auth/Login';

export default function App() {
  const mode = useThemeStore((s) => s.mode);
  const { inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();

  const theme = useMemo(
    () =>
      createTheme({
        palette: { mode },
        shape: { borderRadius: 10 },
      }),
    [mode]
  );

  // Show loading screen during MSAL initialization AND while processing redirects
  // This prevents the flash of login page during auth callback processing
  if (inProgress !== InteractionStatus.None) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
          <CircularProgress size={40} />
        </Box>
      </ThemeProvider>
    );
  }

  // Additional check: if we're on a protected route but not authenticated yet,
  // and we're not on the login page, show loading (might be processing redirect)
  const currentPath = window.location.pathname;
  const isOnLoginPage = currentPath === '/login';
  const isOnProtectedRoute = !isOnLoginPage && currentPath !== '/';
  
  if (!isAuthenticated && isOnProtectedRoute) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
          <CircularProgress size={40} />
        </Box>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Routes>
        {/* Unauthenticated routes */}
        <Route path="/login" element={<Login />} />
        
        {/* Authenticated routes */}
        {isAuthenticated ? (
          <>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<AppShell><Dashboard /></AppShell>} />
            <Route path="/analytics" element={<AppShell><Analytics /></AppShell>} />
            <Route path="/students" element={<AppShell><Students /></AppShell>} />
            <Route path="/goals" element={<AppShell><Goals /></AppShell>} />
            <Route path="/therapy" element={<AppShell><Therapy /></AppShell>} />
            <Route path="/therapy/session/:sessionId" element={<TherapySessionInterface />} />
            <Route path="/schedule" element={<AppShell><Schedule /></AppShell>} />
            <Route path="/schools" element={<AppShell><Schools /></AppShell>} />
            <Route path="/teachers" element={<AppShell><Teachers /></AppShell>} />
            <Route path="/settings" element={<AppShell><Settings /></AppShell>} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </>
        ) : (
          <>
            <Route path="*" element={<Navigate to="/login" replace />} />
          </>
        )}
      </Routes>
    </ThemeProvider>
  );
}


