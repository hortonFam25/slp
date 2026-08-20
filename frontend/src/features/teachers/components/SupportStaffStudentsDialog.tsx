import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Divider,
  Dialog,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Select,
  Stack,
  Switch,
  Tab,
  Tabs,
  TextField,
  Typography
} from '@mui/material';
import { Close, GroupAdd, GroupRemove } from '@mui/icons-material';

import { studentsApi, type StudentSummary } from '../../../lib/api/students';
import type { Teacher } from '../../../lib/api/types/teachers';
import type { SupportStaffRole } from '../../../lib/api/types/teachers';
import { teachersApi } from '../../../lib/api/teachers';
import { schoolsApi } from '../../../lib/api/schools';
import type { SchoolSummary, TeacherSchoolAssignment } from '../../../lib/api/types/schools';
import { ConfirmationModal } from '../../../components/ui/ConfirmationModal';

type AddMode = 'case_manager' | 'teacher';
type PendingAction = 'add' | 'remove' | null;

interface TabPanelProps {
  children?: React.ReactNode;
  value: number;
  index: number;
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return (
    <Box
      role="tabpanel"
      hidden={value !== index}
      sx={{
        display: value === index ? 'flex' : 'none',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0
      }}
    >
      {value === index ? children : null}
    </Box>
  );
}

interface SupportStaffStudentsDialogProps {
  open: boolean;
  staff: Teacher | null;
  onClose: () => void;
  onAssignmentsChanged: () => Promise<void> | void;
}

