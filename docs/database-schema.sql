CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(320) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    gender VARCHAR(32) NOT NULL DEFAULT 'woman',
    date_of_birth DATE,
    country_code VARCHAR(2),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_users_email ON users (email);

CREATE TABLE foot_scans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    foot_side VARCHAR(16) NOT NULL DEFAULT 'unknown',
    status VARCHAR(32) NOT NULL DEFAULT 'created',
    length_mm NUMERIC(6, 2),
    width_mm NUMERIC(6, 2),
    arch_height_mm NUMERIC(6, 2),
    confidence_score NUMERIC(5, 4),
    validation_status VARCHAR(32),
    validation_issues JSONB,
    processing_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_foot_scans_status ON foot_scans (status);
CREATE INDEX ix_foot_scans_user_id ON foot_scans (user_id);

CREATE TABLE uploaded_images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    foot_scan_id UUID REFERENCES foot_scans(id),
    bucket VARCHAR(255) NOT NULL,
    object_key TEXT NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    byte_size BIGINT,
    checksum_sha256 VARCHAR(64),
    upload_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_uploaded_images_user_id ON uploaded_images (user_id);
CREATE INDEX ix_uploaded_images_foot_scan_id ON uploaded_images (foot_scan_id);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(120) NOT NULL,
    entity_type VARCHAR(80),
    entity_id UUID,
    ip_address INET,
    user_agent TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);
CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);

CREATE TABLE foot_measurements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id UUID NOT NULL REFERENCES foot_scans(id),
    model_name VARCHAR(100),
    model_version VARCHAR(50),
    foot_length_pixels NUMERIC(12, 2),
    foot_width_pixels NUMERIC(12, 2),
    heel_x NUMERIC(12, 2),
    heel_y NUMERIC(12, 2),
    toe_x NUMERIC(12, 2),
    toe_y NUMERIC(12, 2),
    width_left_x NUMERIC(12, 2),
    width_left_y NUMERIC(12, 2),
    width_right_x NUMERIC(12, 2),
    width_right_y NUMERIC(12, 2),
    confidence_score NUMERIC(6, 4),
    measurement_status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX ix_foot_measurements_scan_id ON foot_measurements (scan_id);

CREATE TABLE capture_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    foot_scan_id UUID REFERENCES foot_scans(id),
    uploaded_image_id UUID REFERENCES uploaded_images(id),
    capture_status VARCHAR(32) NOT NULL,
    capture_quality_score FLOAT NOT NULL,
    primary_instruction TEXT,
    issues JSONB,
    instructions JSONB,
    blur_score FLOAT,
    lighting_score FLOAT,
    overexposure_score FLOAT,
    foot_detected BOOLEAN,
    one_foot_only BOOLEAN,
    toes_visible BOOLEAN,
    heel_visible BOOLEAN,
    full_foot_visible BOOLEAN,
    lower_leg_ratio FLOAT,
    toe_margin_ratio FLOAT,
    heel_margin_ratio FLOAT,
    side_margin_ratio FLOAT,
    top_down_score FLOAT,
    rotation_angle_degrees FLOAT,
    perspective_risk FLOAT,
    foot_flatness_risk FLOAT,
    foot_frame_coverage FLOAT,
    too_close BOOLEAN,
    too_far BOOLEAN,
    distance_confidence FLOAT,
    user_agent TEXT,
    browser VARCHAR(128),
    os VARCHAR(128),
    device_type VARCHAR(128),
    device_family VARCHAR(128),
    viewport_width INTEGER,
    viewport_height INTEGER,
    video_width INTEGER,
    video_height INTEGER,
    device_pixel_ratio FLOAT,
    facing_mode VARCHAR(64),
    orientation_alpha FLOAT,
    orientation_beta FLOAT,
    orientation_gamma FLOAT,
    motion JSONB,
    raw_device_metadata JSONB,
    raw_capture_quality_result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_capture_sessions_user_id ON capture_sessions (user_id);
CREATE INDEX ix_capture_sessions_foot_scan_id ON capture_sessions (foot_scan_id);
CREATE INDEX ix_capture_sessions_uploaded_image_id ON capture_sessions (uploaded_image_id);
CREATE INDEX ix_capture_sessions_capture_status ON capture_sessions (capture_status);
CREATE INDEX ix_capture_sessions_created_at ON capture_sessions (created_at);

CREATE TABLE scale_estimates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    foot_scan_id UUID NOT NULL REFERENCES foot_scans(id),
    foot_measurement_id UUID REFERENCES foot_measurements(id),
    capture_session_id UUID REFERENCES capture_sessions(id),
    scale_status VARCHAR(32) NOT NULL,
    scale_mode VARCHAR(64) NOT NULL,
    pixels_per_mm FLOAT,
    mm_per_pixel FLOAT,
    confidence FLOAT NOT NULL,
    evidence JSONB,
    issues JSONB,
    instructions JSONB,
    foot_length_mm FLOAT,
    foot_width_mm FLOAT,
    can_recommend_size BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX ix_scale_estimates_user_id ON scale_estimates (user_id);
