CREATE TABLE IF NOT EXISTS document_files (
    document_id VARCHAR NOT NULL PRIMARY KEY,
    blob_path VARCHAR(1024) NOT NULL
);

INSERT INTO schema_migrations (version)
SELECT '0002_document_files'
WHERE NOT EXISTS (
    SELECT 1 FROM schema_migrations WHERE version = '0002_document_files'
);
