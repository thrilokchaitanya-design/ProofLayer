CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR NOT NULL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    page_count INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'ready',
    error TEXT,
    pages_json TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id VARCHAR NOT NULL PRIMARY KEY,
    document_id VARCHAR NOT NULL,
    question TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_reports_document_id ON reports (document_id);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR NOT NULL PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_migrations (version)
SELECT '0001_initial'
WHERE NOT EXISTS (
    SELECT 1 FROM schema_migrations WHERE version = '0001_initial'
);
