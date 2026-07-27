"use client";

import Link from "next/link";
import { Camera, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/status-badge";
import { getScanHistory } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { PaginatedScanHistory } from "@/lib/types";

const PAGE_SIZE = 10;

export function ScanHistoryTable() {
  const { token } = useAuth();
  const [history, setHistory] = useState<PaginatedScanHistory | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      return;
    }
    setIsLoading(true);
    setError(null);
    getScanHistory(token, PAGE_SIZE, offset)
      .then(setHistory)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Could not load history."))
      .finally(() => setIsLoading(false));
  }, [offset, token]);

  const canGoBack = offset > 0;
  const canGoForward = history ? offset + PAGE_SIZE < history.total : false;

  return (
    <div className="grid gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Scan history</h1>
          <p className="mt-2 text-zinc-600">Review captured scans and future recommendations.</p>
        </div>
        <Link
          className="inline-flex h-10 items-center gap-2 rounded-md bg-ink px-4 text-sm font-semibold text-white"
          href="/scans/new"
        >
          <Camera className="h-4 w-4" aria-hidden="true" />
          New
        </Link>
      </div>
      <section className="overflow-hidden rounded-lg border border-zinc-200 bg-white">
        {error ? (
          <p className="p-5 text-sm text-red-700">{error}</p>
        ) : isLoading ? (
          <p className="p-5 text-sm text-zinc-600">Loading scan history...</p>
        ) : history?.items.length ? (
          <>
            <div className="hidden grid-cols-[1.2fr_1fr_1fr_1fr_auto] gap-4 border-b border-zinc-200 px-5 py-3 text-xs font-semibold uppercase text-zinc-500 md:grid">
              <span>Scan</span>
              <span>Status</span>
              <span>Images</span>
              <span>Created</span>
              <span>Open</span>
            </div>
            <div className="divide-y divide-zinc-100">
              {history.items.map((item) => (
                <Link
                  key={item.scan.id}
                  href={`/scans/${item.scan.id}`}
                  className="grid gap-3 px-5 py-4 text-sm md:grid-cols-[1.2fr_1fr_1fr_1fr_auto] md:items-center"
                >
                  <div>
                    <p className="font-semibold capitalize">{item.scan.foot_side} foot</p>
                    <p className="mt-1 truncate text-xs text-zinc-500">{item.scan.id}</p>
                  </div>
                  <StatusBadge status={item.scan.status} />
                  <span className="text-zinc-600">{item.uploaded_image_count}</span>
                  <span className="text-zinc-600">
                    {new Date(item.scan.created_at).toLocaleDateString()}
                  </span>
                  <span className="text-sm font-semibold underline">Details</span>
                </Link>
              ))}
            </div>
          </>
        ) : (
          <p className="p-5 text-sm leading-6 text-zinc-600">
            No scans yet. Create a new scan from the dashboard or capture page.
          </p>
        )}
        <div className="flex items-center justify-between border-t border-zinc-200 px-5 py-4">
          <p className="text-sm text-zinc-600">
            {history ? `${history.total} total scans` : "No scans loaded"}
          </p>
          <div className="flex gap-2">
            <button
              className="inline-flex h-9 items-center gap-1 rounded-md border border-zinc-300 px-3 text-sm font-semibold disabled:opacity-40"
              type="button"
              disabled={!canGoBack || isLoading}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              Back
            </button>
            <button
              className="inline-flex h-9 items-center gap-1 rounded-md border border-zinc-300 px-3 text-sm font-semibold disabled:opacity-40"
              type="button"
              disabled={!canGoForward || isLoading}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

