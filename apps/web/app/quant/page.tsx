import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function QuantLanding() {
  return (
    <div className="space-y-12">
      <header className="space-y-4 text-center">
        <p className="text-sm uppercase tracking-widest text-emerald-500">
          Echo Quant Marketplace
        </p>
        <h1 className="text-4xl font-bold sm:text-5xl">
          Upload alpha. Keep 70%.<br />
          Get paid in USDC, on-chain, weekly.
        </h1>
        <p className="mx-auto max-w-2xl text-zinc-400">
          List your factor or prediction model on Echo. We verify it in a TEE,
          attach a cryptographic performance certificate, and route every API
          call through automated revenue splits — settled directly to your
          Base wallet.
        </p>
        <div className="flex justify-center gap-3 pt-4">
          <Link href="/quant/register">
            <Button>Become a quant →</Button>
          </Link>
          <Link href="/docs/quant">
            <Button variant="secondary">How it works</Button>
          </Link>
        </div>
      </header>

      <div className="grid gap-6 sm:grid-cols-3">
        <Card>
          <div className="text-2xl font-bold text-emerald-400">70%</div>
          <div className="mt-1 text-sm text-zinc-400">
            Default revenue share. Verified quants earn 75%.
          </div>
        </Card>
        <Card>
          <div className="text-2xl font-bold text-emerald-400">TEE-signed</div>
          <div className="mt-1 text-sm text-zinc-400">
            Every model gets an AWS Nitro–attested performance certificate.
          </div>
        </Card>
        <Card>
          <div className="text-2xl font-bold text-emerald-400">Weekly USDC</div>
          <div className="mt-1 text-sm text-zinc-400">
            Batched on-chain settlement every Monday on Base.
          </div>
        </Card>
      </div>
    </div>
  );
}
