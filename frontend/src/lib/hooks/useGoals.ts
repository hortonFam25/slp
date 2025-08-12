import { useState, useEffect, useCallback } from 'react';
import { goalsApi } from '../api/goals';
import type {
  IEPGoal,
  IEPGoalSummary,
  GoalObjective,
  ObjectiveProgressEntry,
  GoalCategory,
  CreateGoalRequest,
  UpdateGoalRequest,
  CreateObjectiveRequest,
  UpdateObjectiveRequest,
  CreateProgressEntryRequest,
  UpdateProgressEntryRequest,
  GoalsFilters
} from '../api/types/goals';

interface UseGoalsState {
  goals: IEPGoal[];
  goalCategories: GoalCategory[];
  loading: boolean;
  error: string | null;
}

interface UseGoalsActions {
  fetchGoals: (filters?: GoalsFilters) => Promise<void>;
  fetchStudentGoals: (studentId: number) => Promise<void>;
  fetchGoalCategories: () => Promise<void>;
  createGoal: (goal: CreateGoalRequest) => Promise<IEPGoal>;
  updateGoal: (goalId: number, updates: UpdateGoalRequest) => Promise<IEPGoal>;
  deleteGoal: (goalId: number) => Promise<void>;
  createObjective: (objective: CreateObjectiveRequest) => Promise<GoalObjective>;
  updateObjective: (objectiveId: number, updates: UpdateObjectiveRequest) => Promise<GoalObjective>;
  deleteObjective: (objectiveId: number) => Promise<void>;
  createProgressEntry: (entry: CreateProgressEntryRequest) => Promise<ObjectiveProgressEntry>;
  updateProgressEntry: (entryId: number, updates: UpdateProgressEntryRequest) => Promise<ObjectiveProgressEntry>;
  deleteProgressEntry: (entryId: number) => Promise<void>;
  refreshGoals: () => Promise<void>;
  clearError: () => void;
}

