import { useEffect } from 'react';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import { InteractionStatus } from '@azure/msal-browser';
import { Button, Card, CardContent, Stack, Typography, Box, CircularProgress } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import { LoginLayout } from '../../layouts/LoginLayout';
import { appScopes } from '../../lib/auth/authConfig';

export default function Login() {
  const { instance, inProgress, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const navigate = useNavigate();
  const location = useLocation() as any;
  const from = location.state?.from?.pathname || "/dashboard";

  useEffect(() => {
    if (isAuthenticated && accounts.length > 0) {
      instance.setActiveAccount(accounts[0]);
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, accounts, from, instance, navigate]);

  const login = () => {
    instance.loginRedirect({ scopes: appScopes });
  };

  // If already authenticated, don't render login UI
  if (isAuthenticated) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress size={40} />
      </Box>
    );
  }

  return (
    <LoginLayout>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 64px)' }}>
        <Stack spacing={4} alignItems="center" sx={{ maxWidth: 500, width: '100%', px: 2 }}>
          <Stack spacing={2} alignItems="center">
            <Typography variant="h3" component="h1" className="font-bold">
              Welcome to SLP Pro
            </Typography>
            <Typography variant="h6" color="text.secondary" textAlign="center">
              Streamline your speech and language pathology practice with powerful tools for IEP management, student tracking, and progress monitoring.
            </Typography>
          </Stack>
          
          <Card variant="outlined" sx={{ maxWidth: 420, width: '100%' }}>
            <CardContent>
              <Stack spacing={2}>
                <Typography variant="h6">Sign in to continue</Typography>
                <Typography variant="body2" color="text.secondary">
                  Use your Microsoft account to access your SLP Pro workspace.
                </Typography>
                <Button 
                  variant="contained" 
                  size="large"
                  onClick={login} 
                  disabled={inProgress !== InteractionStatus.None}
                  sx={{ py: 1.5 }}
                >
                  Sign in with Microsoft
                </Button>
              </Stack>
            </CardContent>
          </Card>
        </Stack>
      </Box>
    </LoginLayout>
  );
}


