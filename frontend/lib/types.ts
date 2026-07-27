export type User = {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  gender: string;
  date_of_birth: string | null;
  country_code: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
};

export type FootSide = "left" | "right" | "unknown";

export type FootScan = {
  id: string;
  user_id: string;
  foot_side: FootSide;
  status:
    | "created"
    | "image_uploaded"
    | "processing"
    | "validation_passed"
    | "validation_failed"
    | "measured"
    | "completed"
    | "failed"
    | "archived";
  validation_status: "passed" | "failed" | null;
  validation_issues: string[] | null;
  length_mm: string | null;
  width_mm: string | null;
  arch_height_mm: string | null;
  confidence_score: string | null;
  processing_error: string | null;
  created_at: string;
  updated_at: string;
};

export type UploadedImage = {
  id: string;
  user_id: string;
  foot_scan_id: string | null;
  bucket: string;
  object_key: string;
  content_type: string;
  byte_size: number | null;
  checksum_sha256: string | null;
  upload_status: "pending" | "uploaded" | "failed";
  created_at: string;
  updated_at: string;
};

export type LocalUploadResponse = {
  image_id: string;
  file_url: string;
  storage_path: string;
  mime_type: string;
  size_bytes: number;
};

export type ScanHistoryItem = {
  scan: FootScan;
  recommendation_count: number;
  uploaded_image_count: number;
};

export type PaginatedScanHistory = {
  items: ScanHistoryItem[];
  total: number;
  limit: number;
  offset: number;
};

export type ScanDetail = FootScan & {
  uploaded_images: UploadedImage[];
  recommendation_count: number;
};

export type PresignUploadResponse = {
  image_id: string;
  upload_url: string;
  method: "PUT";
  headers: Record<string, string>;
  object_key: string;
  expires_in_seconds: number;
};

export type ImageValidationResponse = {
  valid: boolean;
  issues: string[];
  foot_count: number | null;
  segmentation_confidence: number | null;
  foot_bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;
};

export type CaptureStatus = "ready" | "needs_adjustment" | "reject";

export type CaptureDeviceMetadata = {
  user_agent: string;
  viewport_width: number;
  viewport_height: number;
  video_width: number;
  video_height: number;
  device_pixel_ratio: number;
  facing_mode: string;
  orientation: {
    alpha: number | null;
    beta: number | null;
    gamma: number | null;
  };
  motion: Record<string, unknown>;
  timestamp: string;
  reference_mode?: ReferenceObjectMode;
  capture_mode?: "browser_guidance" | "arcore" | "arkit" | "lidar";
  ar_evidence?: Record<string, unknown> | null;
};

export type CaptureQualityResult = {
  success?: boolean;
  stage?: string;
  status?: CaptureStatus;
  capture_status: CaptureStatus;
  score: number;
  issues: string[];
  instructions: string[];
  frame_quality: {
    blur_score: number;
    lighting_score: number;
    overexposure_score: number;
  };
  foot_visibility: {
    foot_detected: boolean;
    one_foot_only: boolean;
    toes_visible: boolean;
    heel_visible: boolean;
    full_foot_visible: boolean;
    lower_leg_ratio: number;
    toe_margin_ratio: number;
    heel_margin_ratio: number;
    side_margin_ratio: number;
  };
  pose_quality: {
    top_down_score: number;
    rotation_angle_degrees: number;
    perspective_risk: number;
    foot_flatness_risk: number;
  };
  distance_quality: {
    foot_frame_coverage: number;
    too_close: boolean;
    too_far: boolean;
    distance_confidence: number;
  };
  guidance: {
    primary_instruction: string;
    secondary_instructions: string[];
  };
  stability?: {
    frame_count: number;
    ready_frame_count: number;
    rejected_frame_count: number;
    score_spread: number;
    stable: boolean;
    mode: "single_frame" | "multi_frame";
  } | null;
};

export type CaptureQualityPersistedResponse = {
  capture_quality: CaptureQualityResult;
  capture_session_id: string | null;
};

export type CaptureQualityResponse = CaptureQualityResult | CaptureQualityPersistedResponse;

export type CaptureSessionAttachPayload = {
  foot_scan_id?: string;
  uploaded_image_id?: string;
};