CREATE INDEX ix_scale_estimates_foot_scan_id ON scale_estimates (foot_scan_id);
CREATE INDEX ix_scale_estimates_capture_session_id ON scale_estimates (capture_session_id);
CREATE INDEX ix_scale_estimates_scale_status ON scale_estimates (scale_status);
CREATE INDEX ix_scale_estimates_scale_mode ON scale_estimates (scale_mode);
CREATE INDEX ix_scale_estimates_created_at ON scale_estimates (created_at);

CREATE TABLE shoe_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    foot_scan_id UUID NOT NULL REFERENCES foot_scans(id),
    scale_estimate_id UUID REFERENCES scale_estimates(id),
    region VARCHAR(16) NOT NULL,
    gender VARCHAR(32),
    shoe_type VARCHAR(64),
    fit_preference VARCHAR(64),
    recommendation_status VARCHAR(64),
    recommended_size VARCHAR(32),
    size_system VARCHAR(32),
    size_value VARCHAR(20) NOT NULL,
    width_category VARCHAR(32),
    brand VARCHAR(120),
    confidence FLOAT,
    confidence_score FLOAT,
    reasoning JSONB,
    alternate_sizes JSONB,
    fit_notes JSONB,
    blocked_reason TEXT,
    rationale TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_shoe_recommendations_foot_scan_id ON shoe_recommendations (foot_scan_id);
CREATE INDEX ix_shoe_recommendations_user_id ON shoe_recommendations (user_id);
CREATE INDEX ix_shoe_recommendations_scale_estimate_id ON shoe_recommendations (scale_estimate_id);
CREATE INDEX ix_shoe_recommendations_recommendation_status ON shoe_recommendations (recommendation_status);
-- Phase 5A note:
-- No new persistent tables are introduced in Phase 5A.
-- Use backend/scripts/verify_database_readiness.py to confirm the Phase 4B-4E tables
-- and migrations exist before real-device validation.
-- Phase 6A: Real-device validation cockpit

CREATE TABLE validation_cases (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    case_id VARCHAR(64) NOT NULL,
    case_label VARCHAR(255),
    image_upload_id UUID REFERENCES uploaded_images(id),
    scan_id UUID REFERENCES foot_scans(id),
    capture_session_id UUID REFERENCES capture_sessions(id),
    device_label VARCHAR(255),
    device_os VARCHAR(128),
    browser VARCHAR(128),
    camera_type VARCHAR(128),
    foot_side VARCHAR(16),
    capture_scenario VARCHAR(128),
    ground_truth_length_mm FLOAT,
    ground_truth_width_mm FLOAT,
    ground_truth_source VARCHAR(128),
    reference_mode VARCHAR(64) NOT NULL DEFAULT 'none',
    reference_width_mm FLOAT,
    reference_height_mm FLOAT,
    reference_bbox_x FLOAT,
    reference_bbox_y FLOAT,
    reference_bbox_width FLOAT,
    reference_bbox_height FLOAT,
    reference_polygon_json JSONB,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX ix_validation_cases_user_id ON validation_cases(user_id);
CREATE INDEX ix_validation_cases_case_id ON validation_cases(case_id);
CREATE INDEX ix_validation_cases_scan_id ON validation_cases(scan_id);
CREATE INDEX ix_validation_cases_status ON validation_cases(status);
CREATE INDEX ix_validation_cases_device_os ON validation_cases(device_os);
CREATE INDEX ix_validation_cases_capture_scenario ON validation_cases(capture_scenario);

CREATE TABLE validation_benchmark_results (
    id UUID PRIMARY KEY,
    validation_case_id UUID NOT NULL REFERENCES validation_cases(id),
    scan_id UUID REFERENCES foot_scans(id),
    measured_length_mm FLOAT,
    measured_width_mm FLOAT,
    ground_truth_length_mm FLOAT,
    ground_truth_width_mm FLOAT,
    length_error_mm FLOAT,
    width_error_mm FLOAT,
    length_abs_error_mm FLOAT,
    width_abs_error_mm FLOAT,
    length_error_percent FLOAT,
    width_error_percent FLOAT,
    capture_status VARCHAR(32),
    measurement_status VARCHAR(32),
    scale_status VARCHAR(32),
    size_status VARCHAR(64),
    recommended_size_system VARCHAR(32),
    recommended_size VARCHAR(32),
    failure_stage VARCHAR(64),
    failure_reasons_json JSONB,
    pipeline_output_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX ix_validation_benchmark_results_validation_case_id
    ON validation_benchmark_results(validation_case_id);
CREATE INDEX ix_validation_benchmark_results_scan_id ON validation_benchmark_results(scan_id);
CREATE INDEX ix_validation_benchmark_results_failure_stage
    ON validation_benchmark_results(failure_stage);
