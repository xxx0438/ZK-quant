import Link from "next/link";

export const metadata = {
  title: "Echo Quant Marketplace",
  description: "Upload models, earn revenue, scale alpha.",
};

export default function QuantLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <nav className="border-b border-zinc-900">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="font-semibold tracking-tight">
            Echo<span className="text-emerald-500">·</span>Quants
          </Link>
          <div className="flex gap-6 text-sm text-zinc-400">
            <Link href="/quant/dashboard" className="hover:text-zinc-100">
              Dashboard
            </Link>
            <Link href="/quant/dashboard/upload" className="hover:text-zinc-100">
              Submit model
            </Link>
            <Link href="/quant/dashboard/earnings" className="hover:text-zinc-100">
              Earnings
            </Link>
            <Link href="/docs" className="hover:text-zinc-100">
              Docs
            </Link>
          </div>
        </div>
      </nav>
      <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
    </div>
  );
}
