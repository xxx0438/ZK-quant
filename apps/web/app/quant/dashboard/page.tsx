"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { quant } from "@/lib/echo-client";
import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { fmtUsd, fmtBps } from "@/lib/format";
import { EarningsCard } from "@/components/quant/EarningsCard";
import { ModelTable } from "@/components/quant/ModelTable";
import { Upload, TrendingUp } from "lucide-react";

export default function DashboardPage() {
  const earningsQ = useQuery({
    queryKey: ["earnings"],
    queryFn: () => quant.earnings(),
    refetchInterval: 30_000,
  });

  const modelsQ = useQuery({
    queryKey: ["my-models"],
    queryFn: () => quant.listModels(),
    refetchInterval: 30_000,
  });

  if (earningsQ.isLoading || modelsQ.isLoading) {
    return <div className="text-zinc-400">Loading…</div>;
  }
  if (earningsQ.error || modelsQ.error) {
    return (
      <div className="text-red-400">
        Failed to load. Try refreshing.{" "}
        {(earningsQ.error as Error)?.message}
      </div>
    );
  }

  const e = earningsQ.data!;
  const m = modelsQ.data!;

  return (
    <div className="space-y-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">@{e.handle}</h1>
          <p className="mt-1 text-sm text-zinc-400">
            {fmtBps(e.revenue_share_bps)} revenue share · Payout{" "}
            <span className="font-mono">{e.payout_address.slice(0, 6)}…{e.payout_address.slice(-4)}</span>
          </p>
        </div>
        <Link href="/quant/dashboard/upload">
          <Button>
            <Upload size={16} />
            Submit new model
          </Button>
        </Link>
      </header>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <EarningsCard
          label="Lifetime earned"
          value={fmtUsd(Math.round(e.lifetime_earned_usd * 100))}
          accent="emerald"
        />
        <EarningsCard
          label="Pending payout"
          value={fmtUsd(Math.round(e.pending_usd * 100))}
          subtitle={`Next settlement: ${e.next_settlement}`}
        />
        <EarningsCard
          label="Settled to wallet"
          value={fmtUsd(Math.round(e.settled_usd * 100))}
          subtitle="On-chain, verifiable"
        />
      </div>

      {/* Submissions */}
      <Card>
        <CardHeader
          title="My models"
          subtitle="Models you've submitted to the marketplace."
          action={
            <Link href="/quant/dashboard/earnings">
              <Button variant="ghost">
                <TrendingUp size={14} />
                See per-model earnings
              </Button>
            </Link>
          }
        />
        <ModelTable submissions={m.submissions} listed={m.listed_models} byModel={e.by_model} />
      </Card>
    </div>
  );
}
