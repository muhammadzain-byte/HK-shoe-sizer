import type {
  FootScan,
  FootSide,
  FullPipelineRequest,
  FullPipelineResponse,
  CaptureSessionAttachPayload,
  ApiHealthResponse,
  CaptureSessionRead,
  CaptureDeviceMetadata,
  CaptureQualityResponse,
  ImageValidationResponse,
  LocalUploadResponse,
  PaginatedScanHistory,
  ReferenceObjectDetectionResponse,
  ReferenceObjectDetectionOptions,
  PresignUploadResponse,
  ScanDetail,
  ScaleEstimateRequest,
  ScaleEstimateResponse,
  ShoeSizeRequest,
  ShoeSizeResponse,
  TokenResponse,
  UploadedImage,
  User,
  ValidationBenchmarkResult,
  ValidationCase,
  ValidationCaseCreate,
  ValidationCaseListResponse,
  ValidationCaseSummary,
} from "@/lib/types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
export const BACKEND_ORIGIN = process.env.NEXT_PUBLIC_BACKEND_ORIGIN ?? "http://localhost:8000";

export type RuntimeApiConfig = {
  api_base_url: string;
  backend_origin: string;
  health_url: string;
  frontend_url?: string;
  database_mode?: string;
  source: "runtime" | "env";
};

const DEFAULT_TIMEOUT_MS = 15000;

let runtimeConfigPromise: Promise<RuntimeApiConfig> | null = null;

const fallbackRuntimeConfig: RuntimeApiConfig = {
  api_base_url: API_BASE_URL,
  backend_origin: BACKEND_ORIGIN,
  health_url: `${API_BASE_URL}/health`,
  source: "env",
};

type RequestOptions = RequestInit & {
  token?: string;
  timeoutMs?: number;
};

function isLocalHostname(hostname: string) {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

export function getRuntimeApiConfig(): Promise<RuntimeApiConfig> {
  if (!runtimeConfigPromise) {
    runtimeConfigPromise = loadRuntimeApiConfig();
  }
  return runtimeConfigPromise;
}

export function resetRuntimeApiConfigForRetry() {
  runtimeConfigPromise = null;
}

async function loadRuntimeApiConfig(): Promise<RuntimeApiConfig> {
  if (typeof window === "undefined") {
    return fallbackRuntimeConfig;
  }
  try {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 2000);
    const response = await fetch(`/local-stack.json?ts=${Date.now()}`, {
      cache: "no-store",
      signal: controller.signal,
    });
    window.clearTimeout(timeout);
    if (!response.ok) {
      return fallbackRuntimeConfig;
    }
    const payload = (await response.json()) as Partial<RuntimeApiConfig>;
    if (!payload.api_base_url || !payload.health_url) {
      return fallbackRuntimeConfig;
    }
    const configuredApiUrl = new URL(payload.api_base_url, window.location.origin);
    if (!isLocalHostname(window.location.hostname) && isLocalHostname(configuredApiUrl.hostname)) {
      return fallbackRuntimeConfig;
    }
    return {
      api_base_url: payload.api_base_url,
      backend_origin: payload.backend_origin ?? payload.api_base_url.replace(/\/api\/v1\/?$/, ""),
      health_url: payload.health_url,
      frontend_url: payload.frontend_url,
      database_mode: payload.database_mode,
      source: "runtime",
    };
  } catch {
    return fallbackRuntimeConfig;
  }
}

