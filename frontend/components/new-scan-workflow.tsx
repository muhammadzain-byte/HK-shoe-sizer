"use client";

import { ChangeEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Camera, Copy, Footprints, RefreshCcw, UploadCloud } from "lucide-react";

import { API_BASE_URL, getApiHealth, getRuntimeApiConfig, resetRuntimeApiConfigForRetry } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { uploadScanImage, type ScanUploadStage } from "@/lib/scan-workflow";
import type { ApiHealthResponse, CaptureQualityResult, FootSide } from "@/lib/types";

const options: Array<{ label: string; value: FootSide }> = [
  { label: "Left foot", value: "left" },
  { label: "Right foot", value: "right" },
];

type BackendStatus = "checking" | "connected" | "not_connected" | "timeout" | "database_unavailable" | "wrong_port";
type ScanState =
  | "idle"
  | "checking_backend"
  | "backend_failed"
  | "creating_scan"
  | "uploading_image"
  | "validating_capture"
  | "processing_scan"
  | "completed"
  | "needs_adjustment"
  | "failed";

const RESTART_COMMAND = ".\\scripts\\run-app-now.ps1 -Force -Lan -PhoneAccess";

export function NewScanWorkflow() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const { token } = useAuth();
  const [footSide, setFootSide] = useState<FootSide>("left");
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");
  const [apiBaseUrl, setApiBaseUrl] = useState(API_BASE_URL);
  const [healthUrl, setHealthUrl] = useState(`${API_BASE_URL}/health`);
  const [databaseMode, setDatabaseMode] = useState("unknown");
  const [progress, setProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [qualityResult, setQualityResult] = useState<CaptureQualityResult | null>(null);
  const [scanState, setScanState] = useState<ScanState>("checking_backend");
  const [lastApiCall, setLastApiCall] = useState("GET /health");
  const [lastErrorStage, setLastErrorStage] = useState<string | null>(null);
  const [health, setHealth] = useState<ApiHealthResponse | null>(null);

  const checkBackend = async (forceRuntimeReload = false) => {
    setScanState((current) => (current === "idle" ? "checking_backend" : current));
    setBackendStatus("checking");
    setLastApiCall("GET /health");
    setLastErrorStage(null);
    if (forceRuntimeReload) {
      resetRuntimeApiConfigForRetry();
    }
    getRuntimeApiConfig()
      .then((runtime) => {
        setApiBaseUrl(runtime.api_base_url);
        setHealthUrl(runtime.health_url);
        return runtime;
      })
      .then(() => getApiHealth())
      .then((health) => {
        setHealth(health);
        setDatabaseMode(health.database_mode ?? health.database ?? "unknown");
        if (health.status === "ok" && ["connected", "sqlite_testing_fallback"].includes(health.database)) {
          setBackendStatus("connected");
          setScanState("idle");
        } else if (health.database === "disconnected" || health.database_mode === "missing") {
          setBackendStatus("database_unavailable");
          setScanState("backend_failed");
        } else {
          setBackendStatus("not_connected");
          setScanState("backend_failed");
        }
      })
      .catch((caught) => {
        const message = caught instanceof Error ? caught.message : "";
        setBackendStatus(message.toLowerCase().includes("timed out") ? "timeout" : "not_connected");
        setScanState("backend_failed");
        setLastErrorStage("backend_health");
        setError(formatBackendStatusMessage(message, healthUrl));
      });
  };

  useEffect(() => {
    void checkBackend();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openCamera = () => {
    if (backendStatus !== "connected") {
      setError(formatBackendStatusMessage("", healthUrl));
      return;
    }
    sessionStorage.setItem("mirrorstep.pendingFootSide", footSide);
    router.push(`/camera?footSide=${footSide}`);
  };

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    if (!token) {
      setError("Session expired. Please sign in again.");
      setScanState("failed");
      setLastErrorStage("auth");
      return;
    }
    if (backendStatus !== "connected") {
      setError(formatBackendStatusMessage("", healthUrl));
      setScanState("backend_failed");
      setLastErrorStage("backend_health");
      return;
    }
    setError(null);
    setQualityResult(null);
    setProgress(0);
    setIsUploading(true);
    setScanState("creating_scan");
    try {
      const scan = await uploadScanImage({
        token,
        footSide,
        file,
        fileName: file.name,
        onProgress: setProgress,
        onStage: (stage: ScanUploadStage) => {
          setScanState(stage);
          setLastApiCall(stageToApiCall(stage));
        },
      });
      setQualityResult(scan.capture_quality);
      if (scan.capture_quality.capture_status !== "ready") {
        setScanState("needs_adjustment");
        setLastErrorStage("capture_quality");
        setError(formatCaptureQualityMessage(scan.capture_quality));
        return;
      }
      setScanState("completed");
      router.push(`/scans/${scan.id}`);
    } catch (caught) {
      setScanState("failed");
      setLastErrorStage(scanState);
      setError(formatNewScanError(caught));
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  };

  return (
    <div className="grid gap-6">
      <div>
        <h1 className="text-3xl font-semibold">New foot scan</h1>
        <p className="mt-2 text-zinc-600">Choose a foot side and capture a measurement-ready image.</p>
      </div>
      <section className="rounded-md border border-zinc-200 bg-white p-4 text-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-semibold text-zinc-800">
              Backend{" "}
              <span className={backendStatus === "connected" ? "text-emerald-700" : "text-red-700"}>
                {formatBackendStatusLabel(backendStatus)}
              </span>
            </p>
            <p className="mt-1 break-all text-xs text-zinc-500">API base: {apiBaseUrl}</p>
            <p className="mt-1 break-all text-xs text-zinc-500">Health: {healthUrl}</p>
          </div>
          {backendStatus !== "connected" && (
            <div className="grid max-w-lg gap-2 text-red-700">
              <p>{formatBackendStatusMessage("", healthUrl)}</p>
              <div className="flex flex-wrap gap-2">
                <button
                  className="inline-flex h-8 items-center gap-1 rounded-md border border-red-200 bg-white px-2 text-xs font-semibold"
                  type="button"
                  onClick={() => void checkBackend(true)}
                >
                  <RefreshCcw className="h-3.5 w-3.5" aria-hidden="true" />
                  Retry backend check
                </button>
                <button
                  className="inline-flex h-8 items-center gap-1 rounded-md border border-red-200 bg-white px-2 text-xs font-semibold"
                  type="button"
                  onClick={() => void navigator.clipboard?.writeText(RESTART_COMMAND)}
                >
                  <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                  Copy restart command
                </button>
              </div>
            </div>
          )}
        </div>
      </section>
      <section className="rounded-md border border-zinc-200 bg-zinc-50 p-4 text-xs text-zinc-600">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-semibold text-zinc-800">Local scan debug</p>
          <button
            className="inline-flex h-8 items-center gap-1 rounded-md border border-zinc-300 bg-white px-2 text-xs font-semibold text-zinc-700"
            type="button"
            onClick={() => void checkBackend(true)}
          >
            <RefreshCcw className="h-3.5 w-3.5" aria-hidden="true" />
            Refresh runtime config
          </button>
        </div>
        <div className="mt-2 grid gap-1 sm:grid-cols-2">
          <Info label="API base" value={apiBaseUrl} />
          <Info label="Health URL" value={healthUrl} />
          <Info label="Backend status" value={backendStatus} />
          <Info label="Database mode" value={databaseMode} />
          <Info label="Auth token present" value={token ? "yes" : "no"} />
          <Info label="Current scan state" value={scanState} />
          <Info label="Last API call" value={lastApiCall} />
          <Info label="Last error stage" value={lastErrorStage ?? "none"} />
        </div>
        {health?.issues?.length ? (
          <p className="mt-2 text-amber-700">{health.issues[0]}</p>
        ) : null}
      </section>
      <section className="grid gap-4 md:grid-cols-2">
        {options.map((option) => (
          <button
            key={option.value}
            className={`flex h-24 items-center gap-4 rounded-lg border bg-white px-5 text-left ${
              footSide === option.value ? "border-ink ring-2 ring-ink/10" : "border-zinc-200"
            }`}
            type="button"
            onClick={() => setFootSide(option.value)}
          >
            <Footprints className="h-6 w-6 text-sage" aria-hidden="true" />
            <span className="text-lg font-semibold">{option.label}</span>
          </button>
        ))}
      </section>
      {error && (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
      {qualityResult && qualityResult.capture_status !== "ready" && (
        <section className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="font-semibold">Image guidance</p>
          <p className="mt-1">{qualityResult.guidance.primary_instruction}</p>
          {qualityResult.instructions.length > 0 && (
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {qualityResult.instructions.map((instruction) => (
                <li key={instruction}>{instruction}</li>
              ))}
            </ul>
          )}
        </section>
      )}
      {isUploading && (
        <div className="rounded-lg border border-zinc-200 bg-white p-4">
          <div className="flex items-center justify-between text-sm font-semibold">
            <span>Uploading scan image</span>
            <span>{progress}%</span>
          </div>
          <div className="mt-3 h-2 rounded-full bg-zinc-100">
            <div className="h-2 rounded-full bg-sage" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}
      <div className="flex flex-wrap gap-3">
        <button
          className="inline-flex h-10 items-center gap-2 rounded-md bg-ink px-4 text-sm font-semibold text-white"
          type="button"
          onClick={openCamera}
          disabled={backendStatus !== "connected"}
        >
          <Camera className="h-4 w-4" aria-hidden="true" />
          Open camera
        </button>
        <button
          className="inline-flex h-10 items-center gap-2 rounded-md border border-zinc-300 px-4 text-sm font-semibold disabled:opacity-60"
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading || backendStatus !== "connected"}
        >
          <UploadCloud className="h-4 w-4" aria-hidden="true" />
          Upload image
        </button>
        <input
          ref={fileInputRef}
          className="hidden"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={handleFileChange}
        />
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <p className="break-all">
      <span className="font-medium text-zinc-800">{label}:</span> {value}
    </p>
  );
}

function formatBackendStatusLabel(status: BackendStatus) {
  if (status === "checking") return "checking...";
  if (status === "connected") return "connected";
  if (status === "timeout") return "timed out";
  if (status === "database_unavailable") return "database unavailable";
  if (status === "wrong_port") return "wrong backend port";
  return "not reachable";
}

function formatBackendStatusMessage(message: string, healthUrl: string) {
  if (message.toLowerCase().includes("timed out")) {
    return `Backend check timed out after 5 seconds. Expected health URL: ${healthUrl}. Run: ${RESTART_COMMAND}`;
  }
  return `Backend not reachable. Expected health URL: ${healthUrl}. Run: ${RESTART_COMMAND}`;
}

function stageToApiCall(stage: ScanUploadStage) {
  if (stage === "creating_scan") return "POST /scans";
  if (stage === "uploading_image") return "POST /uploads/local";
  if (stage === "validating_capture") return "POST /ai/scans/{scan_id}/capture-quality";
  return "completed";
}

function formatNewScanError(caught: unknown) {
  const message = caught instanceof Error ? caught.message : "Upload failed.";
  const lower = message.toLowerCase();
  if (
    message.includes("Backend is not reachable") ||
    message.includes("Failed to fetch") ||
    message.includes("Expected health URL") ||
    lower.includes("timed out")
  ) {
    return message;
  }
  if (lower.includes("not authenticated") || lower.includes("authentication") || lower.includes("401")) {
    return "Session expired. Please sign in again.";
  }
  if (lower.includes("upload") || lower.includes("image file") || lower.includes("local upload")) {
    return `Upload failed: ${message}`;
  }
  return message;
}

function formatCaptureQualityMessage(quality: CaptureQualityResult) {
  const guidance =
    quality.guidance.primary_instruction ||
    "This image is not measurement-ready. Use a top-down photo of the full foot.";
  return [
    "This image is not measurement-ready.",
    guidance,
    "Use a top-down photo of the full foot. Place a credit card or A4 paper flat beside the foot. Keep the camera parallel to the floor. Avoid side-view images and cropped feet.",
  ].join(" ");
}
