import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  IconButton,
  Tabs,
  Tab
} from '@mui/material';
import { Close, TrackChanges, TrendingUp } from '@mui/icons-material';
import { GoalManagement } from './GoalManagement';
import { ProgressTracking } from './ProgressTracking';

interface StudentGoalsDialogProps {
  open: boolean;
  onClose: () => void;
  studentId: number;
  studentName: string;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`goals-tabpanel-${index}`}
      aria-labelledby={`goals-tab-${index}`}
    >
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  );
}

export function StudentGoalsDialog({ open, onClose, studentId, studentName }: StudentGoalsDialogProps) {
  const [currentTab, setCurrentTab] = useState(0);

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
  };

  return (
    <Dialog 
      open={open} 
      onClose={onClose} 
      maxWidth="lg" 
      fullWidth
      PaperProps={{
        sx: { 
          height: '90vh', 
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column'
        }
      }}
    >
      <DialogTitle sx={{ 
        bgcolor: '#40A8B6', 
        color: 'white', 
        py: 2,
        borderBottom: '1px solid rgba(0,0,0,0.12)'
      }}>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box display="flex" alignItems="center">
            <TrackChanges sx={{ mr: 1, color: 'white' }} />
            <Typography variant="h6" sx={{ color: 'white', fontWeight: 600 }}>
              IEP Goals - {studentName}
            </Typography>
          </Box>
          <IconButton 
            onClick={onClose} 
            size="small" 
            sx={{ 
              color: 'white',
              '&:hover': { 
                bgcolor: 'rgba(255,255,255,0.1)' 
              }
            }}
          >
            <Close />
          </IconButton>
        </Box>
      </DialogTitle>
      
      <DialogContent sx={{ p: 0, overflow: 'hidden', flex: 1, display: 'flex', flexDirection: 'column', bgcolor: '#fafafa' }}>
        <Box sx={{ 
          bgcolor: 'white',
          borderBottom: '2px solid #40A8B6', 
          flexShrink: 0,
          boxShadow: '0 2px 4px rgba(64,168,182,0.1)'
        }}>
          <Tabs 
            value={currentTab} 
            onChange={handleTabChange}
            sx={{
              '& .MuiTab-root': {
                textTransform: 'none',
                fontWeight: 500,
                minHeight: '56px'
              },
              '& .Mui-selected': {
                color: '#40A8B6 !important'
              },
              '& .MuiTabs-indicator': {
                backgroundColor: '#40A8B6',
                height: '3px'
              }
            }}
          >
            <Tab 
              label="Goals & Objectives" 
              icon={<TrackChanges sx={{ color: currentTab === 0 ? '#40A8B6' : 'inherit' }} />} 
              iconPosition="start"
              id="goals-tab-0"
              aria-controls="goals-tabpanel-0"
            />
            <Tab 
              label="Progress Overview" 
              icon={<TrendingUp sx={{ color: currentTab === 1 ? '#40A8B6' : 'inherit' }} />} 
              iconPosition="start"
              id="goals-tab-1"
              aria-controls="goals-tabpanel-1"
            />
          </Tabs>
        </Box>
        
        <Box sx={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
          <TabPanel value={currentTab} index={0}>
            <Box sx={{ p: 2, height: '100%' }}>
              <GoalManagement studentId={studentId} studentName={studentName} />
            </Box>
          </TabPanel>
          <TabPanel value={currentTab} index={1}>
            <Box sx={{ p: 3, textAlign: 'center', bgcolor: 'white', m: 2, borderRadius: 2, boxShadow: 1 }}>
              <TrendingUp sx={{ fontSize: 48, color: '#40A8B6', mb: 2 }} />
              <Typography variant="h6" sx={{ mb: 2, color: '#40A8B6', fontWeight: 600 }}>
                Progress Overview Coming Soon
              </Typography>
              <Typography color="text.secondary">
                This section will show comprehensive progress tracking across all goals and objectives.
              </Typography>
            </Box>
          </TabPanel>
        </Box>
      </DialogContent>
      
      <DialogActions sx={{ 
        flexShrink: 0, 
        bgcolor: '#f5f5f5', 
        borderTop: '1px solid #e0e0e0',
        px: 3,
        py: 2
      }}>
        <Button 
          onClick={onClose}
          variant="contained"
          sx={{
            bgcolor: '#40A8B6',
            '&:hover': {
              bgcolor: '#369aa6'
            },
            textTransform: 'none',
            fontWeight: 500,
            px: 3
          }}
        >
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
}
