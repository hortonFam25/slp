import { useEffect, useState, type KeyboardEvent, type MouseEvent } from 'react';
import {
  Alert,
  Autocomplete,
  Avatar,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Drawer,
  IconButton,
  Menu,
  MenuItem,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { Timeline as TimelineIcon } from '@mui/icons-material';
import {
  Bot,
  ChevronLeft,
  ChevronRight,
  Copy,
  Menu as MenuIcon,
  MessageSquare,
  Pencil,
  Plus,
  Save,
  SendHorizonal,
  Trash2,
  User,
  X,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { AIChatMessage, AIChatSession, AISavedProgressNote } from '../../lib/api/aiChat';
import { ConfirmationModal } from '../../components/ui/ConfirmationModal';
import { StudentTherapyHistoryDialog } from '../../components/StudentTherapyHistoryDialog';
import { useStudents } from '../../lib/hooks/useStudents';
import { StudentSummary } from '../../lib/api/students';
import { useAIChat } from '../../lib/hooks/useAIChat';

function getStudentLabel(student: StudentSummary): string {
  const grade = student.grade_level ? ` - Grade ${student.grade_level}` : '';
  return `${student.first} ${student.last}${grade}`;
}

function formatMessageTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
}

function markdownSignature(content: string) {
  return {
    h1ToH6: (content.match(/^#{1,6}\s/gm) || []).length,
    bullets: (content.match(/^\s*[-*+]\s/gm) || []).length,
    ordered: (content.match(/^\s*\d+\.\s/gm) || []).length,
    quotes: (content.match(/^\s*>\s/gm) || []).length,
    fences: (content.match(/```/g) || []).length,
    tableLines: (content.match(/^\s*\|.*\|\s*$/gm) || []).length,
    hr: (content.match(/^\s*([-*_]){3,}\s*$/gm) || []).length,
  };
}

function signaturesMatch(a: string, b: string): boolean {
  const left = markdownSignature(a);
  const right = markdownSignature(b);
  return Object.keys(left).every((key) => left[key as keyof typeof left] === right[key as keyof typeof right]);
}

function formatToolName(toolName: string): string {
  return toolName
    .replace(/[_-]+/g, ' ')
    .replace(/\bget\b/gi, 'Load')
    .replace(/\bsave\b/gi, 'Save')
    .replace(/\bread\b/gi, 'Read')
    .replace(/\bwrite\b/gi, 'Write')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

const RIGHT_SIDEBAR_EXPANDED_WIDTH = 288;
const RIGHT_SIDEBAR_COLLAPSED_WIDTH = 56;

type EditableMarkdownLine = {
  kind: 'text' | 'table';
  prefix: string;
  content: string;
  editable: boolean;
  lockedRaw: string;
  tableIndent: string;
  tableCells: string[];
};

function parseEditableMarkdownLines(markdown: string): EditableMarkdownLine[] {
  const lines = markdown.split('\n');
  const parsed: EditableMarkdownLine[] = [];
  let inFence = false;

  for (const line of lines) {
    if (/^\s*```/.test(line)) {
      inFence = !inFence;
      parsed.push({
        kind: 'text',
        prefix: '',
        content: '',
        editable: false,
        lockedRaw: line,
        tableIndent: '',
        tableCells: [],
      });
      continue;
    }

    if (inFence) {
      parsed.push({
        kind: 'text',
        prefix: '',
        content: '',
        editable: false,
        lockedRaw: line,
        tableIndent: '',
        tableCells: [],
      });
      continue;
    }

    if (line.trim() === '') {
      parsed.push({
        kind: 'text',
        prefix: '',
        content: '',
        editable: false,
        lockedRaw: '',
        tableIndent: '',
        tableCells: [],
      });
      continue;
    }

    if (/^\s*([-*_]){3,}\s*$/.test(line)) {
      parsed.push({
        kind: 'text',
        prefix: '',
        content: '',
        editable: false,
        lockedRaw: line,
        tableIndent: '',
        tableCells: [],
      });
      continue;
    }

    const tableSeparatorRegex = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/;
    if (tableSeparatorRegex.test(line)) {
      parsed.push({
        kind: 'text',
        prefix: '',
        content: '',
        editable: false,
        lockedRaw: line,
        tableIndent: '',
        tableCells: [],
      });
      continue;
    }

    if (/^\s*\|.*\|\s*$/.test(line)) {
      const indent = (line.match(/^(\s*)/)?.[1] ?? '');
      const trimmed = line.trim().replace(/^\|/, '').replace(/\|$/, '');
      const cells = trimmed.split('|').map((cell) => cell.trim());
      parsed.push({
        kind: 'table',
        prefix: '',
        content: '',
        editable: true,
        lockedRaw: '',
        tableIndent: indent,
        tableCells: cells,
      });
      continue;
    }

    const headingMatch = line.match(/^(\s*#{1,6}\s+)(.*)$/);
    if (headingMatch) {
      parsed.push({
        kind: 'text',
        prefix: headingMatch[1],
        content: headingMatch[2],
        editable: true,
        lockedRaw: '',
        tableIndent: '',
        tableCells: [],
      });
      continue;
    }

    const taskListMatch = line.match(/^(\s*[-*+]\s+\[[ xX]\]\s+)(.*)$/);
    if (taskListMatch) {
      parsed.push({
        kind: 'text',
        prefix: taskListMatch[1],
        content: taskListMatch[2],
        editable: true,
        lockedRaw: '',
        tableIndent: '',
        tableCells: [],
      });
      continue;
    }

    const bulletMatch = line.match(/^(\s*[-*+]\s+)(.*)$/);
    if (bulletMatch) {
      parsed.push({
        kind: 'text',
        prefix: bulletMatch[1],
        content: bulletMatch[2],
        editable: true,
        lockedRaw: '',
        tableIndent: '',
        tableCells: [],
      });
      continue;
    }

    const orderedMatch = line.match(/^(\s*\d+\.\s+)(.*)$/);
    if (orderedMatch) {
      parsed.push({
        kind: 'text',
        prefix: orderedMatch[1],
        content: orderedMatch[2],
        editable: true,
        lockedRaw: '',
        tableIndent: '',
        tableCells: [],
      });
      continue;
    }

    const quoteMatch = line.match(/^(\s*>\s+)(.*)$/);
    if (quoteMatch) {
      parsed.push({
        kind: 'text',
        prefix: quoteMatch[1],
        content: quoteMatch[2],
        editable: true,
        lockedRaw: '',
        tableIndent: '',
        tableCells: [],
      });
      continue;
    }

    parsed.push({
      kind: 'text',
      prefix: '',
      content: line,
      editable: true,
      lockedRaw: '',
      tableIndent: '',
      tableCells: [],
    });
  }

  return parsed;
}

function rebuildMarkdownFromLines(lines: EditableMarkdownLine[]): string {
  return lines
    .map((line) => {
      if (!line.editable) {
        return line.lockedRaw;
      }
      if (line.kind === 'table') {
        return `${line.tableIndent}| ${line.tableCells.join(' | ')} |`;
      }
      return `${line.prefix}${line.content}`;
    })
    .join('\n');
}

export default function Chat() {
  const { students, loading: studentsLoading } = useStudents({ include_archived: false });
  const [selectedStudent, setSelectedStudent] = useState<StudentSummary | null>(null);
  const [draft, setDraft] = useState('');
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true);
  const [sidebarTab, setSidebarTab] = useState(0);
  const [activeNote, setActiveNote] = useState<AISavedProgressNote | null>(null);
  const [noteDraft, setNoteDraft] = useState('');
  const [noteSaving, setNoteSaving] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);
  const [noteEditorMode, setNoteEditorMode] = useState<'preview' | 'edit'>('preview');
  const [noteEditableLines, setNoteEditableLines] = useState<EditableMarkdownLine[]>([]);
  const [tableCellEditor, setTableCellEditor] = useState<{
    lineIndex: number;
    cellIndex: number;
    value: string;
  } | null>(null);
  const [pendingSaveMessage, setPendingSaveMessage] = useState<AIChatMessage | null>(null);
  const [pendingDeleteMessage, setPendingDeleteMessage] = useState<AIChatMessage | null>(null);
  const [pendingDeleteNote, setPendingDeleteNote] = useState<AISavedProgressNote | null>(null);
  const [pendingDeleteSession, setPendingDeleteSession] = useState<AIChatSession | null>(null);
  const [saveMessageLoading, setSaveMessageLoading] = useState(false);
  const [deleteMessageLoading, setDeleteMessageLoading] = useState(false);
  const [deleteNoteLoading, setDeleteNoteLoading] = useState(false);
  const [deleteSessionLoading, setDeleteSessionLoading] = useState(false);
  const [saveAsAnchorEl, setSaveAsAnchorEl] = useState<null | HTMLElement>(null);
  const [saveAsMessage, setSaveAsMessage] = useState<AIChatMessage | null>(null);
  const [therapyHistoryOpen, setTherapyHistoryOpen] = useState(false);

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!saveStatus) {
      return;
    }
    const timeoutId = window.setTimeout(() => {
      setSaveStatus(null);
    }, 4000);
    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [saveStatus]);

  const {
    sessions,
    session,
    messages,
    savedNotes,
    loading: chatLoading,
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
    updateSavedProgressNote,
    deleteSavedProgressNote,
    saveAssistantMessageAsNote,
    deleteMessage,
    editLastUserMessage,
  } = useAIChat(selectedStudent?.id ?? null);

  const lastUserMessageId = [...messages].reverse().find((item) => item.role === 'user')?.id ?? null;

  const onSend = async () => {
    const content = draft.trim();
    if (!content || sending) {
      return;
    }
    await sendMessage(content);
    setDraft('');
  };

  const onDraftKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void onSend();
    }
  };

  const buildDefaultMessageSaveTitle = () => {
    const fallbackName = selectedStudent ? `${selectedStudent.first} ${selectedStudent.last}` : 'Student';
    const datePart = new Date().toLocaleDateString();
    return `${fallbackName} - Progress Note ${datePart}`;
  };

  const handleCopyAssistantMessage = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setSaveStatus('Copied message to clipboard');
    } catch (_err) {
      setSaveStatus('Failed to copy message');
    }
  };

  const onConfirmSaveMessage = async () => {
    if (!pendingSaveMessage) return;
    setSaveMessageLoading(true);
    try {
      const saved = await saveAssistantMessageAsNote(
        pendingSaveMessage.content,
        buildDefaultMessageSaveTitle()
      );
      setSaveStatus(`Saved note #${saved.id} (${saved.status})`);
      setPendingSaveMessage(null);
    } catch (err) {
      setSaveStatus(err instanceof Error ? err.message : 'Failed to save progress note');
    } finally {
      setSaveMessageLoading(false);
    }
  };

  const onConfirmDeleteMessage = async () => {
    if (!pendingDeleteMessage) return;
    setDeleteMessageLoading(true);
    try {
      await deleteMessage(pendingDeleteMessage.id);
      setSaveStatus('Message deleted');
      setPendingDeleteMessage(null);
    } catch (err) {
      setSaveStatus(err instanceof Error ? err.message : 'Failed to delete message');
    } finally {
      setDeleteMessageLoading(false);
    }
  };

  const onEditUserMessage = async (message: AIChatMessage) => {
    const next = window.prompt('Edit your message', message.content);
    if (!next) {
      return;
    }
    const normalized = next.trim();
    if (!normalized || normalized === message.content) {
      return;
    }
    try {
      await editLastUserMessage(message.id, normalized);
      setSaveStatus('Updated message and regenerated assistant response.');
    } catch (err) {
      setSaveStatus(err instanceof Error ? err.message : 'Failed to edit message');
    }
  };

  const onConfirmDeleteNote = async () => {
    if (!pendingDeleteNote) return;
    setDeleteNoteLoading(true);
    try {
      await deleteSavedProgressNote(pendingDeleteNote.id);
      if (activeNote?.id === pendingDeleteNote.id) {
        onCloseNote();
      }
      setSaveStatus('Progress note deleted');
      setPendingDeleteNote(null);
    } catch (err) {
      setSaveStatus(err instanceof Error ? err.message : 'Failed to delete progress note');
    } finally {
      setDeleteNoteLoading(false);
    }
  };

  const onOpenSaveAsMenu = (event: MouseEvent<HTMLButtonElement>, message: AIChatMessage) => {
    setSaveAsAnchorEl(event.currentTarget);
    setSaveAsMessage(message);
  };

  const onCloseSaveAsMenu = () => {
    setSaveAsAnchorEl(null);
    setSaveAsMessage(null);
  };

  const onSaveAsProgressNote = () => {
    if (!saveAsMessage) {
      return;
    }
    setPendingSaveMessage(saveAsMessage);
    onCloseSaveAsMenu();
  };

  const onCreateSession = async () => {
    try {
      const label = selectedStudent ? `${selectedStudent.first} ${selectedStudent.last}` : 'General AI';
      const title = window.prompt('New chat title', `${label} - Chat ${sessions.length + 1}`);
      if (!title) {
        return;
      }
      await createNewSession(title.trim());
      setSaveStatus('New chat session created.');
      setSidebarTab(0);
    } catch (err) {
      setSaveStatus(err instanceof Error ? err.message : 'Failed to create a new chat');
    }
  };

  const handleOpenTherapyHistory = () => {
    if (!selectedStudent) {
      return;
    }
    setTherapyHistoryOpen(true);
  };

  const handleCloseTherapyHistory = () => {
    setTherapyHistoryOpen(false);
  };

  const onOpenNote = (note: AISavedProgressNote) => {
    setActiveNote(note);
    setNoteDraft(note.note_content);
    setNoteEditableLines(parseEditableMarkdownLines(note.note_content));
    setNoteEditorMode('preview');
    setNoteError(null);
  };

  const onConfirmDeleteSession = async () => {
    if (!pendingDeleteSession) return;
    setDeleteSessionLoading(true);
    try {
      await deleteSession(pendingDeleteSession.id);
      setSaveStatus('Chat session deleted');
      setPendingDeleteSession(null);
    } catch (err) {
      setSaveStatus(err instanceof Error ? err.message : 'Failed to delete chat session');
    } finally {
      setDeleteSessionLoading(false);
    }
  };

  const onCloseNote = () => {
    setActiveNote(null);
    setNoteDraft('');
    setNoteError(null);
    setNoteEditorMode('preview');
    setNoteEditableLines([]);
    setTableCellEditor(null);
  };

  const onChangeEditableLine = (lineIndex: number, nextValue: string) => {
    setNoteEditableLines((prev) => {
      const updated = prev.map((line, idx) =>
        idx === lineIndex ? { ...line, content: nextValue } : line
      );
      setNoteDraft(rebuildMarkdownFromLines(updated));
      return updated;
    });
  };

  const onChangeTableCell = (lineIndex: number, cellIndex: number, nextValue: string) => {
    setNoteEditableLines((prev) => {
      const updated = prev.map((line, idx) => {
        if (idx !== lineIndex || line.kind !== 'table') {
          return line;
        }
        const nextCells = line.tableCells.map((cell, currentIndex) =>
          currentIndex === cellIndex ? nextValue : cell
        );
        return { ...line, tableCells: nextCells };
      });
      setNoteDraft(rebuildMarkdownFromLines(updated));
      return updated;
    });
  };

  const onOpenTableCellEditor = (lineIndex: number, cellIndex: number, value: string) => {
    setTableCellEditor({ lineIndex, cellIndex, value });
  };

  const onSaveTableCellEditor = () => {
    if (!tableCellEditor) {
      return;
    }
    onChangeTableCell(tableCellEditor.lineIndex, tableCellEditor.cellIndex, tableCellEditor.value);
    setTableCellEditor(null);
  };

  const onSaveEditedNote = async () => {
    if (!activeNote) {
      return;
    }
    if (!noteDraft.trim()) {
      setNoteError('Note content cannot be empty.');
      return;
    }
    if (!signaturesMatch(activeNote.note_content, noteDraft)) {
      setNoteError('Please edit text only. Markdown structure must stay the same.');
      return;
    }

    setNoteSaving(true);
    setNoteError(null);
    try {
      const updated = await updateSavedProgressNote(activeNote.id, { note_content: noteDraft });
      setActiveNote(updated);
      setSaveStatus(`Updated saved note #${updated.id}.`);
    } catch (err) {
      setNoteError(err instanceof Error ? err.message : 'Failed to update note');
    } finally {
      setNoteSaving(false);
    }
  };

  const renderSidebarContent = (mobile: boolean) => (
    <>
      <Box
        sx={{
          px: 2,
          py: 1.5,
          minHeight: 60,
          borderBottom: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          background: 'linear-gradient(to left, #eefcfd, #fff)',
          justifyContent: mobile || rightSidebarOpen ? 'space-between' : 'center',
          alignItems: 'center',
        }}
      >
        {(mobile || rightSidebarOpen) && (
          <Typography variant="subtitle2" sx={{ color: '#40A8B6', fontWeight: 700 }}>
            Chat Tools
          </Typography>
        )}
        {mobile ? (
          <IconButton size="small" onClick={() => setMobileOpen(false)}>
            <X size={16} />
          </IconButton>
        ) : (
          <IconButton size="small" onClick={() => setRightSidebarOpen((prev) => !prev)}>
            {rightSidebarOpen ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </IconButton>
        )}
      </Box>

      {!mobile && !rightSidebarOpen && (
        <Stack sx={{ p: 1 }} spacing={1} alignItems="center">
          <Button
            size="small"
            onClick={() => {
              setRightSidebarOpen(true);
              setSidebarTab(0);
            }}
            sx={{ minWidth: 0, px: 1 }}
          >
            Chats
          </Button>
          <Button
            size="small"
            onClick={() => {
              setRightSidebarOpen(true);
              setSidebarTab(1);
            }}
            sx={{ minWidth: 0, px: 1 }}
          >
            Notes
          </Button>
        </Stack>
      )}

      {(mobile || rightSidebarOpen) && (
        <>
          <Box sx={{ p: 2 }}>
            <Autocomplete
              options={students}
              loading={studentsLoading}
              value={selectedStudent}
              onChange={(_, value) => setSelectedStudent(value)}
              getOptionLabel={getStudentLabel}
              isOptionEqualToValue={(option, value) => option.id === value.id}
              size="small"
              renderOption={(props, option) => (
                <Box component="li" {...props} sx={{ whiteSpace: 'normal', wordBreak: 'break-word' }}>
                  {getStudentLabel(option)}
                </Box>
              )}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Student"
                  placeholder="Select student"
                  InputProps={{
                    ...params.InputProps,
                    endAdornment: (
                      <>
                        {studentsLoading ? <CircularProgress color="inherit" size={14} /> : null}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  }}
                />
              )}
            />
          </Box>

          <Tabs
            value={sidebarTab}
            onChange={(_, value) => setSidebarTab(value)}
            variant="fullWidth"
            sx={{
              minHeight: 40,
              borderBottom: '1px solid',
              borderColor: 'rgba(0,0,0,0.08)',
              '& .MuiTab-root': {
                minHeight: 40,
                fontSize: '0.85rem',
                textTransform: 'none',
                fontWeight: 600,
              },
              '& .Mui-selected': {
                color: '#40A8B6',
              },
              '& .MuiTabs-indicator': {
                backgroundColor: '#40A8B6',
                height: 3,
                borderRadius: '3px 3px 0 0',
              },
            }}
          >
            <Tab label="Chats" />
            <Tab label="Notes" />
          </Tabs>

          <Box sx={{ p: 2, overflowY: 'auto', flex: 1, minHeight: 0 }}>
            {sidebarTab === 0 && (
              <Stack spacing={1}>
                <Button
                  variant="contained"
                  startIcon={<Plus size={16} />}
                  onClick={onCreateSession}
                  sx={{
                    textTransform: 'none',
                    bgcolor: '#40A8B6',
                    '&:hover': { bgcolor: '#2e7f8a' },
                    mb: 1,
                    py: 0.75,
                    fontWeight: 600,
                    boxShadow: 'none',
                  }}
                >
                  New Chat
                </Button>
                {sessions.map((item) => (
                  <Box
                    key={item.id}
                    onClick={() => selectSession(item.id)}
                    sx={{
                      p: 1.5,
                      borderRadius: 2,
                      cursor: 'pointer',
                      bgcolor: session?.id === item.id ? 'rgba(64, 168, 182, 0.08)' : 'transparent',
                      color: session?.id === item.id ? '#2e7f8a' : 'text.primary',
                      transition: 'all 0.2s ease',
                      '&:hover': {
                        bgcolor: session?.id === item.id ? 'rgba(64, 168, 182, 0.12)' : 'rgba(0,0,0,0.03)',
                      },
                    }}
                  >
                    <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={0.5}>
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: session?.id === item.id ? 700 : 500,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          fontSize: '0.9rem',
                        }}
                        title={item.title || 'Chat'}
                      >
                        {item.title || 'Untitled Chat'}
                      </Typography>
                      {session?.id !== item.id && (
                        <IconButton
                          size="small"
                          sx={{
                            color: 'text.disabled',
                            p: 0.5,
                            '&:hover': { color: 'error.main', bgcolor: 'rgba(211, 47, 47, 0.08)' },
                          }}
                          onClick={(event) => {
                            event.stopPropagation();
                            setPendingDeleteSession(item);
                          }}
                        >
                          <Trash2 size={13} />
                        </IconButton>
                      )}
                    </Stack>
                    <Typography
                      variant="caption"
                      sx={{
                        color: session?.id === item.id ? '#40A8B6' : 'text.secondary',
                        opacity: session?.id === item.id ? 0.9 : 0.7,
                        display: 'block',
                        mt: 0.25,
                      }}
                    >
                      {formatDate(item.created_date)}
                    </Typography>
                  </Box>
                ))}
                {sessions.length === 0 && (
                  <Typography variant="caption" color="text.secondary" align="center" sx={{ mt: 2, display: 'block' }}>
                    No chat sessions yet.
                  </Typography>
                )}
              </Stack>
            )}

            {sidebarTab === 1 && (
              <Stack spacing={1}>
                {savedNotes.map((note) => (
                  <Box
                    key={note.id}
                    onClick={() => onOpenNote(note)}
                    sx={{
                      p: 1.5,
                      borderRadius: 2,
                      cursor: 'pointer',
                      border: '1px solid',
                      borderColor: 'transparent',
                      '&:hover': {
                        bgcolor: 'rgba(0,0,0,0.03)',
                        borderColor: 'rgba(0,0,0,0.05)',
                      },
                    }}
                  >
                    <Typography
                      variant="body2"
                      sx={{
                        fontWeight: 600,
                        whiteSpace: 'normal',
                        wordBreak: 'break-word',
                        fontSize: '0.9rem',
                        mb: 0.5,
                      }}
                      title={note.title}
                    >
                      {note.title}
                    </Typography>
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                      <Typography variant="caption" color="text.secondary">
                        {note.status} • {formatDate(note.modified_date)}
                      </Typography>
                      <IconButton
                        size="small"
                        sx={{
                          color: 'text.disabled',
                          p: 0.5,
                          '&:hover': { color: 'error.main', bgcolor: 'rgba(211, 47, 47, 0.08)' },
                        }}
                        onClick={(event) => {
                          event.stopPropagation();
                          setPendingDeleteNote(note);
                        }}
                      >
                        <Trash2 size={13} />
                      </IconButton>
                    </Stack>
                  </Box>
                ))}
                {savedNotes.length === 0 && (
                  <Typography variant="caption" color="text.secondary" align="center" sx={{ mt: 2, display: 'block' }}>
                    {selectedStudent
                      ? 'No saved notes for this student.'
                      : 'Select a student to view saved notes.'}
                  </Typography>
                )}
              </Stack>
            )}
          </Box>
        </>
      )}
    </>
  );

  return (
    <Box
      sx={{
        height: '100%',
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        bgcolor: 'background.default',
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        overflow: 'hidden', // Fixes header clipping
      }}
    >
      <Box sx={{ flex: 1, minHeight: 0, display: 'flex', overflow: 'hidden' }}>
        <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          <Box
            sx={{
              px: 2,
              py: 1.5,
              minHeight: 60, // Force exact height alignment
              borderBottom: '1px solid',
              borderColor: 'divider',
              background: 'linear-gradient(to right, #eefcfd, #fff)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <Stack direction="row" spacing={1} alignItems="center">
              <MessageSquare size={18} color="#40A8B6" />
              <Typography variant="h6" sx={{ color: '#40A8B6', fontWeight: 700 }}>
                SLP AI
              </Typography>
            </Stack>
            <Stack direction="row" spacing={0.5} alignItems="center">
              {selectedStudent && (
                <IconButton
                  size="small"
                  aria-label="Open therapy history"
                  onClick={handleOpenTherapyHistory}
                  title="View Therapy History"
                  sx={{ color: '#40A8B6' }}
                >
                  <TimelineIcon fontSize="small" />
                </IconButton>
              )}
              {isMobile && (
                <IconButton size="small" onClick={() => setMobileOpen(true)} sx={{ mr: -1 }}>
                  <MenuIcon size={20} color="#40A8B6" />
                </IconButton>
              )}
            </Stack>
          </Box>

          <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto', p: 2, bgcolor: '#fafcfc' }}>
            {/* Watermark for empty state */}
            {messages.length === 0 && !chatLoading && (
              <Box
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  opacity: 0.06,
                  userSelect: 'none',
                  pb: 8,
                }}
              >
                <Bot size={120} />
                <Typography variant="h4" sx={{ mt: 3, fontWeight: 800, letterSpacing: '-0.02em' }}>
                  SLP AI
                </Typography>
              </Box>
            )}

            {chatLoading && (
              <Stack direction="row" spacing={1} alignItems="center">
                <CircularProgress size={18} />
                <Typography variant="body2" color="text.secondary">
                  Loading chat session...
                </Typography>
              </Stack>
            )}

            {!chatLoading && (
              <Stack spacing={2}>
                {messages.map((message) => (
                  <Stack
                    key={message.id}
                    direction="row"
                    spacing={1.25}
                    sx={{
                      alignSelf: message.role === 'user' ? 'flex-end' : 'flex-start',
                      width: '100%',
                      justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
                    }}
                  >
                    {message.role === 'assistant' && (
                      <Avatar
                        sx={{
                          width: 32,
                          height: 32,
                          mt: 0.25,
                          bgcolor: '#40A8B6',
                          color: 'white',
                        }}
                      >
                        <Bot size={16} />
                      </Avatar>
                    )}
                    <Box sx={{ maxWidth: 'min(88%, 780px)' }}>
                      {(message.role !== 'assistant' || message.content.trim().length > 0) && (
                        <Paper
                          elevation={0}
                          sx={{
                            px: 1.75,
                            py: 1.25,
                            borderRadius: 2.5,
                            bgcolor: message.role === 'user' ? '#40A8B6' : 'background.paper',
                            color: message.role === 'user' ? 'white' : 'text.primary',
                            border: message.role === 'assistant' ? '1px solid' : 'none',
                            borderColor: message.role === 'assistant' ? '#d4ecef' : undefined,
                            boxShadow:
                              message.role === 'assistant'
                                ? '0 2px 10px rgba(64, 168, 182, 0.08)'
                                : '0 4px 14px rgba(64, 168, 182, 0.25)',
                          }}
                        >
                        {message.role === 'assistant' ? (
                          <Box
                            sx={{
                              fontSize: '0.92rem',
                              lineHeight: 1.55,
                              '& p': { my: 0.9 },
                              '& p:first-of-type': { mt: 0 },
                              '& p:last-of-type': { mb: 0 },
                              '& h1, & h2, & h3, & h4': {
                                mt: 1.4,
                                mb: 0.7,
                                lineHeight: 1.3,
                                fontWeight: 700,
                              },
                              '& h1': { fontSize: '1.1rem' },
                              '& h2': { fontSize: '1.03rem' },
                              '& h3, & h4': { fontSize: '0.98rem' },
                              '& ul': {
                                my: 0.9,
                                ml: 2.2,
                                pl: 2.2,
                                listStyleType: 'disc',
                                listStylePosition: 'outside',
                              },
                              '& ol': {
                                my: 0.9,
                                ml: 2.2,
                                pl: 2.2,
                                listStyleType: 'decimal',
                                listStylePosition: 'outside',
                              },
                              '& li': {
                                my: 0.35,
                                display: 'list-item',
                              },
                              '& li::marker': {
                                color: 'currentColor',
                              },
                              '& code': {
                                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                                fontSize: '0.82rem',
                                px: 0.45,
                                py: 0.2,
                                borderRadius: 1,
                                bgcolor: 'rgba(64, 168, 182, 0.12)',
                              },
                              '& pre': {
                                overflowX: 'auto',
                                p: 1.1,
                                borderRadius: 1.5,
                                bgcolor: 'rgba(64, 168, 182, 0.08)',
                                border: '1px solid rgba(64, 168, 182, 0.22)',
                              },
                              '& pre code': {
                                px: 0,
                                py: 0,
                                bgcolor: 'transparent',
                                borderRadius: 0,
                              },
                              '& blockquote': {
                                m: 0,
                                my: 1,
                                px: 1.25,
                                py: 0.8,
                                borderLeft: '3px solid #40A8B6',
                                bgcolor: 'rgba(64, 168, 182, 0.08)',
                                color: 'text.secondary',
                              },
                              '& table': {
                                width: '100%',
                                borderCollapse: 'collapse',
                                my: 1,
                                fontSize: '0.84rem',
                              },
                              '& th, & td': {
                                border: '1px solid rgba(64, 168, 182, 0.22)',
                                px: 0.8,
                                py: 0.5,
                                textAlign: 'left',
                                verticalAlign: 'top',
                              },
                              '& th': {
                                bgcolor: 'rgba(64, 168, 182, 0.08)',
                                fontWeight: 600,
                              },
                              '& hr': {
                                border: 0,
                                borderTop: '1px solid rgba(64, 168, 182, 0.28)',
                                my: 1.2,
                              },
                            }}
                          >
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                          </Box>
                        ) : (
                          <Typography
                            variant="body2"
                            sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.45, fontWeight: 500 }}
                          >
                            {message.content}
                          </Typography>
                        )}
                        </Paper>
                      )}
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{
                          mt: 0.55,
                          display: 'block',
                          textAlign: message.role === 'user' ? 'right' : 'left',
                        }}
                      >
                        {message.role === 'user' ? 'You' : 'AI Assistant'}
                        {formatMessageTime(message.created_date)
                          ? ` • ${formatMessageTime(message.created_date)}`
                          : ''}
                      </Typography>
                      {message.role === 'assistant' && (
                        <Stack direction="row" spacing={0.25} sx={{ mt: 0.25 }}>
                          <Button
                            size="small"
                            startIcon={<Save size={13} />}
                            sx={{ textTransform: 'none', minWidth: 0, px: 0.8 }}
                            onClick={(event) => onOpenSaveAsMenu(event, message)}
                          >
                            Save As
                          </Button>
                          <Button
                            size="small"
                            startIcon={<Copy size={13} />}
                            sx={{ textTransform: 'none', minWidth: 0, px: 0.8 }}
                            onClick={() => handleCopyAssistantMessage(message.content)}
                          >
                            Copy
                          </Button>
                          <Button
                            size="small"
                            color="error"
                            startIcon={<Trash2 size={13} />}
                            sx={{ textTransform: 'none', minWidth: 0, px: 0.8 }}
                            onClick={() => setPendingDeleteMessage(message)}
                          >
                            Delete
                          </Button>
                        </Stack>
                      )}
                      {message.role === 'assistant' &&
                        sending &&
                        message.id === streamingMessageId &&
                        !streamHasStartedResponse && (
                        <Paper
                          variant="outlined"
                          sx={{
                            mt: 0.8,
                            px: 1,
                            py: 0.75,
                            borderColor: '#d4ecef',
                            bgcolor: 'rgba(64, 168, 182, 0.06)',
                          }}
                        >
                          <Typography variant="caption" sx={{ fontWeight: 700, color: '#2e7f8a', display: 'block' }}>
                            Active Agent: {streamActiveAgent || 'Supervisor'}
                          </Typography>
                          <Typography variant="caption" sx={{ fontWeight: 700, color: '#2e7f8a', display: 'block', mt: 0.5 }}>
                            Using Tools:
                          </Typography>
                          {streamToolNames.length > 0 ? (
                            <Box component="ul" sx={{ m: 0, mt: 0.3, pl: 2, color: 'text.secondary' }}>
                              {streamToolNames.map((toolName) => (
                                <Typography component="li" key={toolName} variant="caption">
                                  {formatToolName(toolName)}
                                </Typography>
                              ))}
                            </Box>
                          ) : (
                            <Typography variant="caption" color="text.secondary">
                              Waiting for tool selection...
                            </Typography>
                          )}
                        </Paper>
                      )}
                      {message.role === 'user' && (
                        <Stack direction="row" spacing={0.25} sx={{ mt: 0.25, justifyContent: 'flex-end' }}>
                          {message.id === lastUserMessageId && (
                            <Button
                              size="small"
                              startIcon={<Pencil size={13} />}
                              sx={{ textTransform: 'none', minWidth: 0, px: 0.8 }}
                              onClick={() => onEditUserMessage(message)}
                            >
                              Edit
                            </Button>
                          )}
                          <Button
                            size="small"
                            startIcon={<Copy size={13} />}
                            sx={{ textTransform: 'none', minWidth: 0, px: 0.8 }}
                            onClick={() => handleCopyAssistantMessage(message.content)}
                          >
                            Copy
                          </Button>
                        </Stack>
                      )}
                    </Box>
                    {message.role === 'user' && (
                      <Avatar
                        sx={{
                          width: 32,
                          height: 32,
                          mt: 0.25,
                          bgcolor: 'background.paper',
                          color: '#40A8B6',
                          border: '1px solid',
                          borderColor: '#d4ecef',
                        }}
                      >
                        <User size={16} />
                      </Avatar>
                    )}
                  </Stack>
                ))}
              </Stack>
            )}
          </Box>

          <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
            {error && (
              <Alert severity="error" sx={{ mb: 1 }}>
                {error}
              </Alert>
            )}
            {saveStatus && (
              <Alert severity="info" sx={{ mb: 1 }}>
                {saveStatus}
              </Alert>
            )}
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
              <TextField
                fullWidth
                multiline
                minRows={1}
                maxRows={15}
                size="small"
                disabled={sending}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={onDraftKeyDown}
                placeholder={
                  selectedStudent
                    ? 'Ask the AI assistant about this student...'
                    : 'Ask the AI assistant...'
                }
              />
              <IconButton
                color="primary"
                aria-label="Send message"
                disabled={sending || !draft.trim()}
                onClick={onSend}
                sx={{
                  alignSelf: 'flex-end',
                  width: 40,
                  height: 40,
                  bgcolor: 'primary.main',
                  color: 'primary.contrastText',
                  '&:hover': { bgcolor: 'primary.dark' },
                  '&.Mui-disabled': {
                    bgcolor: 'action.disabledBackground',
                    color: 'action.disabled',
                  },
                }}
              >
                <SendHorizonal size={20} />
              </IconButton>
            </Stack>
          </Box>
        </Box>

        {isMobile ? (
          <Drawer
            anchor="right"
            open={mobileOpen}
            onClose={() => setMobileOpen(false)}
            PaperProps={{ sx: { width: 280, display: 'flex', flexDirection: 'column' } }}
          >
            {renderSidebarContent(true)}
          </Drawer>
        ) : (
          <Box
            sx={{
              width: rightSidebarOpen ? RIGHT_SIDEBAR_EXPANDED_WIDTH : RIGHT_SIDEBAR_COLLAPSED_WIDTH,
              borderLeft: '1px solid',
              borderColor: 'rgba(0,0,0,0.06)',
              display: 'flex',
              flexDirection: 'column',
              bgcolor: '#fff',
              transition: 'width 0.2s ease',
              overflow: 'hidden',
            }}
          >
            {renderSidebarContent(false)}
          </Box>
        )}
      </Box>

      <Dialog
        open={Boolean(activeNote)}
        onClose={onCloseNote}
        fullWidth
        maxWidth="xl"
        PaperProps={{
          sx: {
            width: '92vw',
            maxWidth: '1400px',
            height: '88vh',
            maxHeight: '88vh',
            display: 'flex',
            flexDirection: 'column',
          },
        }}
      >
        <DialogTitle>{activeNote?.title || 'Saved Progress Note'}</DialogTitle>
        <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {noteError && (
            <Alert severity="warning" sx={{ mb: 1.5 }}>
              {noteError}
            </Alert>
          )}
          <Typography variant="caption" color="text.secondary">
            Preview uses markdown rendering. Edit Text mode allows only non-markdown text edits.
          </Typography>
          <Stack direction="row" spacing={1} sx={{ mt: 1, mb: 1 }}>
            <Button
              size="small"
              variant={noteEditorMode === 'preview' ? 'contained' : 'outlined'}
              onClick={() => setNoteEditorMode('preview')}
            >
              Preview
            </Button>
            <Button
              size="small"
              variant={noteEditorMode === 'edit' ? 'contained' : 'outlined'}
              onClick={() => setNoteEditorMode('edit')}
            >
              Edit Text
            </Button>
          </Stack>

          <Paper
            variant="outlined"
            sx={{
              p: 1.5,
              flex: 1,
              minHeight: 0,
              overflowY: 'auto',
              bgcolor: 'background.default',
            }}
          >
            {noteEditorMode === 'preview' ? (
              <Box
                sx={{
                  fontSize: '0.92rem',
                  lineHeight: 1.55,
                  '& p': { my: 0.9 },
                  '& p:first-of-type': { mt: 0 },
                  '& p:last-of-type': { mb: 0 },
                  '& h1, & h2, & h3, & h4': {
                    mt: 1.4,
                    mb: 0.7,
                    lineHeight: 1.3,
                    fontWeight: 700,
                  },
                  '& h1': { fontSize: '1.1rem' },
                  '& h2': { fontSize: '1.03rem' },
                  '& h3, & h4': { fontSize: '0.98rem' },
                  '& ul': {
                    my: 0.9,
                    ml: 2.2,
                    pl: 2.2,
                    listStyleType: 'disc',
                    listStylePosition: 'outside',
                  },
                  '& ol': {
                    my: 0.9,
                    ml: 2.2,
                    pl: 2.2,
                    listStyleType: 'decimal',
                    listStylePosition: 'outside',
                  },
                  '& li': {
                    my: 0.35,
                    display: 'list-item',
                  },
                  '& li::marker': {
                    color: 'currentColor',
                  },
                  '& code': {
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                    fontSize: '0.82rem',
                    px: 0.45,
                    py: 0.2,
                    borderRadius: 1,
                    bgcolor: 'rgba(64, 168, 182, 0.12)',
                  },
                  '& pre': {
                    overflowX: 'auto',
                    p: 1.1,
                    borderRadius: 1.5,
                    bgcolor: 'rgba(64, 168, 182, 0.08)',
                    border: '1px solid rgba(64, 168, 182, 0.22)',
                  },
                  '& pre code': {
                    px: 0,
                    py: 0,
                    bgcolor: 'transparent',
                    borderRadius: 0,
                  },
                  '& blockquote': {
                    m: 0,
                    my: 1,
                    px: 1.25,
                    py: 0.8,
                    borderLeft: '3px solid #40A8B6',
                    bgcolor: 'rgba(64, 168, 182, 0.08)',
                    color: 'text.secondary',
                  },
                  '& table': {
                    width: '100%',
                    borderCollapse: 'collapse',
                    my: 1,
                    fontSize: '0.84rem',
                  },
                  '& th, & td': {
                    border: '1px solid rgba(64, 168, 182, 0.22)',
                    px: 0.8,
                    py: 0.5,
                    textAlign: 'left',
                    verticalAlign: 'top',
                  },
                  '& th': {
                    bgcolor: 'rgba(64, 168, 182, 0.08)',
                    fontWeight: 600,
                  },
                  '& hr': {
                    border: 0,
                    borderTop: '1px solid rgba(64, 168, 182, 0.28)',
                    my: 1.2,
                  },
                }}
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{noteDraft}</ReactMarkdown>
              </Box>
            ) : (
              <Stack spacing={1}>
                {noteEditableLines.map((line, index) =>
                  line.editable && line.kind === 'table' ? (
                    <Box
                      key={index}
                      sx={{
                        display: 'grid',
                        width: '100%',
                        gap: 1,
                        pb: 0.2,
                        gridTemplateColumns: `repeat(${Math.max(line.tableCells.length, 1)}, minmax(0, 1fr))`,
                      }}
                    >
                      {line.tableCells.map((cell, cellIndex) => (
                        <TextField
                          key={`${index}-${cellIndex}`}
                          size="small"
                          value={cell}
                          multiline
                          maxRows={2}
                          onClick={() => onOpenTableCellEditor(index, cellIndex, cell)}
                          InputProps={{ readOnly: true }}
                          sx={{
                            width: '100%',
                            '& .MuiInputBase-input': { cursor: 'pointer' },
                          }}
                        />
                      ))}
                    </Box>
                  ) : line.editable ? (
                    <Stack key={index} direction="row" spacing={1} alignItems="flex-start">
                      {line.prefix ? (
                        <Typography
                          variant="body2"
                          sx={{
                            minWidth: 52,
                            px: 1,
                            py: 0.8,
                            borderRadius: 1,
                            bgcolor: 'rgba(64, 168, 182, 0.08)',
                            color: '#2e7f8a',
                            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                            whiteSpace: 'pre',
                          }}
                        >
                          {line.prefix}
                        </Typography>
                      ) : null}
                      <TextField
                        fullWidth
                        size="small"
                        value={line.content}
                        onChange={(event) => onChangeEditableLine(index, event.target.value)}
                      />
                    </Stack>
                  ) : (
                    <Typography
                      key={index}
                      variant="body2"
                      sx={{
                        px: 1,
                        py: 0.7,
                        borderRadius: 1,
                        color: 'text.secondary',
                        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                        bgcolor: 'action.hover',
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {line.lockedRaw || ' '}
                    </Typography>
                  )
                )}
              </Stack>
            )}
          </Paper>
        </DialogContent>
        <DialogActions>
          <Button onClick={onCloseNote}>Close</Button>
          <Button variant="contained" onClick={onSaveEditedNote} disabled={!activeNote || noteSaving}>
            {noteSaving ? 'Saving...' : 'Save Changes'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(tableCellEditor)}
        onClose={() => setTableCellEditor(null)}
        fullWidth
        maxWidth="md"
        PaperProps={{
          sx: {
            width: '80vw',
            maxWidth: '1000px',
          },
        }}
      >
        <DialogTitle>Edit Table Cell</DialogTitle>
        <DialogContent dividers>
          <TextField
            autoFocus
            fullWidth
            multiline
            minRows={8}
            maxRows={16}
            value={tableCellEditor?.value || ''}
            onChange={(event) =>
              setTableCellEditor((prev) => (prev ? { ...prev, value: event.target.value } : prev))
            }
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTableCellEditor(null)}>Cancel</Button>
          <Button variant="contained" onClick={onSaveTableCellEditor}>
            Apply Cell Update
          </Button>
        </DialogActions>
      </Dialog>

      <Menu
        anchorEl={saveAsAnchorEl}
        open={Boolean(saveAsAnchorEl)}
        onClose={onCloseSaveAsMenu}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
      >
        <MenuItem onClick={onSaveAsProgressNote}>Progress Note</MenuItem>
      </Menu>

      <ConfirmationModal
        open={Boolean(pendingSaveMessage)}
        onClose={() => setPendingSaveMessage(null)}
        onConfirm={onConfirmSaveMessage}
        title="Save As Progress Note"
        message="Save this assistant message as a progress note draft?"
        confirmText="Save"
        severity="info"
        loading={saveMessageLoading}
        loadingText="Saving..."
      />

      <ConfirmationModal
        open={Boolean(pendingDeleteMessage)}
        onClose={() => setPendingDeleteMessage(null)}
        onConfirm={onConfirmDeleteMessage}
        title="Delete Assistant Message"
        message="Delete this assistant message from the current chat session?"
        confirmText="Delete"
        severity="warning"
        loading={deleteMessageLoading}
        loadingText="Deleting..."
      />

      <ConfirmationModal
        open={Boolean(pendingDeleteNote)}
        onClose={() => setPendingDeleteNote(null)}
        onConfirm={onConfirmDeleteNote}
        title="Delete Progress Note"
        message="Delete this saved progress note?"
        confirmText="Delete"
        severity="warning"
        loading={deleteNoteLoading}
        loadingText="Deleting..."
      />

      <ConfirmationModal
        open={Boolean(pendingDeleteSession)}
        onClose={() => setPendingDeleteSession(null)}
        onConfirm={onConfirmDeleteSession}
        title="Delete Chat Session"
        message="Delete this chat session and all messages in it?"
        confirmText="Delete"
        severity="warning"
        loading={deleteSessionLoading}
        loadingText="Deleting..."
      />

      {selectedStudent && (
        <StudentTherapyHistoryDialog
          open={therapyHistoryOpen}
          onClose={handleCloseTherapyHistory}
          studentId={selectedStudent.id}
          studentName={`${selectedStudent.first} ${selectedStudent.last}`}
        />
      )}
    </Box>
  );
}

