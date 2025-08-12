-- SQL Script to Remove All Column Comments from Azure SQL Database
-- Run this script in Azure SQL Database to remove all existing column comments
-- This will make the database schema match your cleaned-up SQLAlchemy models

-- Generate DROP statements for all column comments
DECLARE @sql NVARCHAR(MAX) = '';

SELECT @sql = @sql + 
    'EXEC sp_dropextendedproperty 
        @name = ''MS_Description'', 
        @level0type = ''SCHEMA'', 
        @level0name = ''' + SCHEMA_NAME(t.schema_id) + ''', 
        @level1type = ''TABLE'', 
        @level1name = ''' + t.name + ''', 
        @level2type = ''COLUMN'', 
        @level2name = ''' + c.name + ''';' + CHAR(13)
FROM sys.tables t
INNER JOIN sys.columns c ON t.object_id = c.object_id
INNER JOIN sys.extended_properties ep ON ep.major_id = t.object_id 
    AND ep.minor_id = c.column_id 
    AND ep.name = 'MS_Description'
WHERE t.schema_id = SCHEMA_ID('dbo')  -- Adjust schema if needed
ORDER BY t.name, c.column_id;

-- Print the generated SQL for review (optional)
PRINT 'Generated SQL to remove all column comments:';
PRINT @sql;

-- Execute the generated SQL to remove all comments
EXEC sp_executesql @sql;

-- Verify all comments have been removed
SELECT 
    t.name AS table_name,
    c.name AS column_name,
    ep.value AS comment
FROM sys.tables t
INNER JOIN sys.columns c ON t.object_id = c.object_id
INNER JOIN sys.extended_properties ep ON ep.major_id = t.object_id 
    AND ep.minor_id = c.column_id 
    AND ep.name = 'MS_Description'
WHERE t.schema_id = SCHEMA_ID('dbo')
ORDER BY t.name, c.column_id;

-- If the above query returns no rows, all comments have been successfully removed
PRINT 'Script completed. If no results are shown above, all column comments have been removed.';
