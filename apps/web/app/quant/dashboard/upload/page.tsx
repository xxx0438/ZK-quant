"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label, Textarea } from "@/components/ui/input";
import { UploadDropzone } from "@/components/quant/UploadDropzone";
import { quant, EchoApiError } from "@/lib/echo-client";
import { sha256File } from "@/lib/format";
import { toast } from "sonner";

const schema = z.object({
  proposed_model_id: z.string().regex(/^[a-z0-9\-]{3,64}$/),
  name: z.string().min(3).max(128),
  description: z.string().max(4000).optional(),
  category: z.enum(["factor", "prediction", "signal", "ensemble"]).default("factor"),
});

type FormData = z.infer<typeof schema>;

type Uploaded = {
  url: string;       // S3 GET URL (or canonical URL)
  sha256: string;
  fileName: string;
};

export default function UploadPage() {
  const router = useRouter();
  const [artifact, setArtifact] = useState<Uploaded | null>(null);
  const [kit, setKit] = useState<Uploaded | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { category: "factor" },
  });

  async function handleUpload(file: File, type: "artifact" | "kit") {
    const modelIdInput = document.querySelector<HTMLInputElement>(
      'input[name="proposed_model_id"]',
    );
    const proposed_model_id = modelIdInput?.value;
    if (!proposed_model_id) {
      toast.error("Set the model ID first.");
      throw new Error("missing model id");
    }

    // Compute SHA256 locally
    const sha256 = await sha256File(file);

    // Ask backend for signed PUT URL
    const { upload_url, key } = await quant.getUploadUrl({
      proposed_model_id,
      artifact_type: type,
    });

    // Upload directly to S3
    const putRes = await fetch(upload_url, {
      method: "PUT",
      body: file,
      headers: { "content-type": "application/octet-stream" },
    });
    if (!putRes.ok) throw new Error(`Upload failed: ${putRes.status}`);

    // The "url" stored backend-side is the object key; pass full canonical URL
    const canonicalUrl = `s3://${key}`;
    return { url: canonicalUrl, sha256, fileName: file.name };
  }

  async function onSubmit(data: FormData) {
    if (!artifact || !kit) {
      toast.error("Upload both artifact and reproducibility kit.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await quant.submitModel({
        ...data,
        artifact_url: artifact.url,
        artifact_sha256: artifact.sha256,
        backtest_kit_url: kit.url,
        backtest_kit_sha256: kit.sha256,
      });
      toast.success("Submitted!", {
        description: "TEE backtest is running. You'll see results in a few minutes.",
      });
      router.push("/quant/dashboard");
    } catch (e) {
      if (e instanceof EchoApiError) {
        toast.error(e.message, { description: e.hint });
      } else {
        toast.error("Submission failed");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Card>
        <CardHeader
          title="Submit a model"
          subtitle="Upload your artifact + reproducibility kit. We'll run it in a TEE and list it automatically if metrics pass."
        />

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          <div>
            <Label htmlFor="proposed_model_id">Model ID</Label>
            <Input
              id="proposed_model_id"
              placeholder="whale-netflow-eth"
              {...register("proposed_model_id")}
            />
            <p className="mt-1 text-xs text-zinc-500">
              Lowercase, digits, hyphens. This becomes part of the API URL.
            </p>
            {errors.proposed_model_id && (
              <p className="text-xs text-red-400">{errors.proposed_model_id.message}</p>
            )}
          </div>

          <div>
            <Label htmlFor="name">Display name</Label>
            <Input id="name" placeholder="Whale Netflow ETH" {...register("name")} />
          </div>

          <div>
            <Label htmlFor="category">Category</Label>
            <select
              id="category"
              {...register("category")}
              className="w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm"
            >
              <option value="factor">Factor</option>
              <option value="prediction">Prediction</option>
              <option value="signal">Signal</option>
              <option value="ensemble">Ensemble</option>
            </select>
          </div>

          <div>
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              rows={4}
              placeholder="Briefly describe what this model does and what data it uses."
              {...register("description")}
            />
          </div>

          <div className="space-y-3">
            <Label>Model artifact</Label>
            <UploadDropzone
              accept={{ "application/octet-stream": [".pkl", ".bin", ".onnx", ".pt", ".joblib"] }}
              onUpload={(f) => handleUpload(f, "artifact").then(setArtifact).catch(() => {})}
              uploaded={artifact}
              hint="Pickled model, ONNX, or PyTorch state dict. Max 500 MB."
            />
          </div>

          <div className="space-y-3">
            <Label>Reproducibility kit</Label>
            <UploadDropzone
              accept={{ "application/gzip": [".tar.gz", ".tgz"] }}
              onUpload={(f) => handleUpload(f, "kit").then(setKit).catch(() => {})}
              uploaded={kit}
              hint="tar.gz with backtest.py, requirements.txt, dataset_hash.txt. See docs."
            />
          </div>

          <div className="rounded-md border border-amber-900/50 bg-amber-950/20 p-3 text-xs text-amber-200">
            <strong>Auto-list thresholds:</strong> Sharpe ≥ 1.0, Max DD ≤ 20%,
            tested capacity ≥ $10k. Below these → manual review.
          </div>

          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Submitting…" : "Submit for verification"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
