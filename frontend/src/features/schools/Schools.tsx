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
  School as SchoolIcon,
  LocationOn,
  Phone,
  Email,
  Person,
  Business,
  Refresh,
  FilterList
} from '@mui/icons-material';
import { useSchools } from '../../lib/hooks/useSchools';
import { SchoolForm } from './components/SchoolForm';
import { SchoolCard } from './components/SchoolCard';
import type { School, SchoolsFilters } from '../../lib/api/types/schools';

export default function Schools() {
  const { 
    schools, 
    loading, 
    error, 
    districts, 
    fetchSchools, 
    createSchool, 
    updateSchool, 
    deleteSchool,
    clearError 
  } = useSchools();

  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDistrict, setSelectedDistrict] = useState<string>('');
  const [showActiveOnly, setShowActiveOnly] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingSchool, setEditingSchool] = useState<School | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [schoolToDelete, setSchoolToDelete] = useState<School | null>(null);

  useEffect(() => {
    loadSchools();
  }, [searchTerm, selectedDistrict, showActiveOnly]);

  const loadSchools = () => {
    const filters: SchoolsFilters = {
      is_active: showActiveOnly ? true : undefined,
      district: selectedDistrict || undefined,
      search: searchTerm || undefined,
      limit: 100
    };
    fetchSchools(filters);
  };

  const handleCreateSchool = () => {
    setEditingSchool(null);
    setShowForm(true);
  };

  const handleEditSchool = (school: School) => {
    setEditingSchool(school);
    setShowForm(true);
  };

  const handleDeleteSchool = (school: School) => {
    setSchoolToDelete(school);
    setDeleteConfirmOpen(true);
  };

  const confirmDelete = async () => {
    if (schoolToDelete) {
      try {
        await deleteSchool(schoolToDelete.id);
        setDeleteConfirmOpen(false);
        setSchoolToDelete(null);
      } catch (error) {
        // Error is handled by the hook
      }
    }
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditingSchool(null);
  };

  const handleFormSubmit = async (schoolData: any) => {
    try {
      if (editingSchool) {
        await updateSchool(editingSchool.id, schoolData);
      } else {
        await createSchool(schoolData);
      }
      handleFormClose();
    } catch (error) {
      // Error is handled by the hook
    }
  };

  const clearFilters = () => {
    setSearchTerm('');
    setSelectedDistrict('');
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
            mb: 2, 
            display: 'flex', 
            alignItems: 'center',
            color: '#40A8B6',
            fontWeight: 600
          }}
        >
          <SchoolIcon sx={{ mr: 2, fontSize: 32 }} />
          School Management
        </Typography>
        <Typography variant="h6" color="text.secondary">
          Manage schools, contacts, and district information
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
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                label="Search Schools"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search by name, district, principal..."
                InputProps={{
                  startAdornment: <Search sx={{ color: '#40A8B6', mr: 1 }} />
                }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <Autocomplete
                options={districts}
                value={selectedDistrict}
                onChange={(_, newValue) => setSelectedDistrict(newValue || '')}
                renderInput={(params) => (
                  <TextField {...params} label="Filter by District" />
                )}
                freeSolo
              />
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
                  <MenuItem value="all">All Schools</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={3}>
              <Box display="flex" gap={1}>
                <Button
                  variant="contained"
                  startIcon={<Add />}
                  onClick={handleCreateSchool}
                  sx={{
                    bgcolor: '#40A8B6',
                    '&:hover': { bgcolor: '#369aa6' },
                    textTransform: 'none',
                    fontWeight: 500
                  }}
                >
                  Add School
                </Button>
                <IconButton 
                  onClick={loadSchools}
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

      {/* Schools List */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress size={40} />
        </Box>
      ) : schools.length === 0 ? (
        <Card sx={{ 
          bgcolor: 'white', 
          borderRadius: 3, 
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          border: '1px solid #e0e0e0'
        }}>
          <CardContent sx={{ textAlign: 'center', py: 6 }}>
            <SchoolIcon sx={{ fontSize: 64, color: '#40A8B6', mb: 2 }} />
            <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 600, mb: 1 }}>
              No Schools Found
            </Typography>
            <Typography color="text.secondary" sx={{ mb: 3 }}>
              {searchTerm || selectedDistrict 
                ? 'Try adjusting your search filters or add a new school.'
                : 'Get started by adding your first school.'
              }
            </Typography>
            <Button 
              variant="contained" 
              startIcon={<Add />} 
              onClick={handleCreateSchool}
              sx={{
                bgcolor: '#40A8B6',
                '&:hover': { bgcolor: '#369aa6' },
                textTransform: 'none',
                fontWeight: 500
              }}
            >
              Add First School
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Grid container spacing={3}>
          {schools.map((school) => (
            <Grid item xs={12} md={6} lg={4} key={school.id}>
              <SchoolCard
                school={school}
                onEdit={() => handleEditSchool(school)}
                onDelete={() => handleDeleteSchool(school)}
              />
            </Grid>
          ))}
        </Grid>
      )}

      {/* School Form Dialog */}
      <Dialog 
        open={showForm} 
        onClose={handleFormClose}
        maxWidth="md" 
        fullWidth
      >
        <DialogTitle sx={{ bgcolor: '#40A8B6', color: 'white' }}>
          {editingSchool ? 'Edit School' : 'Add New School'}
        </DialogTitle>
        <DialogContent sx={{ p: 0 }}>
          <SchoolForm
            school={editingSchool}
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
            Are you sure you want to deactivate "{schoolToDelete?.name}"? 
            This will mark the school as inactive but preserve all data.
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
