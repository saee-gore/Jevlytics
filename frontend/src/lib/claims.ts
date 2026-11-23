/**
 * Reads the payload of the session token for DISPLAY ONLY (merchant ID and user ID in the sidebar).
 * The browser does not verify the signature and never uses these values for an authorization decision.
 * Every request is authorised by the backend from the token it receives.
 */
export interface DisplayClaims {
  merchantId: string | null;
  userId: string | null;
}

export function readDisplayClaims(token: string | null): DisplayClaims {
  const empty: DisplayClaims = { merchantId: null, userId: null };
  if (!token) return empty;
  const parts = token.split(".");
  if (parts.length !== 3) return empty;
  try {
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    const payload = JSON.parse(atob(padded)) as Record<string, unknown>;
    return {
      merchantId: typeof payload.merchant_id === "string" ? payload.merchant_id : null,
      userId: typeof payload.sub === "string" ? payload.sub : null,
    };
  } catch {
    return empty;
  }
}
