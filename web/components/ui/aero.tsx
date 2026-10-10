import type { ButtonHTMLAttributes, HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function AeroButton({ className, variant = "primary", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "quiet" | "secondary" }) {
  return <button className={cn("aero-button", `aero-button--${variant}`, className)} {...props} />;
}

export function AeroPanel({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={cn("aero-panel", className)} {...props} />;
}

export function PocketwatchLogo({ size = 44 }: { size?: number }) {
  return <img className="pocketwatch-logo" src="/images/pocketwatch-logo.png" width={size} height={size} alt="" aria-hidden="true" draggable={false} />;
}

export function GlassLayers() {
  return <span className="glass-layers" aria-hidden="true"><span /><span /><span /></span>;
}
