export const fmtUsd = (cents: number): string =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(cents / 100);

export const fmtNumber = (n: number): string =>
  new Intl.NumberFormat("en-US").format(n);

export const fmtPct = (n: number, digits = 2): string =>
  `${(n * 100).toFixed(digits)}%`;

export const fmtDate = (iso: string): string =>
  new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

export const fmtAddr = (addr: string): string =>
  `${addr.slice(0, 6)}…${addr.slice(-4)}`;

export const fmtBps = (bps: number): string => `${(bps / 100).toFixed(1)}%`;

// SHA256 in browser
export async function sha256File(file: File): Promise<string> {
  const buf = await file.arrayBuffer();
  const hash = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
