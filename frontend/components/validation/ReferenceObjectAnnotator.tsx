"use client";

import { useRef, useState } from "react";

type BBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type ReferenceObjectAnnotatorProps = {
  imageUrl: string;
  bbox: BBox | null;
  onChange: (bbox: BBox) => void;
  onReset?: () => void;
};

export function ReferenceObjectAnnotator({ imageUrl, bbox, onChange, onReset }: ReferenceObjectAnnotatorProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [start, setStart] = useState<{ x: number; y: number } | null>(null);
  const [draft, setDraft] = useState<BBox | null>(null);

  const pointFromEvent = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) {
      return { x: 0, y: 0 };
    }
    return {
      x: Math.max(0, Math.round(event.clientX - rect.left)),
      y: Math.max(0, Math.round(event.clientY - rect.top)),
    };
  };

  const activeBox = draft ?? bbox;

  return (
    <div className="grid gap-3">
      <div
        ref={containerRef}
        className="relative min-h-80 overflow-hidden rounded-md border border-zinc-300 bg-zinc-100"
        onPointerDown={(event) => {
          const point = pointFromEvent(event);
          setStart(point);
          setDraft({ ...point, width: 1, height: 1 });
        }}
        onPointerMove={(event) => {
          if (!start) {
            return;
          }
          const point = pointFromEvent(event);
          setDraft({
            x: Math.min(start.x, point.x),
            y: Math.min(start.y, point.y),
            width: Math.max(1, Math.abs(point.x - start.x)),
            height: Math.max(1, Math.abs(point.y - start.y)),
          });
        }}
        onPointerUp={() => {
          if (draft) {
            onChange(draft);
          }
          setStart(null);
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="block max-h-[620px] w-full object-contain" src={imageUrl} alt="Validation case" />
        {activeBox && (
          <div
            className="pointer-events-none absolute border-2 border-sage bg-sage/20"
            style={{
              left: activeBox.x,
              top: activeBox.y,
              width: activeBox.width,
              height: activeBox.height,
            }}
          />
        )}
      </div>
      <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
        <p className="text-sm text-zinc-600">
          Draw a rectangle around the full reference object. Keep it on the same floor plane as the foot.
        </p>
        <button
          className="h-9 rounded-md border border-zinc-300 px-3 text-sm font-semibold"
          type="button"
          onClick={() => {
            setDraft(null);
            onReset?.();
          }}
        >
          Reset box
        </button>
      </div>
    </div>
  );
}
