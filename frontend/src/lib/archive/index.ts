/**
 * Archive-with-undo, wired in three places:
 *
 *   store.ts                what undo is currently on offer
 *   ArchiveUndoSnackbar     mounted in App.tsx — the "[UNDO]" itself
 *   useArchiveWithUndo      used by every screen with an Archive button
 *   copy.ts                 the confirmation wording, written once
 *
 * The API calls live in `lib/api/archive.ts`; this directory is the UX around
 * them.
 */

export { ArchiveUndoSnackbar } from './ArchiveUndoSnackbar';
export { ARCHIVE_REASSURANCE, archiveMessage, archiveTitle, archivedToast } from './copy';
export { archiveUndo, useArchiveUndoStore } from './store';
export type { ArchiveUndoState, PendingUndo } from './store';
export { useArchiveWithUndo } from './useArchiveWithUndo';
export type { ArchiveWithUndoOptions } from './useArchiveWithUndo';