export function useGoals(initialFilters?: GoalsFilters): UseGoalsState & UseGoalsActions {
  const [state, setState] = useState<UseGoalsState>({
    goals: [],
    goalCategories: [],
    loading: false,
    error: null,
  });

  const [currentFilters, setCurrentFilters] = useState<GoalsFilters | undefined>(initialFilters);

  const setLoading = useCallback((loading: boolean) => {
    setState(prev => ({ ...prev, loading }));
  }, []);

  const setError = useCallback((error: string | null) => {
    setState(prev => ({ ...prev, error }));
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, [setError]);

  const fetchGoals = useCallback(async (filters?: GoalsFilters) => {
    try {
      setLoading(true);
      setError(null);
      setCurrentFilters(filters);
      const goals = await goalsApi.getGoals(filters);
      setState(prev => ({ ...prev, goals }));
    } catch (error) {
      console.error('Error fetching goals:', error);
      setError(error instanceof Error ? error.message : 'Failed to fetch goals');
    } finally {
      setLoading(false);
    }
  }, [setLoading, setError]);

  const fetchStudentGoals = useCallback(async (studentId: number) => {
    try {
      setLoading(true);
      setError(null);
      const goals = await goalsApi.getStudentGoals(studentId);
      setState(prev => ({ ...prev, goals }));
    } catch (error) {
      console.error('Error fetching student goals:', error);
      setError(error instanceof Error ? error.message : 'Failed to fetch student goals');
    } finally {
      setLoading(false);
    }
  }, [setLoading, setError]);

  const fetchGoalCategories = useCallback(async () => {
    try {
      const goalCategories = await goalsApi.getGoalCategories();
      setState(prev => ({ ...prev, goalCategories }));
    } catch (error) {
      console.error('Error fetching goal categories:', error);
      setError(error instanceof Error ? error.message : 'Failed to fetch goal categories');
    }
  }, [setError]);

  const createGoal = useCallback(async (goal: CreateGoalRequest): Promise<IEPGoal> => {
    try {
      setError(null);
      const newGoal = await goalsApi.createGoal(goal);
      setState(prev => ({ ...prev, goals: [...prev.goals, newGoal] }));
      return newGoal;
    } catch (error) {
      console.error('Error creating goal:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to create goal';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const updateGoal = useCallback(async (goalId: number, updates: UpdateGoalRequest): Promise<IEPGoal> => {
    try {
      setError(null);
      const updatedGoal = await goalsApi.updateGoal(goalId, updates);
      setState(prev => ({
        ...prev,
        goals: prev.goals.map(goal => goal.id === goalId ? updatedGoal : goal)
      }));
      return updatedGoal;
    } catch (error) {
      console.error('Error updating goal:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to update goal';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const deleteGoal = useCallback(async (goalId: number): Promise<void> => {
    try {
      setError(null);
      await goalsApi.deleteGoal(goalId);
      setState(prev => ({
        ...prev,
        goals: prev.goals.filter(goal => goal.id !== goalId)
      }));
    } catch (error) {
      console.error('Error deleting goal:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete goal';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const createObjective = useCallback(async (objective: CreateObjectiveRequest): Promise<GoalObjective> => {
    try {
      setError(null);
      const newObjective = await goalsApi.createObjective(objective);
      // Update the goals state to include the new objective
      setState(prev => ({
        ...prev,
        goals: prev.goals.map(goal => 
          goal.id === objective.goal_id 
            ? { ...goal, objectives: [...(goal.objectives || []), newObjective] }
            : goal
        )
      }));
      return newObjective;
    } catch (error) {
      console.error('Error creating objective:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to create objective';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const updateObjective = useCallback(async (objectiveId: number, updates: UpdateObjectiveRequest): Promise<GoalObjective> => {
    try {
      setError(null);
      const updatedObjective = await goalsApi.updateObjective(objectiveId, updates);
      // Update the goals state with the updated objective
      setState(prev => ({
        ...prev,
        goals: prev.goals.map(goal => ({
          ...goal,
          objectives: goal.objectives?.map(obj => 
            obj.id === objectiveId ? updatedObjective : obj
          )
        }))
      }));
      return updatedObjective;
    } catch (error) {
      console.error('Error updating objective:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to update objective';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const deleteObjective = useCallback(async (objectiveId: number): Promise<void> => {
    try {
      setError(null);
      await goalsApi.deleteObjective(objectiveId);
      // Remove objective from goals state
      setState(prev => ({
        ...prev,
        goals: prev.goals.map(goal => ({
          ...goal,
          objectives: goal.objectives?.filter(obj => obj.id !== objectiveId)
        }))
      }));
    } catch (error) {
      console.error('Error deleting objective:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete objective';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const createProgressEntry = useCallback(async (entry: CreateProgressEntryRequest): Promise<ObjectiveProgressEntry> => {
    try {
      setError(null);
      const newEntry = await goalsApi.createProgressEntry(entry);
      // Update the objectives with the new progress entry
      setState(prev => ({
        ...prev,
        goals: prev.goals.map(goal => ({
          ...goal,
          objectives: goal.objectives?.map(obj => 
            obj.id === entry.objective_id 
              ? { 
                  ...obj, 
                  progress_entries: [...(obj.progress_entries || []), newEntry],
                  progress_count: obj.progress_count + 1
                }
              : obj
          )
        }))
      }));
      return newEntry;
    } catch (error) {
      console.error('Error creating progress entry:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to create progress entry';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const updateProgressEntry = useCallback(async (entryId: number, updates: UpdateProgressEntryRequest): Promise<ObjectiveProgressEntry> => {
    try {
      setError(null);
      const updatedEntry = await goalsApi.updateProgressEntry(entryId, updates);
      // Update the progress entry in state
      setState(prev => ({
        ...prev,
        goals: prev.goals.map(goal => ({
          ...goal,
          objectives: goal.objectives?.map(obj => ({
            ...obj,
            progress_entries: obj.progress_entries?.map(entry => 
              entry.id === entryId ? updatedEntry : entry
            )
          }))
        }))
      }));
      return updatedEntry;
    } catch (error) {
      console.error('Error updating progress entry:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to update progress entry';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const deleteProgressEntry = useCallback(async (entryId: number): Promise<void> => {
    try {
      setError(null);
      await goalsApi.deleteProgressEntry(entryId);
      // Remove progress entry from state
      setState(prev => ({
        ...prev,
        goals: prev.goals.map(goal => ({
          ...goal,
          objectives: goal.objectives?.map(obj => ({
            ...obj,
            progress_entries: obj.progress_entries?.filter(entry => entry.id !== entryId),
            progress_count: Math.max(0, obj.progress_count - 1)
          }))
        }))
      }));
    } catch (error) {
      console.error('Error deleting progress entry:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete progress entry';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const refreshGoals = useCallback(async () => {
    if (currentFilters) {
      await fetchGoals(currentFilters);
    }
  }, [fetchGoals, currentFilters]);

  // Load goal categories on mount
  useEffect(() => {
    fetchGoalCategories();
  }, [fetchGoalCategories]);

  // Load initial goals if filters provided
  useEffect(() => {
    if (initialFilters) {
      fetchGoals(initialFilters);
    }
  }, [fetchGoals, initialFilters]);

  return {
    ...state,
    fetchGoals,
    fetchStudentGoals,
    fetchGoalCategories,
    createGoal,
    updateGoal,
    deleteGoal,
    createObjective,
    updateObjective,
    deleteObjective,
    createProgressEntry,
    updateProgressEntry,
    deleteProgressEntry,
    refreshGoals,
    clearError,
  };
}
