"use client";

import { useCallback, useState } from "react";
import { useDropzone, type Accept } from "react-dropzone";
import { twMerge } from "tailwind-merge";
import { Upload, CheckCircle2, Loader2 } from "lucide-react";

export function UploadDropzone({
  accept,
  onUpload,
  uploaded,
  hint,
}: {
  accept: Accept;
  onUpload: (f: File) => Promise<void> | void;
  uploaded: { fileName: string; sha256: string } | null;
  hint?: string;
}) {
  const [busy, setBusy] = useState(false);

  const onDrop = useCallback(
    async (files: File[]) => {
      if (!files[0]) return;
      setBusy(true);
      try {
        await onUpload(files[0]);
      } finally {
        setBusy(false);
      }
    },
    [onUpload],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept,
    multiple: false,
    onDrop,
    disabled: busy,
  });

  return (
    <div
      {...getRootProps()}
      className={twMerge(
        "cursor-pointer rounded-md border-2 border-dashed border-zinc-800 p-6 text-center transition",
        isDragActive && "border-emerald-500 bg-emerald-950/20",
        busy && "cursor-wait opacity-60",
      )}
    >
      <input {...getInputProps()} />
      {uploaded ? (
        <div className="space-y-2">
          <CheckCircle2 className="mx-auto text-emerald-500" size={28} />
          <div className="text-sm font-medium text-zinc-100">{uploaded.fileName}</div>
          <div className="font-mono text-xs text-zinc-500">
            sha256:{uploaded.sha256.slice(0, 16)}…
          </div>
          <div className="text-xs text-emerald-400">Drop a new file to replace</div>
        </div>
      ) : busy ? (
        <div className="space-y-2">
          <Loader2 className="mx-auto animate-spin text-zinc-400" size={28} />
          <div className="text-sm text-zinc-400">Hashing + uploading…</div>
        </div>
      ) : (
        <div className="space-y-2">
          <Upload className="mx-auto text-zinc-500" size={28} />
          <div className="text-sm text-zinc-300">
            {isDragActive ? "Drop the file here" : "Drag & drop, or click to select"}
          </div>
          {hint && <div className="text-xs text-zinc-500">{hint}</div>}
        </div>
      )}
    </div>
  );
}
