"use client";

import { Check, ChevronUp, UserCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { getStoredToken, setStoredToken } from "@/lib/api";
import { readDisplayClaims } from "@/lib/claims";
import { IS_MOCK } from "@/lib/config";
import { DEMO_MERCHANTS } from "@/lib/mock";
import {
  DEMO_USERS,
  DEFAULT_USER,
  TOKEN_CHANGED_EVENT,
  USER_CHANGED_EVENT,
  findDemoUser,
  getActiveUser,
  setActiveUser,
  type DemoUser,
} from "@/lib/users";
import { cn } from "@/lib/utils";

/**
 * Bottom-left of the sidebar. Chooses which demo user the app acts as.
 * Display and selection only: the backend authorises every request from the token it receives.
 * In live mode, switching user clears the stored token, so that user's own token must be pasted on Activity.
 */
export function UserSwitcher() {
  const [active, setActive] = useState<DemoUser>(DEFAULT_USER);
  const [hasToken, setHasToken] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function syncFromToken() {
      const token = getStoredToken();
      setHasToken(Boolean(token));
      // A token for a roster user selects that user, so the sidebar matches the data on screen.
      const fromToken = findDemoUser(readDisplayClaims(token).userId);
      if (fromToken) setActiveUser(fromToken);
      setActive(getActiveUser());
    }
    function syncUser() {
      setActive(getActiveUser());
    }
    syncFromToken();
    window.addEventListener(TOKEN_CHANGED_EVENT, syncFromToken);
    window.addEventListener(USER_CHANGED_EVENT, syncUser);
    return () => {
      window.removeEventListener(TOKEN_CHANGED_EVENT, syncFromToken);
      window.removeEventListener(USER_CHANGED_EVENT, syncUser);
    };
  }, []);

  function choose(user: DemoUser) {
    setOpen(false);
    if (user.userId === active.userId) return;
    setActiveUser(user);
    const tokenUser = readDisplayClaims(getStoredToken()).userId;
    if (!IS_MOCK && tokenUser !== user.userId) {
      // Each live user needs their own token. Drop the previous user's token rather than reuse it.
      setStoredToken(null);
    }
  }

  const merchantName = DEMO_MERCHANTS.find((m) => m.id === active.merchantId)?.name ?? active.merchantId;
  const status = IS_MOCK
    ? "Demo user"
    : hasToken
      ? "Signed in with this user's token"
      : "Paste this user's token on Activity";

  return (
    <div className="relative border-t border-line p-3">
      {open ? (
        <div
          role="listbox"
          aria-label="Switch user"
          className="absolute bottom-full left-3 right-3 mb-2 overflow-hidden rounded-xl border border-line bg-surface shadow-card"
        >
          {DEMO_USERS.map((user) => {
            const selected = user.userId === active.userId;
            return (
              <button
                key={user.userId}
                role="option"
                aria-selected={selected}
                type="button"
                onClick={() => choose(user)}
                className={cn(
                  "flex w-full items-start gap-2 px-3 py-2.5 text-left text-xs transition hover:bg-canvas",
                  selected && "bg-accent-soft",
                )}
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium text-ink">{user.displayName}</span>
                  <span className="block truncate text-muted">
                    {user.merchantId} · Analyst
                  </span>
                </span>
                {selected ? <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" aria-hidden /> : null}
              </button>
            );
          })}
        </div>
      ) : null}

      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left text-xs transition hover:bg-canvas"
      >
        <UserCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium text-ink">{active.displayName}</span>
          <span className="block truncate text-muted">{merchantName}</span>
          <span className="block truncate text-[11px] text-muted">
            {active.merchantId} · Analyst · {status}
          </span>
        </span>
        <ChevronUp className={cn("mt-0.5 h-4 w-4 shrink-0 text-muted transition", !open && "rotate-180")} aria-hidden />
      </button>
    </div>
  );
}
