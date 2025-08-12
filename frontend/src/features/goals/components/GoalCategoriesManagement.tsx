import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  CircularProgress,
  Chip,
  Stack,
  useMediaQuery,
  useTheme
} from '@mui/material';
import {
  Add,
  Edit,
  Delete,
  Category,
  CheckCircle,
  Cancel
} from '@mui/icons-material';
import { goalsApi, GoalCategory } from '../../../lib/api/goals';

interface CategoryFormData {
  name: string;
  description: string;
  is_active: boolean;
}

export function GoalCategoriesManagement() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  const [categories, setCategories] = useState<GoalCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<GoalCategory | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState<CategoryFormData>({
    name: '',
    description: '',
    is_active: true
  });

  // Load categories
  useEffect(() => {
    loadCategories();
  }, []);

  const loadCategories = async () => {
    try {
      setLoading(true);
      setError(null);
      // Get all categories (both active and inactive)
      const data = await goalsApi.getGoalCategories(false);
      console.log('Goal Categories loaded:', data.length, 'categories:', data);
      setCategories(data);
    } catch (err) {
      console.error('Error loading goal categories:', err);
      setError(err instanceof Error ? err.message : 'Failed to load goal categories');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingCategory(null);
    setFormData({
      name: '',
      description: '',
      is_active: true
    });
    setDialogOpen(true);
  };

  const handleEdit = (category: GoalCategory) => {
    setEditingCategory(category);
    setFormData({
      name: category.name,
      description: category.description || '',
      is_active: category.is_active
    });
    setDialogOpen(true);
  };

  const handleDelete = async (category: GoalCategory) => {
    if (!window.confirm(`Are you sure you want to delete the category "${category.name}"?`)) {
      return;
    }

    try {
      setSubmitting(true);
      await goalsApi.deleteGoalCategory(category.id);
      setCategories(prev => prev.filter(c => c.id !== category.id));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete category';
      if (errorMessage.includes('currently in use')) {
        setError(`Cannot delete "${category.name}" because it is currently used by existing student goals. Please remove or reassign those goals first.`);
      } else {
        setError(errorMessage);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      setError('Category name is required');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);

      if (editingCategory) {
        const updated = await goalsApi.updateGoalCategory(editingCategory.id, formData);
        setCategories(prev => prev.map(c => 
          c.id === editingCategory.id ? updated : c
        ));
      } else {
        const newCategory = await goalsApi.createGoalCategory(formData);
        setCategories(prev => [...prev, newCategory]);
      }

      setDialogOpen(false);
      setEditingCategory(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to save category';
      if (errorMessage.includes('unique') || errorMessage.includes('duplicate')) {
        setError(`A category with the name "${formData.name}" already exists. Please choose a different name.`);
      } else {
        setError(errorMessage);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setDialogOpen(false);
    setEditingCategory(null);
    setError(null);
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: isMobile ? 'stretch' : 'center',
        flexDirection: isMobile ? 'column' : 'row',
        gap: isMobile ? 2 : 0,
        mb: 3 
      }}>
        <Box>
          <Typography 
            variant={isMobile ? "h6" : "h5"} 
            component="h2" 
            sx={{ 
              display: 'flex', 
              alignItems: 'center',
              fontSize: isMobile ? '1.2rem' : undefined
            }}
          >
            <Category sx={{ mr: 1, fontSize: isMobile ? 20 : 24 }} />
            Goal Categories
          </Typography>
          <Typography 
            variant="body2" 
            color="text.secondary"
            sx={{ fontSize: isMobile ? '0.85rem' : undefined }}
          >
            Manage categories used for organizing IEP goals
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={handleCreate}
          fullWidth={isMobile}
          size={isMobile ? 'medium' : 'large'}
          sx={{ fontSize: isMobile ? '0.9rem' : undefined }}
        >
          {isMobile ? "Add Category" : "Add New Category"}
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Categories Table/Cards */}
      {isMobile ? (
        // Mobile: Card-based layout
        <Box sx={{ 
          maxHeight: '60vh', 
          overflow: 'auto',
          '&::-webkit-scrollbar': {
            width: '8px',
          },
          '&::-webkit-scrollbar-track': {
            backgroundColor: '#f1f1f1',
            borderRadius: '4px',
          },
          '&::-webkit-scrollbar-thumb': {
            backgroundColor: '#c1c1c1',
            borderRadius: '4px',
            '&:hover': {
              backgroundColor: '#a8a8a8',
            },
          },
        }}>
          <Stack spacing={2}>
            {categories.map((category) => (
            <Card key={category.id} variant="outlined">
              <CardContent sx={{ p: 2 }}>
                <Box sx={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'flex-start',
                  mb: 1
                }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                    {category.name}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <IconButton
                      size="small"
                      onClick={() => handleEdit(category)}
                      sx={{ width: 32, height: 32 }}
                    >
                      <Edit fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleDelete(category)}
                      color="error"
                      sx={{ width: 32, height: 32 }}
                    >
                      <Delete fontSize="small" />
                    </IconButton>
                  </Box>
                </Box>
                
                {category.description && (
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    {category.description}
                  </Typography>
                )}
                
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Chip
                    label={category.is_active ? 'Active' : 'Inactive'}
                    color={category.is_active ? 'success' : 'default'}
                    size="small"
                    icon={category.is_active ? <CheckCircle /> : <Cancel />}
                  />
                  <Typography variant="caption" color="text.secondary">
                    ID: {category.id}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
            ))}
          </Stack>
        </Box>
      ) : (
        // Desktop: Table layout
        <TableContainer 
          component={Paper} 
          sx={{ 
            maxHeight: '60vh',
            overflow: 'auto',
            '&::-webkit-scrollbar': {
              width: '8px',
              height: '8px',
            },
            '&::-webkit-scrollbar-track': {
              backgroundColor: '#f1f1f1',
              borderRadius: '4px',
            },
            '&::-webkit-scrollbar-thumb': {
              backgroundColor: '#c1c1c1',
              borderRadius: '4px',
              '&:hover': {
                backgroundColor: '#a8a8a8',
              },
            },
          }}
        >
          <Table stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Description</TableCell>
                <TableCell align="center">Status</TableCell>
                <TableCell align="center">Created</TableCell>
                <TableCell align="center">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {categories.map((category) => (
                <TableRow key={category.id} hover>
                  <TableCell>
                    <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                      {category.name}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {category.description || 'No description'}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Chip
                      label={category.is_active ? 'Active' : 'Inactive'}
                      color={category.is_active ? 'success' : 'default'}
                      size="small"
                      icon={category.is_active ? <CheckCircle /> : <Cancel />}
                    />
                  </TableCell>
                  <TableCell align="center">
                    <Typography variant="body2" color="text.secondary">
                      {new Date(category.created_date).toLocaleDateString()}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip title="Edit Category">
                      <IconButton
                        size="small"
                        onClick={() => handleEdit(category)}
                      >
                        <Edit />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete Category">
                      <IconButton
                        size="small"
                        onClick={() => handleDelete(category)}
                        color="error"
                      >
                        <Delete />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {categories.length === 0 && !loading && (
        <Card>
          <CardContent sx={{ textAlign: 'center', py: 6 }}>
            <Category sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
            <Typography variant="h6" color="text.secondary" sx={{ mb: 1 }}>
              No Goal Categories
            </Typography>
            <Typography color="text.secondary" sx={{ mb: 3 }}>
              Create your first goal category to start organizing IEP goals.
            </Typography>
            <Button
              variant="outlined"
              startIcon={<Add />}
              onClick={handleCreate}
            >
              Add First Category
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Create/Edit Dialog */}
      <Dialog 
        open={dialogOpen} 
        onClose={handleClose}
        fullWidth
        maxWidth="sm"
        fullScreen={isMobile}
      >
        <DialogTitle>
          {editingCategory ? 'Edit Goal Category' : 'Create Goal Category'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <TextField
              fullWidth
              label="Category Name"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              margin="normal"
              required
              error={!formData.name.trim()}
              helperText={!formData.name.trim() ? 'Name is required' : ''}
            />
            <TextField
              fullWidth
              label="Description"
              value={formData.description}
              onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
              margin="normal"
              multiline
              rows={3}
              placeholder="Optional description for this category..."
            />
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Status
              </Typography>
              <Stack direction="row" spacing={1}>
                <Chip
                  label="Active"
                  color={formData.is_active ? 'success' : 'default'}
                  onClick={() => setFormData(prev => ({ ...prev, is_active: true }))}
                  variant={formData.is_active ? 'filled' : 'outlined'}
                  clickable
                />
                <Chip
                  label="Inactive"
                  color={!formData.is_active ? 'error' : 'default'}
                  onClick={() => setFormData(prev => ({ ...prev, is_active: false }))}
                  variant={!formData.is_active ? 'filled' : 'outlined'}
                  clickable
                />
              </Stack>
            </Box>
          </Box>
        </DialogContent>
        <DialogActions sx={{ p: 3 }}>
          <Button onClick={handleClose} disabled={submitting}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={submitting || !formData.name.trim()}
          >
            {submitting ? (
              <CircularProgress size={20} />
            ) : (
              editingCategory ? 'Update' : 'Create'
            )}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
