export type DataMode = "mock" | "live";

// Read at build time. Only NEXT_PUBLIC_* values reach the browser; keep secrets out of this variable.
export const DATA_MODE: DataMode =
  process.env.NEXT_PUBLIC_DATA_MODE === "live" ? "live" : "mock";

export const IS_MOCK = DATA_MODE === "mock";

/** Browser-side API base. The Next.js rewrite forwards it to the FastAPI server. */
export const API_BASE = "/api/backend";

export const TOKEN_STORAGE_KEY = "mpa_access_token";
