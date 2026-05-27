import type { VerificationResult } from "@echo-protocol/verify-cert";
import { CheckCircle2, XCircle, AlertTriangle } from "lucide-react";

export function VerificationReport({
  result,
  cert,
}: {
  result: VerificationResult;
  cert: any;
}) {
  return (
    <div className="mt-6 space-y-4">
      <div
        className={`rounded-md border p-4 ${
          result.ok
            ? "border-emerald-900 bg-emerald-950/30"
            : "border-red-900 bg-red-950/30"
        }`}
      >
        <div className="flex items-center gap-2 text-lg font-semibold">
          {result.ok ? (
            <>
              <CheckCircle2 className="text-emerald-500" size={22} />
              <span className="text-emerald-300">Signature valid</span>
            </>
          ) : (
            <>
              <XCircle className="text-red-500" size={22} />
              <span className="text-red-300">Verification failed</span>
            </>
          )}
        </div>
        <div className="mt-2 text-xs text-zinc-400">
          Cert ID: <span className="font-mono">{result.cert_id}</span>
          {" · "}
          Model: <span className="font-mono">{result.model_id}</span>
          {" · "}
          Signed by: <span className="font-mono">{result.issuer_key_id}</span>
        </div>
      </div>

      <div className="rounded-md border border-zinc-800 p-4">
        <div className="mb-2 text-xs uppercase text-zinc-500">Checks</div>
        <ul className="space-y-2 text-sm">
          <Check label="Signature" ok={result.checks.signature.ok} error={result.checks.signature.error} />
          <Check label="Key resolved" ok={result.checks.key_resolved.ok} error={result.checks.key_resolved.error} />
          <Check
            label="Expiry"
            ok={!result.checks.expiry.expired}
            error={result.checks.expiry.error}
          />
        </ul>
        {result.warnings.length > 0 && (
          <div className="mt-3 flex items-start gap-2 text-xs text-amber-300">
            <AlertTriangle size={14} />
            <div>{result.warnings.join("; ")}</div>
          </div>
        )}
      </div>

      {cert?.backtest_metrics && (
        <div className="rounded-md border border-zinc-800 p-4">
          <div className="mb-2 text-xs uppercase text-zinc-500">Claimed metrics</div>
          <table className="w-full text-sm">
            <tbody>
              {Object.entries(cert.backtest_metrics)
                .filter(([k]) => !["harness_version", "fee_bps", "slippage_bps"].includes(k))
                .map(([k, v]) => (
                  <tr key={k} className="border-b border-zinc-900 last:border-0">
                    <td className="py-1.5 pr-4 text-zinc-400">{k}</td>
                    <td className="py-1.5 text-right font-mono">{String(v)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Check({ label, ok, error }: { label: string; ok: boolean; error: string | null }) {
  return (
    <li className="flex items-start gap-2">
      {ok ? (
        <CheckCircle2 size={16} className="mt-0.5 text-emerald-500" />
      ) : (
        <XCircle size={16} className="mt-0.5 text-red-500" />
      )}
      <div>
        <div className="text-zinc-100">{label}</div>
        {error && <div className="text-xs text-red-300">{error}</div>}
      </div>
    </li>
  );
}
