import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { clampZoom, fitZoom, toImageData, viewportRect, type Board } from "./board.ts";

const GRID_FROM = 8; // screen px per board pixel before a grid is legible
const MINIMAP = 160;
const WHEEL_STEP = 1.06; // one wheel notch; gentle enough to land on a level
const BUTTON_STEP = 1.25;

/** Pan with the native scrollbars, zoom with ctrl/cmd+wheel or the buttons. */
export default function BoardView({ board }: { board: Board }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const minimapRef = useRef<HTMLCanvasElement>(null);

  /** Board point to keep under the cursor across the next zoom change. */
  const anchor = useRef<{ x: number; y: number; cx: number; cy: number } | null>(null);

  const [zoom, setZoom] = useState(1);
  const [view, setView] = useState({ left: 0, top: 0, width: 0, height: 0 });
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null);

  const readView = () => {
    const el = scrollRef.current;
    if (el) {
      setView({ left: el.scrollLeft, top: el.scrollTop, width: el.clientWidth, height: el.clientHeight });
    }
  };

  const fit = fitZoom(view, board.width, board.height);
  const showMinimap = zoom > fit * 1.001; // useless while the board is fully zoomed out

  // The wheel listener is installed once, so it reads the floor through a ref
  // rather than closing over the first render's unmeasured viewport.
  const fitRef = useRef(fit);
  fitRef.current = fit;

  useEffect(() => {
    canvasRef.current?.getContext("2d")?.putImageData(toImageData(board), 0, 0);
  }, [board]);

  // Downscale the board canvas into the minimap. Effects run in order, so the
  // board is already painted; keyed on visibility so a re-mount redraws.
  useEffect(() => {
    const ctx = minimapRef.current?.getContext("2d");
    if (!canvasRef.current || !ctx) return;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(canvasRef.current, 0, 0, MINIMAP, MINIMAP);
  }, [board, showMinimap]);

  // A resize can grow the viewport past the current zoom; follow it back up.
  useEffect(() => {
    setZoom((z) => Math.max(z, fit));
  }, [fit]);

  useEffect(() => {
    window.addEventListener("resize", readView);
    return () => window.removeEventListener("resize", readView);
  }, []);

  const zoomAt = (factor: number, cx: number, cy: number) => {
    const el = scrollRef.current;
    if (!el) return;

    setZoom((z) => {
      const next = clampZoom(z * factor, fitRef.current);
      if (next === z) return z;
      anchor.current = { x: (el.scrollLeft + cx) / z, y: (el.scrollTop + cy) / z, cx, cy };
      return next;
    });
  };

  // The scaled wrapper has already been resized by the time this runs, so the
  // anchor can be restored before the browser paints.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    if (anchor.current) {
      el.scrollLeft = anchor.current.x * zoom - anchor.current.cx;
      el.scrollTop = anchor.current.y * zoom - anchor.current.cy;
      anchor.current = null;
    }
    readView();
  }, [zoom]);

  // React attaches onWheel passively, so preventDefault needs a manual listener.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return; // plain wheel keeps native scrolling
      e.preventDefault();
      const r = el.getBoundingClientRect();
      zoomAt(e.deltaY < 0 ? WHEEL_STEP : 1 / WHEEL_STEP, e.clientX - r.left, e.clientY - r.top);
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const zoomFromCentre = (factor: number) => zoomAt(factor, view.width / 2, view.height / 2);

  const scale = board.width * zoom;
  const rect = viewportRect(view, zoom, board.width, MINIMAP);

  return (
    <div className="relative w-full max-w-3xl">
      <div
        ref={scrollRef}
        onScroll={readView}
        className="h-[70vh] overflow-auto border border-slate-800 bg-slate-900"
      >
        <div
          className="relative"
          style={{ width: scale, height: board.height * zoom }}
          onMouseMove={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            const x = Math.floor((e.clientX - r.left) / zoom);
            const y = Math.floor((e.clientY - r.top) / zoom);
            setCursor(x >= 0 && y >= 0 && x < board.width && y < board.height ? { x, y } : null);
          }}
          onMouseLeave={() => setCursor(null)}
        >
          <canvas
            ref={canvasRef}
            width={board.width}
            height={board.height}
            className="absolute inset-0 h-full w-full [image-rendering:pixelated]"
          />
          {zoom >= GRID_FROM && (
            <div
              className="pointer-events-none absolute inset-0"
              style={{
                backgroundImage:
                  "linear-gradient(to right, rgba(148,163,184,.3) 1px, transparent 1px)," +
                  "linear-gradient(to bottom, rgba(148,163,184,.3) 1px, transparent 1px)",
                backgroundSize: `${zoom}px ${zoom}px`,
              }}
            />
          )}
        </div>
      </div>

      {showMinimap && (
        <div className="absolute right-3 top-3 border border-slate-700 bg-slate-950/80">
          <canvas
            ref={minimapRef}
            width={MINIMAP}
            height={MINIMAP}
            className="block [image-rendering:pixelated]"
          />
          <div
            className="pointer-events-none absolute border border-sky-400 bg-sky-400/20"
            style={rect}
          />
        </div>
      )}

      <div className="absolute bottom-3 right-3 flex items-center gap-2 rounded border border-slate-700 bg-slate-950/80 px-2 py-1 font-mono text-xs text-slate-300">
        <button onClick={() => zoomFromCentre(1 / BUTTON_STEP)} className="px-1 hover:text-white" aria-label="Zoom out">
          −
        </button>
        <span className="tabular-nums">{Math.round(zoom * 100)}%</span>
        <button onClick={() => zoomFromCentre(BUTTON_STEP)} className="px-1 hover:text-white" aria-label="Zoom in">
          +
        </button>
        <span className="tabular-nums text-slate-500">
          {cursor ? `${cursor.x}, ${cursor.y}` : `${board.width}×${board.height}`}
        </span>
      </div>
    </div>
  );
}
