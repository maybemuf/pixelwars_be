import { useEffect, useState } from "react";

import { getBoard, isSignedIn, signIn, signOut, type Board } from "./api.ts";
import { PALETTE } from "./board.ts";
import BoardView from "./BoardView.tsx";
import { onUsers, placePixel, socket } from "./socket.ts";

export default function App() {
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [signedIn, setSignedIn] = useState(isSignedIn);
  const [live, setLive] = useState(false);
  const [users, setUsers] = useState<number | null>(null);
  const [color, setColor] = useState(5);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    getBoard()
      .then(setBoard)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Anyone opening the board joins the live feed; no auth for reading.
  useEffect(() => {
    const on = () => setLive(true);
    // While offline the last count is a lie — the room moved on without us.
    const off = () => {
      setLive(false);
      setUsers(null);
    };
    socket.on("connect", on);
    socket.on("disconnect", off);
    const offUsers = onUsers(setUsers);
    socket.connect();

    return () => {
      socket.off("connect", on);
      socket.off("disconnect", off);
      offUsers();
      socket.disconnect();
    };
  }, []);

  const place = (offset: number) =>
    placePixel({ offset, color }, (ack) => setNotice(ack?.error ?? null));

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <h1 className="flex items-center gap-3 text-lg font-semibold tracking-tight">
          PixelWars
          <span
            title={live ? "Live" : "Reconnecting…"}
            className={`h-2 w-2 rounded-full ${live ? "bg-emerald-400" : "bg-slate-600"}`}
          />
          {users !== null && (
            <span className="text-sm font-normal text-slate-400">
              {users} {users === 1 ? "person" : "people"} here
            </span>
          )}
        </h1>
        {signedIn ? (
          <button
            onClick={() => signOut().then(() => setSignedIn(false))}
            className="rounded-md border border-slate-700 px-3 py-1.5 text-sm hover:bg-slate-800"
          >
            Sign out
          </button>
        ) : (
          <button
            onClick={signIn}
            className="rounded-md bg-white px-3 py-1.5 text-sm font-medium text-slate-900 hover:bg-slate-200"
          >
            Sign in with Google
          </button>
        )}
      </header>

      <main className="flex flex-col items-center gap-4 p-6">
        {loading && <p className="text-slate-400">Loading board…</p>}
        {error && <p className="max-w-xl text-center text-red-400">{error}</p>}
        {!loading && !error && !board && <p className="text-slate-400">No board yet.</p>}
        {board && <BoardView board={board} color={signedIn ? color : null} onPlace={place} />}

        {board && signedIn && (
          <div className="flex flex-wrap justify-center gap-1">
            {PALETTE.map((hex, i) => (
              <button
                key={hex}
                onClick={() => setColor(i)}
                aria-label={`Colour ${i}`}
                aria-pressed={i === color}
                style={{ backgroundColor: hex }}
                className={`h-8 w-8 rounded border-2 ${i === color ? "border-sky-400" : "border-slate-800"}`}
              />
            ))}
          </div>
        )}

        {notice && <p className="text-sm text-amber-400">{notice}</p>}

        {!loading && !error && (
          <p className="text-sm text-slate-500">
            Scroll to pan, ctrl/⌘+wheel to zoom.
            {signedIn ? " Pick a colour, then click a pixel." : " Sign in to place pixels."}
          </p>
        )}
      </main>
    </div>
  );
}
