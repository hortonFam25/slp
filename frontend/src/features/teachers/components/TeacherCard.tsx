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
  School,
  ContactMail,
  Badge
} from '@mui/icons-material';
import type { Teacher, CONTACT_METHODS } from '../../../lib/api/types/teachers';

interface TeacherCardProps {
  teacher: Teacher;
  onEdit: () => void;
  onDelete: () => void;
}

export function TeacherCard({ teacher, onEdit, onDelete }: TeacherCardProps) {
  const getContactMethodIcon = (method?: string) => {
    switch (method) {
      case 'email':
        return <Email sx={{ fontSize: 14, mr: 0.5 }} />;
      case 'phone':
        return <Phone sx={{ fontSize: 14, mr: 0.5 }} />;
      case 'text':
        return <ContactMail sx={{ fontSize: 14, mr: 0.5 }} />;
      default:
        return <ContactMail sx={{ fontSize: 14, mr: 0.5 }} />;
    }
  };

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
      <CardContent sx={{ p: 2.5, flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
          <Box flex={1}>
            <Box display="flex" alignItems="center" mb={1}>
              <Person sx={{ color: '#40A8B6', mr: 1 }} />
              <Typography variant="h6" sx={{ fontWeight: 600, color: '#333' }}>
                {teacher.first_name} {teacher.last_name}
              </Typography>
            </Box>
            {teacher.title && (
              <Box display="flex" alignItems="center" mb={1}>
                <Badge sx={{ fontSize: 16, color: '#666', mr: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  {teacher.title}
                </Typography>
              </Box>
            )}
            {teacher.department && (
              <Box display="flex" alignItems="center">
                <Business sx={{ fontSize: 16, color: '#666', mr: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  {teacher.department}
                </Typography>
              </Box>
            )}
            {teacher.primary_school_name && (
              <Box display="flex" alignItems="center" mt={1}>
                <School sx={{ fontSize: 16, color: '#40A8B6', mr: 1 }} />
                <Typography variant="body2" sx={{ color: '#40A8B6', fontWeight: 500 }}>
                  {teacher.primary_school_name}
                </Typography>
              </Box>
            )}
          </Box>
          <Box>
            <Chip
              label={teacher.is_active ? 'Active' : 'Inactive'}
              size="small"
              sx={{
                bgcolor: teacher.is_active ? '#e8f4f5' : '#ffeaa7',
                color: teacher.is_active ? '#40A8B6' : '#f39c12',
                fontWeight: 500
              }}
            />
          </Box>
        </Box>

        {/* Contact Information */}
        <Box sx={{ flex: 1, mb: 1.5 }}>
          {teacher.email && (
            <Box display="flex" alignItems="center" mb={1}>
              <Email sx={{ fontSize: 16, color: '#666', mr: 1 }} />
              <Typography variant="body2" color="text.secondary" sx={{ 
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {teacher.email}
              </Typography>
            </Box>
          )}
          
          {teacher.phone && (
            <Box display="flex" alignItems="center" mb={1}>
              <Phone sx={{ fontSize: 16, color: '#666', mr: 1 }} />
              <Typography variant="body2" color="text.secondary">
                {teacher.phone}
              </Typography>
            </Box>
          )}

          {teacher.room_number && (
            <Box display="flex" alignItems="center" mb={1}>
              <LocationOn sx={{ fontSize: 16, color: '#666', mr: 1 }} />
              <Typography variant="body2" color="text.secondary">
                Room {teacher.room_number}
              </Typography>
            </Box>
          )}

          {teacher.preferred_contact_method && (
            <Box display="flex" alignItems="center" mb={1}>
              {getContactMethodIcon(teacher.preferred_contact_method)}
              <Typography variant="caption" color="text.secondary">
                Prefers: {teacher.preferred_contact_method.charAt(0).toUpperCase() + teacher.preferred_contact_method.slice(1)}
              </Typography>
            </Box>
          )}
        </Box>

        {/* School Assignments */}
        {(teacher.active_schools_count !== undefined || teacher.current_students_count !== undefined) && (
          <>
            <Divider sx={{ my: 0, borderColor: '#e8f4f5' }} />
            <Grid container spacing={2}>
              {teacher.active_schools_count !== undefined && (
                <Grid item xs={6}>
                  <Box textAlign="center">
                    <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600 }}>
                      {teacher.active_schools_count}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Schools
                    </Typography>
                  </Box>
                </Grid>
              )}
              {teacher.current_students_count !== undefined && (
                <Grid item xs={6}>
                  <Box textAlign="center">
                    <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600 }}>
                      {teacher.current_students_count}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Students
                    </Typography>
                  </Box>
                </Grid>
              )}
            </Grid>
          </>
        )}

        {/* Notes */}
        {teacher.notes && (
          <>
            <Divider sx={{ my: 1.5, borderColor: '#e8f4f5' }} />
            <Typography variant="body2" color="text.secondary" sx={{ 
              fontStyle: 'italic',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical'
            }}>
              {teacher.notes}
            </Typography>
          </>
        )}

        {/* Actions */}
        <Box display="flex" justifyContent="flex-end" gap={1} mt={1.5}>
          <IconButton
            onClick={onEdit}
            size="small"
            sx={{
              color: '#40A8B6',
              '&:hover': {
                bgcolor: 'rgba(64,168,182,0.1)'
              }
            }}
            title="Edit Support Staff"
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
            title="Deactivate Support Staff"
          >
            <Delete />
          </IconButton>
        </Box>
      </CardContent>
    </Card>
  );
}
