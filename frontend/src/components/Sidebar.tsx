import { Box, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Typography } from '@mui/material';
import { Link, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  BarChart3,
  UsersRound, 
  Target,
  Stethoscope,
  Calendar, 
  GraduationCap, 
  UserSquare2,
  Settings 
} from 'lucide-react';

interface SidebarProps {
  open?: boolean;
  onNavigate?: () => void;
}

const navigationItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/students', label: 'Students', icon: UsersRound },
  { path: '/goals', label: 'Goals', icon: Target },
  { path: '/therapy', label: 'Therapy', icon: Stethoscope },
  { path: '/schedule', label: 'Schedule', icon: Calendar },
  { path: '/schools', label: 'Schools', icon: GraduationCap },
  { path: '/teachers', label: 'Teachers', icon: UserSquare2 },
  { path: '/settings', label: 'Settings', icon: Settings },
  { path: '/analytics', label: 'Analytics', icon: BarChart3 },
];

export function Sidebar({ open = true, onNavigate }: SidebarProps) {
  const location = useLocation();

  return (
    <Box
      sx={{
        width: open ? 240 : 0,
        flexShrink: 0,
        transition: 'width 0.3s ease',
        overflow: 'hidden',
        borderRight: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh' // Full viewport height
      }}
    >
      {/* Sticky Logo Section */}
      <Box
        sx={{
          p: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderBottom: 1,
          borderColor: 'divider',
          flexShrink: 0, // Prevent shrinking
          bgcolor: 'background.paper', // Ensure background
        }}
      >
        <img
          src="/images/SLPro.png"
          alt="SLP Pro"
          style={{
            height: '60px',
            width: 'auto',
            maxWidth: '100%',
          }}
        />
      </Box>
      
      {/* Scrollable Navigation */}
      <Box sx={{ 
        flex: 1, 
        overflow: 'auto', // Independent scrolling for navigation
        minHeight: 0 // Allow shrinking
      }}>
        <List sx={{ pt: 0 }}>
          {navigationItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            
            return (
              <ListItem key={item.path} disablePadding>
                <ListItemButton
                  component={Link}
                  to={item.path}
                  selected={isActive}
                  onClick={() => onNavigate?.()}
                  sx={{
                    minHeight: 48,
                    px: 2.5,
                    '&.Mui-selected': {
                      bgcolor: '#40A8B6',
                      color: 'white',
                      '&:hover': {
                        bgcolor: '#369aa6',
                      },
                    },
                  }}
                >
                  <ListItemIcon
                    sx={{
                      minWidth: 0,
                      mr: 3,
                      color: isActive ? 'inherit' : 'text.secondary',
                    }}
                  >
                    <Icon size={20} />
                  </ListItemIcon>
                  <ListItemText 
                    primary={item.label}
                    sx={{
                      opacity: open ? 1 : 0,
                      transition: 'opacity 0.3s ease',
                    }}
                  />
                </ListItemButton>
              </ListItem>
            );
          })}
        </List>
      </Box>
    </Box>
  );
}
