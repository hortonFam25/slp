import { useQuery, UseQueryResult } from '@tanstack/react-query';
import { goalsApi } from '../api/goals';
import { IEPGoalWithObjectives } from '../api/types/goals';

// Hook to get active goals for a specific student
export function useStudentActiveGoals(
  studentId: number,
  enabled = true
): UseQueryResult<IEPGoalWithObjectives[]> {
  return useQuery({
    queryKey: ['goals', 'student', studentId, 'active'],
    queryFn: () => goalsApi.getStudentActiveGoals(studentId),
    enabled: enabled && !!studentId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Utility function to flatten goals and objectives for selection
export function flattenGoalsAndObjectives(goals: IEPGoalWithObjectives[]) {
  const flatGoals = goals.map(goal => ({
    id: goal.id,
    type: 'goal' as const,
    title: goal.goal_description,
    category: goal.goal_category,
    status: goal.status,
    parent: null,
  }));

  const flatObjectives = goals.flatMap(goal =>
    goal.objectives?.map(objective => ({
      id: objective.id,
      type: 'objective' as const,
      title: objective.objective_description,
      goalId: goal.id,
      goalTitle: goal.goal_description,
      status: objective.status,
      successRate: objective.success_rate,
      parent: goal.id,
    })) || []
  );

  return {
    goals: flatGoals,
    objectives: flatObjectives,
    all: [...flatGoals, ...flatObjectives],
  };
}

// Utility function to get selected goals and objectives
export function parseSelectedGoalsAndObjectives(
  selectedIds: number[],
  goals: IEPGoalWithObjectives[]
) {
  const selectedGoals: number[] = [];
  const selectedObjectives: number[] = [];

  selectedIds.forEach(id => {
    // Check if it's a goal
    const goal = goals.find(g => g.id === id);
    if (goal) {
      selectedGoals.push(id);
      return;
    }

    // Check if it's an objective
    const objective = goals.flatMap(g => g.objectives || []).find(o => o.id === id);
    if (objective) {
      selectedObjectives.push(id);
    }
  });

  return {
    goalIds: selectedGoals,
    objectiveIds: selectedObjectives,
  };
}
