import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  IconButton,
  Grid,
  Divider
} from '@mui/material';
import {
  Edit,
  Delete,
  LocationOn,
  Phone,
  Email,
  Person,
  Business,
  School as SchoolIcon,
  People
} from '@mui/icons-material';
import type { School } from '../../../lib/api/types/schools';

interface SchoolCardProps {
  school: School;
  onEdit: () => void;
  onDelete: () => void;
}

export function SchoolCard({ school, onEdit, onDelete }: SchoolCardProps) {
  return (
    <Card sx={{
      bgcolor: 'white',
      borderRadius: 3,
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
      border: '1px solid #e0e0e0',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      '&:hover': {
        boxShadow: '0 4px 16px rgba(64,168,182,0.15)',
        borderColor: '#40A8B6'
      },
      transition: 'all 0.2s ease-in-out'
    }}>
      <CardContent sx={{ p: 3, flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
          <Box flex={1}>
            <Box display="flex" alignItems="center" mb={1}>
              <SchoolIcon sx={{ color: '#40A8B6', mr: 1 }} />
              <Typography variant="h6" sx={{ fontWeight: 600, color: '#333' }}>
                {school.name}
              </Typography>
            </Box>
            {school.district && (
              <Box display="flex" alignItems="center" mb={1}>
                <Business sx={{ fontSize: 16, color: '#666', mr: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  {school.district}
                </Typography>
              </Box>
            )}
          </Box>
          <Box>
            <Chip
              label={school.is_active ? 'Active' : 'Inactive'}
              size="small"
              sx={{
                bgcolor: school.is_active ? '#e8f4f5' : '#ffeaa7',
                color: school.is_active ? '#40A8B6' : '#f39c12',
                fontWeight: 500
              }}
            />
          </Box>
        </Box>

        {/* Contact Information */}
        <Box sx={{ flex: 1, mb: 2 }}>
          {school.address && (
            <Box display="flex" alignItems="flex-start" mb={1}>
              <LocationOn sx={{ fontSize: 16, color: '#666', mr: 1, mt: 0.2 }} />
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.875rem' }}>
                {school.address}
              </Typography>
            </Box>
          )}
          
          {school.phone && (
            <Box display="flex" alignItems="center" mb={1}>
              <Phone sx={{ fontSize: 16, color: '#666', mr: 1 }} />
              <Typography variant="body2" color="text.secondary">
                {school.phone}
              </Typography>
            </Box>
          )}
          
          {school.email && (
            <Box display="flex" alignItems="center" mb={1}>
              <Email sx={{ fontSize: 16, color: '#666', mr: 1 }} />
              <Typography variant="body2" color="text.secondary">
                {school.email}
              </Typography>
            </Box>
          )}
        </Box>

        {/* Principal/Contact */}
        {(school.principal_name || school.contact_person) && (
          <>
            <Divider sx={{ my: 2, borderColor: '#e8f4f5' }} />
            <Box>
              {school.principal_name && (
                <Box display="flex" alignItems="center" mb={1}>
                  <Person sx={{ fontSize: 16, color: '#40A8B6', mr: 1 }} />
                  <Box>
                    <Typography variant="caption" color="text.secondary" display="block">
                      Principal
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {school.principal_name}
                    </Typography>
                  </Box>
                </Box>
              )}
              
              {school.contact_person && school.contact_person !== school.principal_name && (
                <Box display="flex" alignItems="center" mb={1}>
                  <Person sx={{ fontSize: 16, color: '#40A8B6', mr: 1 }} />
                  <Box>
                    <Typography variant="caption" color="text.secondary" display="block">
                      Contact
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {school.contact_person}
                      {school.contact_phone && (
                        <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                          • {school.contact_phone}
                        </Typography>
                      )}
                    </Typography>
                  </Box>
                </Box>
              )}
            </Box>
          </>
        )}

        {/* Statistics */}
        {(school.active_students_count !== undefined || school.active_teachers_count !== undefined) && (
          <>
            <Divider sx={{ my: 2, borderColor: '#e8f4f5' }} />
            <Grid container spacing={2}>
              {school.active_students_count !== undefined && (
                <Grid item xs={6}>
                  <Box textAlign="center">
                    <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600 }}>
                      {school.active_students_count}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Students
                    </Typography>
                  </Box>
                </Grid>
              )}
              {school.active_teachers_count !== undefined && (
                <Grid item xs={6}>
                  <Box textAlign="center">
                    <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600 }}>
                      {school.active_teachers_count}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Support Staff
                    </Typography>
                  </Box>
                </Grid>
              )}
            </Grid>
          </>
        )}

        {/* Notes */}
        {school.notes && (
          <>
            <Divider sx={{ my: 2, borderColor: '#e8f4f5' }} />
            <Typography variant="body2" color="text.secondary" sx={{ 
              fontStyle: 'italic',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical'
            }}>
              {school.notes}
            </Typography>
          </>
        )}

        {/* Actions */}
        <Box display="flex" justifyContent="flex-end" gap={1} mt={2}>
          <IconButton
            onClick={onEdit}
            size="small"
            sx={{
              color: '#40A8B6',
              '&:hover': {
                bgcolor: 'rgba(64,168,182,0.1)'
              }
            }}
            title="Edit School"
          >
            <Edit />
          </IconButton>
          <IconButton
            onClick={onDelete}
            size="small"
            sx={{
              color: '#f44336',
              '&:hover': {
                bgcolor: 'rgba(244,67,54,0.1)'
              }
            }}
            title="Deactivate School"
          >
            <Delete />
          </IconButton>
        </Box>
      </CardContent>
    </Card>
  );
}
