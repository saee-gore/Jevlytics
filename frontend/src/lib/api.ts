import { API_BASE, TOKEN_STORAGE_KEY } from "./config";
import type { TransactionListResponse, TransactionSummaryResponse } from "./transactions";
import { TOKEN_CHANGED_EVENT } from "./users";
import {
  ApiError,
  type CapabilitiesResponse,
  type ChatResponse,
  type HealthResponse,
} from "./types";

/** The access token is the user's own session token, held in sessionStorage only. It is never
 * compiled into the bundle and never stored by the server or in localStorage. */
export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) window.sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
  else window.sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  window.dispatchEvent(new Event(TOKEN_CHANGED_EVENT));
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  const token = getStoredToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiError("The analytics service could not be reached. Check that the API is running.", 0);
  }

  if (response.status === 401) {
    throw new ApiError("Your session has expired or is not authorised. Paste a valid token in Settings.", 401);
  }
  if (response.status === 429) {
    throw new ApiError("Too many requests. Wait a moment and try again.", 429);
  }
  if (response.status === 413) {
    throw new ApiError("That message is too long. Shorten it and try again.", 413);
  }
  if (!response.ok) {
    throw new ApiError("The service returned an error. Please try again.", response.status);
  }
  return (await response.json()) as T;
}

export function liveAsk(message: string): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", { method: "POST", body: JSON.stringify({ message }) });
}

export function liveCapabilities(): Promise<CapabilitiesResponse> {
  return request<CapabilitiesResponse>("/capabilities");
}

export function liveHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export interface TransactionQuery {
  start: string;
  end: string;
  status?: string;
  limit: number;
}

export function liveTransactions(q: TransactionQuery): Promise<TransactionListResponse> {
  const params = new URLSearchParams({ start: q.start, end: q.end, limit: String(q.limit), offset: "0" });
  if (q.status && q.status !== "ALL") params.set("status", q.status);
  return request<TransactionListResponse>(`/transactions?${params.toString()}`);
}

export function liveTransactionSummary(start: string, end: string): Promise<TransactionSummaryResponse> {
  const params = new URLSearchParams({ start, end });
  return request<TransactionSummaryResponse>(`/transactions/summary?${params.toString()}`);
}
