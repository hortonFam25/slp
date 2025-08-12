import React, { useState, useEffect } from 'react';
import {
  Box,
  TextField,
  Button,
  Grid,
  FormControlLabel,
  Switch,
  Divider,
  Typography,
  Alert
} from '@mui/material';
import { Save, Cancel } from '@mui/icons-material';
import type { School, CreateSchoolRequest, UpdateSchoolRequest } from '../../../lib/api/types/schools';

interface SchoolFormProps {
  school?: School | null;
  onSubmit: (data: CreateSchoolRequest | UpdateSchoolRequest) => Promise<void>;
  onCancel: () => void;
}

export function SchoolForm({ school, onSubmit, onCancel }: SchoolFormProps) {
  const [formData, setFormData] = useState({
    name: '',
    address: '',
    phone: '',
    email: '',
    district: '',
    principal_name: '',
    contact_person: '',
    contact_phone: '',
    notes: '',
    is_active: true
  });

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    if (school) {
      setFormData({
        name: school.name || '',
        address: school.address || '',
        phone: school.phone || '',
        email: school.email || '',
        district: school.district || '',
        principal_name: school.principal_name || '',
        contact_person: school.contact_person || '',
        contact_phone: school.contact_phone || '',
        notes: school.notes || '',
        is_active: school.is_active ?? true
      });
    }
  }, [school]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name.trim()) {
      setError('School name is required');
      return;
    }

    setSubmitting(true);
    setError('');

    try {
      await onSubmit(formData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save school');
    } finally {
      setSubmitting(false);
    }
  };

  const handleChange = (field: string) => (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  return (
    <Box sx={{ p: 3 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit}>
        <Grid container spacing={3}>
          {/* Basic Information */}
          <Grid item xs={12}>
            <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600, mb: 2 }}>
              Basic Information
            </Typography>
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              required
              label="School Name"
              value={formData.name}
              onChange={handleChange('name')}
              placeholder="Enter school name"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="District"
              value={formData.district}
              onChange={handleChange('district')}
              placeholder="Enter school district"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Address"
              value={formData.address}
              onChange={handleChange('address')}
              placeholder="Enter full school address"
              multiline
              rows={2}
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          {/* Contact Information */}
          <Grid item xs={12}>
            <Divider sx={{ my: 2, borderColor: '#e8f4f5' }} />
            <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600, mb: 2 }}>
              Contact Information
            </Typography>
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Phone Number"
              value={formData.phone}
              onChange={handleChange('phone')}
              placeholder="(555) 123-4567"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Email Address"
              type="email"
              value={formData.email}
              onChange={handleChange('email')}
              placeholder="school@district.edu"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          {/* Personnel Information */}
          <Grid item xs={12}>
            <Divider sx={{ my: 2, borderColor: '#e8f4f5' }} />
            <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600, mb: 2 }}>
              Personnel Information
            </Typography>
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Principal Name"
              value={formData.principal_name}
              onChange={handleChange('principal_name')}
              placeholder="Enter principal's name"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Primary Contact Person"
              value={formData.contact_person}
              onChange={handleChange('contact_person')}
              placeholder="Enter contact person's name"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Contact Phone"
              value={formData.contact_phone}
              onChange={handleChange('contact_phone')}
              placeholder="Contact person's phone number"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          {/* Additional Information */}
          <Grid item xs={12}>
            <Divider sx={{ my: 2, borderColor: '#e8f4f5' }} />
            <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600, mb: 2 }}>
              Additional Information
            </Typography>
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Notes"
              value={formData.notes}
              onChange={handleChange('notes')}
              placeholder="Add any additional notes about the school..."
              multiline
              rows={3}
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&.Mui-focused fieldset': {
                    borderColor: '#40A8B6'
                  }
                }
              }}
            />
          </Grid>

          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Switch
                  checked={formData.is_active}
                  onChange={handleChange('is_active')}
                  sx={{
                    '& .MuiSwitch-switchBase.Mui-checked': {
                      color: '#40A8B6'
                    },
                    '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                      backgroundColor: '#40A8B6'
                    }
                  }}
                />
              }
              label="School is active"
            />
          </Grid>
        </Grid>

        <Divider sx={{ my: 3, borderColor: '#e8f4f5' }} />

        {/* Action Buttons */}
        <Box display="flex" justifyContent="flex-end" gap={2}>
          <Button
            onClick={onCancel}
            startIcon={<Cancel />}
            disabled={submitting}
            sx={{ 
              textTransform: 'none',
              fontWeight: 500,
              color: '#666'
            }}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            startIcon={<Save />}
            disabled={submitting || !formData.name.trim()}
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
            {submitting ? 'Saving...' : school ? 'Update School' : 'Create School'}
          </Button>
        </Box>
      </form>
    </Box>
  );
}
