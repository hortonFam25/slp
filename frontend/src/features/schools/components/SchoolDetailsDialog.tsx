import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Stack,
  Switch,
  Tab,
  Tabs,
  TextField,
  Typography
} from '@mui/material';
import { Close, GroupAdd, GroupRemove } from '@mui/icons-material';

import { schoolsApi } from '../../../lib/api/schools';
import { teachersApi } from '../../../lib/api/teachers';
import type { School } from '../../../lib/api/types/schools';
import type { Teacher, TeacherSummary } from '../../../lib/api/types/teachers';
import { studentsApi, type StudentSummary } from '../../../lib/api/students';
import { ConfirmationModal } from '../../../components/ui/ConfirmationModal';

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
      sx={{ display: value === index ? 'flex' : 'none', flexDirection: 'column', flex: 1, minHeight: 0 }}
    >
      {value === index ? children : null}
    </Box>
  );
}

interface SchoolDetailsDialogProps {
  open: boolean;
  school: School | null;
  onClose: () => void;
  onSaved: () => Promise<void> | void;
  initialTab?: number;
}

export function SchoolDetailsDialog({ open, school, onClose, onSaved, initialTab = 0 }: SchoolDetailsDialogProps) {
  const [activeTab, setActiveTab] = useState(0);
  const [loadingStaff, setLoadingStaff] = useState(false);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [loadingAllStaff, setLoadingAllStaff] = useState(false);
  const [staffSubmitting, setStaffSubmitting] = useState(false);
  const [studentsSubmitting, setStudentsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [assignedStaff, setAssignedStaff] = useState<TeacherSummary[]>([]);
  const [allStaff, setAllStaff] = useState<Teacher[]>([]);
  const [students, setStudents] = useState<StudentSummary[]>([]);
  const [staffSearch, setStaffSearch] = useState('');
  const [studentSearch, setStudentSearch] = useState('');
  const [selectedAddStaffIds, setSelectedAddStaffIds] = useState<number[]>([]);
  const [selectedRemoveStaffIds, setSelectedRemoveStaffIds] = useState<number[]>([]);
  const [selectedAddStudentIds, setSelectedAddStudentIds] = useState<number[]>([]);
  const [selectedRemoveStudentIds, setSelectedRemoveStudentIds] = useState<number[]>([]);
  const [staffConfirmOpen, setStaffConfirmOpen] = useState(false);
  const [pendingStaffAction, setPendingStaffAction] = useState<'add' | 'remove' | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingStudentAction, setPendingStudentAction] = useState<'add' | 'remove' | null>(null);

  const [profileForm, setProfileForm] = useState({
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
  const [initialProfileForm, setInitialProfileForm] = useState(profileForm);

  useEffect(() => {
    if (!open || !school) {
      return;
    }
    setActiveTab(initialTab);
    const nextProfile = {
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
    };
    setProfileForm(nextProfile);
    setInitialProfileForm(nextProfile);
    void loadAssignedStaff();
    void loadAllStaff();
    void loadStudents();
  }, [open, school?.id, initialTab]);

  const loadAssignedStaff = async () => {
    if (!school) {
      return;
    }
    setLoadingStaff(true);
    setError('');
    try {
      const staff = await teachersApi.getTeachersBySchool(school.id, true);
      setAssignedStaff(staff);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load support staff assignments');
    } finally {
      setLoadingStaff(false);
    }
  };

  const loadAllStaff = async () => {
    setLoadingAllStaff(true);
    setError('');
    try {
      const staff = await teachersApi.getTeachers({ is_active: true, limit: 1000 });
      setAllStaff(staff);
      setSelectedAddStaffIds([]);
      setSelectedRemoveStaffIds([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load support staff list');
    } finally {
      setLoadingAllStaff(false);
    }
  };

  const loadStudents = async () => {
    if (!school) {
      return;
    }
    setLoadingStudents(true);
    setError('');
    try {
      const scopedStudents = await studentsApi.getStudents({ enrollment_status: 'Active' });
      setStudents(scopedStudents);
      setSelectedAddStudentIds([]);
      setSelectedRemoveStudentIds([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load student assignments');
    } finally {
      setLoadingStudents(false);
    }
  };

  const profileDirty = JSON.stringify(profileForm) !== JSON.stringify(initialProfileForm);

  const handleProfileFieldChange = (field: keyof typeof profileForm, value: string | boolean) => {
    setProfileForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleResetProfile = () => {
    setProfileForm(initialProfileForm);
  };

  const handleSaveProfile = async () => {
    if (!school) {
      return;
    }
    setSavingProfile(true);
    setError('');
    try {
      await schoolsApi.updateSchool(school.id, {
        name: profileForm.name.trim(),
        address: profileForm.address.trim() || undefined,
        phone: profileForm.phone.trim() || undefined,
        email: profileForm.email.trim() || undefined,
        district: profileForm.district.trim() || undefined,
        principal_name: profileForm.principal_name.trim() || undefined,
        contact_person: profileForm.contact_person.trim() || undefined,
        contact_phone: profileForm.contact_phone.trim() || undefined,
        notes: profileForm.notes.trim() || undefined,
        is_active: profileForm.is_active
      });
      const refreshed = { ...profileForm };
      setInitialProfileForm(refreshed);
      await onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save school profile');
    } finally {
      setSavingProfile(false);
    }
  };

  const assignedStudents = students.filter((student) => student.school_id === school?.id);
  const availableStudents = students.filter((student) => student.school_id !== school?.id);
  const normalizedStudentSearch = studentSearch.trim().toLowerCase();
  const filteredAssignedStudents = assignedStudents.filter((student) =>
    `${student.first} ${student.last}`.toLowerCase().includes(normalizedStudentSearch)
  );
  const filteredAvailableStudents = availableStudents.filter((student) =>
    `${student.first} ${student.last}`.toLowerCase().includes(normalizedStudentSearch)
  );

  const toggleStudentSelection = (target: 'add' | 'remove', studentId: number) => {
    const setter = target === 'add' ? setSelectedAddStudentIds : setSelectedRemoveStudentIds;
    setter((prev) => (prev.includes(studentId) ? prev.filter((id) => id !== studentId) : [...prev, studentId]));
  };

  const executeStudentAssignmentChange = async () => {
    if (!school || !pendingStudentAction) {
      return;
    }
    setStudentsSubmitting(true);
    setError('');
    try {
      if (pendingStudentAction === 'add') {
        const selectedSet = new Set(selectedAddStudentIds);
        const targets = availableStudents.filter((student) => selectedSet.has(student.id));
        for (const student of targets) {
          await studentsApi.updateStudent(student.id, { school_id: school.id });
        }
      }

      if (pendingStudentAction === 'remove') {
        const selectedSet = new Set(selectedRemoveStudentIds);
        const targets = assignedStudents.filter((student) => selectedSet.has(student.id));
        for (const student of targets) {
          await studentsApi.updateStudent(student.id, { school_id: null });
        }
      }

      setConfirmOpen(false);
      setPendingStudentAction(null);
      await loadStudents();
      await onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update student assignments');
    } finally {
      setStudentsSubmitting(false);
    }
  };

  const assignedStaffIds = new Set(assignedStaff.map((staffMember) => staffMember.id));
  const availableStaff = allStaff.filter((staffMember) => !assignedStaffIds.has(staffMember.id));
  const normalizedStaffSearch = staffSearch.trim().toLowerCase();
  const filteredAssignedStaff = assignedStaff.filter((staffMember) =>
    staffMember.full_name.toLowerCase().includes(normalizedStaffSearch)
  );
  const filteredAvailableStaff = availableStaff.filter((staffMember) =>
    staffMember.full_name.toLowerCase().includes(normalizedStaffSearch)
  );

  const toggleStaffSelection = (target: 'add' | 'remove', staffId: number) => {
    const setter = target === 'add' ? setSelectedAddStaffIds : setSelectedRemoveStaffIds;
    setter((prev) => (prev.includes(staffId) ? prev.filter((id) => id !== staffId) : [...prev, staffId]));
  };

  const executeStaffAssignmentChange = async () => {
    if (!school || !pendingStaffAction) {
      return;
    }
    setStaffSubmitting(true);
    setError('');
    try {
      if (pendingStaffAction === 'add') {
        for (const teacherId of selectedAddStaffIds) {
          await teachersApi.createTeacherSchoolAssignment({
            teacher_id: teacherId,
            school_id: school.id,
            start_date: new Date().toISOString().split('T')[0],
            is_primary: false
          });
        }
      }

      if (pendingStaffAction === 'remove') {
        for (const teacherId of selectedRemoveStaffIds) {
          const assignments = await teachersApi.getTeacherSchoolAssignments(teacherId);
          const matchingAssignments = assignments.filter(
            (assignment) => assignment.school_id === school.id && !assignment.end_date
          );
          for (const assignment of matchingAssignments) {
            await teachersApi.deleteTeacherSchoolAssignment(assignment.id);
          }
        }
      }

      setStaffConfirmOpen(false);
      setPendingStaffAction(null);
      await Promise.all([loadAssignedStaff(), loadAllStaff()]);
      await onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update support staff assignments');
    } finally {
      setStaffSubmitting(false);
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
        sx: { height: '85vh', maxHeight: '85vh', overflow: 'hidden', display: 'flex', flexDirection: 'column' }
      }}
    >
      <DialogTitle sx={{ bgcolor: '#40A8B6', color: 'white', display: 'flex', justifyContent: 'space-between' }}>
        <Typography variant="h6">School Details - {school?.name}</Typography>
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
          <Tabs value={activeTab} onChange={(_, value) => setActiveTab(value)} variant="scrollable" scrollButtons="auto">
            <Tab label="Profile Information" />
            <Tab label="Support Staff Assignments" />
            <Tab label="Student Assignments" />
          </Tabs>
        </Box>

        <Box sx={{ p: 2, flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <TabPanel value={activeTab} index={0}>
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2, overflow: 'auto', pt: 1 }}>
              <TextField fullWidth size="small" label="School Name" value={profileForm.name} onChange={(e) => handleProfileFieldChange('name', e.target.value)} />
              <TextField fullWidth size="small" label="District" value={profileForm.district} onChange={(e) => handleProfileFieldChange('district', e.target.value)} />
              <TextField fullWidth size="small" label="Email" value={profileForm.email} onChange={(e) => handleProfileFieldChange('email', e.target.value)} />
              <TextField fullWidth size="small" label="Phone" value={profileForm.phone} onChange={(e) => handleProfileFieldChange('phone', e.target.value)} />
              <TextField fullWidth size="small" label="Principal Name" value={profileForm.principal_name} onChange={(e) => handleProfileFieldChange('principal_name', e.target.value)} />
              <TextField fullWidth size="small" label="Primary Contact Person" value={profileForm.contact_person} onChange={(e) => handleProfileFieldChange('contact_person', e.target.value)} />
              <TextField fullWidth size="small" label="Contact Phone" value={profileForm.contact_phone} onChange={(e) => handleProfileFieldChange('contact_phone', e.target.value)} />
              <TextField fullWidth size="small" label="Address" value={profileForm.address} onChange={(e) => handleProfileFieldChange('address', e.target.value)} />
              <Box sx={{ gridColumn: { xs: '1', md: '1 / -1' } }}>
                <TextField fullWidth size="small" multiline minRows={3} label="Notes" value={profileForm.notes} onChange={(e) => handleProfileFieldChange('notes', e.target.value)} />
              </Box>
              <Box sx={{ gridColumn: { xs: '1', md: '1 / -1' }, display: 'flex', alignItems: 'center', gap: 1 }}>
                <Switch
                  checked={profileForm.is_active}
                  onChange={(e) => handleProfileFieldChange('is_active', e.target.checked)}
                  sx={{
                    '& .MuiSwitch-switchBase.Mui-checked': { color: '#40A8B6' },
                    '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { backgroundColor: '#40A8B6' }
                  }}
                />
                <Typography variant="body2" color="text.secondary">
                  {profileForm.is_active ? 'Active' : 'Inactive'}
                </Typography>
              </Box>
            </Box>
            <Divider sx={{ my: 2 }} />
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
              <Button variant="outlined" onClick={handleResetProfile} disabled={!profileDirty || savingProfile} sx={{ textTransform: 'none' }}>
                Reset
              </Button>
              <Button
                variant="contained"
                onClick={() => void handleSaveProfile()}
                disabled={!profileDirty || savingProfile || !profileForm.name.trim()}
                sx={{ bgcolor: '#40A8B6', '&:hover': { bgcolor: '#369aa6' }, textTransform: 'none' }}
              >
                {savingProfile ? 'Saving...' : 'Save Profile'}
              </Button>
            </Box>
          </TabPanel>

          <TabPanel value={activeTab} index={1}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
              <TextField
                size="small"
                label="Search Support Staff"
                value={staffSearch}
                onChange={(e) => setStaffSearch(e.target.value)}
                sx={{ flex: 1, maxWidth: 520 }}
              />
              <Box sx={{ display: 'flex', gap: 1, ml: 2 }}>
                <Button
                  variant="contained"
                  startIcon={<GroupAdd />}
                  onClick={() => {
                    setPendingStaffAction('add');
                    setStaffConfirmOpen(true);
                  }}
                  disabled={selectedAddStaffIds.length === 0 || loadingStaff || loadingAllStaff || staffSubmitting}
                  sx={{ bgcolor: '#40A8B6', '&:hover': { bgcolor: '#369aa6' }, textTransform: 'none' }}
                >
                  Add Selected ({selectedAddStaffIds.length})
                </Button>
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<GroupRemove />}
                  onClick={() => {
                    setPendingStaffAction('remove');
                    setStaffConfirmOpen(true);
                  }}
                  disabled={selectedRemoveStaffIds.length === 0 || loadingStaff || loadingAllStaff || staffSubmitting}
                  sx={{ textTransform: 'none' }}
                >
                  Remove Selected ({selectedRemoveStaffIds.length})
                </Button>
              </Box>
            </Stack>

            {loadingStaff || loadingAllStaff ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                <CircularProgress />
              </Box>
            ) : (
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ flex: 1, minHeight: 0 }}>
                <Box sx={{ flex: 1, border: '1px solid #e0e0e0', borderRadius: 2, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                  <Box sx={{ p: 1.5, borderBottom: '1px solid #e0e0e0', bgcolor: '#f8f9fa' }}>
                    <Typography sx={{ fontWeight: 600 }}>Assigned Support Staff ({assignedStaff.length})</Typography>
                  </Box>
                  <List dense sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
                    {filteredAssignedStaff.map((staffMember) => (
                      <ListItem
                        key={`assigned-staff-${staffMember.id}`}
                        secondaryAction={
                          <Checkbox
                            edge="end"
                            checked={selectedRemoveStaffIds.includes(staffMember.id)}
                            onChange={() => toggleStaffSelection('remove', staffMember.id)}
                          />
                        }
                      >
                        <ListItemText
                          primary={staffMember.full_name}
                          secondary={staffMember.email || staffMember.title || 'No additional details'}
                        />
                      </ListItem>
                    ))}
                    {filteredAssignedStaff.length === 0 && (
                      <ListItem>
                        <ListItemText primary="No assigned support staff found." />
                      </ListItem>
                    )}
                  </List>
                </Box>

                <Box sx={{ flex: 1, border: '1px solid #e0e0e0', borderRadius: 2, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                  <Box sx={{ p: 1.5, borderBottom: '1px solid #e0e0e0', bgcolor: '#f8f9fa' }}>
                    <Typography sx={{ fontWeight: 600 }}>Available Support Staff</Typography>
                  </Box>
                  <List dense sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
                    {filteredAvailableStaff.map((staffMember) => (
                      <ListItem
                        key={`available-staff-${staffMember.id}`}
                        secondaryAction={
                          <Checkbox
                            edge="end"
                            checked={selectedAddStaffIds.includes(staffMember.id)}
                            onChange={() => toggleStaffSelection('add', staffMember.id)}
                          />
                        }
                      >
                        <ListItemText
                          primary={staffMember.full_name}
                          secondary={staffMember.email || staffMember.title || 'No additional details'}
                        />
                      </ListItem>
                    ))}
                    {filteredAvailableStaff.length === 0 && (
                      <ListItem>
                        <ListItemText primary="No available support staff found." />
                      </ListItem>
                    )}
                  </List>
                </Box>
              </Stack>
            )}
          </TabPanel>

          <TabPanel value={activeTab} index={2}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
              <TextField
                size="small"
                label="Search Students"
                value={studentSearch}
                onChange={(e) => setStudentSearch(e.target.value)}
                sx={{ flex: 1, maxWidth: 520 }}
              />
              <Box sx={{ display: 'flex', gap: 1, ml: 2 }}>
                <Button
                  variant="contained"
                  startIcon={<GroupAdd />}
                  onClick={() => {
                    setPendingStudentAction('add');
                    setConfirmOpen(true);
                  }}
                  disabled={selectedAddStudentIds.length === 0 || loadingStudents || studentsSubmitting}
                  sx={{ bgcolor: '#40A8B6', '&:hover': { bgcolor: '#369aa6' }, textTransform: 'none' }}
                >
                  Add Selected ({selectedAddStudentIds.length})
                </Button>
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<GroupRemove />}
                  onClick={() => {
                    setPendingStudentAction('remove');
                    setConfirmOpen(true);
                  }}
                  disabled={selectedRemoveStudentIds.length === 0 || loadingStudents || studentsSubmitting}
                  sx={{ textTransform: 'none' }}
                >
                  Remove Selected ({selectedRemoveStudentIds.length})
                </Button>
              </Box>
            </Stack>

            {loadingStudents ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                <CircularProgress />
              </Box>
            ) : (
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ flex: 1, minHeight: 0 }}>
                <Box sx={{ flex: 1, border: '1px solid #e0e0e0', borderRadius: 2, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                  <Box sx={{ p: 1.5, borderBottom: '1px solid #e0e0e0', bgcolor: '#f8f9fa' }}>
                    <Typography sx={{ fontWeight: 600 }}>Assigned Students ({assignedStudents.length})</Typography>
                  </Box>
                  <List dense sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
                    {filteredAssignedStudents.map((student) => (
                      <ListItem
                        key={`assigned-student-${student.id}`}
                        secondaryAction={
                          <Checkbox
                            edge="end"
                            checked={selectedRemoveStudentIds.includes(student.id)}
                            onChange={() => toggleStudentSelection('remove', student.id)}
                          />
                        }
                      >
                        <ListItemText primary={`${student.first} ${student.last}`} />
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
                        key={`available-student-${student.id}`}
                        secondaryAction={
                          <Checkbox
                            edge="end"
                            checked={selectedAddStudentIds.includes(student.id)}
                            onChange={() => toggleStudentSelection('add', student.id)}
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
      open={staffConfirmOpen}
      onClose={() => {
        if (!staffSubmitting) {
          setStaffConfirmOpen(false);
          setPendingStaffAction(null);
        }
      }}
      onConfirm={() => {
        void executeStaffAssignmentChange();
      }}
      title={pendingStaffAction === 'add' ? 'Confirm Support Staff Assignments' : 'Confirm Support Staff Removals'}
      message={
        pendingStaffAction === 'add'
          ? `Assign ${selectedAddStaffIds.length} selected support staff member(s) to ${school?.name}?`
          : `Remove ${selectedRemoveStaffIds.length} selected support staff assignment(s) from ${school?.name}?`
      }
      confirmText={pendingStaffAction === 'add' ? 'Confirm Add' : 'Confirm Remove'}
      severity={pendingStaffAction === 'remove' ? 'warning' : 'info'}
      loading={staffSubmitting}
      loadingText="Applying..."
    />

    <ConfirmationModal
      open={confirmOpen}
      onClose={() => {
        if (!studentsSubmitting) {
          setConfirmOpen(false);
          setPendingStudentAction(null);
        }
      }}
      onConfirm={() => {
        void executeStudentAssignmentChange();
      }}
      title={pendingStudentAction === 'add' ? 'Confirm Student Assignments' : 'Confirm Student Removals'}
      message={
        pendingStudentAction === 'add'
          ? `Assign ${selectedAddStudentIds.length} selected student(s) to ${school?.name}?`
          : `Remove ${selectedRemoveStudentIds.length} selected student assignment(s) from ${school?.name}?`
      }
      confirmText={pendingStudentAction === 'add' ? 'Confirm Add' : 'Confirm Remove'}
      severity={pendingStudentAction === 'remove' ? 'warning' : 'info'}
      loading={studentsSubmitting}
      loadingText="Applying..."
    />
    </>
  );
}

