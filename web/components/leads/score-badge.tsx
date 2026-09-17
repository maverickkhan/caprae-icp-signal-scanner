import { cn } from "cn";
import { toneBadge, type Tone } from "@/lib/badge-tones";
import { LOW_EVIDENCE_BELOW } from "@/lib/api";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

function scoreTone(score: number): Tone {
  if (score >= 70) return "emerald";
  if (score >= 40) return "amber";
  return "rose";
}

export function ScoreBadge({
  score,
  status,
  error,
  coverage,
  className,
}: {
  score: number | null;
  status?: "done" | "error" | null;
  error?: string | null;
  /** When given, coverage under 40% adds a "Low evidence" flag next to the score. */
  coverage?: number | null;
  className?: string;
}) {
  if (status === "error") {
    return (
      <Tooltip>
        <TooltipTrigger render={<span className={cn(toneBadge({ tone: "rose" }), className)} />}>
          Error
        </TooltipTrigger>
        <TooltipContent>{error ?? "Scan failed"}</TooltipContent>
      </Tooltip>
    );
  }

  if (score === null || score === undefined) {
    // A finished scan with no known verdict is not the same as "never scanned".
    if (status === "done") {
      return (
        <Tooltip>
          <TooltipTrigger render={<span className={cn(toneBadge({ tone: "gray" }), className)} />}>
            No evidence
          </TooltipTrigger>
          <TooltipContent>Scanned, but no criterion could be verified from the public website — nothing was scored.</TooltipContent>
        </Tooltip>
      );
    }
    return <span className={cn(toneBadge({ tone: "gray" }), className)}>Not scanned</span>;
  }

  const lowEvidence = coverage !== undefined && coverage !== null && coverage < LOW_EVIDENCE_BELOW;
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn(toneBadge({ tone: scoreTone(score) }), "tabular-nums", className)}>
        {Math.round(score)}
      </span>
      {lowEvidence && (
        <Tooltip>
          <TooltipTrigger
            render={<span className={cn(toneBadge({ tone: "amber" }), "border border-amber-300 bg-transparent text-amber-800")} />}
          >
            Low evidence
          </TooltipTrigger>
          <TooltipContent>
            Only {Math.round(coverage)}% of criteria could be verified — the score rests on few known verdicts.
          </TooltipContent>
        </Tooltip>
      )}
    </span>
  );
}
