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
import Chat from './features/chat/Chat';
import ConnectAuthorize from './features/connect/ConnectAuthorize';
import { readPendingConsent, CONSENT_PATH } from './lib/auth/pendingConsent';

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
  // The OAuth consent screen renders in BOTH states, like the login page: a
  // therapist arriving from Claude while signed out must see "sign in to
  // continue" rather than the spinner below, which never resolves for a
  // signed-out visitor and would strand the connector flow with no way out.
  const isOnConsentPage = currentPath === CONSENT_PATH;
  const isOnProtectedRoute = !isOnLoginPage && !isOnConsentPage && currentPath !== '/';
  
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

  // Read once per render; sessionStorage, and empty in every normal session.
  const pendingConsent = readPendingConsent();

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Routes>
        {/* Unauthenticated routes */}
        <Route path="/login" element={<Login />} />

        {/* The connector consent screen. Registered outside the authenticated
            block on purpose: it is entered from Claude, not from the app, and
            it handles the signed-out case itself (see ConnectAuthorize). */}
        <Route path={CONSENT_PATH} element={<ConnectAuthorize />} />
        
        {/* Authenticated routes */}
        {isAuthenticated ? (
          <>
            {/* Entra sends the browser back to the bare origin after
                sign-in, which loses the OAuth query string. If one was stashed
                on the way in, replay it instead of landing on the dashboard -
                otherwise the connector flow dies silently at the sign-in step. */}
            <Route
              path="/"
              element={
                pendingConsent ? (
                  <Navigate to={`${CONSENT_PATH}${pendingConsent}`} replace />
                ) : (
                  <Navigate to="/dashboard" replace />
                )
              }
            />
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
            <Route path="/chat" element={<AppShell><Chat /></AppShell>} />
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


