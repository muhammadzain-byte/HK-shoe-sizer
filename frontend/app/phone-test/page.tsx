"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Activity, RefreshCcw, ShieldCheck, UploadCloud, Wifi } from "lucide-react";

import {
  getApiHealth,
  getMe,
  getRuntimeApiConfig,
  resetRuntimeApiConfigForRetry,
  uploadLocalValidationImage,
  type RuntimeApiConfig,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

type TestStatus = "idle" | "running" | "passed" | "failed" | "skipped";

type TestResult = {
  status: TestStatus;
  output: string;
};

const EMPTY_RESULT: TestResult = { status: "idle", output: "Not run yet." };

export default function PhoneTestPage() {
  const { token, user } = useAuth();
  const [runtime, setRuntime] = useState<RuntimeApiConfig | null>(null);
  const [browserUrl, setBrowserUrl] = useState("");
  const [healthResult, setHealthResult] = useState<TestResult>(EMPTY_RESULT);
  const [authResult, setAuthResult] = useState<TestResult>(EMPTY_RESULT);
  const [uploadResult, setUploadResult] = useState<TestResult>(EMPTY_RESULT);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);

  const tokenState = token ? "present" : "missing";
  const statusMessage = useMemo(() => {
    if (healthResult.status === "failed") {
      return "Your phone cannot reach the backend. This is usually Windows Firewall or Wi-Fi isolation.";
    }
    if (healthResult.status === "passed") {
      return "Backend is reachable from this browser.";
    }
    return "Run the backend health test from your phone.";
  }, [healthResult.status]);

  const loadRuntime = async (force = false) => {
    try {
      setRuntimeError(null);
      if (force) {
        resetRuntimeApiConfigForRetry();
      }
      const config = await getRuntimeApiConfig();
      setRuntime(config);
      setBrowserUrl(window.location.href);
    } catch (caught) {
      setRuntimeError(caught instanceof Error ? caught.message : "Runtime config could not be loaded.");
    }
  };

  useEffect(() => {
    void loadRuntime();
  }, []);

  const testHealth = async () => {
    setHealthResult({ status: "running", output: "Checking backend health..." });
    try {
      const response = await getApiHealth();
      setHealthResult({ status: "passed", output: JSON.stringify(response, null, 2) });
    } catch (caught) {
      setHealthResult({ status: "failed", output: formatError(caught) });
    }
  };

  const testAuth = async () => {
    if (!token) {
      setAuthResult({ status: "skipped", output: "No token found. Log in on this browser, then retry." });
      return;
    }
    setAuthResult({ status: "running", output: "Checking /auth/me..." });
    try {
      const response = await getMe(token);
      setAuthResult({ status: "passed", output: JSON.stringify(response, null, 2) });
    } catch (caught) {
      setAuthResult({ status: "failed", output: formatError(caught) });
    }
  };

  const testUpload = async () => {
    if (!token) {
      setUploadResult({ status: "skipped", output: "No token found. Log in on this browser, then retry." });
      return;
    }
    setUploadResult({ status: "running", output: "Uploading tiny generated PNG..." });
    try {
      const tinyPng = base64ToBlob(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
        "image/png",
      );
      const file = new File([tinyPng], `phone-test-${Date.now()}.png`, { type: "image/png" });
      const response = await uploadLocalValidationImage(token, { file });
      setUploadResult({ status: "passed", output: JSON.stringify(response, null, 2) });
    } catch (caught) {
      setUploadResult({ status: "failed", output: formatError(caught) });
    }
  };

  return (
    <main className="min-h-screen bg-zinc-50 px-4 py-6 text-zinc-900 sm:px-6 lg:px-8">
      <div className="mx-auto grid max-w-5xl gap-5">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-sage">Phone access</p>
            <h1 className="mt-1 text-3xl font-semibold">Phone network test</h1>
            <p className="mt-2 max-w-2xl text-sm text-zinc-600">{statusMessage}</p>
          </div>
          <button
            className="inline-flex h-10 items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-semibold"
            type="button"
            onClick={() => void loadRuntime(true)}
          >
            <RefreshCcw className="h-4 w-4" aria-hidden="true" />
            Refresh runtime config
          </button>
        </header>

        <section className="rounded-md border border-zinc-200 bg-white p-4 text-sm">
          <div className="grid gap-2 md:grid-cols-2">
            <Info label="Current browser URL" value={browserUrl || "loading..."} />
            <Info label="Runtime source" value={runtime?.source ?? "loading"} />
            <Info label="Runtime API base" value={runtime?.api_base_url ?? "loading..."} />
            <Info label="Runtime backend health" value={runtime?.health_url ?? "loading..."} />
            <Info label="Runtime frontend URL" value={runtime?.frontend_url ?? "loading..."} />
            <Info label="Auth token" value={tokenState} />
            <Info label="Signed in as" value={user?.email ?? "not signed in"} />
            <Info label="Database mode" value={runtime?.database_mode ?? "unknown"} />
          </div>
          {runtimeError ? <p className="mt-3 text-red-700">{runtimeError}</p> : null}
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          <PhoneTestCard
            title="Backend health"
            icon={<Wifi className="h-5 w-5" aria-hidden="true" />}
            buttonLabel="Test backend health"
            result={healthResult}
            onRun={testHealth}
          />
          <PhoneTestCard
            title="Auth session"
            icon={<ShieldCheck className="h-5 w-5" aria-hidden="true" />}
            buttonLabel="Test auth/me"
            result={authResult}
            onRun={testAuth}
          />
          <PhoneTestCard
            title="Local upload"
            icon={<UploadCloud className="h-5 w-5" aria-hidden="true" />}
            buttonLabel="Test tiny upload"
            result={uploadResult}
            onRun={testUpload}
          />
        </section>

        <section className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
          <div className="flex items-start gap-2">
            <Activity className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-semibold">If this page loads but backend health fails</p>
              <p className="mt-1">
                Check Windows Firewall, same Wi-Fi, VPN, Windows network profile, and router client isolation.
                Camera capture on mobile may require HTTPS; use the tunnel helper when LAN HTTP works but camera
                permissions are blocked.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <p className="break-all">
      <span className="font-medium text-zinc-800">{label}:</span> {value}
    </p>
  );
}

