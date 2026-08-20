import { Avatar, Box, Button, IconButton, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Menu, MenuItem, Tooltip, Typography } from '@mui/material';
import { Link, useLocation } from 'react-router-dom';
import { useMsal } from '@azure/msal-react';
import { useMemo, useState } from 'react';
import type { MouseEvent } from 'react';
import { 
  LayoutDashboard, 
  BarChart3,
  UsersRound, 
  Target,
  Stethoscope,
  Calendar, 
  GraduationCap, 
  UserSquare2,
  Settings,
  MessageSquare,
  Menu as MenuIcon,
} from 'lucide-react';

interface SidebarProps {
  open?: boolean;
  onNavigate?: () => void;
  onToggle?: () => void;
}

const navigationItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/therapy', label: 'Therapy', icon: Stethoscope },
  { path: '/chat', label: 'AI Chat', icon: MessageSquare },
  { path: '/schedule', label: 'Schedule', icon: Calendar },
  { path: '/students', label: 'Students', icon: UsersRound },
  { path: '/goals', label: 'Goals', icon: Target },
  { path: '/teachers', label: 'Support Staff', icon: UserSquare2 },
  { path: '/schools', label: 'Schools', icon: GraduationCap },
  { path: '/analytics', label: 'Analytics', icon: BarChart3 },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export function Sidebar({ open = true, onNavigate, onToggle }: SidebarProps) {
  const location = useLocation();
  const { instance } = useMsal();
  const account = useMemo(() => instance.getActiveAccount(), [instance]);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const isMenuOpen = Boolean(anchorEl);

  const onMenu = (e: MouseEvent<HTMLButtonElement>) => setAnchorEl(e.currentTarget);
  const onClose = () => setAnchorEl(null);

  const signOut = () => {
    instance.clearCache();
    window.location.href = '/login';
  };

  return (
    <Box
      sx={{
        width: open ? 240 : 64,
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
          p: open ? 2 : 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderBottom: 1,
          borderColor: 'divider',
          flexShrink: 0, // Prevent shrinking
          bgcolor: 'background.paper', // Ensure background
          minHeight: 84, // Consistent height regardless of state
        }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'center', width: '100%' }}>
          {open ? (
            <img
              src="/images/SLPro.png"
              alt="SLP Pro"
              style={{
                height: '60px',
                width: 'auto',
                maxWidth: '100%',
              }}
            />
          ) : (
            <Tooltip title="Expand sidebar" placement="right" arrow>
              <IconButton onClick={onToggle} aria-label="expand sidebar">
                <Box
                  sx={{
                    width: 32,
                    height: 32,
                    borderRadius: '6px',
                    bgcolor: 'primary.main',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'white',
                    fontWeight: 'bold',
                    fontSize: '1.2rem',
                  }}
                >
                  S
                </Box>
              </IconButton>
            </Tooltip>
          )}
        </Box>
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
            
            const buttonContent = (
              <ListItemButton
                component={Link}
                to={item.path}
                selected={isActive}
                onClick={() => onNavigate?.()}
                sx={{
                  minHeight: 48,
                  px: open ? 2.5 : 1.5,
                  justifyContent: open ? 'flex-start' : 'center',
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
                    mr: open ? 3 : 0,
                    color: isActive ? 'inherit' : 'text.secondary',
                    justifyContent: 'center',
                  }}
                >
                  <Icon size={20} />
                </ListItemIcon>
                {open && (
                  <ListItemText 
                    primary={item.label}
                    sx={{
                      opacity: 1,
                    }}
                  />
                )}
              </ListItemButton>
            );

            return (
              <ListItem key={item.path} disablePadding>
                {open ? (
                  buttonContent
                ) : (
                  <Tooltip title={item.label} placement="right" arrow>
                    {buttonContent}
                  </Tooltip>
                )}
              </ListItem>
            );
          })}
        </List>
      </Box>

      {onToggle && (
        <Box
          sx={{
            px: open ? 2 : 1,
            pb: 0.75,
            display: 'flex',
            justifyContent: open ? 'flex-start' : 'center',
            flexShrink: 0,
          }}
        >
          <Box
            sx={{ display: 'flex' }}
          >
            <Tooltip title={open ? 'Collapse sidebar' : 'Expand sidebar'} placement="right" arrow>
              <IconButton
                onClick={onToggle}
                aria-label={open ? 'collapse sidebar' : 'expand sidebar'}
                size="small"
              >
                <MenuIcon size={16} />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
      )}

      <Box
        sx={{
          p: open ? 2 : 1,
          borderTop: 1,
          borderColor: 'divider',
          flexShrink: 0,
        }}
      >
        {open ? (
          <Button
            onClick={onMenu}
            startIcon={<Avatar sx={{ width: 24, height: 24 }}>{(account?.name || '?').slice(0, 1)}</Avatar>}
            fullWidth
            sx={{ justifyContent: 'flex-start', textTransform: 'none', color: 'text.primary' }}
          >
            <Typography noWrap sx={{ maxWidth: 140 }}>
              {account?.name || account?.username || 'User'}
            </Typography>
          </Button>
        ) : (
          <Tooltip title={account?.name || account?.username || 'User'} placement="right" arrow>
            <IconButton onClick={onMenu} sx={{ width: '100%' }}>
              <Avatar sx={{ width: 28, height: 28 }}>{(account?.name || '?').slice(0, 1)}</Avatar>
            </IconButton>
          </Tooltip>
        )}
        <Menu anchorEl={anchorEl} open={isMenuOpen} onClose={onClose} anchorOrigin={{ vertical: 'top', horizontal: 'right' }}>
          <MenuItem onClick={() => { onClose(); signOut(); }}>Sign out</MenuItem>
        </Menu>
      </Box>
    </Box>
  );
}
