/** Smallest check that fails if board decoding breaks. Run: npm run check */
import assert from "node:assert/strict";

import {
  BOARD_BYTES,
  clampZoom,
  decodeBoard,
  fitZoom,
  HEIGHT,
  MAX_ZOOM,
  MIN_ZOOM,
  viewportRect,
  WIDTH,
} from "./board.ts";
import { getBoard } from "./api.ts";

/** Base64 of `bytes`, the way the API sends the board. */
const b64 = (bytes: number[]) => Buffer.from(bytes).toString("base64");

const reply = (body: unknown, status = 200) => {
  globalThis.fetch = (async () => new Response(JSON.stringify(body), { status })) as typeof fetch;
};

reply(null);
assert.equal(await getBoard(), null, "missing key -> null");

// What redis holds today: an all-zero buffer with one trailing byte.
reply(b64(new Array(BOARD_BYTES + 1).fill(0)));
const board = await getBoard();
assert.ok(board, "empty buffer decodes");
assert.equal(board.pixels.length, WIDTH * HEIGHT, "one palette index per pixel");
assert.ok(
  board.pixels.every((p) => p === 0),
  "all pixels are palette 0",
);

// Two nibbles per byte, high nibble first. Bytes >= 0x80 must survive the
// round trip -- they are exactly what the old UTF-8 transport could not carry.
const pair = decodeBoard(b64([0xc3, 0xa9, ...new Array(BOARD_BYTES - 2).fill(0)]));
assert.deepEqual([...pair.pixels.slice(0, 4)], [0xc, 0x3, 0xa, 0x9], "high nibble first");

assert.throws(() => decodeBoard(b64([0])), /expected at least/, "short buffer rejected");

reply(null, 404);
await assert.rejects(getBoard, /failed \(404\)/, "other errors surfaced");

// Zoom stays inside its bounds whatever the wheel throws at it.
assert.equal(clampZoom(1000, 0.5), MAX_ZOOM, "zoom capped");
assert.equal(clampZoom(0.0001, 0.5), 0.5, "zoom floored at the fit level");
assert.equal(clampZoom(4, 0.5), 4, "zoom in range untouched");

// The floor covers the viewport in BOTH axes, so no whitespace can appear:
// a wide viewport is driven by its width, a tall one by its height.
const wideView = { left: 0, top: 0, width: 2048, height: 512 };
assert.equal(fitZoom(wideView, WIDTH, HEIGHT), 2, "wide viewport floors on width");
const tallView = { left: 0, top: 0, width: 512, height: 4096 };
assert.equal(fitZoom(tallView, WIDTH, HEIGHT), 4, "tall viewport floors on height");

// Before the first measurement there is no viewport to fit; fall back rather
// than returning 0 and letting the board collapse.
const unmeasured = { left: 0, top: 0, width: 0, height: 0 };
assert.equal(fitZoom(unmeasured, WIDTH, HEIGHT), MIN_ZOOM, "unmeasured falls back");

// At 1x the whole 1024 board maps onto a 160px minimap: a 512px viewport
// scrolled to the middle covers the bottom-right quarter of the map.
const rect = viewportRect({ left: 512, top: 512, width: 512, height: 512 }, 1, WIDTH, 160);
assert.deepEqual(rect, { left: 80, top: 80, width: 80, height: 80 }, "viewport maps onto minimap");

// Zoomed out far enough that the board is smaller than the viewport, the
// rect must not spill past the minimap.
const wide = viewportRect({ left: 0, top: 0, width: 4000, height: 4000 }, 0.25, WIDTH, 160);
assert.deepEqual(wide, { left: 0, top: 0, width: 160, height: 160 }, "rect clamped to minimap");

console.log("board checks passed");
