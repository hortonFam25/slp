/**
 * The words every archive confirmation uses.
 *
 * There is one sentence in this application that a therapist has to believe:
 * *nothing is deleted*. It is only believable if it reads the same in the goal
 * drawer, the session table and the calendar — so the copy lives here rather
 * than being retyped at each of the dozen call sites.
 *
 * The cascades quoted below are the ones `backend/app/services/archive.py`
 * actually performs. If one changes there, it changes here.
 */

import type { ArchivableEntityType } from '../api/archive';

/** The promise, in one line. Ends every confirmation message. */
export const ARCHIVE_REASSURANCE =
  'This will be archived, not deleted — you can restore it from Archive.';

/** What each archive takes with it, as a sentence, or '' for a leaf. */
const CASCADE_NOTE: Record<ArchivableEntityType, string> = {
  student:
    'Their goals, objectives, progress entries, therapy sessions and appointments are archived with them.',
  goal: 'Its objectives and their progress entries are archived with it.',
  objective: 'Its progress entries are archived with it.',
  progress_entry: '',
  // Deliberately different from the delete it replaced, which took the entries
  // with it. See the therapy_session cascade note in the archive service.
  therapy_session: 'Its progress entries stay where they are — they are the record a service was delivered.',
  appointment: 'Its therapy session is archived with it.',
  time_block: 'Its appointments and therapy sessions are archived with it. Student assignments are kept.',
};

/** "Archive Goal", "Archive Therapy Session" — the confirmation dialog title. */
export function archiveTitle(entity: ArchivableEntityType): string {
  const words = entity.split('_').map((w) => w[0].toUpperCase() + w.slice(1));
  return `Archive ${words.join(' ')}`;
}

/**
 * The confirmation body: what is being archived, what goes with it, and the
 * promise that none of it is destroyed.
 *
 * `name` is whatever identifies the thing to the person looking at it — a
 * student's name, a goal's number, a session's date. Omit it when the dialog is
 * already anchored to one obvious row.
 */
export function archiveMessage(entity: ArchivableEntityType, name?: string): string {
  const subject = name ? `“${name}”` : `this ${entity.replace(/_/g, ' ')}`;
  const lines = [`Archive ${subject}?`, ''];
  const cascade = CASCADE_NOTE[entity];
  if (cascade) lines.push(cascade, '');
  lines.push(ARCHIVE_REASSURANCE);
  return lines.join('\n');
}

/** "Goal archived." — what the undo snackbar leads with. */
export function archivedToast(entity: ArchivableEntityType, name?: string): string {
  const words = entity.replace(/_/g, ' ');
  const subject = name ? `${words[0].toUpperCase()}${words.slice(1)} “${name}”` : `${words[0].toUpperCase()}${words.slice(1)}`;
  return `${subject} archived.`;
}
