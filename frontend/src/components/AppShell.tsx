import { AppBar, Box, Container, IconButton, Toolbar, Typography, Button, Avatar, Menu, MenuItem, Drawer, useMediaQuery, useTheme } from '@mui/material';
import { Moon, Sun, Menu as MenuIcon } from 'lucide-react';
import { useThemeStore } from '@/lib/stores/themeStore';
import { useMsal } from '@azure/msal-react';
import { useMemo, useState } from 'react';
import type { PropsWithChildren, MouseEvent } from 'react';
import { Sidebar } from './Sidebar';

// AppShell is ONLY for authenticated users - no auth checks needed here
export function AppShell({ children }: PropsWithChildren) {
  const mode = useThemeStore((s) => s.mode);
  const toggle = useThemeStore((s) => s.toggle);
  const { instance } = useMsal();
  const account = useMemo(() => instance.getActiveAccount(), [instance]);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);
  const onMenu = (e: MouseEvent<HTMLButtonElement>) => setAnchorEl(e.currentTarget);
  const onClose = () => setAnchorEl(null);
  
  // Mobile responsive setup
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  
  const handleDrawerToggle = () => {
    setMobileDrawerOpen(!mobileDrawerOpen);
  };

  const handleSidebarToggle = () => {
    setSidebarOpen(!sidebarOpen);
  };
  const signOut = () => {
    // Clear local session without Microsoft redirect
    instance.clearCache();
    window.location.href = '/login';
  };
  
  return (
    <Box sx={{ 
      display: 'flex', 
      height: '100vh', 
      overflow: 'hidden' // Prevent viewport scrolling
    }}>
      {/* Desktop Sidebar - Always shown but collapsible */}
      {!isMobile && <Sidebar open={sidebarOpen} />}
      
      {/* Mobile Drawer */}
      {isMobile && (
        <Drawer
          variant="temporary"
          open={mobileDrawerOpen}
          onClose={handleDrawerToggle}
          ModalProps={{
            keepMounted: true, // Better open performance on mobile
          }}
          sx={{
            '& .MuiDrawer-paper': {
              width: 240,
              boxSizing: 'border-box',
            },
          }}
        >
          <Sidebar onNavigate={() => setMobileDrawerOpen(false)} />
        </Drawer>
      )}
      
      {/* Main Content Area */}
      <Box sx={{ 
        display: 'flex', 
        flexDirection: 'column', 
        flex: 1,
        overflow: 'hidden' // Prevent main area from scrolling
      }}>
        {/* Sticky Header */}
        <AppBar position="static" color="transparent" elevation={0} sx={{ flexShrink: 0 }}>
          <Toolbar className="flex items-center gap-4">
            {/* Hamburger Menu Button - Always shown */}
            <IconButton
              edge="start"
              onClick={isMobile ? handleDrawerToggle : handleSidebarToggle}
              aria-label={isMobile ? "open drawer" : "toggle sidebar"}
              sx={{ mr: 2 }}
            >
              <MenuIcon size={24} />
            </IconButton>
            

            <div className="flex-1" />
            <IconButton onClick={toggle} size="small" aria-label="Toggle theme">
              {mode === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            </IconButton>
            <Button onClick={onMenu} startIcon={<Avatar sx={{ width: 24, height: 24 }}>{(account?.name || '?').slice(0,1)}</Avatar>} sx={{ textTransform: 'none' }}>
              {account?.name || account?.username || 'User'}
            </Button>
            <Menu anchorEl={anchorEl} open={open} onClose={onClose} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}>
              <MenuItem onClick={() => { onClose(); signOut(); }}>Sign out</MenuItem>
            </Menu>
          </Toolbar>
        </AppBar>
        
        {/* Scrollable Content Area */}
        <Box sx={{ 
          flex: 1, 
          overflow: 'auto', // Allow this area to scroll
          display: 'flex',
          flexDirection: 'column'
        }}>
          <Box sx={{ 
            px: isMobile ? 0 : 1.5, // No padding on mobile, smaller padding on desktop
            py: isMobile ? 0 : 1.5, // No padding on mobile
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0, // Important: allows flex children to shrink
            maxWidth: 'none' // Remove container width restrictions
          }}>
            {children}
          </Box>
        </Box>
      </Box>
    </Box>
  );
}


