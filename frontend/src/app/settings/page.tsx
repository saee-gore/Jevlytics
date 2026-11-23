"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Input } from "@/components/ui/primitives";
import { ErrorState, LoadingState } from "@/components/states/states";
import { getStoredToken, setStoredToken } from "@/lib/api";
import { DATA_MODE, IS_MOCK } from "@/lib/config";
import { getHealth } from "@/lib/data";
import { readDisplayClaims, type DisplayClaims } from "@/lib/claims";

export default function SettingsPage() {
  const [token, setToken] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  // sessionStorage is only readable in the browser, so read it after mount to keep server and client HTML equal.
  const [hasToken, setHasToken] = useState(false);
  const [claims, setClaims] = useState<DisplayClaims>({ merchantId: null, userId: null });
  useEffect(() => {
    const token = getStoredToken();
    setHasToken(token !== null);
    setClaims(readDisplayClaims(token));
  }, []);
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth, retry: false });

  function save() {
    const value = token.trim();
    if (!value) return;
    setStoredToken(value);
    setToken("");
    setHasToken(true);
    setClaims(readDisplayClaims(value));
    setSaved("Token saved for this browser tab. It clears when the tab closes.");
  }

  function clear() {
    setStoredToken(null);
    setHasToken(false);
    setClaims({ merchantId: null, userId: null });
    setSaved("Token removed.");
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm text-muted">Connection and session.</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Data mode</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p>
            <Badge tone={IS_MOCK ? "warn" : "ok"}>{IS_MOCK ? "Demo data" : "Live API"}</Badge>{" "}
            <span className="text-muted">Set with NEXT_PUBLIC_DATA_MODE at build time (current: {DATA_MODE}).</span>
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Backend health</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {health.isLoading ? <LoadingState /> : null}
          {health.error ? <ErrorState message={(health.error as Error).message} /> : null}
          {health.data ? (
            <ul className="space-y-1">
              <li>Status: <span className="font-medium">{health.data.status}</span></li>
              <li>Database: <span className="font-medium">{health.data.database}</span></li>
              {health.data.configured ? (
                <li className="text-muted">
                  Configured: auth {String(health.data.configured.auth)}, Jev {String(health.data.configured.jev)}, LLM{" "}
                  {String(health.data.configured.llm)}
                </li>
              ) : null}
            </ul>
          ) : null}
        </CardContent>
      </Card>

      {!IS_MOCK ? (
        <Card>
          <CardHeader>
            <CardTitle>Session token</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="text-muted">
              Paste the access token issued for your account. It is kept in this tab&apos;s session storage only and is
              never written into the app&apos;s code or sent anywhere except the API.
            </p>
            <p>
              Status:{" "}
              {hasToken ? (
                <span className="font-medium text-ink">
                  Token present{claims.merchantId ? ` for ${claims.merchantId} (display only)` : ""}
                </span>
              ) : (
                <span className="text-muted">No token</span>
              )}
            </p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <label className="sr-only" htmlFor="token">Access token</label>
              <Input
                id="token"
                type="password"
                autoComplete="off"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste access token"
              />
              <Button onClick={save} disabled={!token.trim()}>Save token</Button>
              <Button variant="outline" onClick={clear} disabled={!hasToken}>Remove</Button>
            </div>
            {saved ? <p className="text-xs text-muted">{saved}</p> : null}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-5 text-sm text-muted">
            Demo mode does not need a token. Build with NEXT_PUBLIC_DATA_MODE=live to connect to the API.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
