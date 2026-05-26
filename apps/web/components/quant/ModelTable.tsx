import type { Submission } from "@/lib/echo-client";
import { fmtUsd, fmtDate, fmtNumber } from "@/lib/format";
import { SubmissionStatus } from "./SubmissionStatus";

type ListedModel = {
  id: string;
  name: string;
  is_listed: boolean;
  price_per_call_cents: number;
  live_sharpe_30d: number | null;
};

export function ModelTable({
  submissions,
  listed,
  byModel,
}: {
  submissions: Submission[];
  listed: ListedModel[];
  byModel: Array<{ model_id: string; earned_cents: number; calls: number }>;
}) {
  const earnedByModel = new Map(byModel.map((b) => [b.model_id, b]));
  const listedById = new Map(listed.map((l) => [l.id, l]));

  if (submissions.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-zinc-800 p-8 text-center text-sm text-zinc-500">
        No submissions yet. Submit your first model to start earning.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-left text-xs uppercase tracking-wide text-zinc-500">
            <th className="py-3 pr-4">Model</th>
            <th className="py-3 pr-4">Status</th>
            <th className="py-3 pr-4">Live Sharpe (30d)</th>
            <th className="py-3 pr-4">Calls</th>
            <th className="py-3 pr-4">Earned</th>
            <th className="py-3 pr-4">Submitted</th>
          </tr>
        </thead>
        <tbody>
          {submissions.map((s) => {
            const earnings = earnedByModel.get(s.model_id);
            const listed = listedById.get(s.model_id);
            return (
              <tr key={s.id} className="border-b border-zinc-900 last:border-0">
                <td className="py-3 pr-4">
                  <div className="font-medium text-zinc-100">{s.name}</div>
                  <div className="font-mono text-xs text-zinc-500">{s.model_id}</div>
                </td>
                <td className="py-3 pr-4">
                  <SubmissionStatus status={s.status} />
                </td>
                <td className="py-3 pr-4 text-zinc-300">
                  {listed?.live_sharpe_30d?.toFixed(2) ?? "—"}
                </td>
                <td className="py-3 pr-4 text-zinc-300">
                  {earnings ? fmtNumber(earnings.calls) : "—"}
                </td>
                <td className="py-3 pr-4 text-emerald-400">
                  {earnings ? fmtUsd(earnings.earned_cents) : "—"}
                </td>
                <td className="py-3 pr-4 text-zinc-400">{fmtDate(s.submitted_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
