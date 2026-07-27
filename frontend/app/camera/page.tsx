import { Suspense } from "react";

import { CameraCapture } from "@/components/camera-capture";

export default function CameraCapturePage() {
  return (
    <Suspense fallback={<div className="grid min-h-screen place-items-center bg-zinc-950 text-white">Loading camera...</div>}>
      <CameraCapture />
    </Suspense>
  );
}
