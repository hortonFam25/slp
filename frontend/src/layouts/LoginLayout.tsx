import { PropsWithChildren } from 'react';
import { Box, AppBar, Toolbar, Typography, IconButton } from '@mui/material';
import { Moon, Sun } from 'lucide-react';
import { useThemeStore } from '@/lib/stores/themeStore';

export function LoginLayout({ children }: PropsWithChildren) {
  const mode = useThemeStore((s) => s.mode);
  const toggle = useThemeStore((s) => s.toggle);

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar position="static" color="transparent" elevation={0}>
        <Toolbar>
          <Typography variant="h6" className="font-semibold">SLP Pro</Typography>
          <div className="flex-1" />
          <IconButton onClick={toggle} size="small" aria-label="Toggle theme">
            {mode === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </IconButton>
        </Toolbar>
      </AppBar>
      {children}
    </Box>
  );
}