export type CaptureSessionRead = {
  id: string;
  user_id: string;
  foot_scan_id: string | null;
  uploaded_image_id: string | null;
  capture_status: CaptureStatus;
  capture_quality_score: number;
  primary_instruction: string | null;
  issues: string[];
  instructions: string[];
  frame_quality: CaptureQualityResult["frame_quality"];
  foot_visibility: CaptureQualityResult["foot_visibility"];
  pose_quality: CaptureQualityResult["pose_quality"];
  distance_quality: CaptureQualityResult["distance_quality"];
  device_metadata: CaptureDeviceMetadata & {
    browser: string | null;
    os: string | null;
    device_type: string | null;
    device_family: string | null;
  };
  created_at: string;
};

export type CaptureSessionListResponse = {
  items: CaptureSessionRead[];
  total: number;
  limit: number;
  offset: number;
};

export type ReferenceObjectInput = {
  type: "credit_card" | "a4_paper" | "calibration_card" | "custom_object";
  reference_mode?: "credit_card" | "a4_paper" | "calibration_card" | "custom_object" | null;
  known_width_mm?: number | null;
  known_height_mm?: number | null;
  bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  polygon?: { x: number; y: number }[] | null;
  detection_confidence: number;
  same_plane_confidence?: number | null;
  distortion_score?: number | null;
  source?: "manual" | "auto_detected" | "user_adjusted";
};

export type ReferenceObjectMode =
  | "none"
  | "credit_card"
  | "a4_paper"
  | "calibration_card"
  | "custom_object";

export type ReferenceObjectDetectionOptions = {
  enabled: boolean;
  reference_mode: ReferenceObjectMode;
  known_width_mm?: number | null;
  known_height_mm?: number | null;
  manual_bbox?: ReferenceObjectInput["bbox"] | null;
  manual_polygon?: { x: number; y: number }[] | null;
  detection_confidence?: number | null;
  same_plane_confidence?: number | null;
  distortion_score?: number | null;
  source?: "manual" | "auto_detected" | "user_adjusted";
};

export type ReferenceObjectDetectionResponse = {
  detected: boolean;
  reference_mode: ReferenceObjectMode;
  bbox: ReferenceObjectInput["bbox"] | null;
  polygon: { x: number; y: number }[] | null;
  confidence: number;
  distortion_score: number;
  same_plane_confidence: number;
  source: "manual" | "auto_detected" | "user_adjusted";
  reference_object: ReferenceObjectInput | null;
  issues: string[];
  instructions: string[];
};

export type DepthMetadataInput = {
  depth_available: boolean;
  depth_mode: "arcore" | "arkit" | "lidar" | "monocular" | "uploaded_depth" | "none";
  camera_intrinsics?: {
    fx?: number | null;
    fy?: number | null;
    cx?: number | null;
    cy?: number | null;
    width?: number | null;
    height?: number | null;
  } | null;
  floor_plane?: {
    normal?: number[];
    distance_mm?: number | null;
    confidence?: number;
  } | null;
  distance_to_floor_mm?: number | null;
  distance_to_foot_plane_mm?: number | null;
  plane_confidence: number;
  depth_confidence: number;
  calibrated?: boolean;
  timestamp?: string | null;
  source_device?: string | null;
  raw?: Record<string, unknown>;
};

export type ScaleEstimateRequest = {
  reference_object?: ReferenceObjectInput | null;
  reference_object_detection?: ReferenceObjectDetectionOptions | null;
  calibration_mat?: Record<string, unknown> | null;
  depth_metadata?: DepthMetadataInput | null;
  device_metadata?: Record<string, unknown> | null;
  image_metadata?: Record<string, unknown> | null;
};

export type RealWorldMeasurementResult = {
  foot_length_mm: number | null;
  foot_width_mm: number | null;
  scale_status: "available" | "low_confidence" | "unavailable" | "needs_reference";
  measurement_status: string;
  can_recommend_size: boolean;
};

export type ScaleEstimateResponse = {
  scale_status: "available" | "low_confidence" | "unavailable" | "needs_reference";
  scale_mode:
    | "reference_object"
    | "calibration_mat"
    | "ar_depth"
    | "device_camera_model"
    | "monocular_depth_model"
    | "unavailable";
  pixels_per_mm: number | null;
  mm_per_pixel: number | null;
  confidence: number;
  evidence: Record<string, unknown>;
  issues: string[];
  instructions: string[];
  real_world_measurement: RealWorldMeasurementResult | null;
};

export type ShoeSizeRequest = {
  region: "EU" | "US" | "UK" | "PK";
  gender: "women";
  fit_preference: "snug" | "regular" | "relaxed";
  shoe_type: "flat" | "heel" | "sandal" | "sneaker" | "khussa" | "formal";
  foot_length_mm?: number | null;
  foot_width_mm?: number | null;
  measurement_status?: string;
  scale_status?: string;
  scale_confidence?: number;
};

