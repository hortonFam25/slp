import { useState, useEffect } from 'react';
import { studentsApi, StudentSummary, CreateStudentRequest, StudentsFilters } from '../api/students';

export function useStudents(filters?: StudentsFilters) {
  const [students, setStudents] = useState<StudentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStudents = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await studentsApi.getStudents(filters);
      setStudents(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load students');
    } finally {
      setLoading(false);
    }
  };

  const createStudent = async (data: CreateStudentRequest) => {
    try {
      setError(null);
      const newStudent = await studentsApi.createStudent(data);
      // Add to local state for immediate UI update
      setStudents(prev => [...prev, {
        id: newStudent.id,
        first: newStudent.first,
        last: newStudent.last,
        grade_level: newStudent.grade_level,
        case_manager: newStudent.case_manager,
        enrollment_status: newStudent.enrollment_status,
        is_archived: newStudent.is_archived,
      }]);
      return newStudent;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create student';
      setError(errorMessage);
      throw new Error(errorMessage);
    }
  };

  const deleteStudent = async (id: number) => {
    try {
      setError(null);
      await studentsApi.deleteStudent(id);
      // Remove from local state for immediate UI update
      setStudents(prev => prev.filter(student => student.id !== id));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete student';
      setError(errorMessage);
      throw new Error(errorMessage);
    }
  };

  const archiveStudent = async (id: number) => {
    try {
      setError(null);
      await studentsApi.archiveStudent(id);
      // Remove from local state for immediate UI update (archived students don't show in main list)
      setStudents(prev => prev.filter(student => student.id !== id));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to archive student';
      setError(errorMessage);
      throw new Error(errorMessage);
    }
  };

  const unarchiveStudent = async (id: number) => {
    try {
      setError(null);
      const unArchivedStudent = await studentsApi.unarchiveStudent(id);
      // Add back to local state for immediate UI update
      setStudents(prev => [...prev, {
        id: unArchivedStudent.id,
        first: unArchivedStudent.first,
        last: unArchivedStudent.last,
        grade_level: unArchivedStudent.grade_level,
        case_manager: unArchivedStudent.case_manager,
        enrollment_status: unArchivedStudent.enrollment_status,
        is_archived: unArchivedStudent.is_archived,
      }]);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to unarchive student';
      setError(errorMessage);
      throw new Error(errorMessage);
    }
  };

  useEffect(() => {
    loadStudents();
  }, [filters?.enrollment_status, filters?.case_manager]);

  return {
    students,
    loading,
    error,
    createStudent,
    deleteStudent,
    archiveStudent,
    unarchiveStudent,
    refetch: loadStudents,
  };
}
