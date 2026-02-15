import { apiClient } from './client';
import { BaseApiService } from './base';

// Goals CSV Import interfaces
export interface GoalImportResult {
  total_rows: number;
  successful_imports: number;
  failed_imports: number;
  skipped_duplicates: number;
  updated_existing: number;
  goals_created: number;
  objectives_created: number;
  progress_entries_created: number;
  errors: Array<{
    row: number;
    error: string;
    data?: any;
  }>;
  imported_goals: Array<{
    id: number;
    student_name: string;
    objectives_count: number;
    action: 'created' | 'updated';
  }>;
}

export interface GoalPreviewResult {
  filename: string;
  file_size: number;
  valid: boolean;
  total_rows: number;
  preview_rows: Array<{
    row_number: number;
    data: any;
    status: 'create' | 'update' | 'error';
    existing_goals_count?: number;
    error?: string;
    valid: boolean;
  }>;
  validation_errors: Array<{
    row: number;
    error: string;
    data: any;
  }>;
  has_more_rows: boolean;
}

export interface GoalImportOptions {
  skip_duplicates?: boolean;
  update_existing?: boolean;
  max_rows?: number;
  default_goal_category?: string;
}

class GoalsCSVApiService extends BaseApiService {
  constructor() {
    super('/api/goals-csv');
  }

  // Download Goals CSV template
  async downloadTemplate(): Promise<Blob> {
    const response = await apiClient.get('/api/goals-csv/template', {
      responseType: 'blob'
    });
    return response.data;
  }

  // Preview Goals CSV import
  async previewImport(
    file: File, 
    options: GoalImportOptions = {}
  ): Promise<GoalPreviewResult> {
    const formData = new FormData();
    formData.append('file', file);
    
    const queryParams: any = {};
    if (options.max_rows) {
      queryParams.max_rows = options.max_rows;
    }
    
    const response = await apiClient.post('/api/goals-csv/preview', formData, {
      params: queryParams,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    return response.data;
  }

  // Import goals from CSV file
  async importFromFile(
    file: File, 
    options: GoalImportOptions = {}
  ): Promise<GoalImportResult> {
    const formData = new FormData();
    formData.append('file', file);
    
    const queryParams: any = {};
    if (options.skip_duplicates !== undefined) {
      queryParams.skip_duplicates = options.skip_duplicates;
    }
    if (options.update_existing !== undefined) {
      queryParams.update_existing = options.update_existing;
    }
    if (options.default_goal_category) {
      queryParams.default_goal_category = options.default_goal_category;
    }
    
    const response = await apiClient.post('/api/goals-csv/import', formData, {
      params: queryParams,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    return response.data;
  }

  // Export goals to CSV
  async exportGoals(studentUic?: string): Promise<Blob> {
    const params = studentUic ? { student_uic: studentUic } : {};
    const response = await apiClient.get('/api/goals-csv/export', {
      params,
      responseType: 'blob'
    });
    return response.data;
  }

  // Helper method to download blob as file
  downloadBlob(blob: Blob, filename: string): void {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  }

  // Convenience method to download template
  async downloadTemplateFile(): Promise<void> {
    const blob = await this.downloadTemplate();
    this.downloadBlob(blob, 'goals_objectives_template.csv');
  }

  // Convenience method to export and download goals
  async exportAndDownloadGoals(studentUic?: string): Promise<void> {
    const blob = await this.exportGoals(studentUic);
    
    // Generate filename based on filters
    let filename = 'goals_export.csv';
    if (studentUic) {
      filename = `goals_for_uic_${studentUic}.csv`;
    }
    
    this.downloadBlob(blob, filename);
  }
}

// Export singleton instance
export const goalsCSVApi = new GoalsCSVApiService();

export default goalsCSVApi;
