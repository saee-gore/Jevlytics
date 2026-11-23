"use client";

import { Activity } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserSwitcher } from "@/components/layout/user-switcher";
import { DATA_MODE } from "@/lib/config";
import { cn } from "@/lib/utils";

// The sidebar pages. Other routes redirect to Activity, which also holds the AI Assistant (see next.config.mjs).
const NAV = [{ href: "/activity", label: "Activity", icon: Activity }];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen bg-canvas text-ink md:h-screen md:overflow-hidden">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-line bg-surface md:flex">
        <div className="flex items-center gap-3 px-5 py-5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand text-white shadow-glow">
            <Activity className="h-4.5 w-4.5" aria-hidden />
          </span>
          <div>
            <p className="text-sm font-semibold text-ink">Merchant Analytics</p>
            <p className="text-xs text-muted">Payment analytics assistant</p>
          </div>
        </div>
        <nav aria-label="Main" className="flex-1 space-y-1 px-3">
          {NAV.map((item) => {
            const active = pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition",
                  active
                    ? "bg-brand-soft font-semibold text-violet ring-1 ring-violet/15"
                    : "text-muted hover:bg-canvas hover:text-ink",
                )}
              >
                <Icon className="h-4 w-4" aria-hidden />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <UserSwitcher />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col md:h-screen md:min-h-0">
        <header className="flex items-center justify-between border-b border-line bg-surface px-4 py-3 md:hidden">
          <p className="text-sm font-semibold">Merchant Analytics</p>
          <nav aria-label="Mobile" className="flex gap-3 overflow-x-auto text-xs text-muted">
            {NAV.map((item) => (
              <Link key={item.href} href={item.href} className="whitespace-nowrap hover:text-ink">
                {item.label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="mx-auto flex min-h-0 w-full max-w-6xl flex-1 flex-col p-4 md:overflow-hidden md:p-5">{children}</main>
        <p className="sr-only">Data mode: {DATA_MODE}</p>
      </div>
    </div>
  );
}
