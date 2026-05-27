"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { VerifierUI } from "./components/VerifierUI";

export default function VerifyPage() {
  const router = useRouter();
  const [certId, setCertId] = useState("");

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <header className="mb-8 text-center">
          <p className="text-xs uppercase tracking-widest text-emerald-500">
            Public Verifier
          </p>
          <h1 className="mt-2 text-3xl font-bold sm:text-4xl">
            Verify an Echo performance certificate
          </h1>
          <p className="mt-3 text-sm text-zinc-400">
            Cryptographically check that a backtest claim was actually signed by Echo.
            All verification runs <strong>in your browser</strong> — no data leaves your machine.
          </p>
        </header>

        <Card className="mb-6">
          <CardHeader title="Look up by cert ID" />
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (certId.trim()) router.push(`/verify/${certId.trim()}`);
            }}
            className="flex gap-2"
          >
            <Input
              placeholder="cert_a1b2c3d4e5f6g7h8"
              value={certId}
              onChange={(e) => setCertId(e.target.value)}
              className="font-mono"
            />
            <Button type="submit">Verify</Button>
          </form>
          <p className="mt-3 text-xs text-zinc-500">
            We'll fetch the cert from the Echo API, then verify it locally with the
            embedded Echo public key.
          </p>
        </Card>

        <Card>
          <CardHeader
            title="Or paste a cert JSON"
            subtitle="Drop a cert.json file or paste the full JSON below"
          />
          <VerifierUI />
        </Card>

        <details className="mt-8 text-sm text-zinc-400">
          <summary className="cursor-pointer">How does this work?</summary>
          <div className="mt-3 space-y-2">
            <p>
              Each Echo cert is signed with an ed25519 private key. The corresponding
              public key is embedded in <code className="text-emerald-400">@echo-protocol/verify-cert</code>,
              the same library this page uses.
            </p>
            <p>
              When you click Verify, the page:
            </p>
            <ol className="ml-6 list-decimal space-y-1">
              <li>Canonicalizes the cert JSON (sorted keys, fixed float precision)</li>
              <li>Looks up the public key by <code>issuer.key_id</code></li>
              <li>Runs <code>ed25519.verify(sig, canonical, pubkey)</code> in your browser</li>
              <li>Checks expiry and key validity windows</li>
            </ol>
            <p>
              The same library is available as <code>pip install echo-verify</code> for offline / CI use.
            </p>
          </div>
        </details>
      </div>
    </div>
  );
}
