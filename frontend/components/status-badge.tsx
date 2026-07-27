import type { FootScan } from "@/lib/types";

const labels: Record<FootScan["status"], string> = {
  created: "Created",
  image_uploaded: "Image uploaded",
  processing: "Processing",
  validation_passed: "Validation passed",
  validation_failed: "Validation failed",
  measured: "Measured",
  completed: "Completed",
  failed: "Failed",
  archived: "Archived",
};

const styles: Record<FootScan["status"], string> = {
  created: "bg-zinc-100 text-zinc-700",
  image_uploaded: "bg-sage/15 text-sage",
  processing: "bg-lilac/15 text-lilac",
  validation_passed: "bg-emerald-100 text-emerald-700",
  validation_failed: "bg-red-100 text-red-700",
  measured: "bg-emerald-100 text-emerald-700",
  completed: "bg-emerald-100 text-emerald-700",
  failed: "bg-red-100 text-red-700",
  archived: "bg-zinc-200 text-zinc-600",
};

export function StatusBadge({ status }: { status: FootScan["status"] }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${styles[status]}`}>
      {labels[status]}
    </span>
  );
}
