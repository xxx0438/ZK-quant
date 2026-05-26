import { twMerge } from "tailwind-merge";
import { CheckCircle2, Clock, AlertTriangle, XCircle, Loader2 } from "lucide-react";

const config = {
  pending: { label: "Pending", color: "bg-zinc-800 text-zinc-300", Icon: Clock },
  verifying: { label: "TEE verifying", color: "bg-blue-900/40 text-blue-300", Icon: Loader2 },
  approved: { label: "Listed", color: "bg-emerald-900/40 text-emerald-300", Icon: CheckCircle2 },
  rejected: { label: "Rejected", color: "bg-red-900/40 text-red-300", Icon: XCircle },
  pending_human: { label: "Manual review", color: "bg-amber-900/40 text-amber-300", Icon: AlertTriangle },
} as const;

export function SubmissionStatus({ status }: { status: keyof typeof config | string }) {
  const c = (config as Record<string, typeof config.pending>)[status] ?? config.pending;
  const { Icon, label, color } = c;
  return (
    <span
      className={twMerge(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        color,
      )}
    >
      <Icon size={12} className={status === "verifying" ? "animate-spin" : ""} />
      {label}
    </span>
  );
}
