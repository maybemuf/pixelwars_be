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

/** Subscribe to live writes. Server may send one pixel or a batch. */
export function onPixels(handler: (pixels: PixelEvent[]) => void) {
  const fn = (data: PixelEvent | PixelEvent[]) => handler(Array.isArray(data) ? data : [data]);
  socket.on("pixel", fn);
  return () => {
    socket.off("pixel", fn);
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
