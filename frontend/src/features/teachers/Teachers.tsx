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
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow
} from '@mui/material';
import {
  Add,
  Search,
  Delete,
  Person as TeacherIcon,
  Info,
  FilterList
} from '@mui/icons-material';
import { UserSquare2 } from 'lucide-react';
import { useTeachers } from '../../lib/hooks/useTeachers';
import { useSchools } from '../../lib/hooks/useSchools';
import { TeacherForm } from './components/TeacherForm';
import { SupportStaffStudentsDialog } from './components/SupportStaffStudentsDialog';
import type { Teacher, TeachersFilters, SupportStaffRole } from '../../lib/api/types/teachers';

export default function Teachers() {
  const { 
    teachers, 
    loading, 
    error, 
    fetchTeachers, 
    createTeacher, 
    updateTeacher, 
    deleteTeacher,
    getRoles,
    clearError 
  } = useTeachers();

  const { schoolsSummary, fetchSchoolsSummary } = useSchools();

  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSchool, setSelectedSchool] = useState<number | ''>('');
  const [selectedRole, setSelectedRole] = useState<number | ''>('');
  const [roles, setRoles] = useState<SupportStaffRole[]>([]);
  const [showActiveOnly, setShowActiveOnly] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingTeacher, setEditingTeacher] = useState<Teacher | null>(null);
  const [detailsTeacher, setDetailsTeacher] = useState<Teacher | null>(null);
  const [showStudentDetails, setShowStudentDetails] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [teacherToDelete, setTeacherToDelete] = useState<Teacher | null>(null);

  useEffect(() => {
    loadTeachers();
  }, [searchTerm, selectedSchool, selectedRole, showActiveOnly]);

  useEffect(() => {
    const loadFilterOptions = async () => {
      const [, roleOptions] = await Promise.all([fetchSchoolsSummary(true), getRoles(true)]);
      setRoles(roleOptions);
    };
    loadFilterOptions().catch(() => undefined);
  }, [fetchSchoolsSummary, getRoles]);

  const loadTeachers = () => {
    const filters: TeachersFilters = {
      is_active: showActiveOnly ? true : false,
      school_id: selectedSchool || undefined,
      role_id: selectedRole || undefined,
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

  const handleOpenDetails = (teacher: Teacher) => {
    setDetailsTeacher(teacher);
    setShowStudentDetails(true);
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
    setSelectedSchool('');
    setSelectedRole('');
    setShowActiveOnly(true);
  };

  return (
    <Box sx={{ p: { xs: 1.5, sm: 2 }, height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <Box sx={{ mb: 2, flexShrink: 0 }}>
        <Typography
          component="h1"
          sx={{
            display: 'flex',
            alignItems: 'center',
            color: '#41AAB7',
            fontWeight: 700,
            gap: 1.25,
            fontSize: { xs: '1.35rem', sm: '1.5rem' },
            lineHeight: 1.2,
          }}
        >
          <UserSquare2 size={24} />
          Support Staff
        </Typography>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3, flexShrink: 0 }} onClose={clearError}>
          {error}
        </Alert>
      )}

      {/* Filters and Actions */}
      <Card sx={{ 
        mb: 3,
        bgcolor: 'white',
        borderRadius: 3,
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        border: '1px solid #e0e0e0',
        flexShrink: 0
      }}>
        <CardContent sx={{ p: 2 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={5}>
              <TextField
                fullWidth
                size="small"
                label="Search Support Staff"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search by name, email, title..."
                InputProps={{
                  startAdornment: <Search sx={{ color: '#40A8B6', mr: 1 }} />
                }}
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <FormControl fullWidth size="small">
                <InputLabel>School</InputLabel>
                <Select
                  value={selectedSchool}
                  onChange={(e) => setSelectedSchool(e.target.value === '' ? '' : Number(e.target.value))}
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
              <FormControl fullWidth size="small">
                <InputLabel>Role</InputLabel>
                <Select
                  value={selectedRole}
                  onChange={(e) => setSelectedRole(e.target.value === '' ? '' : Number(e.target.value))}
                  label="Role"
                >
                  <MenuItem value="">All Roles</MenuItem>
                  {roles.map((role) => (
                    <MenuItem key={role.id} value={role.id}>
                      {role.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={3}>
              <Box display="flex" gap={1} alignItems="center" justifyContent="flex-end" sx={{ minHeight: 40, width: '100%' }}>
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <Switch
                    size="small"
                    checked={showActiveOnly}
                    onChange={(e) => setShowActiveOnly(e.target.checked)}
                    sx={{
                      '& .MuiSwitch-switchBase.Mui-checked': { color: '#40A8B6' },
                      '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { backgroundColor: '#40A8B6' }
                    }}
                  />
                  <Typography variant="caption" sx={{ mt: -0.5, color: 'text.secondary' }}>
                    {showActiveOnly ? 'Active' : 'Inactive'}
                  </Typography>
                </Box>
                <IconButton 
                  onClick={clearFilters}
                  sx={{ color: '#666' }}
                  title="Clear Filters"
                >
                  <FilterList />
                </IconButton>
                <Button
                  variant="contained"
                  startIcon={<Add />}
                  onClick={handleCreateTeacher}
                  sx={{
                    bgcolor: '#40A8B6',
                    '&:hover': { bgcolor: '#369aa6' },
                    textTransform: 'none',
                    fontWeight: 500,
                    minWidth: 84
                  }}
                >
                  Add
                </Button>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Support Staff List */}
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
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
                No Support Staff Found
              </Typography>
              <Typography color="text.secondary" sx={{ mb: 3 }}>
                {searchTerm || selectedSchool || selectedRole
                  ? 'Try adjusting your search filters or add a new support staff member.'
                  : 'Get started by adding your first support staff member.'
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
                Add First Support Staff
              </Button>
            </CardContent>
          </Card>
        ) : (
          <Card sx={{
            bgcolor: 'white',
            borderRadius: 3,
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            border: '1px solid #e0e0e0',
            flex: 1,
            minHeight: 0,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}>
            <TableContainer sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
              <Table stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Name</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Roles</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Primary School</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Schools</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Students</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {teachers.map((teacher) => (
                  <TableRow key={teacher.id} hover>
                    <TableCell>
                      <Box>
                        <Typography sx={{ fontWeight: 600 }}>
                          {teacher.first_name} {teacher.last_name}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {teacher.email || teacher.phone || 'No contact info'}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {(teacher.roles || []).length > 0 ? (
                          (teacher.roles || []).map((role) => (
                            <Chip key={role.id} label={role.name} size="small" sx={{ bgcolor: '#e8f4f5', color: '#40A8B6' }} />
                          ))
                        ) : (
                          <Typography variant="body2" color="text.secondary">None</Typography>
                        )}
                      </Box>
                    </TableCell>
                    <TableCell>{teacher.primary_school_name || '-'}</TableCell>
                    <TableCell>{teacher.active_schools_count ?? 0}</TableCell>
                    <TableCell>
                      <Button size="small" onClick={() => handleOpenDetails(teacher)} sx={{ textTransform: 'none' }}>
                        {teacher.current_students_count ?? 0}
                      </Button>
                    </TableCell>
                    <TableCell align="right">
                      <Button
                        variant="outlined"
                        size="small"
                        startIcon={<Info />}
                        onClick={() => handleOpenDetails(teacher)}
                        sx={{ color: '#40A8B6', borderColor: '#40A8B6', textTransform: 'none', mr: 1 }}
                      >
                        Details
                      </Button>
                      <IconButton
                        onClick={() => handleDeleteTeacher(teacher)}
                        size="small"
                        sx={{ color: '#f44336' }}
                        title="Deactivate Support Staff"
                      >
                        <Delete />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
              </Table>
            </TableContainer>
          </Card>
        )}
      </Box>

      {/* Support Staff Form Dialog */}
      <Dialog 
        open={showForm} 
        onClose={handleFormClose}
        maxWidth="md" 
        fullWidth
      >
        <DialogTitle sx={{ bgcolor: '#40A8B6', color: 'white' }}>
          {editingTeacher ? 'Edit Support Staff' : 'Add New Support Staff'}
        </DialogTitle>
        <DialogContent sx={{ p: 0 }}>
          <TeacherForm
            teacher={editingTeacher}
            onSubmit={handleFormSubmit}
            onCancel={handleFormClose}
          />
        </DialogContent>
      </Dialog>

      <SupportStaffStudentsDialog
        open={showStudentDetails}
        staff={detailsTeacher}
        onClose={() => {
          setShowStudentDetails(false);
          setDetailsTeacher(null);
        }}
        onAssignmentsChanged={async () => {
          await fetchTeachers({
            is_active: showActiveOnly ? true : false,
            school_id: selectedSchool || undefined,
            role_id: selectedRole || undefined,
            search: searchTerm || undefined,
            limit: 100
          });
        }}
      />

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
            This will mark this support staff member as inactive but preserve all data.
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
