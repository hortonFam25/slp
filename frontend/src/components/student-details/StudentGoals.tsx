import React from 'react';
import {
  Box,
  useMediaQuery,
  useTheme
} from '@mui/material';
import { GoalManagement } from '../GoalManagement';

interface StudentGoalsProps {
  studentId: number;
  studentName?: string;
}

export function StudentGoals({ studentId, studentName }: StudentGoalsProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  return (
    <Box sx={{ 
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      minHeight: 0
    }}>
      <GoalManagement 
        studentId={studentId} 
        studentName={studentName}
      />
    </Box>
  );
}