import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  TextField,
  Grid,
  Chip,
  IconButton,
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Autocomplete,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider
} from '@mui/material';
import {
  Add,
  Search,
  Edit,
  Delete,
  Person as TeacherIcon,
  LocationOn,
  Phone,
  Email,
  School,
  Business,
  Refresh,
  FilterList
} from '@mui/icons-material';
import { UserSquare2 } from 'lucide-react';
import { useTeachers } from '../../lib/hooks/useTeachers';
import { useSchools } from '../../lib/hooks/useSchools';
import { TeacherForm } from './components/TeacherForm';
import { TeacherCard } from './components/TeacherCard';
import type { Teacher, TeachersFilters } from '../../lib/api/types/teachers';

export default function Teachers() {
  const { 
    teachers, 
    loading, 
    error, 
    departments, 
    fetchTeachers, 
    createTeacher, 
    updateTeacher, 
    deleteTeacher,
    clearError 
  } = useTeachers();

  const { schoolsSummary, fetchSchoolsSummary } = useSchools();

  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDepartment, setSelectedDepartment] = useState<string>('');
  const [selectedSchool, setSelectedSchool] = useState<number | ''>('');
  const [showActiveOnly, setShowActiveOnly] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingTeacher, setEditingTeacher] = useState<Teacher | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [teacherToDelete, setTeacherToDelete] = useState<Teacher | null>(null);

  useEffect(() => {
    loadTeachers();
  }, [searchTerm, selectedDepartment, selectedSchool, showActiveOnly]);

  useEffect(() => {
    fetchSchoolsSummary(true); // Load active schools for filtering
  }, [fetchSchoolsSummary]);

  const loadTeachers = () => {
    const filters: TeachersFilters = {
      is_active: showActiveOnly ? true : undefined,
      department: selectedDepartment || undefined,
      school_id: selectedSchool || undefined,
      search: searchTerm || undefined,
      limit: 100
    };
    fetchTeachers(filters);
  };

  const handleCreateTeacher = () => {
    setEditingTeacher(null);
    setShowForm(true);
  };

  const handleEditTeacher = (teacher: Teacher) => {
    setEditingTeacher(teacher);
    setShowForm(true);
  };

  const handleDeleteTeacher = (teacher: Teacher) => {
    setTeacherToDelete(teacher);
    setDeleteConfirmOpen(true);
  };

  const confirmDelete = async () => {
    if (teacherToDelete) {
      try {
        await deleteTeacher(teacherToDelete.id);
        setDeleteConfirmOpen(false);
        setTeacherToDelete(null);
      } catch (error) {
        // Error is handled by the hook
      }
    }
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditingTeacher(null);
  };

  const handleFormSubmit = async (teacherData: any) => {
    try {
      if (editingTeacher) {
        const updatedTeacher = await updateTeacher(editingTeacher.id, teacherData);
        return updatedTeacher;
      } else {
        const createdTeacher = await createTeacher(teacherData);
        return createdTeacher;
      }
    } catch (error) {
      // Error is handled by the hook
      throw error; // Re-throw so the form can handle it
    }
  };

  const clearFilters = () => {
    setSearchTerm('');
    setSelectedDepartment('');
    setSelectedSchool('');
    setShowActiveOnly(true);
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography 
          variant="h4" 
          component="h1" 
          sx={{ 
            display: 'flex', 
            alignItems: 'center',
            color: '#41AAB7',
            fontWeight: 700,
            gap: 2
          }}
        >
          <UserSquare2 size={32} />
          Teachers
        </Typography>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={clearError}>
          {error}
        </Alert>
      )}

      {/* Filters and Actions */}
      <Card sx={{ 
        mb: 3,
        bgcolor: 'white',
        borderRadius: 3,
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        border: '1px solid #e0e0e0'
      }}>
        <CardContent sx={{ p: 3 }}>
          <Grid container spacing={3} alignItems="center">
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                label="Search Teachers"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search by name, email, title..."
                InputProps={{
                  startAdornment: <Search sx={{ color: '#40A8B6', mr: 1 }} />
                }}
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <Autocomplete
                options={departments}
                value={selectedDepartment}
                onChange={(_, newValue) => setSelectedDepartment(newValue || '')}
                renderInput={(params) => (
                  <TextField {...params} label="Department" />
                )}
                freeSolo
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <FormControl fullWidth>
                <InputLabel>School</InputLabel>
                <Select
                  value={selectedSchool}
                  onChange={(e) => setSelectedSchool(e.target.value)}
                  label="School"
                >
                  <MenuItem value="">All Schools</MenuItem>
                  {schoolsSummary.map((school) => (
                    <MenuItem key={school.id} value={school.id}>
                      {school.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={2}>
              <FormControl fullWidth>
                <InputLabel>Status</InputLabel>
                <Select
                  value={showActiveOnly ? 'active' : 'all'}
                  onChange={(e) => setShowActiveOnly(e.target.value === 'active')}
                  label="Status"
                >
                  <MenuItem value="active">Active Only</MenuItem>
                  <MenuItem value="all">All Teachers</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={3}>
              <Box display="flex" gap={1}>
                <Button
                  variant="contained"
                  startIcon={<Add />}
                  onClick={handleCreateTeacher}
                  sx={{
                    bgcolor: '#40A8B6',
                    '&:hover': { bgcolor: '#369aa6' },
                    textTransform: 'none',
                    fontWeight: 500
                  }}
                >
                  Add Teacher
                </Button>
                <IconButton 
                  onClick={loadTeachers}
                  sx={{ color: '#40A8B6' }}
                  title="Refresh"
                >
                  <Refresh />
                </IconButton>
                <IconButton 
                  onClick={clearFilters}
                  sx={{ color: '#666' }}
                  title="Clear Filters"
                >
                  <FilterList />
                </IconButton>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Teachers List */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress size={40} />
        </Box>
      ) : teachers.length === 0 ? (
        <Card sx={{ 
          bgcolor: 'white', 
          borderRadius: 3, 
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          border: '1px solid #e0e0e0'
        }}>
          <CardContent sx={{ textAlign: 'center', py: 6 }}>
            <TeacherIcon sx={{ fontSize: 64, color: '#40A8B6', mb: 2 }} />
            <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600, mb: 1 }}>
              No Teachers Found
            </Typography>
            <Typography color="text.secondary" sx={{ mb: 3 }}>
              {searchTerm || selectedDepartment || selectedSchool
                ? 'Try adjusting your search filters or add a new teacher.'
                : 'Get started by adding your first teacher.'
              }
            </Typography>
            <Button 
              variant="contained" 
              startIcon={<Add />} 
              onClick={handleCreateTeacher}
              sx={{
                bgcolor: '#40A8B6',
                '&:hover': { bgcolor: '#369aa6' },
                textTransform: 'none',
                fontWeight: 500
              }}
            >
              Add First Teacher
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Grid container spacing={3}>
          {teachers.map((teacher) => (
            <Grid item xs={12} md={6} lg={4} key={teacher.id}>
              <TeacherCard
                teacher={teacher}
                onEdit={() => handleEditTeacher(teacher)}
                onDelete={() => handleDeleteTeacher(teacher)}
              />
            </Grid>
          ))}
        </Grid>
      )}

      {/* Teacher Form Dialog */}
      <Dialog 
        open={showForm} 
        onClose={handleFormClose}
        maxWidth="md" 
        fullWidth
      >
        <DialogTitle sx={{ bgcolor: '#40A8B6', color: 'white' }}>
          {editingTeacher ? 'Edit Teacher' : 'Add New Teacher'}
        </DialogTitle>
        <DialogContent sx={{ p: 0 }}>
          <TeacherForm
            teacher={editingTeacher}
            onSubmit={handleFormSubmit}
            onCancel={handleFormClose}
          />
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog 
        open={deleteConfirmOpen} 
        onClose={() => setDeleteConfirmOpen(false)}
        maxWidth="sm"
      >
        <DialogTitle>Confirm Delete</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to deactivate "{teacherToDelete?.first_name} {teacherToDelete?.last_name}"? 
            This will mark the teacher as inactive but preserve all data.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirmOpen(false)}>
            Cancel
          </Button>
          <Button 
            onClick={confirmDelete} 
            color="error" 
            variant="contained"
          >
            Deactivate
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
