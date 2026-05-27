"use client";

import { useState } from "react";
import { CertVerifier, type VerificationResult } from "@echo-protocol/verify-cert";
import { Button } from "@/components/ui/button";
import { VerificationReport } from "./VerificationReport";

export function VerifierUI() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [cert, setCert] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  function run() {
    setResult(null);
    setError(null);
    setCert(null);
    try {
      const parsed = JSON.parse(text);
      const v = new CertVerifier();
      const r = v.verify(parsed);
      setCert(parsed);
      setResult(r);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-4">
      <textarea
        className="h-48 w-full rounded-md border border-zinc-800 bg-zinc-900 p-3 font-mono text-xs"
        placeholder='{"version": "1.0.0", "cert_id": "...", ...}'
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <Button onClick={run} disabled={!text.trim()}>
        Verify cert
      </Button>

      {error && (
        <div className="rounded-md border border-red-900 bg-red-950/30 p-3 text-sm text-red-300">
          Parse error: {error}
        </div>
      )}

      {result && cert && <VerificationReport result={result} cert={cert} />}
    </div>
  );
}
