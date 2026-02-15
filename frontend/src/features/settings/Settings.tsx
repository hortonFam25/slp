import { Button, Stack, TextField, Typography } from '@mui/material';
import { useState } from 'react';
import { Settings as SettingsIcon } from 'lucide-react';

export default function Settings() {
  const [apiBaseUrl, setApiBaseUrl] = useState<string>(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');
  return (
    <Stack spacing={3}>
      <Typography variant="h4" sx={{
        display: 'flex',
        alignItems: 'center',
        color: '#41AAB7',
        fontWeight: 700,
        gap: 2
      }}>
        <SettingsIcon size={32} />
        Settings
      </Typography>
      <Stack spacing={2}>
        <TextField label="API Base URL" value={apiBaseUrl} onChange={(e) => setApiBaseUrl(e.target.value)} helperText="Set via VITE_API_BASE_URL" />
        <Button variant="outlined" onClick={() => navigator.clipboard.writeText(apiBaseUrl)}>Copy</Button>
      </Stack>
    </Stack>
  );
}


