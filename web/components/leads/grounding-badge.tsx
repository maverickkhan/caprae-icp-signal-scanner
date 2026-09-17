import { cn } from "cn";
import { toneBadge } from "@/lib/badge-tones";
import type { Grounding } from "@/lib/api";

const LABEL: Record<Grounding, string> = {
  exact: "Verified · exact match",
  fuzzy: "Verified · fuzzy match",
  record: "Public record",
  none: "Unverified",
};

const TONE: Record<Grounding, "emerald" | "amber" | "blue" | "gray"> = {
  exact: "emerald",
  fuzzy: "amber",
  record: "blue",
  none: "gray",
};

export function GroundingBadge({ grounding, className }: { grounding: Grounding; className?: string }) {
  return (
    <span className={cn(toneBadge({ tone: TONE[grounding] }), className)}>{LABEL[grounding]}</span>
  );
}
