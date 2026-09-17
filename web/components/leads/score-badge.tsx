import { cn } from "cn";
import { toneBadge, type Tone } from "@/lib/badge-tones";
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
  className,
}: {
  score: number | null;
  status?: "done" | "error" | null;
  error?: string | null;
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

  return (
    <span className={cn(toneBadge({ tone: scoreTone(score) }), "tabular-nums", className)}>
      {Math.round(score)}
    </span>
  );
}
