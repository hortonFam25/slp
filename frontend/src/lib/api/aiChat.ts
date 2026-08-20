import { BaseApiService } from './base';
import { apiClient, buildAuthenticatedFetchHeaders } from './client';

export interface AIChatSession {
  id: number;
  student_id: number | null;
  student_alias: string | null;
  title?: string;
  created_date: string;
  modified_date: string;
}

export interface AIChatMessage {
  id: number;
  chat_session_id: number;
  role: 'user' | 'assistant';
  content: string;
  created_date: string;
}

export interface AIChatMessagePair {
  user_message: AIChatMessage;
  assistant_message: AIChatMessage;
}

export interface AIChatStreamEvent {
  type: string;
  source?: string;
  status?: string;
  label?: string;
  agent_name?: string;
  tool_name?: string;
  tool_call_id?: string;
  delta?: string;
  request_id?: string;
  sequence?: number;
  timestamp?: string;
  message?: AIChatMessage;
  fallback_used?: boolean;
}

export interface AISavedProgressNote {
  id: number;
  chat_session_id?: number;
  student_id: number;
  student_alias: string;
  title: string;
  note_content: string;
  template_version: string;
  status: string;
  created_date: string;
  modified_date: string;
}

export interface AIUpdateSavedProgressNotePayload {
  title?: string;
  note_content?: string;
  status?: string;
}

class AIChatApiService extends BaseApiService {
  constructor() {
    super('/api/ai-chat');
  }

  async createSession(studentId?: number, title?: string): Promise<AIChatSession> {
    return this.post<AIChatSession>('/sessions', {
      student_id: studentId,
      title,
    });
  }

  async listSessions(studentId?: number): Promise<AIChatSession[]> {
    const params = studentId ? { student_id: studentId } : undefined;
    return this.get<AIChatSession[]>('/sessions', params);
  }

  async deleteSession(sessionId: number): Promise<void> {
    return this.delete<void>(`/sessions/${sessionId}`);
  }

  async listMessages(sessionId: number): Promise<AIChatMessage[]> {
    return this.get<AIChatMessage[]>(`/sessions/${sessionId}/messages`);
  }

  async sendMessage(sessionId: number, content: string): Promise<AIChatMessage> {
    return this.post<AIChatMessage>(`/sessions/${sessionId}/messages`, { content });
  }

  async sendMessageStream(
    sessionId: number,
    content: string,
    handlers: {
      onDelta: (delta: string) => void;
      onDone: (message: AIChatMessage) => void;
      onEvent?: (event: AIChatStreamEvent) => void;
    }
  ): Promise<void> {
    const baseUrl = apiClient.defaults.baseURL || '';
    const headers = await buildAuthenticatedFetchHeaders({
      'Content-Type': 'application/json',
    });
    const response = await fetch(`${baseUrl}/api/ai-chat/sessions/${sessionId}/messages/stream`, {
      method: 'POST',
      credentials: 'include',
      headers,
      body: JSON.stringify({ content }),
    });

    if (!response.ok) {
      throw new Error(`Streaming request failed (${response.status})`);
    }

    if (!response.body) {
      throw new Error('Streaming response body is not available');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    const processEventBlock = (block: string) => {
      const lines = block
        .split('\n')
        .map((line) => line.trim())
        .filter((line) => line.startsWith('data:'));
      if (!lines.length) {
        return;
      }
      const dataText = lines.map((line) => line.replace(/^data:\s*/, '')).join('\n');
      if (!dataText) {
        return;
      }

      let payload: unknown;
      try {
        payload = JSON.parse(dataText);
      } catch {
        return;
      }
      if (!payload || typeof payload !== 'object') {
        return;
      }

      const typed = payload as Record<string, unknown>;
      const streamEvent: AIChatStreamEvent = {
        type: typeof typed.type === 'string' ? typed.type : '',
        source: typeof typed.source === 'string' ? typed.source : undefined,
        status: typeof typed.status === 'string' ? typed.status : undefined,
        label: typeof typed.label === 'string' ? typed.label : undefined,
        agent_name: typeof typed.agent_name === 'string' ? typed.agent_name : undefined,
        tool_name: typeof typed.tool_name === 'string' ? typed.tool_name : undefined,
        tool_call_id: typeof typed.tool_call_id === 'string' ? typed.tool_call_id : undefined,
        delta: typeof typed.delta === 'string' ? typed.delta : undefined,
        request_id: typeof typed.request_id === 'string' ? typed.request_id : undefined,
        sequence: typeof typed.sequence === 'number' ? typed.sequence : undefined,
        timestamp: typeof typed.timestamp === 'string' ? typed.timestamp : undefined,
        fallback_used: typeof typed.fallback_used === 'boolean' ? typed.fallback_used : undefined,
      };
      if (handlers.onEvent && streamEvent.type) {
        handlers.onEvent(streamEvent);
      }

      const eventType = typeof typed.type === 'string' ? typed.type : '';
      if (eventType === 'delta') {
        const delta = typeof typed.delta === 'string' ? typed.delta : '';
        if (delta) {
          handlers.onDelta(delta);
        }
        return;
      }
      if (eventType === 'done') {
        const message = typed.message as AIChatMessage | undefined;
        if (message && typeof message.id === 'number') {
          handlers.onDone(message);
        }
        return;
      }
      if (eventType === 'error') {
        const message = typeof typed.message === 'string' ? typed.message : 'Streaming request failed';
        throw new Error(message);
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';
      for (const part of parts) {
        processEventBlock(part);
      }
    }

    if (buffer.trim()) {
      processEventBlock(buffer);
    }
  }

  async deleteMessage(sessionId: number, messageId: number): Promise<void> {
    return this.delete<void>(`/sessions/${sessionId}/messages/${messageId}`);
  }

  async editAndRegenerateMessage(
    sessionId: number,
    messageId: number,
    content: string
  ): Promise<AIChatMessagePair> {
    return this.patch<AIChatMessagePair>(
      `/sessions/${sessionId}/messages/${messageId}/edit-and-regenerate`,
      { content }
    );
  }

  async saveProgressNote(
    sessionId: number,
    payload: { title: string; note_content: string; template_version?: string; status?: string }
  ): Promise<AISavedProgressNote> {
    return this.post<AISavedProgressNote>(`/sessions/${sessionId}/save-progress-note`, payload);
  }

  async listSavedProgressNotes(studentId?: number): Promise<AISavedProgressNote[]> {
    const params = studentId ? { student_id: studentId } : undefined;
    return this.get<AISavedProgressNote[]>('/saved-progress-notes', params);
  }

  async updateSavedProgressNote(
    noteId: number,
    payload: AIUpdateSavedProgressNotePayload
  ): Promise<AISavedProgressNote> {
    return this.patch<AISavedProgressNote>(`/saved-progress-notes/${noteId}`, payload);
  }

  async deleteSavedProgressNote(noteId: number): Promise<void> {
    return this.delete<void>(`/saved-progress-notes/${noteId}`);
  }
}

export const aiChatApi = new AIChatApiService();

