/*==========================================================================
  grant_migration_identity.sql
  --------------------------------------------------------------------------
  Give the GitHub Actions service principal "slp-deploy-github" exactly the
  permissions .github/workflows/migrate.yml needs in ONE database -- and not
  one permission more.

  Run this ONCE per database, connected AS AN ENTRA ADMIN of the logical
  server hortonfam.database.windows.net, with the target database selected:

      sqlcmd -S hortonfam.database.windows.net -d slpdb_dev -G \
             -i backend/scripts/grant_migration_identity.sql

      sqlcmd -S hortonfam.database.windows.net -d slpdb_2 -G \
             -i backend/scripts/grant_migration_identity.sql

  (`-G` is Entra interactive/default auth. Azure Data Studio or the portal
  query editor work just as well -- what matters is that the session is an
  Entra admin, because CREATE USER ... FROM EXTERNAL PROVIDER is an admin-only
  statement.)

  Run it against slpdb_dev FIRST and rehearse a migration there. The grant set
  is deliberately IDENTICAL on both databases, so a green dev run is real
  evidence that prod has enough permission -- which is the whole point of
  having a dev database.

  --------------------------------------------------------------------------
  WHY THESE GRANTS AND NOT MORE
  --------------------------------------------------------------------------
  slpdb_2 holds real student records: names, dates of birth, UICs, IEP goals,
  therapy notes. The migration identity is a non-interactive principal whose
  credential is a GitHub OIDC federation -- anyone who can dispatch a workflow
  can act as it. So the question is not "what is convenient" but "what is the
  worst thing this identity can do if the repository is compromised".

  With the grants below the answer is: it can change the SHAPE of the
  database. It cannot READ A SINGLE ROW of student data. `SELECT * FROM
  dbo.students` fails with a permission error, because nothing here grants
  SELECT on any table except a one-column table of alembic revision hashes.

  1. db_ddladmin  -- alembic's actual job is DDL: CREATE TABLE, ALTER TABLE
     ADD CONSTRAINT, CREATE INDEX, DROP. db_ddladmin is the fixed role that
     covers exactly that (CREATE TABLE / VIEW / PROCEDURE / FUNCTION, ALTER
     ANY SCHEMA, REFERENCES) and NO data permission at all. It is the smallest
     off-the-shelf role that does the job; assembling the same thing out of
     individual grants would be longer, would drift from what alembic emits
     as migrations are added, and would not reduce what the identity can do.

  2. The four DML verbs ON dbo.alembic_version, and nothing else -- alembic
     does not only issue DDL. It reads the current revision
     (SELECT version_num FROM alembic_version), writes the new one (INSERT /
     UPDATE), and `stamp` can clear it (DELETE). Creating a table does NOT
     give you DML on it in SQL Server: dbo.alembic_version belongs to the
     schema owner, not to whoever ran the CREATE. So db_ddladmin alone gets
     as far as creating the version table and then fails on the INSERT.

     Hence step 3 below: the table is created HERE, by an admin, empty -- so
     that a grant can name it. That is what breaks the chicken-and-egg between
     "GRANT needs the object to exist" and "the object is created by the very
     command that needs the grant". `alembic stamp` then finds the table
     already present (it creates with checkfirst=True) and only inserts the
     row.

     First run vs steady state:
       * first run on slpdb_2 (no alembic history): the workflow's catalog
         probe sees the table this script created -> it does NOT run the
         bootstrap stamp. That is fine ONLY because this script also inserts
         the baseline revision at step 4. Both paths end with exactly one row
         holding f2d4b8c9a1e0, which is what `upgrade head` needs to see.
       * steady state: `upgrade head` UPDATEs the single row. Same grants.

     EVIDENCE, not assertion. Rendering the pending migrations offline --

         cd backend/app
         alembic -c alembic.ini upgrade f2d4b8c9a1e0:head --sql

     -- produces exactly these statement kinds and no others:

         CREATE TABLE   api_tokens, oauth_clients, oauth_codes,
                        oauth_refresh_tokens                      -> db_ddladmin
         CREATE INDEX   9 indexes across those tables             -> db_ddladmin
         ALTER TABLE .. ADD CONSTRAINT .. FOREIGN KEY  (x2)       -> db_ddladmin
         UPDATE alembic_version SET version_num = ..   (x2)       -> the GRANT below

     Note the two ALTERs: alembic's batch_alter_table renders as a plain
     ALTER TABLE ADD CONSTRAINT on SQL Server (the copy-and-rename dance is a
     SQLite-only fallback), so no table is rebuilt and no data is read.

     There is not one statement against a user table. Re-run that command
     before granting anything wider than what is below.

  3. What is deliberately NOT granted:
       db_datareader / db_datawriter -- these are the easy answer and the
         wrong one. db_datareader alone would let a workflow run print every
         student in the district. No migration between f2d4b8c9a1e0 and
         c5a91b3e77d4 does any DML on a user table (both are pure DDL --
         verified: neither revision contains op.execute or op.bulk_insert), so
         there is nothing to justify them.
       db_owner / CONTROL -- would let the identity grant itself the above.
       VIEW DEFINITION -- not needed: db_ddladmin holds ALTER ANY SCHEMA,
         ALTER on a schema implies ALTER on the objects in it, and ALTER
         implies VIEW DEFINITION. The workflow's sys.tables probe therefore
         sees what it needs to. (If a future SQL Server change breaks that,
         the fix is `GRANT VIEW DEFINITION` -- schema visibility, still no
         data -- not a datareader role.)

  4. When this is NOT enough:
     A migration that BACKFILLS data (op.execute("UPDATE ..."), op.bulk_insert)
     will fail here with a permission error, loudly, before it changes
     anything. That is the intended behaviour. Do not "fix" it with
     db_datawriter. Fix it by adding a grant scoped to the one table that
     migration touches, e.g.

         GRANT UPDATE ON OBJECT::dbo.<the_one_table> TO [slp-deploy-github];

     next to a comment naming the revision, and REVOKE it in the same session
     once that revision is deployed everywhere.

  --------------------------------------------------------------------------
  PREREQUISITE (the step that usually fails first)
  --------------------------------------------------------------------------
  CREATE USER ... FROM EXTERNAL PROVIDER for a SERVICE PRINCIPAL requires the
  logical server's own managed identity to be able to read the directory --
  i.e. the server identity needs the "Directory Readers" Entra role (or the
  Graph application permissions User.Read.All, GroupMember.Read.All,
  Application.Read.All). Without it this script fails with

      Principal 'slp-deploy-github' could not be resolved.
      Error code 0x[...]

  which reads like a typo in the name and is not. Granting Directory Readers
  to the server's managed identity is a one-time Entra change, done by someone
  with Privileged Role Administrator.
==========================================================================*/

