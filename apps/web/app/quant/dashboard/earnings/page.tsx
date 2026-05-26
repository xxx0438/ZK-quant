"use client";

import { useQuery } from "@tanstack/react-query";
import { quant } from "@/lib/echo-client";
import { Card, CardHeader } from "@/components/ui/card";
import { fmtUsd, fmtNumber, fmtBps } from "@/lib/format";

export default function EarningsPage() {
  const q = useQuery({
    queryKey: ["earnings-detail"],
    queryFn: () => quant.earnings(),
    refetchInterval: 30_000,
  });

  if (q.isLoading) return <div className="text-zinc-400">Loading…</div>;
  if (q.error) return <div className="text-red-400">Failed to load.</div>;
  const e = q.data!;

  const avgPerCall =
    e.by_model.reduce((acc, m) => acc + m.earned_cents, 0) /
    Math.max(
      1,
      e.by_model.reduce((acc, m) => acc + m.calls, 0),
    );

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-bold">Earnings</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Live revenue split — {fmtBps(e.revenue_share_bps)} of every API call routes to you.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-4">
        <Card>
          <div className="text-xs uppercase text-zinc-500">Pending</div>
          <div className="mt-1 text-xl font-bold text-amber-400">
            {fmtUsd(Math.round(e.pending_usd * 100))}
          </div>
          <div className="mt-1 text-xs text-zinc-500">Settles {e.next_settlement}</div>
        </Card>
        <Card>
          <div className="text-xs uppercase text-zinc-500">Settled</div>
          <div className="mt-1 text-xl font-bold text-emerald-400">
            {fmtUsd(Math.round(e.settled_usd * 100))}
          </div>
        </Card>
        <Card>
          <div className="text-xs uppercase text-zinc-500">Total calls</div>
          <div className="mt-1 text-xl font-bold">
            {fmtNumber(e.by_model.reduce((a, m) => a + m.calls, 0))}
          </div>
        </Card>
        <Card>
          <div className="text-xs uppercase text-zinc-500">Avg / call</div>
          <div className="mt-1 text-xl font-bold">
            {isFinite(avgPerCall) ? fmtUsd(Math.round(avgPerCall)) : "—"}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader title="Per-model breakdown" />
        {e.by_model.length === 0 ? (
          <div className="rounded-md border border-dashed border-zinc-800 p-8 text-center text-sm text-zinc-500">
            No revenue yet. Submit a model to get started.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-left text-xs uppercase tracking-wide text-zinc-500">
                <th className="py-3 pr-4">Model</th>
                <th className="py-3 pr-4 text-right">Calls</th>
                <th className="py-3 pr-4 text-right">Earned</th>
                <th className="py-3 pr-4 text-right">Avg / call</th>
              </tr>
            </thead>
            <tbody>
              {e.by_model
                .slice()
                .sort((a, b) => b.earned_cents - a.earned_cents)
                .map((m) => (
                  <tr key={m.model_id} className="border-b border-zinc-900 last:border-0">
                    <td className="py-3 pr-4 font-mono text-xs">{m.model_id}</td>
                    <td className="py-3 pr-4 text-right">{fmtNumber(m.calls)}</td>
                    <td className="py-3 pr-4 text-right text-emerald-400">
                      {fmtUsd(m.earned_cents)}
                    </td>
                    <td className="py-3 pr-4 text-right text-zinc-400">
                      {fmtUsd(Math.round(m.earned_cents / Math.max(1, m.calls)))}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
      </Card>

      <div className="rounded-md border border-zinc-800 bg-zinc-900/30 p-4 text-xs text-zinc-500">
        <strong className="text-zinc-300">Settlement schedule:</strong> Weekly,
        Monday 00:00 UTC. Minimum payout $10. Sent to{" "}
        <span className="font-mono text-emerald-400">
          {e.payout_address.slice(0, 6)}…{e.payout_address.slice(-4)}
        </span>{" "}
        on Base.
      </div>
    </div>
  );
}
