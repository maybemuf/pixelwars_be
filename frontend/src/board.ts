/** Board wire format. Change here if the backend fixes the layout. */
export const WIDTH = 1024;
export const HEIGHT = 1024;
export const BITS_PER_PIXEL = 4;

/** Bytes the grid actually occupies; redis holds one trailing byte more. */
export const BOARD_BYTES = (WIDTH * HEIGHT * BITS_PER_PIXEL) / 8;

/** 16-colour palette, indexed by the nibble stored per pixel. */
export const PALETTE = [
  "#ffffff", "#e4e4e4", "#888888", "#222222",
  "#ffa7d1", "#e50000", "#e59500", "#a06a42",
  "#e5d900", "#94e044", "#02be01", "#00d3dd",
  "#0083c7", "#0000ea", "#cf6ee4", "#820080",
] as const;

export type Board = { width: number; height: number; pixels: Uint8Array };

/** The API base64-encodes the raw redis buffer; `atob` gives the bytes back. */
export function decodeBoard(raw: string): Board {
  const bin = atob(raw);
  const buf = Uint8Array.from(bin, (c) => c.charCodeAt(0));
  if (buf.length < BOARD_BYTES) {
    throw new Error(`Board is ${buf.length} bytes, expected at least ${BOARD_BYTES}`);
  }

  // One nibble per pixel, high nibble first.
  const pixels = new Uint8Array(WIDTH * HEIGHT);
  for (let i = 0; i < BOARD_BYTES; i++) {
    pixels[i * 2] = buf[i] >> 4;
    pixels[i * 2 + 1] = buf[i] & 0x0f;
  }

  return { width: WIDTH, height: HEIGHT, pixels };
}

/** Palette indices -> RGBA, ready for `ctx.putImageData`. */
export function toImageData(board: Board): ImageData {
  const rgba = new Uint8ClampedArray(board.pixels.length * 4);

  for (let p = 0; p < board.pixels.length; p++) {
    const hex = PALETTE[board.pixels[p]] ?? PALETTE[0];
    rgba[p * 4] = parseInt(hex.slice(1, 3), 16);
    rgba[p * 4 + 1] = parseInt(hex.slice(3, 5), 16);
    rgba[p * 4 + 2] = parseInt(hex.slice(5, 7), 16);
    rgba[p * 4 + 3] = 255;
  }

  return new ImageData(rgba, board.width, board.height);
}

/** Fallback floor for when the viewport has not been measured yet. */
export const MIN_ZOOM = 0.05;
export const MAX_ZOOM = 32;

export type Viewport = { left: number; top: number; width: number; height: number };

/**
 * Smallest zoom that still covers the viewport in both axes, so the board can
 * never be zoomed out far enough to leave empty space around it.
 */
export function fitZoom(view: Viewport, boardWidth: number, boardHeight: number) {
  return Math.max(view.width / boardWidth, view.height / boardHeight) || MIN_ZOOM;
}

export const clampZoom = (zoom: number, min: number) => Math.min(MAX_ZOOM, Math.max(min, zoom));

/** Where the visible region sits on a `size`-square minimap of `boardWidth`. */
export function viewportRect(view: Viewport, zoom: number, boardWidth: number, size: number): Viewport {
  const k = size / boardWidth;
  return {
    left: (view.left / zoom) * k,
    top: (view.top / zoom) * k,
    width: Math.min(size, (view.width / zoom) * k),
    height: Math.min(size, (view.height / zoom) * k),
  };
}
