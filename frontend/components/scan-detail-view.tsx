"use client";

import Link from "next/link";
import { ArrowLeft, ImageIcon, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/status-badge";
import {
  detectReferenceObject,
  estimateScale,
  getScan,
  requestShoeSize,
  runFullPipeline,
  validateScanImage,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  FullPipelineResponse,
  PipelineStageResult,
  ReferenceObjectDetectionResponse,
  ReferenceObjectMode,
  ScaleEstimateResponse,
  ScanDetail,
  ShoeSizeResponse,
} from "@/lib/types";

export function ScanDetailView({ scanId }: { scanId: string }) {
  const { token } = useAuth();
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validationMessage, setValidationMessage] = useState<string | null>(null);
  const [segmentationSummary, setSegmentationSummary] = useState<string | null>(null);
  const [scaleEstimate, setScaleEstimate] = useState<ScaleEstimateResponse | null>(null);
  const [referenceMode, setReferenceMode] = useState<ReferenceObjectMode>("none");
  const [referenceDetection, setReferenceDetection] =
    useState<ReferenceObjectDetectionResponse | null>(null);
  const [shoeSize, setShoeSize] = useState<ShoeSizeResponse | null>(null);
  const [pipeline, setPipeline] = useState<FullPipelineResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isValidating, setIsValidating] = useState(false);
  const [isEstimatingScale, setIsEstimatingScale] = useState(false);
  const [isDetectingReference, setIsDetectingReference] = useState(false);
  const [isRequestingSize, setIsRequestingSize] = useState(false);
  const [isRunningPipeline, setIsRunningPipeline] = useState(false);

  const loadScan = async () => {
    if (!token) {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      setScan(await getScan(token, scanId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load scan.");
    } finally {
      setIsLoading(false);
    }
  };

  const validateImage = async () => {
    if (!token) {
      return;
    }
    setIsValidating(true);
    setError(null);
    setValidationMessage(null);
    setSegmentationSummary(null);
    try {
      const result = await validateScanImage(token, scanId);
      setValidationMessage(
        result.valid ? "Image validation passed." : `Image validation failed: ${result.issues.join("; ")}`,
      );
      if (result.foot_bbox) {
        setSegmentationSummary(
          `Foot count: ${result.foot_count ?? "unknown"} · Confidence: ${
            result.segmentation_confidence?.toFixed(2) ?? "unknown"
          } · Box: ${result.foot_bbox.x}, ${result.foot_bbox.y}, ${result.foot_bbox.width}x${result.foot_bbox.height}`,
        );
      }
      await loadScan();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not validate image.");
    } finally {
      setIsValidating(false);
    }
  };

  const checkScale = async () => {
    if (!token) {
      return;
    }
    setIsEstimatingScale(true);
    setError(null);
    try {
      setScaleEstimate(
        await estimateScale(
          token,
          scanId,
          referenceMode === "none"
            ? {}
            : {
                reference_object_detection: {
                  enabled: true,
                  reference_mode: referenceMode,
                },
              },
        ),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not estimate scale.");
    } finally {
      setIsEstimatingScale(false);
    }
  };

  const detectReference = async () => {
    if (!token) {
      return;
    }
    setIsDetectingReference(true);
    setError(null);
    setReferenceDetection(null);
    try {
      setReferenceDetection(
        await detectReferenceObject(token, scanId, {
          reference_mode: referenceMode,
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not detect reference object.");
    } finally {
      setIsDetectingReference(false);
    }
  };

  const checkShoeSize = async () => {
    if (!token) {
      return;
    }
    setIsRequestingSize(true);
    setError(null);
    try {
      setShoeSize(
        await requestShoeSize(token, scanId, {
          region: "EU",
          gender: "women",
          fit_preference: "regular",
          shoe_type: "flat",
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not request shoe size.");
    } finally {
      setIsRequestingSize(false);
    }
  };

  const runAnalysis = async () => {
    if (!token) {
      return;
    }
    setIsRunningPipeline(true);
    setError(null);
    try {
      setPipeline(
        await runFullPipeline(token, scanId, {
          reference_object_detection:
            referenceMode === "none"
              ? undefined
              : {
                  enabled: true,
                  reference_mode: referenceMode,
                },
          run_shoe_size: true,
          shoe_size_request: {
            region: "EU",
            gender: "women",
            fit_preference: "regular",
            shoe_type: "flat",
          },
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not run full analysis.");
    } finally {
      setIsRunningPipeline(false);
    }
  };

  const stageLabel = (stage: PipelineStageResult | null) => stage?.stage_status.replaceAll("_", " ") ?? "not run";

  useEffect(() => {
    void loadScan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scanId, token]);

  return (
    <div className="grid gap-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <Link className="inline-flex items-center gap-2 text-sm font-semibold underline" href="/scans">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Back to history
          </Link>
          <h1 className="mt-4 text-3xl font-semibold">Scan detail</h1>
          <p className="mt-2 break-all text-sm text-zinc-600">Scan ID: {scanId}</p>
        </div>
        <button
          className="inline-flex h-10 items-center gap-2 rounded-md border border-zinc-300 px-4 text-sm font-semibold disabled:opacity-60"
          type="button"
          onClick={loadScan}
          disabled={isLoading}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </button>
      </div>

      {validationMessage && (
        <div className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700">
          <p>{validationMessage}</p>
          {segmentationSummary && <p className="mt-1 text-zinc-500">{segmentationSummary}</p>}
        </div>
      )}

      {error && (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {isLoading && !scan ? (
        <section className="rounded-lg border border-zinc-200 bg-white p-5 text-sm text-zinc-600">
          Loading scan...
        </section>
      ) : scan ? (
        <>
          <section className="grid gap-4 md:grid-cols-4">
            <article className="rounded-lg border border-zinc-200 bg-white p-5">
              <p className="text-sm text-zinc-500">Status</p>
              <div className="mt-3">
                <StatusBadge status={scan.status} />
              </div>
            </article>
            <article className="rounded-lg border border-zinc-200 bg-white p-5">
              <p className="text-sm text-zinc-500">Foot</p>
              <p className="mt-2 text-xl font-semibold capitalize">{scan.foot_side}</p>
            </article>
            <article className="rounded-lg border border-zinc-200 bg-white p-5">
              <p className="text-sm text-zinc-500">Images</p>
              <p className="mt-2 text-xl font-semibold">{scan.uploaded_images.length}</p>
            </article>
            <article className="rounded-lg border border-zinc-200 bg-white p-5">
              <p className="text-sm text-zinc-500">Created</p>
              <p className="mt-2 text-sm font-semibold">{new Date(scan.created_at).toLocaleString()}</p>
            </article>
          </section>

          <section className="rounded-lg border border-zinc-200 bg-white p-5">
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
              <h2 className="text-lg font-semibold">Image validation</h2>
              <button
                className="inline-flex h-10 items-center justify-center rounded-md bg-ink px-4 text-sm font-semibold text-white disabled:opacity-60"
                type="button"
                onClick={validateImage}
                disabled={isValidating || scan.uploaded_images.length === 0}
              >
                {isValidating ? "Validating..." : "Validate image"}
              </button>
            </div>
            <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
              <div className="rounded-md bg-zinc-50 p-3">
                <p className="text-zinc-500">Validation status</p>
                <p className="mt-1 font-semibold capitalize">{scan.validation_status ?? "Not checked"}</p>
              </div>
              <div className="rounded-md bg-zinc-50 p-3">
                <p className="text-zinc-500">Issues</p>
                <p className="mt-1 font-semibold">{scan.validation_issues?.length ?? 0}</p>
              </div>
              <div className="rounded-md bg-zinc-50 p-3">
                <p className="text-zinc-500">Recommendations</p>
                <p className="mt-1 font-semibold">{scan.recommendation_count}</p>
              </div>
            </div>
            {scan.validation_issues?.length ? (
              <ul className="mt-4 grid gap-2 text-sm text-red-700">
                {scan.validation_issues.map((issue) => (
                  <li key={issue} className="rounded-md bg-red-50 px-3 py-2">
                    {issue}
                  </li>
                ))}
              </ul>
            ) : null}
          </section>

          <section className="rounded-lg border border-zinc-200 bg-white p-5">
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
              <div>
                <h2 className="text-lg font-semibold">Full analysis</h2>
                <p className="mt-1 text-sm text-zinc-500">
                  Runs the safe capture, measurement, scale, and size gates in order.
                </p>
              </div>
              <button
                className="inline-flex h-10 items-center justify-center rounded-md bg-ink px-4 text-sm font-semibold text-white disabled:opacity-60"
                type="button"
                onClick={runAnalysis}
                disabled={isRunningPipeline}
              >
                {isRunningPipeline ? "Running..." : "Run full analysis"}
              </button>
            </div>
            <div className="mt-4 grid gap-3 text-sm sm:grid-cols-5">
              {[
                ["Capture", pipeline?.capture_quality ?? null],
                ["Measurement", pipeline?.measurement ?? null],
                ["Landmarks", pipeline?.landmark_validation ?? null],
                ["Scale", pipeline?.scale_estimate ?? null],
                ["Size", pipeline?.shoe_recommendation ? { stage_status: "passed", data: {}, issues: [] } : null],
              ].map(([label, stage]) => (
                <div key={label as string} className="rounded-md bg-zinc-50 p-3">
                  <p className="text-zinc-500">{label as string}</p>
                  <p className="mt-1 font-semibold capitalize">{stageLabel(stage as PipelineStageResult | null)}</p>
                </div>
              ))}
            </div>
            {pipeline && (
              <div className="mt-4 rounded-md bg-zinc-50 p-3 text-sm">
                <p className="font-semibold capitalize">{pipeline.overall_status.replaceAll("_", " ")}</p>
                <p className="mt-2 text-zinc-600">{pipeline.user_message}</p>
                <p className="mt-1 text-zinc-500">Next action: {pipeline.next_action}</p>
                {pipeline.shoe_recommendation?.recommendation_status === "recommended" && (
                  <p className="mt-2 font-semibold">
                    Recommended women&apos;s {pipeline.shoe_recommendation.size_system} size:{" "}
                    {pipeline.shoe_recommendation.recommended_size}
                  </p>
                )}
              </div>
            )}
          </section>

          <section className="rounded-lg border border-zinc-200 bg-white p-5">
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
              <div>
                <h2 className="text-lg font-semibold">Real-world scale</h2>
                <p className="mt-1 text-sm text-zinc-500">
                  Use a reference object for accurate real-world measurement.
                </p>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <button
                  className="inline-flex h-10 items-center justify-center rounded-md border border-zinc-300 px-4 text-sm font-semibold disabled:opacity-60"
                  type="button"
                  onClick={detectReference}
                  disabled={isDetectingReference || referenceMode === "none"}
                >
                  {isDetectingReference ? "Detecting..." : "Detect reference object"}
                </button>
                <button
                  className="inline-flex h-10 items-center justify-center rounded-md border border-zinc-300 px-4 text-sm font-semibold disabled:opacity-60"
                  type="button"
                  onClick={checkScale}
                  disabled={isEstimatingScale}
                >
                  {isEstimatingScale ? "Checking..." : "Estimate scale"}
                </button>
              </div>
            </div>
            <div className="mt-4 grid gap-3 text-sm md:grid-cols-[220px_1fr]">
              <label className="grid gap-1">
                <span className="text-zinc-500">Reference mode</span>
                <select
                  className="h-10 rounded-md border border-zinc-300 bg-white px-3 text-sm"
                  value={referenceMode}
                  onChange={(event) => {
                    setReferenceMode(event.target.value as ReferenceObjectMode);
                    setReferenceDetection(null);
                  }}
                >
                  <option value="none">No reference object</option>
                  <option value="credit_card">Credit card</option>
                  <option value="a4_paper">A4 paper</option>
                  <option value="calibration_card">Calibration card</option>
                  <option value="custom_object">Custom object</option>
                </select>
              </label>
              <div className="rounded-md bg-zinc-50 p-3 text-zinc-600">
                <p>
                  Place a credit card or A4 paper flat on the same floor plane as the foot. Keep it
                  fully visible, not tilted, cropped, held in hand, or under the foot.
                </p>
              </div>
            </div>
            {referenceDetection && (
              <div className="mt-4 rounded-md bg-zinc-50 p-3 text-sm">
                <p className="font-semibold">
                  {referenceDetection.detected ? "Reference object detected" : "Reference object missing"}
                </p>
                <p className="mt-1 text-zinc-600">
                  Confidence: {Math.round(referenceDetection.confidence * 100)}% | Distortion:{" "}
                  {Math.round(referenceDetection.distortion_score * 100)}%
                </p>
                {referenceDetection.issues.length > 0 && (
                  <p className="mt-2 text-zinc-600">{referenceDetection.issues.slice(0, 2).join(" ")}</p>
                )}
              </div>
            )}
            <div className="mt-4 rounded-md bg-zinc-50 p-3 text-sm">
              <p className="text-zinc-500">Scale estimate</p>
              <p className="mt-1 font-semibold capitalize">
                {scaleEstimate?.scale_status.replace("_", " ") ?? "Not checked"}
              </p>
              {scaleEstimate?.scale_status === "unavailable" && (
                <p className="mt-2 text-zinc-600">
                  Pixel measurement is available, but real-world size requires a trusted scale source.
                </p>
              )}
              {scaleEstimate?.scale_status === "needs_reference" && (
                <p className="mt-2 text-zinc-600">
                  Please use a reference object or supported depth capture mode.
                </p>
              )}
              {scaleEstimate?.scale_status === "low_confidence" && (
                <p className="mt-2 text-zinc-600">
                  Scale evidence was detected, but confidence is too low for millimeter conversion.
                </p>
              )}
              {scaleEstimate?.scale_status === "available" && (
                <p className="mt-2 text-zinc-600">
                  Scale is available for real-world measurement. Shoe size recommendation is still blocked.
                </p>
              )}
              {scaleEstimate?.issues.length ? (
                <ul className="mt-3 grid gap-2 text-zinc-600">
                  {scaleEstimate.issues.slice(0, 3).map((issue) => (
                    <li key={issue}>{issue}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          </section>

          <section className="rounded-lg border border-zinc-200 bg-white p-5">
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
              <div>
                <h2 className="text-lg font-semibold">Women&apos;s size</h2>
                <p className="mt-1 text-sm text-zinc-500">
                  Recommendation stays blocked until capture, measurement, and scale are trusted.
                </p>
              </div>
              <button
                className="inline-flex h-10 items-center justify-center rounded-md border border-zinc-300 px-4 text-sm font-semibold disabled:opacity-60"
                type="button"
                onClick={checkShoeSize}
                disabled={isRequestingSize}
              >
                {isRequestingSize ? "Checking..." : "Check EU size"}
              </button>
            </div>
            {shoeSize && (
              <div className="mt-4 rounded-md bg-zinc-50 p-3 text-sm">
                {shoeSize.recommendation_status === "recommended" ? (
                  <>
                    <p className="text-zinc-500">Recommended size</p>
                    <p className="mt-1 text-xl font-semibold">
                      {shoeSize.size_system} {shoeSize.recommended_size}
                    </p>
                    <p className="mt-2 text-zinc-600">
                      Width: {shoeSize.width_category ?? "unknown"} | Confidence:{" "}
                      {Math.round(shoeSize.confidence * 100)}%
                    </p>
                    {shoeSize.fit_notes.length > 0 && (
                      <p className="mt-2 text-zinc-600">{shoeSize.fit_notes.slice(0, 2).join(" ")}</p>
                    )}
                  </>
                ) : (
                  <>
                    <p className="font-semibold capitalize">
                      {shoeSize.recommendation_status.replaceAll("_", " ")}
                    </p>
                    <p className="mt-2 text-zinc-600">
                      {shoeSize.blocked_reason ??
                        "Size recommendation is blocked because real-world scale is unavailable."}
                    </p>
                  </>
                )}
              </div>
            )}
          </section>

          <section className="rounded-lg border border-zinc-200 bg-white">
            <div className="flex items-center gap-2 border-b border-zinc-200 px-5 py-4">
              <ImageIcon className="h-4 w-4 text-sage" aria-hidden="true" />
              <h2 className="text-lg font-semibold">Uploaded images</h2>
            </div>
            {scan.uploaded_images.length ? (
              <div className="divide-y divide-zinc-100">
                {scan.uploaded_images.map((image) => (
                  <div key={image.id} className="grid gap-2 px-5 py-4 text-sm md:grid-cols-[1fr_auto]">
                    <div>
                      <p className="break-all font-semibold">{image.object_key}</p>
                      <p className="mt-1 text-zinc-500">
                        {image.content_type} · {image.byte_size ?? 0} bytes
                      </p>
                    </div>
                    <StatusBadge status={image.upload_status === "uploaded" ? "image_uploaded" : "created"} />
                  </div>
                ))}
              </div>
            ) : (
              <p className="p-5 text-sm text-zinc-600">No image is attached to this scan yet.</p>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
