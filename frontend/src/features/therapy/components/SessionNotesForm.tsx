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
  Card,
  CardContent,
  Divider,
  Alert,
  useMediaQuery,
  useTheme
} from '@mui/material';
import {
  Save,
  Notes,
  Visibility,
  Psychology,
  School,
  Star
} from '@mui/icons-material';
import type { TherapySession } from '../../../lib/api/therapySessions';

interface SessionNotesFormProps {
  session: TherapySession;
  onSave: (notes: any) => void;
  disabled?: boolean;
}

const ENGAGEMENT_LEVELS = ['high', 'medium', 'low', 'variable'];
const SESSION_QUALITY_OPTIONS = ['excellent', 'good', 'fair', 'poor'];

export function SessionNotesForm({
  session,
  onSave,
  disabled = false
}: SessionNotesFormProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [formData, setFormData] = useState({
    session_notes: session.session_notes || '',
    therapist_observations: session.therapist_observations || '',
    student_engagement: session.student_engagement || '',
    materials_used: session.materials_used || '',
    session_quality: session.session_quality || '',
    follow_up_needed: session.follow_up_needed || false,
    follow_up_notes: session.follow_up_notes || ''
  });

  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    const hasFormChanges = 
      formData.session_notes !== (session.session_notes || '') ||
      formData.therapist_observations !== (session.therapist_observations || '') ||
      formData.student_engagement !== (session.student_engagement || '') ||
      formData.materials_used !== (session.materials_used || '') ||
      formData.session_quality !== (session.session_quality || '') ||
      formData.follow_up_needed !== (session.follow_up_needed || false) ||
      formData.follow_up_notes !== (session.follow_up_notes || '');
    
    setHasChanges(hasFormChanges);
  }, [formData, session]);

  const handleFieldChange = (field: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSave = () => {
    onSave(formData);
  };

  const handleReset = () => {
    setFormData({
      session_notes: session.session_notes || '',
      therapist_observations: session.therapist_observations || '',
      student_engagement: session.student_engagement || '',
      materials_used: session.materials_used || '',
      session_quality: session.session_quality || '',
      follow_up_needed: session.follow_up_needed || false,
      follow_up_notes: session.follow_up_notes || ''
    });
  };

  return (
    <Box>
      <Box sx={{ 
        display: 'flex', 
        flexDirection: isMobile ? 'column' : 'row',
        justifyContent: 'space-between', 
        alignItems: isMobile ? 'stretch' : 'center', 
        mb: isMobile ? 2 : 3,
        gap: isMobile ? 1.5 : 0
      }}>
        <Typography 
          variant={isMobile ? "h6" : "h5"} 
          sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 1,
            fontSize: isMobile ? '1.25rem' : undefined
          }}
        >
          <Notes color="primary" sx={{ fontSize: isMobile ? 20 : 24 }} />
          Session Documentation
        </Typography>
        
        {hasChanges && !disabled && (
          <Alert 
            severity="info" 
            sx={{ 
              px: isMobile ? 1.5 : 2, 
              py: isMobile ? 0.75 : 0.5,
              fontSize: isMobile ? '0.85rem' : undefined
            }}
          >
            You have unsaved changes
          </Alert>
        )}
      </Box>

      <Grid container spacing={isMobile ? 2 : 3}>
        {/* General Session Notes */}
        <Grid item xs={12}>
          <Card>
            <CardContent sx={{ p: isMobile ? 2 : 3 }}>
              <Typography 
                variant={isMobile ? "subtitle1" : "h6"} 
                sx={{ 
                  mb: isMobile ? 1.5 : 2, 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: 1,
                  fontSize: isMobile ? '1.1rem' : undefined
                }}
              >
                <Notes color="primary" sx={{ fontSize: isMobile ? 18 : 20 }} />
                General Session Notes
              </Typography>
              <TextField
                fullWidth
                multiline
                rows={isMobile ? 4 : 6}
                label="Session Notes"
                value={formData.session_notes}
                onChange={(e) => handleFieldChange('session_notes', e.target.value)}
                disabled={disabled}
                placeholder="Document what happened during the session, activities completed, student responses, strategies used, challenges encountered, etc."
                sx={{
                  '& .MuiOutlinedInput-root': {
                    '&.Mui-focused fieldset': {
                      borderColor: '#40A8B6'
                    }
                  }
                }}
              />
            </CardContent>
          </Card>
        </Grid>

        {/* Clinical Observations */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent sx={{ p: isMobile ? 2 : 3 }}>
              <Typography 
                variant={isMobile ? "subtitle1" : "h6"} 
                sx={{ 
                  mb: isMobile ? 1.5 : 2, 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: 1,
                  fontSize: isMobile ? '1.1rem' : undefined
                }}
              >
                <Visibility color="primary" sx={{ fontSize: isMobile ? 18 : 20 }} />
                Clinical Observations
              </Typography>
              <TextField
                fullWidth
                multiline
                rows={isMobile ? 3 : 5}
                label="Therapist Observations"
                value={formData.therapist_observations}
                onChange={(e) => handleFieldChange('therapist_observations', e.target.value)}
                disabled={disabled}
                placeholder="Clinical observations about student's communication, behavior, learning patterns, strengths, areas of concern, etc."
                sx={{
                  '& .MuiOutlinedInput-root': {
                    '&.Mui-focused fieldset': {
                      borderColor: '#40A8B6'
                    }
                  }
                }}
              />
            </CardContent>
          </Card>
        </Grid>

        {/* Materials and Resources */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent sx={{ p: isMobile ? 2 : 3 }}>
              <Typography 
                variant={isMobile ? "subtitle1" : "h6"} 
                sx={{ 
                  mb: isMobile ? 1.5 : 2, 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: 1,
                  fontSize: isMobile ? '1.1rem' : undefined
                }}
              >
                <School color="primary" sx={{ fontSize: isMobile ? 18 : 20 }} />
                Materials & Resources
              </Typography>
              <TextField
                fullWidth
                multiline
                rows={isMobile ? 3 : 5}
                label="Materials Used"
                value={formData.materials_used}
                onChange={(e) => handleFieldChange('materials_used', e.target.value)}
                disabled={disabled}
                placeholder="List materials, apps, books, games, tools, assistive technology, or other resources used during the session."
                sx={{
                  '& .MuiOutlinedInput-root': {
                    '&.Mui-focused fieldset': {
                      borderColor: '#40A8B6'
                    }
                  }
                }}
              />
            </CardContent>
          </Card>
        </Grid>

        {/* Session Quality Metrics */}
        <Grid item xs={12}>
          <Card>
            <CardContent sx={{ p: isMobile ? 2 : 3 }}>
              <Typography 
                variant={isMobile ? "subtitle1" : "h6"} 
                sx={{ 
                  mb: isMobile ? 1.5 : 2, 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: 1,
                  fontSize: isMobile ? '1.1rem' : undefined
                }}
              >
                <Psychology color="primary" sx={{ fontSize: isMobile ? 18 : 20 }} />
                Session Quality & Engagement
              </Typography>
              
              <Grid container spacing={isMobile ? 1.5 : 2}>
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth>
                    <InputLabel>Student Engagement Level</InputLabel>
                    <Select
                      value={formData.student_engagement}
                      onChange={(e) => handleFieldChange('student_engagement', e.target.value)}
                      disabled={disabled}
                      label="Student Engagement Level"
                    >
                      <MenuItem value="">Not assessed</MenuItem>
                      {ENGAGEMENT_LEVELS.map(level => (
                        <MenuItem key={level} value={level}>
                          {level.toUpperCase()}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth>
                    <InputLabel>Overall Session Quality</InputLabel>
                    <Select
                      value={formData.session_quality}
                      onChange={(e) => handleFieldChange('session_quality', e.target.value)}
                      disabled={disabled}
                      label="Overall Session Quality"
                    >
                      <MenuItem value="">Not rated</MenuItem>
                      {SESSION_QUALITY_OPTIONS.map(quality => (
                        <MenuItem key={quality} value={quality}>
                          {quality.toUpperCase()}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Follow-up Section */}
        <Grid item xs={12}>
          <Card>
            <CardContent sx={{ p: isMobile ? 2 : 3 }}>
              <Typography 
                variant={isMobile ? "subtitle1" : "h6"} 
                sx={{ 
                  mb: isMobile ? 1.5 : 2, 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: 1,
                  fontSize: isMobile ? '1.1rem' : undefined
                }}
              >
                <Star color="primary" sx={{ fontSize: isMobile ? 18 : 20 }} />
                Follow-up & Recommendations
              </Typography>
              
              <Grid container spacing={isMobile ? 1.5 : 2}>
                <Grid item xs={12}>
                  <FormControl component="fieldset">
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                      <Typography variant="body1">Follow-up needed?</Typography>
                      <Select
                        value={formData.follow_up_needed ? 'yes' : 'no'}
                        onChange={(e) => handleFieldChange('follow_up_needed', e.target.value === 'yes')}
                        disabled={disabled}
                        size="small"
                        sx={{ minWidth: 100 }}
                      >
                        <MenuItem value="no">No</MenuItem>
                        <MenuItem value="yes">Yes</MenuItem>
                      </Select>
                    </Box>
                  </FormControl>
                </Grid>

                {formData.follow_up_needed && (
                  <Grid item xs={12}>
                                          <TextField
                        fullWidth
                        multiline
                        rows={isMobile ? 2 : 3}
                        label="Follow-up Notes"
                        value={formData.follow_up_notes}
                        onChange={(e) => handleFieldChange('follow_up_notes', e.target.value)}
                        disabled={disabled}
                        placeholder="Describe what follow-up is needed, recommendations for next session, things to monitor, parent communication needs, etc."
                      sx={{
                        '& .MuiOutlinedInput-root': {
                          '&.Mui-focused fieldset': {
                            borderColor: '#40A8B6'
                          }
                        }
                      }}
                    />
                  </Grid>
                )}
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Save Actions */}
        {!disabled && (
          <Grid item xs={12}>
            <Divider sx={{ my: isMobile ? 1.5 : 2 }} />
            <Box sx={{ 
              display: 'flex', 
              flexDirection: isMobile ? 'column' : 'row',
              gap: isMobile ? 1.5 : 2, 
              justifyContent: isMobile ? 'stretch' : 'flex-end'
            }}>
              <Button
                onClick={handleReset}
                disabled={!hasChanges}
                variant="outlined"
                fullWidth={isMobile}
                size={isMobile ? 'medium' : 'small'}
                sx={{ order: isMobile ? 2 : 1 }}
              >
                Reset Changes
              </Button>
              <Button
                onClick={handleSave}
                disabled={!hasChanges}
                variant="contained"
                startIcon={<Save />}
                fullWidth={isMobile}
                size={isMobile ? 'medium' : 'small'}
                sx={{
                  bgcolor: '#40A8B6',
                  '&:hover': { bgcolor: '#369aa6' },
                  '&:disabled': { bgcolor: '#e0e0e0' },
                  order: isMobile ? 1 : 2
                }}
              >
                Save Session Notes
              </Button>
            </Box>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}
