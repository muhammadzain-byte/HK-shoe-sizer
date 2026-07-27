import Link from "next/link";
import { ArrowRight, Camera, Ruler, ShieldCheck } from "lucide-react";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-porcelain">
      <section className="mx-auto grid min-h-[88vh] max-w-6xl items-center gap-10 px-5 py-10 lg:grid-cols-[1.1fr_0.9fr]">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-clay">Women-only sizing platform</p>
          <h1 className="mt-4 max-w-3xl text-5xl font-semibold leading-tight text-ink sm:text-6xl">
            MirrorStep
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-8 text-zinc-700">
            Capture a guided foot photo today. Add segmentation, depth estimation, and size intelligence tomorrow
            without rebuilding the product foundation.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link className="inline-flex h-11 items-center gap-2 rounded-md bg-ink px-5 text-sm font-semibold text-white" href="/register">
              Start sizing
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
            <Link className="inline-flex h-11 items-center rounded-md border border-zinc-300 px-5 text-sm font-semibold" href="/login">
              Sign in
            </Link>
          </div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-panel">
          <div className="aspect-[4/5] rounded-md bg-[radial-gradient(circle_at_30%_20%,#ffffff,transparent_30%),linear-gradient(145deg,#d8e1d2,#f2d4ca_48%,#dad2e1)] p-5">
            <div className="flex h-full flex-col justify-end rounded-md border border-white/70 bg-white/55 p-5 backdrop-blur">
              <div className="grid gap-3">
                {[
                  { icon: Camera, label: "Guided capture" },
                  { icon: Ruler, label: "Measurement-ready scans" },
                  { icon: ShieldCheck, label: "Private upload contracts" },
                ].map((item) => {
                  const Icon = item.icon;
                  return (
                    <div key={item.label} className="flex items-center gap-3 rounded-md bg-white p-3 text-sm font-semibold">
                      <Icon className="h-4 w-4 text-sage" aria-hidden="true" />
                      {item.label}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </section>
      <section className="border-t border-zinc-200 bg-white">
        <div className="mx-auto grid max-w-6xl gap-4 px-5 py-8 sm:grid-cols-3">
          {["S3 upload abstraction", "JWT authenticated APIs", "SAM and YOLOv8 contracts"].map((label) => (
            <div key={label} className="rounded-md border border-zinc-200 p-4 text-sm font-semibold text-zinc-700">
              {label}
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

