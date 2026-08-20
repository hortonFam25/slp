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
  Autocomplete,
  FormControlLabel,
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
  School as SchoolIcon,
  Info,
  FilterList
} from '@mui/icons-material';
import { GraduationCap } from 'lucide-react';
import { useSchools } from '../../lib/hooks/useSchools';
import { SchoolForm } from './components/SchoolForm';
import { SchoolDetailsDialog } from './components/SchoolDetailsDialog';
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
  const [detailsSchool, setDetailsSchool] = useState<School | null>(null);
  const [detailsInitialTab, setDetailsInitialTab] = useState(0);
  const [showDetails, setShowDetails] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [schoolToDelete, setSchoolToDelete] = useState<School | null>(null);

  useEffect(() => {
    loadSchools();
  }, [searchTerm, selectedDistrict, showActiveOnly]);

  const loadSchools = () => {
    const filters: SchoolsFilters = {
      is_active: showActiveOnly ? true : false,
      district: selectedDistrict || undefined,
      search: searchTerm || undefined,
      limit: 100
    };
    fetchSchools(filters);
  };

  const handleCreateSchool = () => {
    setShowForm(true);
  };

  const handleOpenDetails = (school: School, tabIndex: number = 0) => {
    setDetailsSchool(school);
    setDetailsInitialTab(tabIndex);
    setShowDetails(true);
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
  };

  const handleFormSubmit = async (schoolData: any) => {
    try {
      await createSchool(schoolData);
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
          <GraduationCap size={24} />
          Schools
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
                label="Search Schools"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search by name, district, principal..."
                InputProps={{
                  startAdornment: <Search sx={{ color: '#40A8B6', mr: 1 }} />
                }}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <Autocomplete
                options={districts}
                value={selectedDistrict}
                onChange={(_, newValue) => setSelectedDistrict(newValue || '')}
                renderInput={(params) => (
                  <TextField {...params} size="small" label="Filter by District" />
                )}
                freeSolo
              />
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
                  onClick={handleCreateSchool}
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

      {/* Schools List */}
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
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
                    <TableCell sx={{ fontWeight: 700 }}>District</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Address</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Students</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Support Staff</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700 }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {schools.map((school) => (
                    <TableRow key={school.id} hover>
                      <TableCell>
                        <Box>
                          <Typography sx={{ fontWeight: 600 }}>{school.name}</Typography>
                          <Typography variant="body2" color="text.secondary">
                            {school.email || 'No contact email'}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>{school.district || '-'}</TableCell>
                      <TableCell>{school.address || '-'}</TableCell>
                      <TableCell>
                        <Button size="small" onClick={() => handleOpenDetails(school, 2)} sx={{ textTransform: 'none' }}>
                          {school.active_students_count ?? 0}
                        </Button>
                      </TableCell>
                      <TableCell>
                        <Button size="small" onClick={() => handleOpenDetails(school, 1)} sx={{ textTransform: 'none' }}>
                          {school.active_teachers_count ?? 0}
                        </Button>
                      </TableCell>
                      <TableCell align="right">
                        <Button
                          variant="outlined"
                          size="small"
                          startIcon={<Info />}
                          onClick={() => handleOpenDetails(school, 0)}
                          sx={{ color: '#40A8B6', borderColor: '#40A8B6', textTransform: 'none', mr: 1 }}
                        >
                          Details
                        </Button>
                        <IconButton
                          onClick={() => handleDeleteSchool(school)}
                          size="small"
                          sx={{ color: '#f44336' }}
                          title="Deactivate School"
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

      {/* School Form Dialog */}
      <Dialog 
        open={showForm} 
        onClose={handleFormClose}
        maxWidth="md" 
        fullWidth
      >
        <DialogTitle sx={{ bgcolor: '#40A8B6', color: 'white' }}>
          Add New School
        </DialogTitle>
        <DialogContent sx={{ p: 0 }}>
          <SchoolForm
            school={null}
            onSubmit={handleFormSubmit}
            onCancel={handleFormClose}
          />
        </DialogContent>
      </Dialog>

      <SchoolDetailsDialog
        open={showDetails}
        school={detailsSchool}
        initialTab={detailsInitialTab}
        onClose={() => {
          setShowDetails(false);
          setDetailsSchool(null);
        }}
        onSaved={async () => {
          await fetchSchools({
            is_active: showActiveOnly ? true : false,
            district: selectedDistrict || undefined,
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