SET NOCOUNT ON;
GO

/*--------------------------------------------------------------------------
  0. Refuse to run anywhere unexpected.
     This script is only ever meant for slpdb_dev or slpdb_2 on the hortonfam
     server. Pasting it into the wrong query window is a real failure mode.
--------------------------------------------------------------------------*/
IF DB_NAME() NOT IN ('slpdb_dev', 'slpdb_2')
BEGIN
    RAISERROR(
        'This script grants the CI migration identity DDL rights. It is only for slpdb_dev or slpdb_2; the current database is "%s". Nothing was changed.',
        16, 1, DB_NAME());
    SET NOEXEC ON;
END
GO

PRINT 'Target database: ' + DB_NAME();
GO

/*--------------------------------------------------------------------------
  1. The contained database user for the GitHub OIDC service principal.
     No password: it authenticates with an Entra token, minted by
     azure/login@v2 on the runner.
--------------------------------------------------------------------------*/
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'slp-deploy-github')
BEGIN
    PRINT 'Creating user [slp-deploy-github] from the external provider...';
    CREATE USER [slp-deploy-github] FROM EXTERNAL PROVIDER;
END
ELSE
    PRINT 'User [slp-deploy-github] already exists.';
GO

/*--------------------------------------------------------------------------
  2. DDL rights -- and only DDL rights.
--------------------------------------------------------------------------*/
ALTER ROLE db_ddladmin ADD MEMBER [slp-deploy-github];
PRINT 'Added [slp-deploy-github] to db_ddladmin.';
GO

