-- FormSetu Database Schema
-- Run automatically on first docker compose up

-- Schema registry: stores GovForm Schemas
CREATE TABLE IF NOT EXISTS form_schemas (
    id SERIAL PRIMARY KEY,
    form_id VARCHAR(100) UNIQUE NOT NULL,
    version VARCHAR(20) NOT NULL,
    department VARCHAR(255),
    schema_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_schemas_form_id ON form_schemas(form_id);
CREATE INDEX idx_schemas_department ON form_schemas(department);

-- Schema version history
CREATE TABLE IF NOT EXISTS schema_versions (
    id SERIAL PRIMARY KEY,
    form_id VARCHAR(100) NOT NULL REFERENCES form_schemas(form_id),
    version VARCHAR(20) NOT NULL,
    schema_data JSONB NOT NULL,
    change_summary TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100),
    UNIQUE(form_id, version)
);

-- Session audit logs (no PII stored — only field IDs and events)
CREATE TABLE IF NOT EXISTS session_logs (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL,
    form_id VARCHAR(100) NOT NULL,
    language VARCHAR(10) NOT NULL,
    channel VARCHAR(20) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL,  -- completed, abandoned, error
    fields_collected INTEGER DEFAULT 0,
    fields_total INTEGER DEFAULT 0,
    duration_seconds INTEGER,
    audit_events JSONB  -- array of {event, timestamp, field_id} — NO field values
);

CREATE INDEX idx_sessions_form_id ON session_logs(form_id);
CREATE INDEX idx_sessions_started ON session_logs(started_at);

-- IFSC master data (from RBI)
CREATE TABLE IF NOT EXISTS ifsc_master (
    ifsc VARCHAR(11) PRIMARY KEY,
    bank_name VARCHAR(255) NOT NULL,
    branch_name VARCHAR(255),
    address TEXT,
    city VARCHAR(100),
    district VARCHAR(100),
    state VARCHAR(100),
    bank_name_normalized VARCHAR(255),  -- lowercase, no special chars, for fuzzy matching
    branch_name_normalized VARCHAR(255)
);

CREATE INDEX idx_ifsc_bank ON ifsc_master(bank_name_normalized);
CREATE INDEX idx_ifsc_branch ON ifsc_master(branch_name_normalized);

-- LGD (Local Government Directory) hierarchy
CREATE TABLE IF NOT EXISTS lgd_states (
    state_code VARCHAR(10) PRIMARY KEY,
    name_en VARCHAR(100) NOT NULL,
    name_local VARCHAR(200),
    census_code VARCHAR(10)
);

CREATE TABLE IF NOT EXISTS lgd_districts (
    district_code VARCHAR(10) PRIMARY KEY,
    state_code VARCHAR(10) REFERENCES lgd_states(state_code),
    name_en VARCHAR(100) NOT NULL,
    name_local VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS lgd_subdistricts (
    subdistrict_code VARCHAR(10) PRIMARY KEY,
    district_code VARCHAR(10) REFERENCES lgd_districts(district_code),
    name_en VARCHAR(100) NOT NULL,
    name_local VARCHAR(200)
);

CREATE INDEX idx_districts_state ON lgd_districts(state_code);
CREATE INDEX idx_subdistricts_district ON lgd_subdistricts(district_code);
