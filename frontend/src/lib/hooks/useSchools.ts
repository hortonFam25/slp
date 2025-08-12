import { useState, useEffect, useCallback } from 'react';
import { schoolsApi } from '../api/schools';
import type {
  School,
  SchoolSummary,
  CreateSchoolRequest,
  UpdateSchoolRequest,
  SchoolsFilters,
  SchoolStatistics
} from '../api/types/schools';

interface UseSchoolsState {
  schools: School[];
  schoolsSummary: SchoolSummary[];
  loading: boolean;
  error: string | null;
  districts: string[];
}

interface UseSchoolsActions {
  fetchSchools: (filters?: SchoolsFilters) => Promise<void>;
  fetchSchoolsSummary: (activeOnly?: boolean) => Promise<void>;
  fetchDistricts: () => Promise<void>;
  createSchool: (school: CreateSchoolRequest) => Promise<School>;
  updateSchool: (schoolId: number, updates: UpdateSchoolRequest) => Promise<School>;
  deleteSchool: (schoolId: number) => Promise<void>;
  getSchool: (schoolId: number) => Promise<School>;
  getSchoolStatistics: (schoolId: number) => Promise<SchoolStatistics>;
  refreshSchools: () => Promise<void>;
  clearError: () => void;
}

export function useSchools(initialFilters?: SchoolsFilters): UseSchoolsState & UseSchoolsActions {
  const [state, setState] = useState<UseSchoolsState>({
    schools: [],
    schoolsSummary: [],
    loading: false,
    error: null,
    districts: []
  });

  const [currentFilters, setCurrentFilters] = useState<SchoolsFilters | undefined>(initialFilters);

  const setLoading = useCallback((loading: boolean) => {
    setState(prev => ({ ...prev, loading }));
  }, []);

  const setError = useCallback((error: string | null) => {
    setState(prev => ({ ...prev, error }));
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, [setError]);

  const fetchSchools = useCallback(async (filters?: SchoolsFilters) => {
    try {
      setLoading(true);
      setError(null);
      setCurrentFilters(filters);
      const schools = await schoolsApi.getSchools(filters);
      setState(prev => ({ ...prev, schools }));
    } catch (error) {
      console.error('Error fetching schools:', error);
      setError(error instanceof Error ? error.message : 'Failed to fetch schools');
    } finally {
      setLoading(false);
    }
  }, [setLoading, setError]);

  const fetchSchoolsSummary = useCallback(async (activeOnly = true) => {
    try {
      setError(null);
      const schoolsSummary = await schoolsApi.getSchoolsSummary(activeOnly);
      setState(prev => ({ ...prev, schoolsSummary }));
    } catch (error) {
      console.error('Error fetching schools summary:', error);
      setError(error instanceof Error ? error.message : 'Failed to fetch schools summary');
    }
  }, [setError]);

  const fetchDistricts = useCallback(async () => {
    try {
      const districts = await schoolsApi.getDistricts();
      setState(prev => ({ ...prev, districts }));
    } catch (error) {
      console.error('Error fetching districts:', error);
      setError(error instanceof Error ? error.message : 'Failed to fetch districts');
    }
  }, [setError]);

  const createSchool = useCallback(async (school: CreateSchoolRequest): Promise<School> => {
    try {
      setError(null);
      const newSchool = await schoolsApi.createSchool(school);
      setState(prev => ({ ...prev, schools: [...prev.schools, newSchool] }));
      return newSchool;
    } catch (error) {
      console.error('Error creating school:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to create school';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const updateSchool = useCallback(async (schoolId: number, updates: UpdateSchoolRequest): Promise<School> => {
    try {
      setError(null);
      const updatedSchool = await schoolsApi.updateSchool(schoolId, updates);
      setState(prev => ({
        ...prev,
        schools: prev.schools.map(school => school.id === schoolId ? updatedSchool : school)
      }));
      return updatedSchool;
    } catch (error) {
      console.error('Error updating school:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to update school';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const deleteSchool = useCallback(async (schoolId: number): Promise<void> => {
    try {
      setError(null);
      await schoolsApi.deleteSchool(schoolId);
      setState(prev => ({
        ...prev,
        schools: prev.schools.map(school => 
          school.id === schoolId ? { ...school, is_active: false } : school
        )
      }));
    } catch (error) {
      console.error('Error deleting school:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete school';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const getSchool = useCallback(async (schoolId: number): Promise<School> => {
    try {
      setError(null);
      return await schoolsApi.getSchool(schoolId);
    } catch (error) {
      console.error('Error fetching school:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to fetch school';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const getSchoolStatistics = useCallback(async (schoolId: number): Promise<SchoolStatistics> => {
    try {
      setError(null);
      return await schoolsApi.getSchoolStatistics(schoolId);
    } catch (error) {
      console.error('Error fetching school statistics:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to fetch school statistics';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const refreshSchools = useCallback(async () => {
    if (currentFilters) {
      await fetchSchools(currentFilters);
    }
  }, [fetchSchools, currentFilters]);

  // Load initial data
  useEffect(() => {
    if (initialFilters) {
      fetchSchools(initialFilters);
    }
    fetchDistricts();
  }, [fetchSchools, fetchDistricts, initialFilters]);

  return {
    ...state,
    fetchSchools,
    fetchSchoolsSummary,
    fetchDistricts,
    createSchool,
    updateSchool,
    deleteSchool,
    getSchool,
    getSchoolStatistics,
    refreshSchools,
    clearError,
  };
}