export function SupportStaffStudentsDialog({
  open,
  staff,
  onClose,
  onAssignmentsChanged
}: SupportStaffStudentsDialogProps) {
  const [students, setStudents] = useState<StudentSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState('');
  const [addMode, setAddMode] = useState<AddMode>('case_manager');
  const [selectedAddIds, setSelectedAddIds] = useState<number[]>([]);
  const [selectedRemoveIds, setSelectedRemoveIds] = useState<number[]>([]);
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [activeTab, setActiveTab] = useState(0);
  const [profileSaving, setProfileSaving] = useState(false);
  const [roleOptions, setRoleOptions] = useState<SupportStaffRole[]>([]);
  const [schoolOptions, setSchoolOptions] = useState<SchoolSummary[]>([]);
  const [currentSchoolAssignments, setCurrentSchoolAssignments] = useState<TeacherSchoolAssignment[]>([]);
  const [profileForm, setProfileForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    title: '',
    department: '',
    room_number: '',
    notes: '',
    is_active: true,
    primary_school_id: '' as number | '',
    role_ids: [] as number[]
  });
  const [initialProfileForm, setInitialProfileForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    title: '',
    department: '',
    room_number: '',
    notes: '',
    is_active: true,
    primary_school_id: '' as number | '',
    role_ids: [] as number[]
  });

  useEffect(() => {
    if (!open || !staff) {
      return;
    }
    setActiveTab(0);
    const nextProfile = {
      first_name: staff.first_name || '',
      last_name: staff.last_name || '',
      email: staff.email || '',
      phone: staff.phone || '',
      title: staff.title || '',
      department: staff.department || '',
      room_number: staff.room_number || '',
      notes: staff.notes || '',
      is_active: staff.is_active ?? true,
      primary_school_id: '',
      role_ids: (staff.roles || []).map((role) => role.id)
    };
    setProfileForm(nextProfile);
    setInitialProfileForm(nextProfile);
    void loadRoles();
    void loadSchoolsAndPrimarySelection();
    void loadStudents();
  }, [open, staff?.id]);

  const loadStudents = async () => {
    if (!staff) {
      return;
    }
    setLoading(true);
    setError('');
    try {
      const scopedStudents = await studentsApi.getStudents({ enrollment_status: 'Active' });
      setStudents(scopedStudents);
      setSelectedAddIds([]);
      setSelectedRemoveIds([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load students');
    } finally {
      setLoading(false);
    }
  };

  const loadRoles = async () => {
    try {
      const roles = await teachersApi.getRoles(true);
      setRoleOptions(roles);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load support staff roles');
    }
  };

  const loadSchoolsAndPrimarySelection = async () => {
    if (!staff) {
      return;
    }
    try {
      const [schools, assignments] = await Promise.all([
        schoolsApi.getSchoolsSummary(true),
        teachersApi.getTeacherSchoolAssignments(staff.id)
      ]);
      const activeAssignments = assignments.filter((assignment) => !assignment.end_date);
      const primary = activeAssignments.find((assignment) => assignment.is_primary);

      setSchoolOptions(schools);
      setCurrentSchoolAssignments(activeAssignments);
      const selectedPrimarySchoolId = primary?.school_id ?? '';
      setProfileForm((prev) => ({ ...prev, primary_school_id: selectedPrimarySchoolId }));
      setInitialProfileForm((prev) => ({ ...prev, primary_school_id: selectedPrimarySchoolId }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load schools');
    }
  };

  const assignedStudents = useMemo(() => {
    if (!staff) {
      return [];
    }
    return students.filter((student) => student.teacher_id === staff.id || student.case_manager_id === staff.id);
  }, [students, staff]);

  const availableStudents = useMemo(() => {
    if (!staff) {
      return [];
    }
    return students.filter((student) => student.teacher_id !== staff.id && student.case_manager_id !== staff.id);
  }, [students, staff]);

  const normalizedSearch = searchTerm.trim().toLowerCase();
  const filteredAssignedStudents = useMemo(
    () =>
      assignedStudents.filter((student) =>
        `${student.first} ${student.last}`.toLowerCase().includes(normalizedSearch)
      ),
    [assignedStudents, normalizedSearch]
  );
  const filteredAvailableStudents = useMemo(
    () =>
      availableStudents.filter((student) =>
        `${student.first} ${student.last}`.toLowerCase().includes(normalizedSearch)
      ),
    [availableStudents, normalizedSearch]
  );

  const toggleSelectedId = (target: 'add' | 'remove', studentId: number) => {
    const setter = target === 'add' ? setSelectedAddIds : setSelectedRemoveIds;
    setter((prev) => (prev.includes(studentId) ? prev.filter((id) => id !== studentId) : [...prev, studentId]));
  };

  const runPendingAction = async () => {
    if (!staff || !pendingAction) {
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      if (pendingAction === 'add') {
        const selectedSet = new Set(selectedAddIds);
        const targets = availableStudents.filter((student) => selectedSet.has(student.id));
        for (const student of targets) {
          const payload: Record<string, number> = {};
          if (addMode === 'teacher' && student.teacher_id !== staff.id) {
            payload.teacher_id = staff.id;
          }
          if (addMode === 'case_manager' && student.case_manager_id !== staff.id) {
            payload.case_manager_id = staff.id;
          }
          if (Object.keys(payload).length > 0) {
            await studentsApi.updateStudent(student.id, payload);
          }
        }
      }

      if (pendingAction === 'remove') {
        const selectedSet = new Set(selectedRemoveIds);
        const targets = assignedStudents.filter((student) => selectedSet.has(student.id));
        for (const student of targets) {
          const payload: Record<string, number | null> = {};
          if (student.teacher_id === staff.id) {
            payload.teacher_id = null;
          }
          if (student.case_manager_id === staff.id) {
            payload.case_manager_id = null;
          }
          if (Object.keys(payload).length > 0) {
            await studentsApi.updateStudent(student.id, payload);
          }
        }
      }

      setConfirmOpen(false);
      setPendingAction(null);
      await loadStudents();
      await onAssignmentsChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update assignments');
    } finally {
      setSubmitting(false);
    }
  };

  const openConfirm = (action: PendingAction) => {
    setPendingAction(action);
    setConfirmOpen(true);
  };

  const confirmTitle =
    pendingAction === 'add' ? 'Confirm Student Assignments' : pendingAction === 'remove' ? 'Confirm Student Removals' : '';
  const confirmMessage =
    pendingAction === 'add'
      ? `Assign ${selectedAddIds.length} selected student(s) to ${staff?.first_name} ${staff?.last_name} as ${
          addMode === 'teacher' ? 'Teacher' : 'Case Manager'
        }?`
      : `Remove ${selectedRemoveIds.length} selected student assignment(s) from ${staff?.first_name} ${staff?.last_name}?`;

  const profileDirty = JSON.stringify(profileForm) !== JSON.stringify(initialProfileForm);

  const handleProfileFieldChange = (
    field: keyof typeof profileForm,
    value: string | boolean | number[] | number | ''
  ) => {
    setProfileForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleResetProfile = () => {
    setProfileForm(initialProfileForm);
  };

  const handleSaveProfile = async () => {
    if (!staff) {
      return;
    }
    setProfileSaving(true);
    setError('');
    try {
      await teachersApi.updateTeacher(staff.id, {
        first_name: profileForm.first_name.trim(),
        last_name: profileForm.last_name.trim(),
        email: profileForm.email.trim() || undefined,
        phone: profileForm.phone.trim() || undefined,
        title: profileForm.title.trim() || undefined,
        department: profileForm.department.trim() || undefined,
        room_number: profileForm.room_number.trim() || undefined,
        notes: profileForm.notes.trim() || undefined,
        is_active: profileForm.is_active,
        role_ids: profileForm.role_ids
      });

      const selectedPrimarySchoolId =
        typeof profileForm.primary_school_id === 'number' ? profileForm.primary_school_id : null;

      const activeAssignments = [...currentSchoolAssignments];
      const assignmentForSelectedSchool = selectedPrimarySchoolId
        ? activeAssignments.find((assignment) => assignment.school_id === selectedPrimarySchoolId)
        : undefined;

      if (selectedPrimarySchoolId && !assignmentForSelectedSchool) {
        const newAssignment = await teachersApi.createTeacherSchoolAssignment({
          teacher_id: staff.id,
          school_id: selectedPrimarySchoolId,
          start_date: new Date().toISOString().split('T')[0],
          is_primary: true
        });
        activeAssignments.push(newAssignment);
      }

      for (const assignment of activeAssignments) {
        const shouldBePrimary = selectedPrimarySchoolId !== null && assignment.school_id === selectedPrimarySchoolId;
        if (assignment.is_primary !== shouldBePrimary) {
          await teachersApi.updateTeacherSchoolAssignment(assignment.id, {
            teacher_id: assignment.teacher_id,
            school_id: assignment.school_id,
            start_date: assignment.start_date,
            end_date: assignment.end_date,
            is_primary: shouldBePrimary,
            notes: assignment.notes
          });
        }
      }

      const refreshed = { ...profileForm };
      setInitialProfileForm(refreshed);
      await loadSchoolsAndPrimarySelection();
      await onAssignmentsChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save profile');
    } finally {
      setProfileSaving(false);
    }
  };

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        maxWidth="lg"
        fullWidth
        PaperProps={{
          sx: {
            height: '85vh',
            maxHeight: '85vh',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column'
          }
        }}
      >
        <DialogTitle
          sx={{ bgcolor: '#40A8B6', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
        >
          <Typography variant="h6" component="span">
            Support Staff Details - {staff?.first_name} {staff?.last_name}
          </Typography>
          <IconButton onClick={onClose} size="small" sx={{ color: 'white' }}>
            <Close />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ p: 0, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' }}>
          {error && (
            <Alert severity="error" sx={{ m: 2 }} onClose={() => setError('')}>
              {error}
            </Alert>
          )}
          <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 2, flexShrink: 0 }}>
            <Tabs value={activeTab} onChange={(_, newValue) => setActiveTab(newValue)} variant="scrollable" scrollButtons="auto">
              <Tab label="Profile Information" />
              <Tab label="Student Assignments" />
            </Tabs>
          </Box>

          <Box sx={{ p: 2, flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <TabPanel value={activeTab} index={0}>
              <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2, overflow: 'auto', pt: 1 }}>
                <Box>
                  <TextField
                    fullWidth
                    size="small"
                    label="First Name"
                    value={profileForm.first_name}
                    onChange={(e) => handleProfileFieldChange('first_name', e.target.value)}
                  />
                </Box>
                <Box>
                  <TextField
                    fullWidth
                    size="small"
                    label="Last Name"
                    value={profileForm.last_name}
                    onChange={(e) => handleProfileFieldChange('last_name', e.target.value)}
                  />
                </Box>
                <Box>
                  <TextField
                    fullWidth
                    size="small"
                    label="Email"
                    value={profileForm.email}
                    onChange={(e) => handleProfileFieldChange('email', e.target.value)}
                  />
                </Box>
                <Box>
                  <TextField
                    fullWidth
                    size="small"
                    label="Phone"
                    value={profileForm.phone}
                    onChange={(e) => handleProfileFieldChange('phone', e.target.value)}
                  />
                </Box>
                <Box>
                  <TextField
                    fullWidth
                    size="small"
                    label="Title"
                    value={profileForm.title}
                    onChange={(e) => handleProfileFieldChange('title', e.target.value)}
                  />
                </Box>
                <Box>
                  <TextField
                    fullWidth
                    size="small"
                    label="Department"
                    value={profileForm.department}
                    onChange={(e) => handleProfileFieldChange('department', e.target.value)}
                  />
                </Box>
                <Box>
                  <TextField
                    fullWidth
                    size="small"
                    label="Room"
                    value={profileForm.room_number}
                    onChange={(e) => handleProfileFieldChange('room_number', e.target.value)}
                  />
                </Box>
                <Box>
                  <FormControl fullWidth size="small">
                    <InputLabel>Primary School</InputLabel>
                    <Select
                      value={profileForm.primary_school_id}
                      label="Primary School"
                      onChange={(e) =>
                        handleProfileFieldChange(
                          'primary_school_id',
                          e.target.value === '' ? '' : Number(e.target.value)
                        )
                      }
                    >
                      <MenuItem value="">No Primary School</MenuItem>
                      {schoolOptions.map((school) => (
                        <MenuItem key={school.id} value={school.id}>
                          {school.name}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Box>
                <Box sx={{ gridColumn: { xs: '1', md: '1 / -1' } }}>
                  <Autocomplete
                    multiple
                    options={roleOptions}
                    getOptionLabel={(option) => option.name}
                    value={roleOptions.filter((role) => profileForm.role_ids.includes(role.id))}
                    onChange={(_, selectedRoles) => handleProfileFieldChange('role_ids', selectedRoles.map((role) => role.id))}
                    renderInput={(params) => <TextField {...params} size="small" label="Roles" />}
                    isOptionEqualToValue={(option, value) => option.id === value.id}
                  />
                </Box>
                <Box sx={{ gridColumn: { xs: '1', md: '1 / -1' } }}>
                  <TextField
                    fullWidth
                    multiline
                    minRows={3}
                    size="small"
                    label="Notes"
                    value={profileForm.notes}
                    onChange={(e) => handleProfileFieldChange('notes', e.target.value)}
                  />
                </Box>
                <Box sx={{ gridColumn: { xs: '1', md: '1 / -1' } }}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={profileForm.is_active}
                        onChange={(e) => handleProfileFieldChange('is_active', e.target.checked)}
                        sx={{
                          '& .MuiSwitch-switchBase.Mui-checked': { color: '#40A8B6' },
                          '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { backgroundColor: '#40A8B6' }
                        }}
                      />
                    }
                    label={profileForm.is_active ? 'Active' : 'Inactive'}
                  />
                </Box>
              </Box>
              <Divider sx={{ my: 2 }} />
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                <Button variant="outlined" onClick={handleResetProfile} disabled={!profileDirty || profileSaving} sx={{ textTransform: 'none' }}>
                  Reset
                </Button>
                <Button
                  variant="contained"
                  onClick={() => void handleSaveProfile()}
                  disabled={!profileDirty || profileSaving || !profileForm.first_name.trim() || !profileForm.last_name.trim()}
                  sx={{ bgcolor: '#40A8B6', '&:hover': { bgcolor: '#369aa6' }, textTransform: 'none' }}
                >
                  {profileSaving ? 'Saving...' : 'Save Profile'}
                </Button>
              </Box>
            </TabPanel>

            <TabPanel value={activeTab} index={1}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                <Box>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                    Assigned Students ({assignedStudents.length})
                  </Typography>
                </Box>
              </Stack>

              <Stack
                direction={{ xs: 'column', md: 'row' }}
                spacing={2}
                sx={{ mb: 2, alignItems: { xs: 'stretch', md: 'center' }, flexWrap: { xs: 'nowrap', md: 'nowrap' } }}
              >
                <TextField
                  size="small"
                  label="Search Students"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  sx={{ flex: { xs: '1 1 auto', md: '1 1 420px' }, maxWidth: { md: 560 } }}
                />
                <FormControl size="small" sx={{ minWidth: 200 }}>
                  <InputLabel>Add As</InputLabel>
                  <Select value={addMode} label="Add As" onChange={(e) => setAddMode(e.target.value as AddMode)}>
                    <MenuItem value="case_manager">Case Manager</MenuItem>
                    <MenuItem value="teacher">Teacher</MenuItem>
                  </Select>
                </FormControl>
                <Button
                  variant="contained"
                  startIcon={<GroupAdd />}
                  onClick={() => openConfirm('add')}
                  disabled={selectedAddIds.length === 0 || loading || submitting}
                  sx={{ bgcolor: '#40A8B6', '&:hover': { bgcolor: '#369aa6' }, textTransform: 'none', whiteSpace: 'nowrap' }}
                >
                  Add Selected ({selectedAddIds.length})
                </Button>
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<GroupRemove />}
                  onClick={() => openConfirm('remove')}
                  disabled={selectedRemoveIds.length === 0 || loading || submitting}
                  sx={{ textTransform: 'none', whiteSpace: 'nowrap' }}
                >
                  Remove Selected ({selectedRemoveIds.length})
                </Button>
              </Stack>

              {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                  <CircularProgress />
                </Box>
              ) : (
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ flex: 1, minHeight: 0 }}>
                  <Box sx={{ flex: 1, border: '1px solid #e0e0e0', borderRadius: 2, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                    <Box sx={{ p: 1.5, borderBottom: '1px solid #e0e0e0', bgcolor: '#f8f9fa' }}>
                      <Typography sx={{ fontWeight: 600 }}>Assigned Students</Typography>
                    </Box>
                    <List dense sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
                      {filteredAssignedStudents.map((student) => (
                        <ListItem
                          key={`assigned-${student.id}`}
                          secondaryAction={
                            <Checkbox
                              edge="end"
                              checked={selectedRemoveIds.includes(student.id)}
                              onChange={() => toggleSelectedId('remove', student.id)}
                            />
                          }
                        >
                          <ListItemText
                            primary={`${student.first} ${student.last}`}
                            secondary={
                              <Stack direction="row" spacing={0.5}>
                                {student.teacher_id === staff?.id && <Chip size="small" label="Teacher" />}
                                {student.case_manager_id === staff?.id && <Chip size="small" label="Case Manager" />}
                              </Stack>
                            }
                          />
                        </ListItem>
                      ))}
                      {filteredAssignedStudents.length === 0 && (
                        <ListItem>
                          <ListItemText primary="No assigned students found." />
                        </ListItem>
                      )}
                    </List>
                  </Box>

                  <Box sx={{ flex: 1, border: '1px solid #e0e0e0', borderRadius: 2, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                    <Box sx={{ p: 1.5, borderBottom: '1px solid #e0e0e0', bgcolor: '#f8f9fa' }}>
                      <Typography sx={{ fontWeight: 600 }}>Available Students</Typography>
                    </Box>
                    <List dense sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
                      {filteredAvailableStudents.map((student) => (
                        <ListItem
                          key={`available-${student.id}`}
                          secondaryAction={
                            <Checkbox
                              edge="end"
                              checked={selectedAddIds.includes(student.id)}
                              onChange={() => toggleSelectedId('add', student.id)}
                            />
                          }
                        >
                          <ListItemText primary={`${student.first} ${student.last}`} />
                        </ListItem>
                      ))}
                      {filteredAvailableStudents.length === 0 && (
                        <ListItem>
                          <ListItemText primary="No available students found." />
                        </ListItem>
                      )}
                    </List>
                  </Box>
                </Stack>
              )}
            </TabPanel>
          </Box>
        </DialogContent>
      </Dialog>

      <ConfirmationModal
        open={confirmOpen}
        onClose={() => {
          if (!submitting) {
            setConfirmOpen(false);
            setPendingAction(null);
          }
        }}
        onConfirm={() => {
          void runPendingAction();
        }}
        title={confirmTitle}
        message={confirmMessage}
        confirmText={pendingAction === 'add' ? 'Confirm Add' : 'Confirm Remove'}
        severity={pendingAction === 'remove' ? 'warning' : 'info'}
        loading={submitting}
        loadingText="Applying..."
      />
    </>
  );
}

