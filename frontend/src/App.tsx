import { useEffect, useState } from "react";

import { getBoard, isSignedIn, signIn, signOut, type Board } from "./api.ts";
import BoardView from "./BoardView.tsx";

export default function App() {
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [signedIn, setSignedIn] = useState(isSignedIn);

  useEffect(() => {
    getBoard()
      .then(setBoard)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <h1 className="text-lg font-semibold tracking-tight">PixelWars</h1>
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
        {board && <BoardView board={board} />}

        {!loading && !error && (
          <p className="text-sm text-slate-500">
            Scroll to pan, ctrl/⌘+wheel to zoom.
            {signedIn ? "" : " Sign in to place pixels."}
          </p>
        )}
      </main>
    </div>
  );
}
