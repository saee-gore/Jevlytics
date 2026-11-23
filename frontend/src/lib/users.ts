// Demo user roster, taken from data/users.csv. Display and selection only.
// The backend decides what each user may see from the token it receives; this list never grants access.

export type DemoRole = "ANALYST";

export interface DemoUser {
  userId: string;
  merchantId: string;
  role: DemoRole;
  displayName: string;
}

export const DEMO_USERS: readonly DemoUser[] = [
  { userId: "demo-analyst-001", merchantId: "merchant_001", role: "ANALYST", displayName: "Demo Analyst 001" },
  { userId: "demo-analyst-002", merchantId: "merchant_002", role: "ANALYST", displayName: "Demo Analyst 002" },
  { userId: "demo-analyst-003", merchantId: "merchant_003", role: "ANALYST", displayName: "Demo Analyst 003" },
];

export const DEFAULT_USER: DemoUser = DEMO_USERS[0];

/** Window events so components in the same tab stay in step without a shared store. */
export const USER_CHANGED_EVENT = "mpa-user-changed";
export const TOKEN_CHANGED_EVENT = "mpa-token-changed";

const ACTIVE_USER_KEY = "mpa_active_user";

export function findDemoUser(userId: string | null | undefined): DemoUser | null {
  if (!userId) return null;
  return DEMO_USERS.find((u) => u.userId === userId) ?? null;
}

/** Browser-only. Call from useEffect, never during render. */
export function getActiveUser(): DemoUser {
  if (typeof window === "undefined") return DEFAULT_USER;
  return findDemoUser(window.sessionStorage.getItem(ACTIVE_USER_KEY)) ?? DEFAULT_USER;
}

export function setActiveUser(user: DemoUser): void {
  if (typeof window === "undefined") return;
  if (window.sessionStorage.getItem(ACTIVE_USER_KEY) === user.userId) return;
  window.sessionStorage.setItem(ACTIVE_USER_KEY, user.userId);
  window.dispatchEvent(new Event(USER_CHANGED_EVENT));
}
