import * as React from "react";
import { twMerge } from "tailwind-merge";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const styles: Record<Variant, string> = {
  primary: "bg-emerald-500 hover:bg-emerald-400 text-black",
  secondary: "bg-zinc-800 hover:bg-zinc-700 text-zinc-100",
  ghost: "hover:bg-zinc-800 text-zinc-300",
  danger: "bg-red-600 hover:bg-red-500 text-white",
};

export const Button = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }
>(({ className, variant = "primary", ...props }, ref) => (
  <button
    ref={ref}
    className={twMerge(
      "inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed",
      styles[variant],
      className,
    )}
    {...props}
  />
));
Button.displayName = "Button";
