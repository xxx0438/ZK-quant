import { Card } from "@/components/ui/card";
import { twMerge } from "tailwind-merge";

export function EarningsCard({
  label,
  value,
  subtitle,
  accent,
}: {
  label: string;
  value: string;
  subtitle?: string;
  accent?: "emerald" | "amber";
}) {
  return (
    <Card>
      <div className="text-xs uppercase tracking-wider text-zinc-500">{label}</div>
      <div
        className={twMerge(
          "mt-2 text-3xl font-bold",
          accent === "emerald" && "text-emerald-400",
          accent === "amber" && "text-amber-400",
          !accent && "text-zinc-100",
        )}
      >
        {value}
      </div>
      {subtitle && (
        <div className="mt-2 text-xs text-zinc-400">{subtitle}</div>
      )}
    </Card>
  );
}
