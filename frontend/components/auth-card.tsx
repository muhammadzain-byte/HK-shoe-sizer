"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { API_BASE_URL, getApiHealth, register as registerRequest } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type AuthCardProps = {
  mode: "login" | "register";
};

export function AuthCard({ mode }: AuthCardProps) {
  const isLogin = mode === "login";
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<"checking" | "connected" | "not_connected">("checking");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let isMounted = true;
    getApiHealth()
      .then((health) => {
        if (isMounted) {
          setBackendStatus(
            health.status === "ok" && ["connected", "sqlite_testing_fallback"].includes(health.database)
              ? "connected"
              : "not_connected",
          );
        }
      })
      .catch(() => {
        if (isMounted) {
          setBackendStatus("not_connected");
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      if (!isLogin) {
        await registerRequest({
          email,
          password,
          first_name: firstName || undefined,
          last_name: lastName || undefined,
        });
      }
      await login(email, password);
      router.replace("/dashboard");
    } catch (caught) {
      setError(formatAuthError(caught, isLogin));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-porcelain px-5 py-10">
      <section className="w-full max-w-md rounded-lg border border-zinc-200 bg-white p-8 shadow-panel">
        <h1 className="text-2xl font-semibold">{isLogin ? "Welcome back" : "Create your account"}</h1>
        <p className="mt-2 text-sm leading-6 text-zinc-600">
          {isLogin
            ? "Access your scans, recommendations, and profile."
            : "Start a women-only sizing profile for future foot scans."}
        </p>
        <div className="mt-4 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm">
          <div className="flex items-center justify-between gap-3">
            <span className="font-medium text-zinc-700">Backend</span>
            <span
              className={
                backendStatus === "connected"
                  ? "font-semibold text-emerald-700"
                  : backendStatus === "checking"
                    ? "font-semibold text-zinc-600"
                    : "font-semibold text-red-700"
              }
            >
              {backendStatus === "connected"
                ? "Connected"
                : backendStatus === "checking"
                  ? "Checking..."
                  : "Not connected"}
            </span>
          </div>
          <p className="mt-1 break-all text-xs text-zinc-500">{API_BASE_URL}</p>
        </div>
        <form className="mt-8 grid gap-4" onSubmit={handleSubmit}>
          {!isLogin && (
            <div className="grid gap-2 sm:grid-cols-2">
              <input
                className="h-11 rounded-md border border-zinc-300 px-3"
                placeholder="First name"
                value={firstName}
                onChange={(event) => setFirstName(event.target.value)}
              />
              <input
                className="h-11 rounded-md border border-zinc-300 px-3"
                placeholder="Last name"
                value={lastName}
                onChange={(event) => setLastName(event.target.value)}
              />
            </div>
          )}
          <input
            className="h-11 rounded-md border border-zinc-300 px-3"
            placeholder="Email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
          {isLogin && (
            <p className="text-xs text-zinc-500">
              Use your app email, not the PostgreSQL database username.
            </p>
          )}
          <input
            className="h-11 rounded-md border border-zinc-300 px-3"
            placeholder="Password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            minLength={10}
            required
          />
          {error && (
            <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}
          <button
            className="h-11 rounded-md bg-ink px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Please wait..." : isLogin ? "Sign in" : "Create account"}
          </button>
        </form>
        <p className="mt-6 text-sm text-zinc-600">
          {isLogin ? "Need an account? " : "Already registered? "}
          <Link className="font-semibold text-ink underline" href={isLogin ? "/register" : "/login"}>
            {isLogin ? "Register" : "Sign in"}
          </Link>
        </p>
      </section>
    </main>
  );
}

function formatAuthError(caught: unknown, isLogin: boolean) {
  const message = caught instanceof Error ? caught.message : "Something went wrong.";
  if (message.includes("Backend is not reachable") || message.includes("Failed to fetch")) {
    return `Backend is not reachable. Start the app with scripts/run-app-now.ps1 -Force and check ${API_BASE_URL}/health.`;
  }
  if (isLogin && message.toLowerCase().includes("invalid email or password")) {
    return "Invalid email or password. Use your app email, not the database username.";
  }
  if (!isLogin && (message.toLowerCase().includes("already exists") || message.includes("409"))) {
    return "Account already exists. Please sign in.";
  }
  return message;
}
