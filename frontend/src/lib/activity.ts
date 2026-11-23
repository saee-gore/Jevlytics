// Browser-side log of the questions asked in this session. The backend has no activity endpoint yet,
// so this is NOT the audit trail. The Activity page labels it that way.
import type { ResponseStatus } from "./types";

export interface ActivityEntry {
  at: string;
  question: string;
  status: ResponseStatus | "error";
  tool: string | null;
  requestId: string | null;
}

const KEY = "mpa_session_activity";
const MAX = 50;

export function readActivity(): ActivityEntry[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(window.sessionStorage.getItem(KEY) ?? "[]") as ActivityEntry[];
  } catch {
    return [];
  }
}

export function recordActivity(entry: Omit<ActivityEntry, "at">): void {
  if (typeof window === "undefined") return;
  const next = [{ ...entry, at: new Date().toISOString() }, ...readActivity()].slice(0, MAX);
  window.sessionStorage.setItem(KEY, JSON.stringify(next));
}
