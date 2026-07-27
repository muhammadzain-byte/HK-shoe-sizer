"use client";

import Link from "next/link";
import { Camera, History, Ruler } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "@/components/status-badge";
import { getScanHistory } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { PaginatedScanHistory } from "@/lib/types";

export function DashboardOverview() {
  const { token, user } = useAuth();
  const [history, setHistory] = useState<PaginatedScanHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      return;
    }
    setIsLoading(true);
    getScanHistory(token, 5, 0)
      .then(setHistory)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Could not load scans."))
      .finally(() => setIsLoading(false));
  }, [token]);

  const completedCount = useMemo(
    () => history?.items.filter((item) => item.scan.status === "completed").length ?? 0,
    [history],
  );

  return (
    <div className="grid gap-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-3xl font-semibold">Dashboard</h1>
          <p className="mt-2 text-zinc-600">
            {user?.first_name ? `Welcome back, ${user.first_name}.` : "Your scan activity at a glance."}
          </p>
        </div>
        <Link
          className="inline-flex h-10 items-center gap-2 rounded-md bg-ink px-4 text-sm font-semibold text-white"
          href="/scans/new"
        >
          <Camera className="h-4 w-4" aria-hidden="true" />
          New scan
        </Link>
      </div>
      <section className="grid gap-4 md:grid-cols-3">
        {[
          { label: "Total scans", value: history?.total ?? 0, icon: History },
          { label: "Completed scans", value: completedCount, icon: Ruler },
          { label: "Recent uploads", value: history?.items.filter((item) => item.uploaded_image_count > 0).length ?? 0, icon: Camera },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <article key={item.label} className="rounded-lg border border-zinc-200 bg-white p-5">
              <Icon className="h-5 w-5 text-clay" aria-hidden="true" />
              <p className="mt-4 text-sm text-zinc-500">{item.label}</p>
              <p className="mt-1 text-2xl font-semibold">{isLoading ? "..." : item.value}</p>
            </article>
          );
        })}
      </section>
      <section className="rounded-lg border border-zinc-200 bg-white">
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-4">
          <h2 className="text-lg font-semibold">Recent scans</h2>
          <Link className="text-sm font-semibold underline" href="/scans">
            View all
          </Link>
        </div>
        {error ? (
          <p className="p-5 text-sm text-red-700">{error}</p>
        ) : history?.items.length ? (
          <div className="divide-y divide-zinc-100">
            {history.items.map((item) => (
              <Link
                key={item.scan.id}
                className="flex items-center justify-between gap-4 px-5 py-4 text-sm"
                href={`/scans/${item.scan.id}`}
              >
                <div>
                  <p className="font-semibold capitalize">{item.scan.foot_side} foot</p>
                  <p className="mt-1 text-zinc-500">{new Date(item.scan.created_at).toLocaleString()}</p>
                </div>
                <StatusBadge status={item.scan.status} />
              </Link>
            ))}
          </div>
        ) : (
          <p className="p-5 text-sm leading-6 text-zinc-600">
            {isLoading ? "Loading scans..." : "No scans yet. Create your first scan to begin."}
          </p>
        )}
      </section>
    </div>
  );
}

