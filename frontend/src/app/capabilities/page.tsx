"use client";

import { useQuery } from "@tanstack/react-query";
import { Badge, Card, CardContent, CardHeader, CardTitle } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingState } from "@/components/states/states";
import { getCapabilities } from "@/lib/data";

export default function CapabilitiesPage() {
  const query = useQuery({ queryKey: ["capabilities"], queryFn: getCapabilities, retry: false });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Capabilities</h1>
        <p className="text-sm text-muted">
          Analytics available to your role. The API is the source of truth for what is enabled.
        </p>
      </header>
      <Card>
        <CardHeader>
          <CardTitle>{query.data ? `Role: ${query.data.role}` : "Available analytics"}</CardTitle>
        </CardHeader>
        <CardContent>
          {query.isLoading ? <LoadingState /> : null}
          {query.error ? <ErrorState message={(query.error as Error).message} /> : null}
          {query.data && query.data.capabilities.length === 0 ? (
            <EmptyState title="No capabilities are enabled for your role." />
          ) : null}
          {query.data && query.data.capabilities.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs text-muted">
                    <th className="px-2 py-2 font-medium">Capability</th>
                    <th className="px-2 py-2 font-medium">Description</th>
                    <th className="px-2 py-2 font-medium">Status</th>
                    <th className="px-2 py-2 font-medium">Minimum role</th>
                    <th className="px-2 py-2 font-medium">Supported filters</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.capabilities.map((c) => (
                    <tr key={c.name} className="border-b border-line last:border-0">
                      <td className="px-2 py-3 font-medium text-ink">{c.name}</td>
                      <td className="px-2 py-3 text-muted">{c.description}</td>
                      <td className="px-2 py-3">
                        <Badge tone="ok">Enabled</Badge>
                      </td>
                      <td className="px-2 py-3 text-muted">{c.min_role}</td>
                      <td className="px-2 py-3 text-xs text-muted">Not reported by the API</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