export type ShoeSizeResponse = {
  recommendation_status:
    | "recommended"
    | "blocked_by_capture_quality"
    | "blocked_by_measurement_quality"
    | "blocked_by_scale"
    | "unsupported";
  recommended_size: string | null;
  size_system: string;
  width_category: "narrow" | "regular" | "wide" | null;
  confidence: number;
  reasoning: { code: string; message: string }[];
  alternate_sizes: { size: string; reason: string }[];
  fit_notes: string[];
  blocked_reason: string | null;
};

export type PipelineStageResult = {
  stage_status: "passed" | "needs_review" | "blocked" | "failed" | "not_run" | string;
  data: Record<string, unknown>;
  issues: string[];
};

export type FullPipelineRequest = {
  reference_object?: ReferenceObjectInput | null;
  reference_object_detection?: ReferenceObjectDetectionOptions | null;
  depth_metadata?: DepthMetadataInput | null;
  shoe_size_request?: ShoeSizeRequest | null;
  run_shoe_size?: boolean;
};

export type FullPipelineResponse = {
  overall_status:
    | "capture_needs_adjustment"
    | "measurement_needs_review"
    | "scale_unavailable"
    | "ready_for_size"
    | "size_recommended"
    | "failed";
  capture_quality: PipelineStageResult;
  measurement: PipelineStageResult;
  landmark_validation: PipelineStageResult;
  scale_estimate: PipelineStageResult;
  shoe_recommendation: ShoeSizeResponse | null;
  next_action: string;
  user_message: string;
  debug: Record<string, unknown>;
};

export type ValidationCaseStatus =
  | "draft"
  | "image_uploaded"
  | "annotated"
  | "scan_linked"
  | "benchmark_ready"
  | "benchmark_completed"
  | "rejected";

export type ValidationCase = {
  id: string;
  user_id: string;
  case_id: string;
  case_label: string | null;
  image_upload_id: string | null;
  scan_id: string | null;
  capture_session_id: string | null;
  device_label: string | null;
  device_os: string | null;
  browser: string | null;
  camera_type: string | null;
  foot_side: "left" | "right" | "both" | "none" | "unknown" | null;
  capture_scenario: string | null;
  ground_truth_length_mm: number | null;
  ground_truth_width_mm: number | null;
  ground_truth_source: string | null;
  reference_mode: ReferenceObjectMode;
  reference_width_mm: number | null;
  reference_height_mm: number | null;
  reference_bbox_x: number | null;
  reference_bbox_y: number | null;
  reference_bbox_width: number | null;
  reference_bbox_height: number | null;
  reference_polygon_json: Record<string, unknown>[] | null;
  status: ValidationCaseStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type ValidationCaseCreate = Partial<Omit<ValidationCase, "id" | "user_id" | "created_at" | "updated_at">> & {
  case_id: string;
};

export type ValidationCaseListResponse = {
  items: ValidationCase[];
  total: number;
  limit: number;
  offset: number;
};

export type ValidationCaseSummary = {
  total: number;
  by_status: Record<string, number>;
  by_device_os: Record<string, number>;
  by_capture_scenario: Record<string, number>;
  benchmark_ready_count: number;
  benchmark_completed_count: number;
};

export type ValidationBenchmarkResult = {
  id: string;
  validation_case_id: string;
  scan_id: string | null;
  measured_length_mm: number | null;
  measured_width_mm: number | null;
  ground_truth_length_mm: number | null;
  ground_truth_width_mm: number | null;
  length_error_mm: number | null;
  width_error_mm: number | null;
  length_abs_error_mm: number | null;
  width_abs_error_mm: number | null;
  length_error_percent: number | null;
  width_error_percent: number | null;
  capture_status: string | null;
  measurement_status: string | null;
  scale_status: string | null;
  size_status: string | null;
  recommended_size_system: string | null;
  recommended_size: string | null;
  failure_stage: string | null;
  failure_reasons_json: string[] | null;
  pipeline_output_json: Record<string, unknown> | null;
  created_at: string;
};

export type ApiHealthResponse = {
  status: "ok" | string;
  database: "connected" | "sqlite_testing_fallback" | "disconnected" | string;
  database_mode?: "postgresql" | "sqlite_testing_fallback" | "missing" | string;
  validation_tables: boolean;
  auth_ready?: boolean;
  local_upload_ready?: boolean;
  research_models_enabled: boolean;
  issues?: string[];
};
