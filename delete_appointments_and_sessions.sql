-- Azure SQL Script to Delete All Appointments and Therapy Sessions
-- This script safely deletes all scheduling and session data while preserving student/teacher/school data
-- CAUTION: This will permanently delete all appointment and therapy session data!

-- Start transaction for safety
BEGIN TRANSACTION;

PRINT 'Starting deletion of appointments and therapy sessions...';

-- 1. Delete objective progress entries linked to therapy sessions
PRINT 'Deleting objective progress entries linked to therapy sessions...';
DELETE FROM objective_progress_entries 
WHERE therapy_session_id IS NOT NULL;
PRINT 'Deleted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' objective progress entries linked to therapy sessions.';

-- 2. Delete session objectives (references therapy_sessions and goal_objectives)
PRINT 'Deleting session objectives...';
DELETE FROM session_objectives;
PRINT 'Deleted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' session objectives.';

-- 3. Delete session goals (references therapy_sessions and iep_goals)
PRINT 'Deleting session goals...';
DELETE FROM session_goals;
PRINT 'Deleted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' session goals.';

-- 4. Delete therapy sessions (main session records)
PRINT 'Deleting therapy sessions...';
DELETE FROM therapy_sessions;
PRINT 'Deleted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' therapy sessions.';

-- 5. Delete appointments (main appointment records)
PRINT 'Deleting appointments...';
DELETE FROM appointments;
PRINT 'Deleted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' appointments.';

-- 6. Delete time block activities (activities within time blocks)
PRINT 'Deleting time block activities...';
DELETE FROM time_block_activities;
PRINT 'Deleted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' time block activities.';

-- 7. Delete block assignments (student assignments to time blocks)
PRINT 'Deleting block assignments...';
DELETE FROM block_assignments;
PRINT 'Deleted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' block assignments.';

-- 8. Delete time blocks (group therapy blocks)
PRINT 'Deleting time blocks...';
DELETE FROM time_blocks;
PRINT 'Deleted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' time blocks.';

-- Optional: Reset identity columns if you want IDs to start from 1 again
-- Uncomment the following lines if you want to reset auto-increment IDs:

-- PRINT 'Resetting identity columns...';
-- DBCC CHECKIDENT ('objective_progress_entries', RESEED, 0);
-- DBCC CHECKIDENT ('session_objectives', RESEED, 0);
-- DBCC CHECKIDENT ('session_goals', RESEED, 0);
-- DBCC CHECKIDENT ('therapy_sessions', RESEED, 0);
-- DBCC CHECKIDENT ('appointments', RESEED, 0);
-- DBCC CHECKIDENT ('time_block_activities', RESEED, 0);
-- DBCC CHECKIDENT ('block_assignments', RESEED, 0);
-- DBCC CHECKIDENT ('time_blocks', RESEED, 0);

-- Commit the transaction
COMMIT TRANSACTION;

PRINT 'Successfully deleted all appointments and therapy sessions!';
PRINT 'The following data has been preserved:';
PRINT '- Students and their information';
PRINT '- Teachers and school assignments';
PRINT '- Schools';
PRINT '- IEP Goals and Objectives (structure preserved)';
PRINT '- Assessment data';
PRINT '- Service information';
PRINT '- All other non-scheduling related data';

-- Verify deletion with counts
PRINT '';
PRINT 'Verification counts (should all be 0):';
PRINT 'Appointments: ' + CAST((SELECT COUNT(*) FROM appointments) AS VARCHAR(10));
PRINT 'Therapy Sessions: ' + CAST((SELECT COUNT(*) FROM therapy_sessions) AS VARCHAR(10));
PRINT 'Session Objectives: ' + CAST((SELECT COUNT(*) FROM session_objectives) AS VARCHAR(10));
PRINT 'Session Goals: ' + CAST((SELECT COUNT(*) FROM session_goals) AS VARCHAR(10));
PRINT 'Time Blocks: ' + CAST((SELECT COUNT(*) FROM time_blocks) AS VARCHAR(10));
PRINT 'Block Assignments: ' + CAST((SELECT COUNT(*) FROM block_assignments) AS VARCHAR(10));
PRINT 'Time Block Activities: ' + CAST((SELECT COUNT(*) FROM time_block_activities) AS VARCHAR(10));
PRINT 'Progress Entries (session-linked): ' + CAST((SELECT COUNT(*) FROM objective_progress_entries WHERE therapy_session_id IS NOT NULL) AS VARCHAR(10));
