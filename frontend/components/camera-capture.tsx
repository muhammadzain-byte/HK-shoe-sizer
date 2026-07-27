"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, Aperture, CheckCircle2, Footprints, ScanLine, ShieldCheck, RotateCcw, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ProtectedRoute } from "@/components/protected-route";
import { attachCaptureSession, checkCaptureQuality } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { uploadScanImage } from "@/lib/scan-workflow";
import type {
  CaptureDeviceMetadata,
  CaptureQualityResult,
  CaptureStatus,
  FootSide,
  ReferenceObjectMode,
} from "@/lib/types";

function isFootSide(value: string | null): value is FootSide {
  return value === "left" || value === "right" || value === "unknown";
}

function isReferenceObjectMode(value: string | null): value is ReferenceObjectMode {
  return (
    value === "none" ||
    value === "credit_card" ||
    value === "a4_paper" ||
    value === "calibration_card" ||
    value === "custom_object"
  );
}

export function CameraCapture() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { token } = useAuth();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [isCheckingQuality, setIsCheckingQuality] = useState(false);
  const [captureQuality, setCaptureQuality] = useState<CaptureQualityResult | null>(null);
  const [captureSessionId, setCaptureSessionId] = useState<string | null>(null);
  const [telemetryWarning, setTelemetryWarning] = useState<string | null>(null);
  const [localStatus, setLocalStatus] = useState<CaptureStatus>("needs_adjustment");
  const [localInstruction, setLocalInstruction] = useState("Place one bare foot inside the guide.");
  const [captureStep, setCaptureStep] = useState<"prepare" | "floor" | "position" | "review">("prepare");
  const [floorCheckProgress, setFloorCheckProgress] = useState(0);
  const [orientation, setOrientation] = useState<{ alpha: number | null; beta: number | null; gamma: number | null }>({
    alpha: null,
    beta: null,
    gamma: null,
  });
  const [facingMode, setFacingMode] = useState("environment");
  const [referenceMode, setReferenceMode] = useState<ReferenceObjectMode>(() => {
    if (typeof window === "undefined") {
      return "none";
    }
    const stored = sessionStorage.getItem("mirrorstep.referenceMode");
    return isReferenceObjectMode(stored) ? stored : "none";
  });

  const requestedFootSide = searchParams.get("footSide");
  const storedFootSide =
    typeof window !== "undefined" ? sessionStorage.getItem("mirrorstep.pendingFootSide") : null;
  const footSide: FootSide = isFootSide(requestedFootSide)
    ? requestedFootSide
    : isFootSide(storedFootSide)
      ? storedFootSide
      : "unknown";

  useEffect(() => {
    let cancelled = false;

    async function startCamera() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setError("Camera access is not available in this browser.");
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: "environment" },
            width: { ideal: 1920 },
            height: { ideal: 1080 },
          },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        const settings = stream.getVideoTracks()[0]?.getSettings();
        if (settings?.facingMode) {
          setFacingMode(settings.facingMode);
        }
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch {
        setError("Could not access the camera. Check browser permissions and try again.");
      }
    }

    void startCamera();

    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  useEffect(() => {
    const handleOrientation = (event: DeviceOrientationEvent) => {
      setOrientation({
        alpha: event.alpha,
        beta: event.beta,
        gamma: event.gamma,
      });
    };
    window.addEventListener("deviceorientation", handleOrientation);
    return () => window.removeEventListener("deviceorientation", handleOrientation);
  }, []);

  useEffect(() => {
    if (previewUrl) {
      return;
    }
    const interval = window.setInterval(() => {
      const video = videoRef.current;
      if (!video?.videoWidth || !video.videoHeight) {
        setLocalStatus("needs_adjustment");
        setLocalInstruction("Allow camera access and place your foot inside the guide.");
        return;
      }
      const tilt = Math.max(Math.abs(orientation.beta ?? 0), Math.abs(orientation.gamma ?? 0));
      if (tilt > 32) {
        setLocalStatus("needs_adjustment");
        setLocalInstruction("Hold phone directly above the foot.");
        return;
      }
      setLocalStatus("ready");
      setLocalInstruction("Ready to capture.");
    }, 700);
    return () => window.clearInterval(interval);
  }, [orientation.beta, orientation.gamma, previewUrl]);

  useEffect(() => {
    sessionStorage.setItem("mirrorstep.referenceMode", referenceMode);
  }, [referenceMode]);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const collectDeviceMetadata = (): CaptureDeviceMetadata => {
    const video = videoRef.current;
    return {
      user_agent: navigator.userAgent,
      viewport_width: window.innerWidth,
      viewport_height: window.innerHeight,
      video_width: video?.videoWidth ?? 0,
      video_height: video?.videoHeight ?? 0,
      device_pixel_ratio: window.devicePixelRatio || 1,
      facing_mode: facingMode,
      orientation,
      motion: {},
      timestamp: new Date().toISOString(),
      reference_mode: referenceMode,
      capture_mode: "browser_guidance",
      ar_evidence: null,
    };
  };

  const checkQuality = async (blob: Blob, supportingFrames: Blob[] = []) => {
    if (!token) {
      return;
    }
    setIsCheckingQuality(true);
    setError(null);
    setCaptureQuality(null);
    setCaptureSessionId(null);
    setTelemetryWarning(null);
    try {
      const result = await checkCaptureQuality(token, {
        file: blob,
        fileName: `capture-quality-${Date.now()}.jpg`,
        supportingFrames,
        deviceMetadata: collectDeviceMetadata(),
        persistSession: true,
      });
      if ("capture_quality" in result) {
        setCaptureQuality(result.capture_quality);
        setCaptureSessionId(result.capture_session_id);
      } else {
        setCaptureQuality(result);
      }
    } catch (caught) {
      const failedMessage = caught instanceof Error ? caught.message : "Capture quality check failed.";
      // A second full quality request previously doubled the wait on slow
      // networks. Persisting telemetry is useful, but it must not trap a user
      // on the checking state.
      if (failedMessage.toLowerCase().includes("timed out")) {
        setError("Capture check took too long. Retake the photo or continue with review.");
        setCaptureQuality({
          capture_status: "needs_adjustment",
          score: 0,
          issues: ["capture_quality_timeout"],
          instructions: ["Retake the photo with one full foot clearly visible."],
          frame_quality: { blur_score: 0, lighting_score: 0, overexposure_score: 0 },
          foot_visibility: {
            foot_detected: false,
            one_foot_only: false,
            toes_visible: false,
            heel_visible: false,
            full_foot_visible: false,
            lower_leg_ratio: 1,
            toe_margin_ratio: 0,
            heel_margin_ratio: 0,
            side_margin_ratio: 0,
          },
          pose_quality: {
            top_down_score: 0,
            rotation_angle_degrees: 0,
            perspective_risk: 1,
            foot_flatness_risk: 1,
          },
          distance_quality: {
            foot_frame_coverage: 0,
            too_close: false,
            too_far: true,
            distance_confidence: 0,
          },
          guidance: {
            primary_instruction: "Capture check timed out. Retake the photo or use review mode.",
            secondary_instructions: [],
          },
        });
      } else {
        try {
        const fallback = await checkCaptureQuality(token, {
          file: blob,
          fileName: `capture-quality-${Date.now()}.jpg`,
          supportingFrames,
          deviceMetadata: collectDeviceMetadata(),
          persistSession: false,
        });
        setCaptureQuality("capture_quality" in fallback ? fallback.capture_quality : fallback);
        setTelemetryWarning("Capture guidance worked, but telemetry storage is unavailable.");
        } catch {
        setCaptureQuality({
          capture_status: "needs_adjustment",
          score: 0,
          issues: ["capture_quality_unavailable"],
          instructions: [caught instanceof Error ? caught.message : "Capture quality check failed."],
          frame_quality: { blur_score: 0, lighting_score: 0, overexposure_score: 0 },
          foot_visibility: {
            foot_detected: false,
            one_foot_only: false,
            toes_visible: false,
            heel_visible: false,
            full_foot_visible: false,
            lower_leg_ratio: 1,
            toe_margin_ratio: 0,
            heel_margin_ratio: 0,
            side_margin_ratio: 0,
          },
          pose_quality: {
            top_down_score: 0,
            rotation_angle_degrees: 0,
            perspective_risk: 1,
            foot_flatness_risk: 1,
          },
          distance_quality: {
            foot_frame_coverage: 0,
            too_close: false,
            too_far: true,
            distance_confidence: 0,
          },
          guidance: {
            primary_instruction: "Capture quality check failed. Retake or continue with review required.",
            secondary_instructions: [],
          },
        });
        }
      }
    } finally {
      setIsCheckingQuality(false);
    }
  };

  const captureFrame = (): Promise<Blob> =>
    new Promise((resolve, reject) => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || !video.videoWidth || !video.videoHeight) {
        reject(new Error("Camera frame is not ready."));
        return;
      }
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const context = canvas.getContext("2d");
      if (!context) {
        reject(new Error("Could not capture the frame."));
        return;
      }
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("Could not prepare the frame."))), "image/jpeg", 0.92);
    });

  const capture = async () => {
    try {
      const frames = [await captureFrame()];
      await new Promise((resolve) => window.setTimeout(resolve, 180));
      frames.push(await captureFrame());
      await new Promise((resolve) => window.setTimeout(resolve, 180));
      frames.push(await captureFrame());
      const blob = frames[1];
        if (previewUrl) {
          URL.revokeObjectURL(previewUrl);
        }
        setCapturedBlob(blob);
        setPreviewUrl(URL.createObjectURL(blob));
        setCaptureStep("review");
      void checkQuality(blob, [frames[0], frames[2]]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not capture the frame.");
    }
  };

  const retake = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setCapturedBlob(null);
    setCaptureQuality(null);
    setCaptureSessionId(null);
    setTelemetryWarning(null);
    setProgress(0);
    setCaptureStep("position");
  };

  const beginFloorCheck = () => {
    setError(null);
    setFloorCheckProgress(0);
    setCaptureStep("floor");
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      const elapsed = Date.now() - startedAt;
      const progress = Math.min(100, Math.round((elapsed / 2200) * 100));
      setFloorCheckProgress(progress);
      if (progress < 100) return;
      window.clearInterval(timer);
      setCaptureStep("position");
    }, 80);
  };

  const uploadCapture = async () => {
    if (!token || !capturedBlob) {
      return;
    }
    setError(null);
    setIsUploading(true);
    setProgress(0);
    try {
      const scan = await uploadScanImage({
        token,
        footSide,
        file: capturedBlob,
        fileName: `foot-${footSide}-${Date.now()}.jpg`,
        onProgress: setProgress,
      });
      if (captureSessionId) {
        try {
          await attachCaptureSession(token, captureSessionId, {
            foot_scan_id: scan.id,
            uploaded_image_id: scan.uploaded_image_id,
          });
        } catch {
          setTelemetryWarning("Upload succeeded, but capture telemetry could not be attached.");
        }
      }
      router.replace(`/scans/${scan.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Upload failed.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <ProtectedRoute>
      <main className="min-h-screen bg-zinc-950 text-white">
        <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 py-5 sm:px-5">
          <div className="flex items-center justify-between">
            <Link
              className="inline-flex h-10 w-10 items-center justify-center rounded-md bg-white/10"
              href="/scans/new"
              aria-label="Close camera"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </Link>
            <span className="text-sm font-semibold capitalize">{footSide} foot capture</span>
            <span className="h-10 w-10" />
          </div>

          <section className="mt-5 grid grid-cols-3 gap-2 text-center text-xs">
            {[
              ["1", "Floor", captureStep === "prepare" || captureStep === "floor"],
              ["2", "Foot", captureStep === "position"],
              ["3", "Review", captureStep === "review"],
            ].map(([number, label, active]) => (
              <div key={label as string} className={`border-b-2 pb-2 ${active ? "border-amber-400 text-amber-200" : "border-white/15 text-white/45"}`}>
                <span className="mr-1 font-bold">{number}</span>{label}
              </div>
            ))}
          </section>

          <section className="relative my-5 grid min-h-[52vh] flex-1 place-items-center overflow-hidden rounded-xl border border-white/15 bg-zinc-900 shadow-2xl shadow-black/20">
            {previewUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img className="h-full w-full object-contain" src={previewUrl} alt="Captured foot preview" />
            ) : (
              <video ref={videoRef} className="h-full w-full object-cover" autoPlay muted playsInline />
            )}
            {!previewUrl && captureStep === "position" && (
              <div className="pointer-events-none absolute flex aspect-[3/4] w-[72%] max-w-sm flex-col overflow-hidden rounded-[44%] border-2 border-dashed border-white/70 shadow-[0_0_0_9999px_rgba(0,0,0,0.16)]">
                <div className="grid flex-[1.05] place-items-center border-b border-white/35 bg-sky-400/10">
                  <span className="rounded bg-zinc-950/65 px-2 py-1 text-xs font-semibold text-white/85">Toes</span>
                </div>
                <div className="flex-[1.65] border-b border-white/25 bg-emerald-400/10" />
                <div className="grid flex-[0.9] place-items-center bg-amber-300/10">
                  <span className="rounded bg-zinc-950/65 px-2 py-1 text-xs font-semibold text-white/85">Heel</span>
                </div>
                <div className="absolute inset-y-0 left-[8%] border-l border-white/30" />
                <div className="absolute inset-y-0 right-[8%] border-r border-white/30" />
              </div>
            )}
            {!previewUrl && captureStep === "position" && referenceMode !== "none" && (
              <div className="pointer-events-none absolute right-[7%] top-[31%] grid aspect-[1.58/1] w-[24%] max-w-40 place-items-center rounded-md border-2 border-dashed border-cyan-200/85 bg-cyan-300/10">
                <span className="rounded bg-zinc-950/70 px-2 py-1 text-[11px] font-semibold text-white/85">
                  Reference
                </span>
              </div>
            )}
            {!previewUrl && captureStep === "prepare" && (
              <div className="absolute inset-0 grid place-items-center bg-zinc-950/75 p-7 text-center">
                <div className="max-w-xs">
                  <Footprints className="mx-auto h-9 w-9 text-amber-300" aria-hidden="true" />
                  <h1 className="mt-4 text-2xl font-semibold">Start your foot scan</h1>
                  <p className="mt-2 text-sm leading-6 text-white/75">Sit comfortably, remove shoe and sock, then point the camera at a textured floor.</p>
                  <button className="mt-6 inline-flex h-11 items-center gap-2 rounded-full bg-amber-400 px-5 text-sm font-bold text-zinc-950" type="button" onClick={beginFloorCheck}>
                    <ScanLine className="h-4 w-4" aria-hidden="true" /> Check floor
                  </button>
                </div>
              </div>
            )}
            {!previewUrl && captureStep === "floor" && (
              <div className="absolute inset-0 grid place-items-center bg-zinc-950/65 p-7 text-center">
                <div className="w-full max-w-xs">
                  <ScanLine className="mx-auto h-9 w-9 animate-pulse text-emerald-300" aria-hidden="true" />
                  <h1 className="mt-4 text-xl font-semibold">Checking floor and phone stability</h1>
                  <p className="mt-2 text-sm leading-6 text-white/75">Keep the phone steady over a visible, textured floor.</p>
                  <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-white/15"><div className="h-full bg-emerald-300 transition-[width]" style={{ width: `${floorCheckProgress}%` }} /></div>
                  <p className="mt-2 text-xs text-white/55">Browser guidance only. Trusted no-card scale requires supported AR capture.</p>
                </div>
              </div>
            )}
            {!previewUrl && captureStep === "position" && (
              <div className="absolute left-4 right-4 top-4 rounded-md border border-white/15 bg-zinc-950/75 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold">{localStatus === "ready" ? "Frame aligned" : "Align your frame"}</span>
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${
                      localStatus === "ready" ? "bg-emerald-400" : "bg-amber-300"
                    }`}
                  />
                </div>
                <p className="mt-1 text-sm text-white/80">{localInstruction}</p>
                <p className="mt-1 text-xs text-cyan-100">For browser sizing, keep a calibration card or credit card beside the foot.</p>
              </div>
            )}
          </section>

          {captureQuality && (
            <div
              className={`mb-4 rounded-lg border px-4 py-3 ${
                captureQuality.capture_status === "ready"
                  ? "border-emerald-400/40 bg-emerald-500/10"
                  : captureQuality.capture_status === "reject"
                    ? "border-red-400/40 bg-red-500/10"
                    : "border-amber-300/40 bg-amber-300/10"
              }`}
            >
              <div className="flex items-start gap-2">
                {captureQuality.capture_status !== "ready" && (
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                )}
                <div>
                  <p className="text-sm font-semibold">
                    {captureQuality.capture_status === "ready"
                      ? "Capture quality passed"
                      : captureQuality.guidance.primary_instruction}
                  </p>
                  {captureQuality.guidance.secondary_instructions.length > 0 && (
                    <p className="mt-1 text-xs text-white/75">
                      {captureQuality.guidance.secondary_instructions.slice(0, 2).join(" ")}
                    </p>
                  )}
                  {captureQuality.stability && (
                    <p className="mt-2 text-xs text-white/75">
                      {captureQuality.stability.ready_frame_count}/{captureQuality.stability.frame_count} nearby frames passed · {captureQuality.stability.stable ? "steady capture" : "movement detected"}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {error && (
            <p className="mb-4 rounded-md border border-red-400/30 bg-red-500/10 px-3 py-2 text-sm text-red-100">
              {error}
            </p>
          )}

          {telemetryWarning && (
            <p className="mb-4 rounded-md border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-sm text-amber-50">
              {telemetryWarning}
            </p>
          )}

          {isUploading && (
            <div className="mb-4 rounded-lg bg-white/10 p-4">
              <div className="flex items-center justify-between text-sm font-semibold">
                <span>Uploading</span>
                <span>{progress}%</span>
              </div>
              <div className="mt-3 h-2 rounded-full bg-white/10">
                <div className="h-2 rounded-full bg-white" style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}

          <div className="flex items-center justify-center gap-5 pb-2">
            {previewUrl ? (
              <>
                <button
                  className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-white/10"
                  type="button"
                  onClick={retake}
                  aria-label="Retake photo"
                  disabled={isUploading}
                >
                  <RotateCcw className="h-6 w-6" aria-hidden="true" />
                </button>
                <button
                  className="inline-flex h-14 items-center gap-2 rounded-full bg-white px-5 text-sm font-semibold text-zinc-950 disabled:opacity-60"
                  type="button"
                  onClick={uploadCapture}
                  disabled={isUploading || isCheckingQuality || captureQuality?.capture_status === "reject"}
                >
                  <CheckCircle2 className="h-5 w-5" aria-hidden="true" />
                  {isCheckingQuality ? "Checking" : "Use photo"}
                </button>
              </>
            ) : captureStep === "position" ? (
              <div className="flex flex-col items-center gap-3">
                <button
                  className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-white text-zinc-950 disabled:opacity-50"
                  type="button"
                  onClick={capture}
                  aria-label="Capture photo"
                  disabled={localStatus !== "ready"}
                >
                  <Aperture className="h-8 w-8" aria-hidden="true" />
                </button>
                {localStatus !== "ready" && (
                  <button className="text-xs font-semibold text-white/70 underline" type="button" onClick={capture}>
                    Capture anyway for review
                  </button>
                )}
              </div>
            ) : null}
          </div>
          {!previewUrl && captureStep === "position" && (
            <button
              className="mt-4 flex w-full items-center justify-between border border-white/10 bg-white/[0.04] px-4 py-3 text-left text-sm text-white/80"
              type="button"
              onClick={() => setReferenceMode(referenceMode === "none" ? "credit_card" : "none")}
            >
              <span><ShieldCheck className="mr-2 inline h-4 w-4 text-cyan-200" aria-hidden="true" />{referenceMode === "none" ? "Use calibration card for real-world sizing" : "Calibration card selected"}</span>
              <span className="text-xs text-cyan-200">{referenceMode === "none" ? "Add" : "Remove"}</span>
            </button>
          )}
          <canvas ref={canvasRef} className="hidden" />
        </div>
      </main>
    </ProtectedRoute>
  );
}
