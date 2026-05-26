"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAccount, useConnect } from "wagmi";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { quant, EchoApiError } from "@/lib/echo-client";
import { toast } from "sonner";

export default function RegisterPage() {
  const router = useRouter();
  const { address, isConnected } = useAccount();
  const { connectors, connect } = useConnect();

  const [handle, setHandle] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!address) {
      toast.error("Connect your wallet first.");
      return;
    }
    setSubmitting(true);
    try {
      const profile = await quant.register({
        handle,
        display_name: displayName,
        bio: bio || undefined,
        payout_address: address,
      });
      toast.success(`Welcome, @${profile.handle}!`);
      router.push("/quant/dashboard");
    } catch (e) {
      if (e instanceof EchoApiError) {
        toast.error(e.message, { description: e.hint });
      } else {
        toast.error("Registration failed");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <Card>
        <CardHeader
          title="Register as a quant"
          subtitle="Upload models, earn 70% per call, paid weekly in USDC on Base."
        />

        {!isConnected ? (
          <div className="space-y-4">
            <p className="text-sm text-zinc-400">
              First, connect the wallet that will receive your earnings.
            </p>
            <div className="flex flex-wrap gap-2">
              {connectors.map((c) => (
                <Button
                  key={c.uid}
                  variant="secondary"
                  onClick={() => connect({ connector: c })}
                >
                  Connect {c.name}
                </Button>
              ))}
            </div>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <Label htmlFor="handle">Handle</Label>
              <Input
                id="handle"
                value={handle}
                onChange={(e) => setHandle(e.target.value.toLowerCase())}
                placeholder="whalewatcher"
                pattern="^[a-z0-9_]{3,32}$"
                required
              />
              <p className="mt-1 text-xs text-zinc-500">
                Lowercase, digits, underscore. 3–32 chars.
              </p>
            </div>

            <div>
              <Label htmlFor="display_name">Display name</Label>
              <Input
                id="display_name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Whale Watcher"
                required
              />
            </div>

            <div>
              <Label htmlFor="bio">Bio (optional)</Label>
              <Textarea
                id="bio"
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                placeholder="What kind of models do you build?"
                rows={3}
              />
            </div>

            <div className="rounded-md border border-zinc-800 bg-zinc-900/50 p-3">
              <div className="text-xs uppercase tracking-wide text-zinc-500">
                Payout address (USDC on Base)
              </div>
              <div className="mt-1 font-mono text-sm text-emerald-400">
                {address}
              </div>
            </div>

            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "Creating profile…" : "Create quant profile"}
            </Button>

            <p className="text-xs text-zinc-500">
              By registering you agree to Echo's{" "}
              <a href="/legal/terms" className="underline">Terms</a> and{" "}
              <a href="/legal/disclosures" className="underline">Risk Disclosures</a>.
            </p>
          </form>
        )}
      </Card>
    </div>
  );
}