/*--------------------------------------------------------------------------
  3. Pre-create the alembic version table, EMPTY.

     Shape copied from alembic 1.13.1 (alembic/runtime/migration.py: a single
     String(32) column named version_num, primary key constraint named
     "<table>_pkc"), so `alembic stamp`'s create(checkfirst=True) recognises
     it and leaves it alone.

     It exists here purely so the GRANT in step 4 has an object to name.
--------------------------------------------------------------------------*/
IF OBJECT_ID('dbo.alembic_version', 'U') IS NULL
BEGIN
    PRINT 'Creating dbo.alembic_version (empty)...';
    CREATE TABLE dbo.alembic_version (
        version_num VARCHAR(32) NOT NULL,
        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
    );
END
ELSE
    PRINT 'dbo.alembic_version already exists.';
GO

/*--------------------------------------------------------------------------
  4. Seed the baseline revision on a database that has schema but no alembic
     history -- i.e. prod, whose tables predate alembic entirely.

     This is the SAME thing `alembic stamp f2d4b8c9a1e0` does. It is done here
     as well because step 3 makes the table exist, which makes the workflow's
     "is there an alembic_version table?" probe answer YES and skip its own
     bootstrap stamp. An existing-but-EMPTY version table would then send
     `upgrade head` back to the beginning of history and try to re-create
     every table that is already there.

     Only ever inserts into an EMPTY table: if a revision is already recorded,
     this leaves it exactly as it is.

     f2d4b8c9a1e0 = "Add roles and teacher_roles tables", the last revision
     whose schema matches the pre-MCP production database. The two revisions
     after it (a7f31c9e5d02 api_tokens, c5a91b3e77d4 the OAuth facade tables)
     are what `upgrade head` will actually apply.
--------------------------------------------------------------------------*/
IF NOT EXISTS (SELECT 1 FROM dbo.alembic_version)
BEGIN
    IF EXISTS (SELECT 1 FROM sys.tables WHERE name = 'roles' AND SCHEMA_NAME(schema_id) = 'dbo')
    BEGIN
        PRINT 'Version table is empty and the schema is present: stamping f2d4b8c9a1e0.';
        INSERT INTO dbo.alembic_version (version_num) VALUES ('f2d4b8c9a1e0');
    END
    ELSE
        PRINT 'Version table is empty and the schema is not built yet: leaving it empty (provision/upgrade will fill it).';
END
ELSE
    PRINT 'Version table already records a revision: leaving it untouched.';
GO

/*--------------------------------------------------------------------------
  5. The only data permissions this identity gets, on the only table it needs
     them for. Note OBJECT:: -- this is scoped to one table, not the schema.
--------------------------------------------------------------------------*/
GRANT SELECT, INSERT, UPDATE, DELETE ON OBJECT::dbo.alembic_version TO [slp-deploy-github];
PRINT 'Granted SELECT/INSERT/UPDATE/DELETE on dbo.alembic_version only.';
GO

/*--------------------------------------------------------------------------
  6. Show what was actually granted, so the operator can read it back rather
     than trust this comment block.
--------------------------------------------------------------------------*/
PRINT '--- role memberships ---';
SELECT r.name AS role_name
FROM sys.database_role_members m
JOIN sys.database_principals r ON r.principal_id = m.role_principal_id
JOIN sys.database_principals u ON u.principal_id = m.member_principal_id
WHERE u.name = 'slp-deploy-github';

PRINT '--- explicit object permissions ---';
SELECT p.permission_name,
       p.state_desc,
       OBJECT_SCHEMA_NAME(p.major_id) + '.' + OBJECT_NAME(p.major_id) AS object_name
FROM sys.database_permissions p
JOIN sys.database_principals u ON u.principal_id = p.grantee_principal_id
WHERE u.name = 'slp-deploy-github'
  AND p.class_desc = 'OBJECT_OR_COLUMN';

PRINT '--- current alembic revision ---';
SELECT version_num FROM dbo.alembic_version;
GO

SET NOEXEC OFF;
GO
