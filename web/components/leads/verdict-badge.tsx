import { cn } from "cn";
import { toneBadge } from "@/lib/badge-tones";
import type { Verdict } from "@/lib/api";

const LABEL: Record<Verdict, string> = {
  met: "Met",
  not_met: "Not met",
  unknown: "Unknown",
};

const TONE: Record<Verdict, "emerald" | "rose" | "gray"> = {
  met: "emerald",
  not_met: "rose",
  unknown: "gray",
};

export function VerdictBadge({ verdict, className }: { verdict: Verdict; className?: string }) {
  return (
    <span className={cn(toneBadge({ tone: TONE[verdict] }), className)}>{LABEL[verdict]}</span>
  );
}
