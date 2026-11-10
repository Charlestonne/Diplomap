-- One row per rejected source record and reason; keep all original evidence.
CREATE TABLE IF NOT EXISTS stg_quarantine (
    collection_id VARCHAR NOT NULL,
    target_table VARCHAR NOT NULL,
    source_row_index BIGINT NOT NULL,
    rejection_reason VARCHAR NOT NULL,
    source_file VARCHAR NOT NULL,
    source_record JSON NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (collection_id, target_table, source_row_index, rejection_reason),

    CHECK (trim(collection_id) <> ''),
    CHECK (trim(target_table) <> ''),
    CHECK (source_row_index > 0),
    CHECK (trim(rejection_reason) <> ''),
    CHECK (trim(source_file) <> '')
);
