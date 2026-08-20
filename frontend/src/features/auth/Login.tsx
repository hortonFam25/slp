import { useEffect } from 'react';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import { InteractionStatus } from '@azure/msal-browser';
import { Button, Stack, Typography, Box, CircularProgress, useTheme, useMediaQuery } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import { appScopes } from '../../lib/auth/authConfig';
import { Brain, Sparkles, Activity, CheckCircle } from 'lucide-react';

export default function Login() {
  const { instance, inProgress, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const navigate = useNavigate();
  const location = useLocation() as any;
  const from = location.state?.from?.pathname || "/dashboard";
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  useEffect(() => {
    if (isAuthenticated && accounts.length > 0) {
      instance.setActiveAccount(accounts[0]);
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, accounts, from, instance, navigate]);

  const login = () => {
    instance.loginRedirect({ scopes: appScopes });
  };

  if (isAuthenticated) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh" bgcolor="background.default">
        <CircularProgress size={40} sx={{ color: '#41AAB7' }} />
      </Box>
    );
  }

  const features = [
    { label: 'Smart IEP Management', icon: <Sparkles size={20} /> },
    { label: 'Real-time Progress Tracking', icon: <Activity size={20} /> },
    { label: 'Automated Reporting', icon: <CheckCircle size={20} /> },
  ];

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', bgcolor: 'background.default' }}>
      {/* Left Panel - Branding & Creative */}
      {!isMobile && (
        <Box
          sx={{
            flex: 1,
            position: 'relative',
            background: 'linear-gradient(135deg, #2D8E9E 0%, #41AAB7 100%)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            p: 8,
            overflow: 'hidden',
            color: 'white',
          }}
        >
          {/* Abstract Background Shapes */}
          <Box
            sx={{
              position: 'absolute',
              top: '-10%',
              right: '-10%',
              width: '600px',
              height: '600px',
              background: 'radial-gradient(circle, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0) 70%)',
              borderRadius: '50%',
              pointerEvents: 'none',
            }}
          />
          <Box
            sx={{
              position: 'absolute',
              bottom: '-15%',
              left: '-15%',
              width: '500px',
              height: '500px',
              background: 'radial-gradient(circle, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0) 60%)',
              borderRadius: '50%',
              pointerEvents: 'none',
            }}
          />
          
          <Stack spacing={6} sx={{ position: 'relative', zIndex: 1, maxWidth: 600 }}>
            <Box>
              <Box 
                sx={{ 
                  display: 'inline-flex', 
                  p: 2, 
                  bgcolor: 'rgba(255,255,255,0.15)', 
                  borderRadius: 4,
                  backdropFilter: 'blur(10px)',
                  mb: 4,
                  boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.1)',
                  border: '1px solid rgba(255,255,255,0.2)'
                }}
              >
                <Brain size={48} color="white" strokeWidth={1.5} />
              </Box>
              <Typography variant="h2" fontWeight="800" sx={{ letterSpacing: '-0.02em', mb: 3, lineHeight: 1.1 }}>
                Welcome to<br/>SLP Pro
              </Typography>
              <Typography variant="h5" sx={{ opacity: 0.9, fontWeight: 400, lineHeight: 1.6 }}>
                Streamline your speech and language pathology practice with powerful AI tools.
              </Typography>
            </Box>

            {/* Feature Highlights */}
            <Stack spacing={3}>
              {features.map((item, index) => (
                <Box key={index} sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Box sx={{ 
                    p: 1, 
                    bgcolor: 'rgba(255,255,255,0.2)', 
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    {item.icon}
                  </Box>
                  <Typography variant="h6" fontWeight="500" sx={{ opacity: 0.95 }}>
                    {item.label}
                  </Typography>
                </Box>
              ))}
            </Stack>
          </Stack>
        </Box>
      )}

      {/* Right Panel - Login Form */}
      <Box
        sx={{
          flex: isMobile ? 1 : '0 0 600px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          p: 4,
          bgcolor: 'background.paper',
          position: 'relative',
          boxShadow: isMobile ? 'none' : '-10px 0 30px rgba(0,0,0,0.02)'
        }}
      >
        <Stack spacing={5} sx={{ width: '100%', maxWidth: 420 }}>
            {isMobile && (
                 <Stack direction="row" alignItems="center" gap={2} mb={2}>
                    <Box sx={{ p: 1.5, bgcolor: 'rgba(65, 170, 183, 0.15)', borderRadius: 3, color: '#41AAB7' }}>
                        <Brain size={32} color="#41AAB7" />
                    </Box>
                     <Typography variant="h4" fontWeight="bold" color="text.primary">SLP Pro</Typography>
                </Stack>
            )}
            
            <Box>
                <Typography variant="h4" fontWeight="800" color="text.primary" gutterBottom sx={{ letterSpacing: '-0.01em' }}>
                    Sign in
                </Typography>
                <Typography variant="body1" color="text.secondary">
                    Welcome back! Please enter your details.
                </Typography>
            </Box>

            <Button
                variant="outlined"
                fullWidth
                size="large"
                onClick={login}
                disabled={inProgress !== InteractionStatus.None}
                startIcon={
                    <Box component="img" 
                        src="https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg" 
                        alt="Microsoft" 
                        sx={{ width: 20, height: 20, mr: 1 }} 
                    />
                }
                sx={{
                    py: 1.5,
                    height: 56,
                    borderColor: 'divider',
                    color: 'text.primary',
                    textTransform: 'none',
                    fontSize: '1rem',
                    fontWeight: 600,
                    borderRadius: 2,
                    borderWidth: '1px',
                    transition: 'all 0.2s',
                    '&:hover': {
                        bgcolor: 'action.hover',
                        borderColor: 'text.primary',
                        borderWidth: '1px',
                        transform: 'translateY(-1px)',
                        boxShadow: '0 4px 12px rgba(0,0,0,0.05)'
                    }
                }}
            >
                Sign in with Microsoft
            </Button>
            
            <Box sx={{ pt: 2 }}>
                <Typography variant="body2" color="text.secondary" align="center" sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                   New here? <Box component="span" sx={{ color: 'primary.main', fontWeight: 600, cursor: 'pointer' }}>Contact support</Box>
                </Typography>
            </Box>

            <Box sx={{ mt: 'auto', pt: 8 }}>
                <Typography variant="caption" color="text.disabled" align="center" display="block">
                    © {new Date().getFullYear()} SLP Pro. All rights reserved.
                </Typography>
            </Box>
        </Stack>
      </Box>
    </Box>
  );
}
