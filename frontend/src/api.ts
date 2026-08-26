import { decodeBoard, type Board } from "./board.ts";

export type { Board };

export async function getBoard(): Promise<Board | null> {
  const res = await fetch("/boards/");

  // The endpoint 500s once the buffer holds a byte that is not valid UTF-8,
  // because it returns raw redis `bytes` that pydantic decodes as UTF-8.
  if (res.status === 500) {
    throw new Error(
      "The API could not serialise the board. GET /boards/ returns raw bytes, " +
        "which only survives JSON encoding while the buffer is all zeros.",
    );
  }
  if (!res.ok) throw new Error(`Board request failed (${res.status})`);

  const raw = (await res.json()) as string | null;
  return raw ? decodeBoard(raw) : null;
}

// ponytail: the session cookie is httpOnly and the API has no /auth/me, so
// signed-in state is a local guess: set on sign-in, cleared on any 401.
// Replace with a real `GET /auth/me` call when the endpoint exists.
const KEY = "pixelwars.signedIn";

export const isSignedIn = () => localStorage.getItem(KEY) === "1";

/** Full-page POST — the API answers /auth/google with a redirect to Google. */
export function signIn() {
  localStorage.setItem(KEY, "1");
  const form = document.createElement("form");
  form.method = "POST";
  form.action = "/auth/google";
  document.body.append(form);
  form.submit();
}

export async function signOut() {
  await fetch("/auth/logout", { method: "POST" });
  localStorage.removeItem(KEY);
}

/** Wrap any write so an expired session drops us back to the signed-out UI. */
export async function authed<T>(call: () => Promise<Response>): Promise<T> {
  const res = await call();
  if (res.status === 401) {
    localStorage.removeItem(KEY);
    throw new Error("Session expired — sign in again");
  }
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.json() as Promise<T>;
}
