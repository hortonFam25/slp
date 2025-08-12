import { apiClient } from './client';
import { BaseApiService } from './base';
import { API_ENDPOINTS } from './types';

// CSV Import interfaces
export interface CSVImportResult {
  total_rows: number;
  successful_imports: number;
  failed_imports: number;
  skipped_duplicates: number;
  updated_existing: number;
  errors: Array<{
    row: number;
    error: string;
    data?: any;
  }>;
  imported_students: Array<{
    id: number;
    name: string;
    uic?: string;
    action: 'created' | 'updated';
  }>;
}

export interface CSVPreviewResult {
  filename: string;
  file_size: number;
  valid: boolean;
  total_rows: number;
  preview_rows: Array<{
    row_number: number;
    data: any;
    status: 'create' | 'update' | 'error';
    existing_student?: {
      id: number;
      name: string;
    };
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

export interface CSVImportOptions {
  skip_duplicates?: boolean;
  update_existing?: boolean;
  max_rows?: number;
}

class CSVApiService extends BaseApiService {
  constructor() {
    super('/api/csv');
  }

  // Download CSV template
  async downloadTemplate(): Promise<Blob> {
    const response = await apiClient.get('/api/csv/template', {
      responseType: 'blob'
    });
    return response.data;
  }

  // Preview CSV import
  async previewImport(
    file: File, 
    options: CSVImportOptions = {}
  ): Promise<CSVPreviewResult> {
    const formData = new FormData();
    formData.append('file', file);
    
    const queryParams: any = {};
    if (options.max_rows) {
      queryParams.max_rows = options.max_rows;
    }
    
    const response = await apiClient.post('/api/csv/preview', formData, {
      params: queryParams,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    return response.data;
  }

  // Import students from CSV file
  async importFromFile(
    file: File, 
    options: CSVImportOptions = {}
  ): Promise<CSVImportResult> {
    const formData = new FormData();
    formData.append('file', file);
    
    const queryParams: any = {};
    if (options.skip_duplicates !== undefined) {
      queryParams.skip_duplicates = options.skip_duplicates;
    }
    if (options.update_existing !== undefined) {
      queryParams.update_existing = options.update_existing;
    }
    
    const response = await apiClient.post('/api/csv/import', formData, {
      params: queryParams,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    return response.data;
  }

  // Import students from CSV text content
  async importFromText(
    csvContent: string,
    options: CSVImportOptions = {}
  ): Promise<CSVImportResult> {
    return this.post<CSVImportResult>('/import-text', {
      file_content: csvContent,
      skip_duplicates: options.skip_duplicates ?? true,
      update_existing: options.update_existing ?? false,
    });
  }

  // Export students to CSV
  async exportStudents(filters: {
    enrollment_status?: string;
    case_manager?: string;
  } = {}): Promise<Blob> {
    const response = await apiClient.get('/api/csv/export', {
      params: filters,
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
    this.downloadBlob(blob, 'student_import_template.csv');
  }

  // Convenience method to export and download students
  async exportAndDownloadStudents(
    filters: { enrollment_status?: string; case_manager?: string } = {}
  ): Promise<void> {
    const blob = await this.exportStudents(filters);
    
    // Generate filename based on filters
    let filename = 'students_export.csv';
    if (filters.case_manager) {
      filename = `students_${filters.case_manager.replace(/\s+/g, '_')}.csv`;
    } else if (filters.enrollment_status) {
      filename = `students_${filters.enrollment_status.toLowerCase()}.csv`;
    }
    
    this.downloadBlob(blob, filename);
  }
}

// Export singleton instance
export const csvApi = new CSVApiService();

export default csvApi;
