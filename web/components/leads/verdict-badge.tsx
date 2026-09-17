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

// For "avoid" (negative) criteria: present = red flag, absent = neutral, never a green "Met".
const NEGATIVE_LABEL: Record<Verdict, string> = {
  met: "Red flag",
  not_met: "Not present",
  unknown: "Unknown",
};

const NEGATIVE_TONE: Record<Verdict, "emerald" | "rose" | "gray"> = {
  met: "rose",
  not_met: "gray",
  unknown: "gray",
};

export function VerdictBadge({
  verdict,
  polarity = "positive",
  className,
}: {
  verdict: Verdict;
  polarity?: "positive" | "negative";
  className?: string;
}) {
  const negative = polarity === "negative";
  const label = negative ? NEGATIVE_LABEL[verdict] : LABEL[verdict];
  const tone = negative ? NEGATIVE_TONE[verdict] : TONE[verdict];
  return <span className={cn(toneBadge({ tone }), className)}>{label}</span>;
}
