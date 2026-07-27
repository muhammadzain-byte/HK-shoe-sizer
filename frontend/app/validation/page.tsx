"use client";

import { useEffect, useMemo, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { ReferenceObjectAnnotator } from "@/components/validation/ReferenceObjectAnnotator";
import {
  createValidationCase,
  getApiHealth,
  getValidationCaseSummary,
  listValidationCases,
  markValidationCaseBenchmarkReady,
  runValidationCaseBenchmark,
  updateValidationCase,
  uploadLocalValidationImage,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  ReferenceObjectMode,
  ValidationBenchmarkResult,
  ValidationCase,
  ValidationCaseCreate,
  ValidationCaseSummary,
  ApiHealthResponse,
} from "@/lib/types";

const referenceDefaults: Record<ReferenceObjectMode, { width: number | null; height: number | null }> = {
  none: { width: null, height: null },
  credit_card: { width: 85.6, height: 53.98 },
  a4_paper: { width: 210, height: 297 },
  calibration_card: { width: 100, height: 60 },
  custom_object: { width: null, height: null },
};

export default function ValidationPage() {
  const { token } = useAuth();
  const [cases, setCases] = useState<ValidationCase[]>([]);
  const [summary, setSummary] = useState<ValidationCaseSummary | null>(null);
  const [apiHealth, setApiHealth] = useState<ApiHealthResponse | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [benchmarkResult, setBenchmarkResult] = useState<ValidationBenchmarkResult | null>(null);
  const [imagePreview, setImagePreview] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [form, setForm] = useState<ValidationCaseCreate>({
    case_id: `VAL${Date.now().toString().slice(-6)}`,
    case_label: "",
    device_label: "",
    device_os: "",
    browser: "",
    camera_type: "rear",
    foot_side: "right",
    capture_scenario: "good_capture",
    ground_truth_source: "manual_ruler",
    reference_mode: "credit_card",
    reference_width_mm: 85.6,
    reference_height_mm: 53.98,
  });

  const selectedCase = useMemo(
    () => cases.find((validationCase) => validationCase.id === selectedCaseId) ?? null,
    [cases, selectedCaseId],
  );

  const load = async () => {
    if (!token) {
      return;
    }
    setIsLoading(true);
    setMessage(null);
    try {
      const [healthResult, caseList, summaryResult] = await Promise.all([
        getApiHealth(token),
        listValidationCases(token),
        getValidationCaseSummary(token),
      ]);
      setApiHealth(healthResult);
      setCases(caseList.items);
      setSummary(summaryResult);
      if (!selectedCaseId && caseList.items[0]) {
        setSelectedCaseId(caseList.items[0].id);
      }
    } catch (caught) {
      setMessage(
        caught instanceof Error
          ? `Validation API unavailable or database not migrated: ${caught.message}`
          : "Could not load validation cases.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const saveCase = async () => {
    if (!token) {
      return;
    }
    setMessage(null);
    try {
      const saved = await createValidationCase(token, form);
      setSelectedCaseId(saved.id);
      setMessage("Validation case created. Add image/upload linkage and reference annotation before benchmarking.");
      await load();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Could not create validation case.");
    }
  };

  const saveAnnotation = async () => {
    if (!token || !selectedCase) {
      return;
    }
    setMessage(null);
    try {
      await updateValidationCase(token, selectedCase.id, {
        reference_bbox_x: form.reference_bbox_x,
        reference_bbox_y: form.reference_bbox_y,
        reference_bbox_width: form.reference_bbox_width,
        reference_bbox_height: form.reference_bbox_height,
        reference_mode: form.reference_mode,
        reference_width_mm: form.reference_width_mm,
        reference_height_mm: form.reference_height_mm,
        ground_truth_length_mm: form.ground_truth_length_mm,
        ground_truth_width_mm: form.ground_truth_width_mm,
        ground_truth_source: form.ground_truth_source,
      });
      setMessage("Annotation saved.");
      await load();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Could not save annotation.");
    }
  };

  const uploadSelectedImage = async () => {
    if (!token || !selectedCase || !selectedFile) {
      return;
    }
    setMessage(null);
    try {
      const upload = await uploadLocalValidationImage(token, {
        file: selectedFile,
        validationCaseId: selectedCase.id,
        footScanId: form.scan_id ?? selectedCase.scan_id ?? undefined,
      });
      setMessage(`Image uploaded locally and attached: ${upload.image_id}`);
      await load();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Local upload failed.");
    }
  };

  const markReady = async (validationCase: ValidationCase) => {
    if (!token) {
      return;
    }
    setMessage(null);
    try {
      await markValidationCaseBenchmarkReady(token, validationCase.id);
      setMessage("Case marked benchmark-ready.");
      await load();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Case is not benchmark-ready.");
    }
  };

  const runBenchmark = async (validationCase: ValidationCase) => {
    if (!token) {
      return;
    }
    setMessage(null);
    try {
      setBenchmarkResult(await runValidationCaseBenchmark(token, validationCase.id));
      await load();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Benchmark did not run.");
    }
  };

  const readiness = selectedCase ? validationReadiness(selectedCase, form) : [];
  const canMarkReady = selectedCase ? readiness.every((item) => item.ready) : false;

  const updateReferenceMode = (mode: ReferenceObjectMode) => {
    const defaults = referenceDefaults[mode];
    setForm((current) => ({
      ...current,
      reference_mode: mode,
      reference_width_mm: defaults.width,
      reference_height_mm: defaults.height,
    }));
  };

  return (
    <DashboardShell>
      <div className="grid gap-6">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
          <div>
            <h1 className="text-3xl font-semibold">Real-device validation</h1>
            <p className="mt-2 max-w-3xl text-sm text-zinc-600">
              Capture real phone cases, enter manual millimeter ground truth, annotate reference objects, and run
              benchmark checks. External or synthetic datasets are not accuracy proof.
            </p>
          </div>
          <button
            className="h-10 rounded-md border border-zinc-300 px-4 text-sm font-semibold"
            type="button"
            onClick={load}
            disabled={isLoading}
          >
            Refresh
          </button>
        </div>

        {message && <p className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm">{message}</p>}

        <section className="grid gap-3 sm:grid-cols-4">
          {[
            ["Cases", summary?.total ?? 0],
            ["Ready", summary?.benchmark_ready_count ?? 0],
            ["Completed", summary?.benchmark_completed_count ?? 0],
            ["Drafts", summary?.by_status.draft ?? 0],
          ].map(([label, value]) => (
            <article key={label as string} className="rounded-md border border-zinc-200 bg-white p-4">
              <p className="text-sm text-zinc-500">{label as string}</p>
              <p className="mt-2 text-2xl font-semibold">{value as number}</p>
            </article>
          ))}
        </section>

        <section className="rounded-md border border-zinc-200 bg-white p-4">
          <div className="grid gap-3 text-sm sm:grid-cols-4">
            <Info label="Backend" value={apiHealth?.status === "ok" ? "connected" : "not connected"} />
            <Info label="Database" value={apiHealth?.database ?? "unknown"} />
            <Info label="Validation tables" value={apiHealth?.validation_tables ? "ready" : "not ready"} />
            <Info
              label="Research models"
              value={apiHealth?.research_models_enabled ? "enabled" : "disabled"}
            />
          </div>
          {!apiHealth && (
            <p className="mt-3 text-sm text-zinc-600">
              Backend not connected. Start backend using scripts/start-testing-backend.ps1.
            </p>
          )}
          {apiHealth && apiHealth.database !== "connected" && (
            <p className="mt-3 text-sm text-amber-700">
              {apiHealth.database === "sqlite_testing_fallback"
                ? "Local fallback database active - not production accuracy evidence."
                : "Database not ready. Run scripts/run-app-now.ps1 -Force."}
            </p>
          )}
        </section>

        <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
          <div className="grid gap-6">
            <article className="rounded-md border border-zinc-200 bg-white p-5">
              <h2 className="text-lg font-semibold">Create case</h2>
              <div className="mt-4 grid gap-3">
                <TextInput label="Case ID" value={form.case_id ?? ""} onChange={(case_id) => setForm({ ...form, case_id })} />
                <TextInput
                  label="Label"
                  value={form.case_label ?? ""}
                  onChange={(case_label) => setForm({ ...form, case_label })}
                />
                <TextInput
                  label="Device"
                  value={form.device_label ?? ""}
                  onChange={(device_label) => setForm({ ...form, device_label })}
                />
                <div className="grid grid-cols-2 gap-3">
                  <TextInput label="OS" value={form.device_os ?? ""} onChange={(device_os) => setForm({ ...form, device_os })} />
                  <TextInput label="Browser" value={form.browser ?? ""} onChange={(browser) => setForm({ ...form, browser })} />
                </div>
                <TextInput
                  label="Linked scan ID"
                  value={form.scan_id ?? ""}
                  onChange={(scan_id) => setForm({ ...form, scan_id })}
                />
                <div className="grid grid-cols-2 gap-3">
                  <NumberInput
                    label="Length mm"
                    value={form.ground_truth_length_mm ?? ""}
                    onChange={(ground_truth_length_mm) => setForm({ ...form, ground_truth_length_mm })}
                  />
                  <NumberInput
                    label="Width mm"
                    value={form.ground_truth_width_mm ?? ""}
                    onChange={(ground_truth_width_mm) => setForm({ ...form, ground_truth_width_mm })}
                  />
                </div>
                <label className="grid gap-1 text-sm">
                  <span className="text-zinc-500">Reference object</span>
                  <select
                    className="h-10 rounded-md border border-zinc-300 bg-white px-3"
                    value={form.reference_mode ?? "none"}
                    onChange={(event) => updateReferenceMode(event.target.value as ReferenceObjectMode)}
                  >
                    <option value="none">None</option>
                    <option value="credit_card">Credit card</option>
                    <option value="a4_paper">A4 paper</option>
                    <option value="calibration_card">Calibration card</option>
                    <option value="custom_object">Custom object</option>
                  </select>
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <NumberInput
                    label="Ref width mm"
                    value={form.reference_width_mm ?? ""}
                    onChange={(reference_width_mm) => setForm({ ...form, reference_width_mm })}
                  />
                  <NumberInput
                    label="Ref height mm"
                    value={form.reference_height_mm ?? ""}
                    onChange={(reference_height_mm) => setForm({ ...form, reference_height_mm })}
                  />
                </div>
                <button
                  className="h-10 rounded-md bg-ink px-4 text-sm font-semibold text-white"
                  type="button"
                  onClick={saveCase}
                >
                  Create validation case
                </button>
              </div>
            </article>

            <article className="rounded-md border border-zinc-200 bg-white p-5">
              <h2 className="text-lg font-semibold">Case table</h2>
              <div className="mt-4 grid gap-2">
                {cases.map((validationCase) => (
                  <button
                    key={validationCase.id}
                    className={`rounded-md border px-3 py-2 text-left text-sm ${
                      validationCase.id === selectedCaseId ? "border-ink bg-zinc-100" : "border-zinc-200"
                    }`}
                    type="button"
                    onClick={() => {
                      setSelectedCaseId(validationCase.id);
                      setForm((current) => ({
                        ...current,
                        ground_truth_length_mm: validationCase.ground_truth_length_mm,
                        ground_truth_width_mm: validationCase.ground_truth_width_mm,
                        ground_truth_source: validationCase.ground_truth_source,
                        reference_mode: validationCase.reference_mode,
                        reference_width_mm: validationCase.reference_width_mm,
                        reference_height_mm: validationCase.reference_height_mm,
                        reference_bbox_x: validationCase.reference_bbox_x,
                        reference_bbox_y: validationCase.reference_bbox_y,
                        reference_bbox_width: validationCase.reference_bbox_width,
                        reference_bbox_height: validationCase.reference_bbox_height,
                      }));
                    }}
                  >
                    <span className="font-semibold">{validationCase.case_id}</span>
                    <span className="ml-2 text-zinc-500">{validationCase.status.replaceAll("_", " ")}</span>
                    <p className="mt-1 text-zinc-500">{validationCase.case_label ?? validationCase.capture_scenario}</p>
                  </button>
                ))}
              </div>
            </article>
          </div>

          <div className="grid gap-6">
            <article className="rounded-md border border-zinc-200 bg-white p-5">
              <h2 className="text-lg font-semibold">Upload/capture preview</h2>
              <p className="mt-1 text-sm text-zinc-500">
                Use this panel to annotate a local preview. Link the real uploaded image/scan through the API or scan workflow.
              </p>
              <input
                className="mt-4 block w-full text-sm"
                type="file"
                accept="image/*"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) {
                    setSelectedFile(file);
                    setImagePreview(URL.createObjectURL(file));
                  }
                }}
              />
              {imagePreview ? (
                <div className="mt-4">
                  <ReferenceObjectAnnotator
                    imageUrl={imagePreview}
                    bbox={
                      form.reference_bbox_x !== undefined &&
                      form.reference_bbox_x !== null &&
                      form.reference_bbox_y !== undefined &&
                      form.reference_bbox_y !== null &&
                      form.reference_bbox_width &&
                      form.reference_bbox_height
                        ? {
                            x: form.reference_bbox_x,
                            y: form.reference_bbox_y,
                            width: form.reference_bbox_width,
                            height: form.reference_bbox_height,
                          }
                        : null
                    }
                    onChange={(bbox) =>
                      setForm({
                        ...form,
                        reference_bbox_x: bbox.x,
                        reference_bbox_y: bbox.y,
                        reference_bbox_width: bbox.width,
                        reference_bbox_height: bbox.height,
                      })
                    }
                    onReset={() =>
                      setForm({
                        ...form,
                        reference_bbox_x: null,
                        reference_bbox_y: null,
                        reference_bbox_width: null,
                        reference_bbox_height: null,
                      })
                    }
                  />
                </div>
              ) : (
                <p className="mt-4 rounded-md bg-zinc-50 p-4 text-sm text-zinc-600">Select a local image preview to draw a reference bbox.</p>
              )}
              <div className="mt-4 grid gap-3 sm:grid-cols-4">
                <NumberInput
                  label="BBox x"
                  value={form.reference_bbox_x ?? ""}
                  onChange={(reference_bbox_x) => setForm({ ...form, reference_bbox_x })}
                />
                <NumberInput
                  label="BBox y"
                  value={form.reference_bbox_y ?? ""}
                  onChange={(reference_bbox_y) => setForm({ ...form, reference_bbox_y })}
                />
                <NumberInput
                  label="BBox w"
                  value={form.reference_bbox_width ?? ""}
                  onChange={(reference_bbox_width) => setForm({ ...form, reference_bbox_width })}
                />
                <NumberInput
                  label="BBox h"
                  value={form.reference_bbox_height ?? ""}
                  onChange={(reference_bbox_height) => setForm({ ...form, reference_bbox_height })}
                />
              </div>
              <button
                className="mt-4 mr-2 h-10 rounded-md border border-zinc-300 px-4 text-sm font-semibold disabled:opacity-60"
                type="button"
                disabled={!selectedCase}
                onClick={saveAnnotation}
              >
                Save annotation to selected case
              </button>
              <button
                className="mt-4 h-10 rounded-md bg-ink px-4 text-sm font-semibold text-white disabled:opacity-60"
                type="button"
                disabled={!selectedCase || !selectedFile}
                onClick={uploadSelectedImage}
              >
                Upload image locally
              </button>
            </article>

            {selectedCase && (
              <article className="rounded-md border border-zinc-200 bg-white p-5">
                <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                  <div>
                    <h2 className="text-lg font-semibold">{selectedCase.case_id}</h2>
                    <p className="mt-1 text-sm text-zinc-500">{selectedCase.case_label ?? "Validation case"}</p>
                  </div>
                  <span className="rounded-md bg-zinc-100 px-3 py-1 text-sm font-semibold">
                    {selectedCase.status.replaceAll("_", " ")}
                  </span>
                </div>
                <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                  <Info label="Ground truth" value={`${selectedCase.ground_truth_length_mm ?? "-"} x ${selectedCase.ground_truth_width_mm ?? "-"} mm`} />
                  <Info label="Reference" value={selectedCase.reference_mode} />
                  <Info label="Scan linked" value={selectedCase.scan_id ? "yes" : "no"} />
                </div>
                <div className="mt-4 rounded-md bg-zinc-50 p-3">
                  <p className="text-sm font-semibold">Required fields</p>
                  <div className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
                    {readiness.map((item) => (
                      <div key={item.label} className={item.ready ? "text-emerald-700" : "text-zinc-600"}>
                        {item.ready ? "Ready" : "Missing"}: {item.label}
                      </div>
                    ))}
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    className="h-10 rounded-md border border-zinc-300 px-4 text-sm font-semibold disabled:opacity-60"
                    type="button"
                    disabled={!canMarkReady}
                    onClick={() => markReady(selectedCase)}
                  >
                    Mark benchmark-ready
                  </button>
                  <button
                    className="h-10 rounded-md bg-ink px-4 text-sm font-semibold text-white disabled:opacity-60"
                    type="button"
                    disabled={selectedCase.status !== "benchmark_ready"}
                    onClick={() => runBenchmark(selectedCase)}
                  >
                    Run benchmark
                  </button>
                </div>
              </article>
            )}

            {benchmarkResult && (
              <article className="rounded-md border border-zinc-200 bg-white p-5">
                <h2 className="text-lg font-semibold">Benchmark result</h2>
                <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                  <Info label="Length error" value={benchmarkResult.length_abs_error_mm === null ? "-" : `${benchmarkResult.length_abs_error_mm} mm`} />
                  <Info label="Width error" value={benchmarkResult.width_abs_error_mm === null ? "-" : `${benchmarkResult.width_abs_error_mm} mm`} />
                  <Info label="Failure stage" value={benchmarkResult.failure_stage ?? "none"} />
                  <Info label="Measured length" value={benchmarkResult.measured_length_mm === null ? "-" : `${benchmarkResult.measured_length_mm} mm`} />
                  <Info label="Measured width" value={benchmarkResult.measured_width_mm === null ? "-" : `${benchmarkResult.measured_width_mm} mm`} />
                  <Info label="Ground truth" value={`${benchmarkResult.ground_truth_length_mm ?? "-"} x ${benchmarkResult.ground_truth_width_mm ?? "-"} mm`} />
                </div>
                <p className="mt-4 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  Accuracy claim blocked until at least 50 real-device benchmarks across 3 device groups pass the internal thresholds.
                </p>
                {benchmarkResult.failure_reasons_json?.length ? (
                  <ul className="mt-4 grid gap-2 text-sm text-zinc-600">
                    {benchmarkResult.failure_reasons_json.map((reason) => (
                      <li key={reason} className="rounded-md bg-zinc-50 px-3 py-2">
                        {reason}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </article>
            )}
          </div>
        </section>
      </div>
    </DashboardShell>
  );
}

function TextInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-1 text-sm">
      <span className="text-zinc-500">{label}</span>
      <input className="h-10 rounded-md border border-zinc-300 px-3" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function NumberInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number | "";
  onChange: (value: number | null) => void;
}) {
  return (
    <label className="grid gap-1 text-sm">
      <span className="text-zinc-500">{label}</span>
      <input
        className="h-10 rounded-md border border-zinc-300 px-3"
        type="number"
        value={value}
        onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))}
      />
    </label>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-zinc-50 p-3">
      <p className="text-zinc-500">{label}</p>
      <p className="mt-1 font-semibold">{value}</p>
    </div>
  );
}

function validationReadiness(validationCase: ValidationCase, form: ValidationCaseCreate) {
  const bboxReady = Boolean(
    form.reference_bbox_width ??
      validationCase.reference_bbox_width ??
      (validationCase.reference_polygon_json?.length ? 1 : 0),
  );
  return [
    { label: "image uploaded", ready: Boolean(validationCase.image_upload_id) },
    {
      label: "manual length entered",
      ready: Boolean(form.ground_truth_length_mm ?? validationCase.ground_truth_length_mm),
    },
    {
      label: "manual width entered",
      ready: Boolean(form.ground_truth_width_mm ?? validationCase.ground_truth_width_mm),
    },
    {
      label: "reference object selected",
      ready: (form.reference_mode ?? validationCase.reference_mode) !== "none",
    },
    { label: "reference bbox drawn", ready: bboxReady },
    { label: "scan linked/created", ready: Boolean(form.scan_id ?? validationCase.scan_id) },
  ];
}
