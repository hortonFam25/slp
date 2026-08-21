import { Box, Button, Card, CardContent, FormControlLabel, Stack, Switch, TextField, Typography } from '@mui/material';
import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Settings as SettingsIcon, Plug } from 'lucide-react';
import { useThemeStore } from '../../lib/stores/themeStore';

export default function Settings() {
  const [apiBaseUrl, setApiBaseUrl] = useState<string>(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');
  const mode = useThemeStore((s) => s.mode);
  const toggle = useThemeStore((s) => s.toggle);

  return (
    <Box sx={{ p: { xs: 1.5, sm: 2 }, height: '100%', minHeight: 0, overflow: 'auto' }}>
      <Stack spacing={2}>
        <Typography
          component="h1"
          sx={{
            display: 'flex',
            alignItems: 'center',
            color: '#41AAB7',
            fontWeight: 700,
            gap: 1.25,
            fontSize: { xs: '1.35rem', sm: '1.5rem' },
            lineHeight: 1.2,
            position: 'sticky',
            top: 0,
            zIndex: 2,
            bgcolor: 'background.default',
            py: 0.25,
          }}
        >
          <SettingsIcon size={24} />
          Settings
        </Typography>
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Plug size={20} />
              Connect Claude
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ my: 1 }}>
              Let Claude read and write your own caseload, and manage the connection keys that
              allow it.
            </Typography>
            <Button component={RouterLink} to="/settings/connect-claude" variant="outlined">
              Manage connection
            </Button>
          </CardContent>
        </Card>

        <Stack spacing={2}>
          <FormControlLabel
            control={<Switch checked={mode === 'dark'} onChange={toggle} />}
            label="Dark mode"
          />
          <TextField label="API Base URL" value={apiBaseUrl} onChange={(e) => setApiBaseUrl(e.target.value)} helperText="Set via VITE_API_BASE_URL" />
          <Button variant="outlined" onClick={() => navigator.clipboard.writeText(apiBaseUrl)}>Copy</Button>
        </Stack>
      </Stack>
    </Box>
  );
}


