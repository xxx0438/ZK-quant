"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CertVerifier, type VerificationResult } from "@echo-protocol/verify-cert";
import { Card, CardHeader } from "@/components/ui/card";
import { VerificationReport } from "../components/VerificationReport";

const ECHO_API = process.env.NEXT_PUBLIC_ECHO_API_URL || "https://api.echo.ai";

export default function CertPage() {
  const params = useParams();
  const certId = params.cert_id as string;
  const [cert, setCert] = useState<any>(null);
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${ECHO_API}/v1/certs/${certId}`);
        if (!r.ok) throw new Error(`Cert not found (${r.status})`);
        const c = await r.json();
        setCert(c);
        const v = new CertVerifier();
        setResult(v.verify(c.attestation ?? c));
      } catch (e) {
        setError((e as Error).message);
      }
    })();
  }, [certId]);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <h1 className="text-2xl font-bold">
          Verifying <span className="font-mono text-emerald-400">{certId}</span>
        </h1>

        {error && (
          <Card className="mt-6 border-red-900 bg-red-950/30">
            <p className="text-red-300">{error}</p>
          </Card>
        )}

        {result && cert && (
          <VerificationReport result={result} cert={cert.attestation ?? cert} />
        )}

        {!result && !error && (
          <p className="mt-6 text-zinc-400">Verifying…</p>
        )}
      </div>
    </div>
  );
}