function PhoneTestCard({
  title,
  icon,
  buttonLabel,
  result,
  onRun,
}: {
  title: string;
  icon: ReactNode;
  buttonLabel: string;
  result: TestResult;
  onRun: () => Promise<void>;
}) {
  return (
    <div className="rounded-md border border-zinc-200 bg-white p-4">
      <div className="flex items-center gap-2">
        <span className="text-sage">{icon}</span>
        <h2 className="font-semibold">{title}</h2>
      </div>
      <button
        className="mt-4 inline-flex h-10 items-center rounded-md bg-ink px-3 text-sm font-semibold text-white disabled:opacity-60"
        type="button"
        onClick={() => void onRun()}
        disabled={result.status === "running"}
      >
        {result.status === "running" ? "Testing..." : buttonLabel}
      </button>
      <p className={`mt-3 text-xs font-semibold ${statusClass(result.status)}`}>Status: {result.status}</p>
      <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-zinc-950 p-3 text-xs text-zinc-50">
        {result.output}
      </pre>
    </div>
  );
}

function statusClass(status: TestStatus) {
  if (status === "passed") return "text-emerald-700";
  if (status === "failed") return "text-red-700";
  if (status === "running") return "text-sky-700";
  if (status === "skipped") return "text-amber-700";
  return "text-zinc-500";
}

function formatError(caught: unknown) {
  return caught instanceof Error ? caught.message : "Unknown network error.";
}

function base64ToBlob(base64: string, type: string) {
  const raw = atob(base64);
  const bytes = new Uint8Array(raw.length);
  for (let index = 0; index < raw.length; index += 1) {
    bytes[index] = raw.charCodeAt(index);
  }
  return new Blob([bytes], { type });
}