export function withTimeoutSignal(timeoutMs: number, externalSignal?: AbortSignal) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort();
    } else {
      externalSignal.addEventListener("abort", () => controller.abort(), { once: true });
    }
  }
  return {
    signal: controller.signal,
    clear: () => clearTimeout(timeout),
  };
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const runtime = await getRuntimeApiConfig();
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  let response: Response;
  const timeout = withTimeoutSignal(options.timeoutMs ?? DEFAULT_TIMEOUT_MS, options.signal ?? undefined);
  try {
    response = await fetch(`${runtime.api_base_url}${path}`, {
      ...options,
      headers,
      signal: timeout.signal,
    });
  } catch (caught) {
    const reason =
      caught instanceof DOMException && caught.name === "AbortError"
        ? `Request timed out after ${options.timeoutMs ?? DEFAULT_TIMEOUT_MS}ms.`
        : "Backend is not reachable.";
    throw new Error(
      `${reason} Expected health URL: ${runtime.health_url}. Run: .\\scripts\\run-app-now.ps1 -Force`,
    );
  } finally {
    timeout.clear();
  }

  if (!response.ok) {
    let detail = `API request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // Keep the status-based message when the response is not JSON.
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function login(email: string, password: string) {
  return apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function register(payload: {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
}) {
  return apiFetch<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getMe(token: string) {
  return apiFetch<User>("/auth/me", { token });
}

export function getApiHealth(token?: string) {
  return apiFetch<ApiHealthResponse>("/health", { ...(token ? { token } : {}), timeoutMs: 5000 });
}

export function createScan(token: string, footSide: FootSide) {
  return apiFetch<FootScan>("/scans", {
    method: "POST",
    token,
    body: JSON.stringify({ foot_side: footSide }),
    timeoutMs: 15000,
  });
}

export function getScanHistory(token: string, limit = 25, offset = 0) {
  return apiFetch<PaginatedScanHistory>(`/scans/history?limit=${limit}&offset=${offset}`, { token });
}

export function getScan(token: string, scanId: string) {
  return apiFetch<ScanDetail>(`/scans/${scanId}`, { token });
}

export function validateScanImage(token: string, scanId: string) {
  return apiFetch<ImageValidationResponse>(`/ai/scans/${scanId}/validate`, {
    method: "POST",
    token,
  });
}

export function estimateScale(token: string, scanId: string, payload: ScaleEstimateRequest = {}) {
  return apiFetch<ScaleEstimateResponse>(`/ai/scans/${scanId}/scale-estimate`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function detectReferenceObject(
  token: string,
  scanId: string,
  payload: Omit<ReferenceObjectDetectionOptions, "enabled">,
) {
  return apiFetch<ReferenceObjectDetectionResponse>(`/ai/scans/${scanId}/detect-reference-object`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function requestShoeSize(token: string, scanId: string, payload: ShoeSizeRequest) {
  return apiFetch<ShoeSizeResponse>(`/ai/scans/${scanId}/shoe-size`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function runFullPipeline(token: string, scanId: string, payload: FullPipelineRequest = {}) {
  return apiFetch<FullPipelineResponse>(`/ai/scans/${scanId}/run-full-pipeline`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function checkCaptureQuality(
  token: string,
  payload: {
    file: Blob;
    fileName: string;
    supportingFrames?: Blob[];
    deviceMetadata: CaptureDeviceMetadata;
    persistSession?: boolean;
    footScanId?: string;
    uploadedImageId?: string;
  },
) {
  const form = new FormData();
  form.append("image", payload.file, payload.fileName);
  payload.supportingFrames?.slice(0, 2).forEach((frame, index) => {
    form.append("supporting_images", frame, `capture-support-${index + 1}.jpg`);
  });
  form.append("device_metadata", JSON.stringify(payload.deviceMetadata));
  form.append("persist_session", String(payload.persistSession ?? false));
  if (payload.footScanId) {
    form.append("foot_scan_id", payload.footScanId);
  }
  if (payload.uploadedImageId) {
    form.append("uploaded_image_id", payload.uploadedImageId);
  }
  return apiFetch<CaptureQualityResponse>("/ai/capture-quality", {
    method: "POST",
    token,
    body: form,
    timeoutMs: 30000,
  });
}

export function checkScanCaptureQuality(
  token: string,
  scanId: string,
  payload: {
    device_metadata?: Partial<CaptureDeviceMetadata>;
    uploaded_image_id?: string;
    image_id?: string;
    persist_session?: boolean;
  } = {},
) {
  return apiFetch<CaptureQualityResponse>(`/ai/scans/${scanId}/capture-quality`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    // Capture-quality is intentionally lightweight. A short timeout prevents
    // the upload flow from appearing frozen when connectivity is interrupted.
    timeoutMs: 15000,
  });
}

export function attachCaptureSession(
  token: string,
  captureSessionId: string,
  payload: CaptureSessionAttachPayload,
) {
  return apiFetch<CaptureSessionRead>(`/capture-sessions/${captureSessionId}/attach`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
  });
}

export function presignUpload(
  token: string,
  payload: { file_name: string; content_type: string; byte_size: number; foot_scan_id: string },
) {
  return apiFetch<PresignUploadResponse>("/uploads/presign", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function completeUpload(
  token: string,
  payload: { image_id: string; foot_scan_id: string; checksum_sha256?: string },
) {
  return apiFetch<UploadedImage>("/uploads/complete", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function uploadLocalValidationImage(
  token: string,
  payload: {
    file: File;
    validationCaseId?: string;
    footScanId?: string;
  },
) {
  const form = new FormData();
  form.append("file", payload.file);
  if (payload.validationCaseId) {
    form.append("validation_case_id", payload.validationCaseId);
  }
  if (payload.footScanId) {
    form.append("foot_scan_id", payload.footScanId);
  }
  return apiFetch<LocalUploadResponse>("/uploads/local", {
    method: "POST",
    token,
    body: form,
    timeoutMs: 30000,
  });
}

export function uploadFileToPresignedUrl(
  file: Blob,
  contract: PresignUploadResponse,
  onProgress: (progress: number) => void,
) {
  return new Promise<void>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open(contract.method, contract.upload_url);
    Object.entries(contract.headers).forEach(([key, value]) => request.setRequestHeader(key, value));
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) {
        onProgress(100);
        resolve();
      } else {
        reject(new Error(`Upload failed with status ${request.status}`));
      }
    };
    request.onerror = () => reject(new Error("Upload failed. Check your network and try again."));
    request.send(file);
  });
}

export function createValidationCase(token: string, payload: ValidationCaseCreate) {
  return apiFetch<ValidationCase>("/validation-cases", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function listValidationCases(token: string, limit = 50, offset = 0) {
  return apiFetch<ValidationCaseListResponse>(`/validation-cases?limit=${limit}&offset=${offset}`, { token });
}

export function getValidationCaseSummary(token: string) {
  return apiFetch<ValidationCaseSummary>("/validation-cases/summary", { token });
}

export function updateValidationCase(token: string, validationCaseId: string, payload: Partial<ValidationCaseCreate>) {
  return apiFetch<ValidationCase>(`/validation-cases/${validationCaseId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
  });
}

export function markValidationCaseBenchmarkReady(token: string, validationCaseId: string) {
  return apiFetch<ValidationCase>(`/validation-cases/${validationCaseId}/mark-benchmark-ready`, {
    method: "POST",
    token,
  });
}

export function runValidationCaseBenchmark(token: string, validationCaseId: string) {
  return apiFetch<ValidationBenchmarkResult>(`/validation-cases/${validationCaseId}/run-benchmark`, {
    method: "POST",
    token,
  });
}
