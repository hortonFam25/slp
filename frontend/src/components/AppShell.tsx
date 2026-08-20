import { Box, Drawer, IconButton, useMediaQuery, useTheme } from '@mui/material';
import { Menu as MenuIcon } from 'lucide-react';
import { useState } from 'react';
import type { PropsWithChildren } from 'react';
import { Sidebar } from './Sidebar';

// AppShell is ONLY for authenticated users - no auth checks needed here
export function AppShell({ children }: PropsWithChildren) {
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
  return (
    <Box sx={{ 
      display: 'flex', 
      height: '100vh', 
      overflow: 'hidden' // Prevent viewport scrolling
    }}>
      {/* Desktop Sidebar - Always shown but collapsible */}
      {!isMobile && <Sidebar open={sidebarOpen} onToggle={handleSidebarToggle} />}
      
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
        {/* Scrollable Content Area */}
        <Box sx={{ 
          flex: 1, 
          overflow: 'hidden', // Pages manage their own scrolling
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
        }}>
          {isMobile && (
            <IconButton
              onClick={handleDrawerToggle}
              aria-label="open drawer"
              sx={{
                position: 'absolute',
                top: 8,
                left: 8,
                zIndex: 2,
                bgcolor: 'background.paper',
                border: 1,
                borderColor: 'divider',
                '&:hover': { bgcolor: 'action.hover' },
              }}
            >
              <MenuIcon size={22} />
            </IconButton>
          )}
          <Box sx={{ 
            px: isMobile ? 0 : 1.5, // No padding on mobile, smaller padding on desktop
            py: isMobile ? 0 : 1.5, // No padding on mobile
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0, // Important: allows flex children to shrink
            maxWidth: 'none', // Remove container width restrictions
            pt: isMobile ? 6 : 1.5,
          }}>
            {children}
          </Box>
        </Box>
      </Box>
    </Box>
  );
}


