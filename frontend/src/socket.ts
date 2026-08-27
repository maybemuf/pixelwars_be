import { io } from "socket.io-client";

/** One pixel write, in the same shape the REST endpoint takes. */
export type PixelEvent = { offset: number; color: number };

/** Server's answer to a place_pixel emit; `error` set when it refused. */
export type PlaceAck = { error?: string } | undefined;

/**
 * Same-origin connect: nginx (prod) and the vite dev proxy both forward
 * /socket.io/, so the httpOnly session cookie rides along with the handshake
 * and the server can tell who is painting. Reading the board needs no auth.
 */
export const socket = io("/boards", { path: "/socket.io", withCredentials: true, autoConnect: false });

/**
 * Writes that landed with nobody listening: the HTTP board is still in flight,
 * or the canvas is between mounts. Held here and replayed to the next
 * subscriber so those pixels end up on the board instead of lost. Ordering is
 * preserved, so replaying a write the snapshot already contains is harmless.
 */
let sink: ((pixels: PixelEvent[]) => void) | null = null;
let pending: PixelEvent[] = [];

socket.on("pixel", (data: PixelEvent | PixelEvent[]) => {
  const batch = Array.isArray(data) ? data : [data];
  if (sink) sink(batch);
  else pending.push(...batch);
});

/** Subscribe to live writes, replaying anything buffered. Single subscriber. */
export function onPixels(handler: (pixels: PixelEvent[]) => void) {
  sink = handler;
  if (pending.length) {
    handler(pending);
    pending = [];
  }
  return () => {
    if (sink === handler) sink = null;
  };
}

/** Live count of clients watching the board; server pushes it on every join/leave. */
export function onUsers(handler: (count: number) => void) {
  const fn = (data: { count: number }) => handler(data.count);
  socket.on("users", fn);
  return () => {
    socket.off("users", fn);
  };
}

/** Ask the server to paint. It validates the session and echoes a `pixel`. */
export function placePixel(pixel: PixelEvent, onAck?: (ack: PlaceAck) => void) {
  socket.emit("place_pixel", pixel, onAck ?? (() => {}));
}
