import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Grid,
  Alert,
  Divider
} from '@mui/material';
import { Save, Cancel } from '@mui/icons-material';
import type { GoalObjective } from '../../../lib/api/types/goals';

interface ProgressEntryFormProps {
  objective: GoalObjective;
  sessionDate: Date;
  existingProgress?: {
    objectiveId: number;
    progress: string;
    comments: string;
    sessionType: string;
  };
  onSave: (objectiveId: number, progress: string, comments: string, sessionType: string) => void;
  onCancel: () => void;
}

const PROGRESS_OPTIONS = [
  'Emerging',
  'Developing',
  'Secure',
  'Mastered',
  'Not Attempted',
  'Regression',
  'Maintained',
  'Improving'
];

const SESSION_TYPE_OPTIONS = [
  'Individual',
  'Group',
  'Push-in',
  'Pull-out',
  'Consultation',
  'Assessment',
  'Make-up Session'
];

export function ProgressEntryForm({ 
  objective, 
  sessionDate, 
  existingProgress, 
  onSave, 
  onCancel 
}: ProgressEntryFormProps) {
  const [formData, setFormData] = useState({
    progress: existingProgress?.progress || '',
    comments: existingProgress?.comments || '',
    sessionType: existingProgress?.sessionType || 'Individual'
  });

  const [error, setError] = useState<string>('');

  useEffect(() => {
    if (existingProgress) {
      setFormData({
        progress: existingProgress.progress,
        comments: existingProgress.comments,
        sessionType: existingProgress.sessionType
      });
    }
  }, [existingProgress]);

  const handleSubmit = () => {
    if (!formData.progress) {
      setError('Progress status is required');
      return;
    }

    onSave(objective.id, formData.progress, formData.comments, formData.sessionType);
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* Objective Info */}
      <Box sx={{ 
        bgcolor: '#f8fffe', 
        p: 3, 
        borderRadius: 2, 
        border: '1px solid #e8f4f5',
        mb: 3
      }}>
        <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600, mb: 2 }}>
          Objective {objective.objective_number}
        </Typography>
        <Typography variant="body2" sx={{ color: '#333', mb: 2 }}>
          {objective.objective_description}
        </Typography>
        <Box display="flex" gap={2}>
          <Typography variant="caption" color="text.secondary">
            <strong>Session Date:</strong> {sessionDate.toLocaleDateString()}
          </Typography>
          {objective.schedule_frequency && (
            <Typography variant="caption" color="text.secondary">
              <strong>Frequency:</strong> {objective.schedule_frequency}
            </Typography>
          )}
        </Box>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Form Fields */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <FormControl fullWidth required>
            <InputLabel>Progress Status</InputLabel>
            <Select
              value={formData.progress}
              onChange={(e) => setFormData({ ...formData, progress: e.target.value })}
              label="Progress Status"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            >
              {PROGRESS_OPTIONS.map((option) => (
                <MenuItem key={option} value={option}>
                  {option}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        <Grid item xs={12} md={6}>
          <FormControl fullWidth>
            <InputLabel>Session Type</InputLabel>
            <Select
              value={formData.sessionType}
              onChange={(e) => setFormData({ ...formData, sessionType: e.target.value })}
              label="Session Type"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            >
              {SESSION_TYPE_OPTIONS.map((option) => (
                <MenuItem key={option} value={option}>
                  {option}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            multiline
            rows={4}
            label="Progress Notes & Comments"
            value={formData.comments}
            onChange={(e) => setFormData({ ...formData, comments: e.target.value })}
            placeholder="Enter detailed notes about the student's performance, strategies used, observations, etc."
            sx={{
              '& .MuiOutlinedInput-root': {
                '&.Mui-focused fieldset': {
                  borderColor: '#40A8B6'
                }
              }
            }}
          />
        </Grid>
      </Grid>

      <Divider sx={{ my: 3, borderColor: '#e8f4f5' }} />

      {/* Action Buttons */}
      <Box display="flex" justifyContent="flex-end" gap={2}>
        <Button
          onClick={onCancel}
          startIcon={<Cancel />}
          sx={{ 
            textTransform: 'none',
            fontWeight: 500,
            color: '#666'
          }}
        >
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          startIcon={<Save />}
          disabled={!formData.progress}
          sx={{
            bgcolor: '#40A8B6',
            '&:hover': {
              bgcolor: '#369aa6'
            },
            '&:disabled': {
              bgcolor: '#e0e0e0'
            },
            textTransform: 'none',
            fontWeight: 500,
            px: 3
          }}
        >
          {existingProgress ? 'Update Progress' : 'Save Progress'}
        </Button>
      </Box>
    </Box>
  );
}
