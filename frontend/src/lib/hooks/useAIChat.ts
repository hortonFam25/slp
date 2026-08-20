import { useEffect, useState } from 'react';

import {
  aiChatApi,
  AIChatMessage,
  AIChatSession,
  AISavedProgressNote,
  AIChatStreamEvent,
  AIUpdateSavedProgressNotePayload,
} from '../api/aiChat';

export function useAIChat(selectedStudentId: number | null) {
  const [sessions, setSessions] = useState<AIChatSession[]>([]);
  const [session, setSession] = useState<AIChatSession | null>(null);
  const [messages, setMessages] = useState<AIChatMessage[]>([]);
  const [savedNotes, setSavedNotes] = useState<AISavedProgressNote[]>([]);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [streamingMessageId, setStreamingMessageId] = useState<number | null>(null);
  const [streamActiveAgent, setStreamActiveAgent] = useState<string | null>(null);
  const [streamToolNames, setStreamToolNames] = useState<string[]>([]);
  const [streamHasStartedResponse, setStreamHasStartedResponse] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      setError(null);
      try {
        const loadedSessions = await aiChatApi.listSessions(selectedStudentId ?? undefined);
        const scopedSessions =
          selectedStudentId == null
            ? loadedSessions.filter((item) => item.student_id == null)
            : loadedSessions.filter((item) => item.student_id === selectedStudentId);

        const activeSession =
          scopedSessions[0] ??
          (await aiChatApi.createSession(
            selectedStudentId ?? undefined,
            selectedStudentId == null ? 'General AI Chat' : 'Progress Notes Chat'
          ));

        const allSessions = scopedSessions.length > 0 ? scopedSessions : [activeSession];
        setSessions(allSessions);
        setSession(activeSession);

        const sessionMessages = await aiChatApi.listMessages(activeSession.id);
        setMessages(sessionMessages);
        if (selectedStudentId == null) {
          setSavedNotes([]);
        } else {
          const notes = await aiChatApi.listSavedProgressNotes(selectedStudentId);
          setSavedNotes(notes);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to initialize chat');
      } finally {
        setLoading(false);
      }
    };
    init();
  }, [selectedStudentId]);

  const sendMessage = async (content: string) => {
    if (!session) {
      throw new Error('No active chat session');
    }
    if (!content.trim()) {
      return;
    }

    setSending(true);
    setError(null);
    setStreamingMessageId(null);
    setStreamActiveAgent(null);
    setStreamToolNames([]);
    setStreamHasStartedResponse(false);
    const optimisticUserMessage: AIChatMessage = {
      id: Date.now(),
      chat_session_id: session.id,
      role: 'user',
      content,
      created_date: new Date().toISOString(),
    };
    const optimisticAssistantMessage: AIChatMessage = {
      id: Date.now() + 1,
      chat_session_id: session.id,
      role: 'assistant',
      content: '',
      created_date: new Date().toISOString(),
    };
    setStreamingMessageId(optimisticAssistantMessage.id);
    setMessages((prev) => [...prev, optimisticUserMessage, optimisticAssistantMessage]);
    try {
      let finalizedMessage: AIChatMessage | null = null;
      let responseStarted = false;
      await aiChatApi.sendMessageStream(session.id, content, {
        onDelta: (delta: string) => {
          if (!responseStarted) {
            responseStarted = true;
            setStreamHasStartedResponse(true);
            setStreamActiveAgent(null);
            setStreamToolNames([]);
          }
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === optimisticAssistantMessage.id
                ? {
                    ...msg,
                    content: msg.content + delta,
                  }
                : msg
            )
          );
        },
        onDone: (assistantMessage: AIChatMessage) => {
          finalizedMessage = assistantMessage;
          setMessages((prev) =>
            prev.map((msg) => (msg.id === optimisticAssistantMessage.id ? assistantMessage : msg))
          );
        },
        onEvent: (event: AIChatStreamEvent) => {
          if (responseStarted) {
            return;
          }
          if (event.type === 'agent_update' && event.agent_name) {
            setStreamActiveAgent(event.agent_name);
            return;
          }
          if (event.type === 'tool_call_started' && event.tool_name) {
            setStreamToolNames((prev) => {
              if (prev.includes(event.tool_name as string)) {
                return prev;
              }
              const next = [...prev, event.tool_name as string];
              return next.slice(-6);
            });
          }
        },
      });
      if (finalizedMessage) {
        return finalizedMessage;
      }
      throw new Error('No assistant response returned');
    } catch (err) {
      setMessages((prev) =>
        prev.filter((msg) => msg.id !== optimisticUserMessage.id && msg.id !== optimisticAssistantMessage.id)
      );
      const message = err instanceof Error ? err.message : 'Failed to send message';
      setError(message);
      throw new Error(message);
    } finally {
      setStreamingMessageId(null);
      setStreamActiveAgent(null);
      setStreamToolNames([]);
      setStreamHasStartedResponse(false);
      setSending(false);
    }
  };

  const saveLatestAssistantAsNote = async (title: string): Promise<AISavedProgressNote> => {
    if (!session) {
      throw new Error('No active chat session');
    }
    const lastAssistant = [...messages].reverse().find((msg) => msg.role === 'assistant');
    if (!lastAssistant) {
      throw new Error('No assistant message available to save');
    }
    const saved = await aiChatApi.saveProgressNote(session.id, {
      title,
      note_content: lastAssistant.content,
      template_version: 'v1',
      status: 'draft',
    });
    setSavedNotes((prev) => [saved, ...prev]);
    return saved;
  };

  const saveAssistantMessageAsNote = async (
    messageContent: string,
    title: string
  ): Promise<AISavedProgressNote> => {
    if (!session) {
      throw new Error('No active chat session');
    }
    const saved = await aiChatApi.saveProgressNote(session.id, {
      title,
      note_content: messageContent,
      template_version: 'v1',
      status: 'draft',
    });
    setSavedNotes((prev) => [saved, ...prev]);
    return saved;
  };

  const deleteMessage = async (messageId: number): Promise<void> => {
    if (!session) {
      throw new Error('No active chat session');
    }
    await aiChatApi.deleteMessage(session.id, messageId);
    const refreshed = await aiChatApi.listMessages(session.id);
    setMessages(refreshed);
  };

  const editLastUserMessage = async (messageId: number, content: string): Promise<void> => {
    if (!session) {
      throw new Error('No active chat session');
    }
    if (!content.trim()) {
      throw new Error('Message content cannot be empty');
    }
    setSending(true);
    setError(null);
    try {
      const pair = await aiChatApi.editAndRegenerateMessage(session.id, messageId, content);
      setMessages((prev) =>
        prev.map((item) => {
          if (item.id === pair.user_message.id) {
            return pair.user_message;
          }
          if (item.id === pair.assistant_message.id) {
            return pair.assistant_message;
          }
          return item;
        })
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to edit message';
      setError(message);
      throw new Error(message);
    } finally {
      setSending(false);
    }
  };

  const selectSession = async (sessionId: number) => {
    const selected = sessions.find((item) => item.id === sessionId);
    if (!selected) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const sessionMessages = await aiChatApi.listMessages(sessionId);
      setSession(selected);
      setMessages(sessionMessages);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load session');
    } finally {
      setLoading(false);
    }
  };

  const createNewSession = async (title?: string): Promise<AIChatSession> => {
    const created = await aiChatApi.createSession(
      selectedStudentId ?? undefined,
      title || (selectedStudentId == null ? 'General AI Chat' : 'Progress Notes Chat')
    );
    setSessions((prev) => [created, ...prev]);
    setSession(created);
    setMessages([]);
    return created;
  };

  const deleteSession = async (sessionId: number): Promise<void> => {
    await aiChatApi.deleteSession(sessionId);
    const remainingSessions = sessions.filter((item) => item.id !== sessionId);
    if (session?.id === sessionId) {
      if (remainingSessions.length > 0) {
        const nextSession = remainingSessions[0];
        const nextMessages = await aiChatApi.listMessages(nextSession.id);
        setSessions(remainingSessions);
        setSession(nextSession);
        setMessages(nextMessages);
        return;
      }
      const created = await aiChatApi.createSession(
        selectedStudentId ?? undefined,
        selectedStudentId == null ? 'General AI Chat' : 'Progress Notes Chat'
      );
      setSessions([created]);
      setSession(created);
      setMessages([]);
      return;
    }
    setSessions(remainingSessions);
  };

  const refreshSavedNotes = async () => {
    if (!selectedStudentId) {
      setSavedNotes([]);
      return;
    }
    const notes = await aiChatApi.listSavedProgressNotes(selectedStudentId);
    setSavedNotes(notes);
  };

  const updateSavedProgressNote = async (
    noteId: number,
    payload: AIUpdateSavedProgressNotePayload
  ): Promise<AISavedProgressNote> => {
    const updated = await aiChatApi.updateSavedProgressNote(noteId, payload);
    setSavedNotes((prev) => prev.map((item) => (item.id === noteId ? updated : item)));
    return updated;
  };

  const deleteSavedProgressNote = async (noteId: number): Promise<void> => {
    await aiChatApi.deleteSavedProgressNote(noteId);
    setSavedNotes((prev) => prev.filter((item) => item.id !== noteId));
  };

  return {
    sessions,
    session,
    messages,
    savedNotes,
    loading,
    sending,
    streamingMessageId,
    streamActiveAgent,
    streamToolNames,
    streamHasStartedResponse,
    error,
    sendMessage,
    selectSession,
    createNewSession,
    deleteSession,
    refreshSavedNotes,
    updateSavedProgressNote,
    deleteSavedProgressNote,
    saveLatestAssistantAsNote,
    saveAssistantMessageAsNote,
    deleteMessage,
    editLastUserMessage,
  };
}

