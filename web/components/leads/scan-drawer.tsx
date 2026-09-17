"use client";

import { toast } from "sonner";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { VerdictBadge } from "@/components/leads/verdict-badge";
import { GroundingBadge } from "@/components/leads/grounding-badge";
import { ScoreBadge } from "@/components/leads/score-badge";
import { toneBadge } from "@/lib/badge-tones";
import { hostname, relativeTime, toHref } from "@/lib/format";
import { cn } from "cn";
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  ExternalLink,
  Loader2,
  Minus,
  RadarIcon,
  XCircle,
} from "lucide-react";
import type { CompanyRow, CriterionResult, ScanDetail } from "@/lib/api";

function earnedWeight(c: CriterionResult): number {
  if (c.verdict === "met" && c.polarity === "positive") return c.weight;
  if (c.verdict === "not_met" && c.polarity === "negative") return c.weight;
  return 0;
}

function ReachableIcon({ reachable }: { reachable: boolean | null }) {
  if (reachable === true) return <CheckCircle2 className="size-4 text-emerald-600" />;
  if (reachable === false) return <XCircle className="size-4 text-rose-600" />;
  return <Minus className="size-4 text-muted-foreground" />;
}

function ScoreBreakdownRow({ criterion }: { criterion: CriterionResult }) {
  const isUnknown = criterion.verdict === "unknown";
  const earned = isUnknown ? 0 : earnedWeight(criterion);
  const pct = isUnknown ? 0 : Math.round((earned / criterion.weight) * 100);
  const disqualifier = criterion.polarity === "negative" && criterion.verdict === "met";

  return (
    <div className="flex flex-col gap-1.5 py-2">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="flex flex-wrap items-center gap-1.5">
          <span className="font-medium">{criterion.label}</span>
          <span className="text-xs text-muted-foreground">weight {criterion.weight}</span>
          {criterion.polarity === "negative" && (
            <span className="text-xs text-muted-foreground">(avoid)</span>
          )}
        </span>
        <span className="flex shrink-0 items-center gap-1.5">
          {disqualifier && <span className={toneBadge({ tone: "rose" })}>Disqualifier</span>}
          <VerdictBadge verdict={criterion.verdict} />
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        {isUnknown ? (
          <div
            className="h-full w-full opacity-50"
            style={{
              backgroundImage:
                "repeating-linear-gradient(45deg, var(--color-border) 0px, var(--color-border) 4px, transparent 4px, transparent 8px)",
            }}
          />
        ) : (
          <div
            className={cn("h-full rounded-full", earned > 0 ? "bg-emerald-500" : "bg-rose-300")}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
      {isUnknown && <span className="text-xs text-muted-foreground">Unknown · not scored</span>}
    </div>
  );
}

interface ScanDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  company: CompanyRow | null;
  detail: ScanDetail | null;
  loading: boolean;
  error: string | null;
  scanning: boolean;
  onScanNow: (force: boolean) => void;
}

export function ScanDrawer({
  open,
  onOpenChange,
  company,
  detail,
  loading,
  error,
  scanning,
  onScanNow,
}: ScanDrawerProps) {
  const name = detail?.company.name ?? company?.name ?? "Company";
  const domain = detail?.company.domain ?? company?.domain ?? "";
  const reachable = detail?.company.reachable ?? company?.reachable ?? null;
  const hasScan = Boolean(company?.scan) || Boolean(detail);

  async function handleCopyNote() {
    if (!detail?.outreach_note) return;
    try {
      await navigator.clipboard.writeText(detail.outreach_note);
      toast.success("Copied");
    } catch {
      toast.error("Could not copy to clipboard");
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex w-full flex-col gap-0 p-0 sm:max-w-[560px]">
        <SheetHeader className="border-b">
          <SheetTitle className="flex items-center gap-2">
            {name}
            <ReachableIcon reachable={reachable} />
          </SheetTitle>
          {domain && (
            <a
              href={toHref(domain)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex w-fit items-center gap-1 text-xs text-muted-foreground hover:text-foreground hover:underline"
            >
              {domain}
              <ExternalLink className="size-3" />
            </a>
          )}
          {detail && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <ScoreBadge
                score={detail.score}
                status={detail.status}
                error={detail.error}
                className="text-sm"
              />
              <span className="text-xs text-muted-foreground">
                coverage {detail.coverage === null ? "—" : `${Math.round(detail.coverage)}%`}
              </span>
              {detail.pages_fetched !== null && (
                <span className="text-xs text-muted-foreground">
                  {detail.pages_fetched} pages{detail.fallback_used ? " · fallback used" : ""}
                </span>
              )}
              <Button
                size="sm"
                variant="outline"
                className="ml-auto"
                disabled={scanning}
                onClick={() => onScanNow(true)}
              >
                {scanning ? <Loader2 className="animate-spin" /> : <RadarIcon />}
                Rescan
              </Button>
            </div>
          )}
        </SheetHeader>

        <div className="flex-1 overflow-y-auto p-4">
          {loading && (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
          )}

          {!loading && error && (
            <div className="flex flex-col items-start gap-2 text-sm">
              <div className="flex items-center gap-2 text-destructive">
                <AlertTriangle className="size-4" />
                {error}
              </div>
            </div>
          )}

          {!loading && !error && !hasScan && (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
              <p className="text-sm text-muted-foreground">
                This company hasn&apos;t been scanned yet.
              </p>
              <Button onClick={() => onScanNow(false)} disabled={scanning}>
                {scanning ? <Loader2 className="animate-spin" /> : <RadarIcon />}
                Scan now
              </Button>
            </div>
          )}

          {!loading && !error && detail && (
            <div className="flex flex-col gap-6">
              {detail.status === "error" && (
                <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                  This scan ended with an error: {detail.error ?? "unknown error"}. Partial results below
                  are still evidence-grounded; unknown criteria were not scored.
                </div>
              )}
              <section>
                <h3 className="mb-1 text-sm font-semibold">Score breakdown</h3>
                <div className="divide-y">
                  {detail.criteria.map((c) => (
                    <ScoreBreakdownRow key={c.key} criterion={c} />
                  ))}
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  score = earned weight ÷ weight of known criteria
                </p>
              </section>

              <section>
                <h3 className="mb-2 text-sm font-semibold">Criteria evidence</h3>
                <div className="flex flex-col gap-2">
                  {detail.criteria.map((c) => (
                    <div key={c.key} className="rounded-lg border p-3">
                      <div className="flex items-center justify-between gap-2">
                        <VerdictBadge verdict={c.verdict} />
                        <span className="text-xs text-muted-foreground">weight {c.weight}</span>
                      </div>
                      <p className="mt-1.5 text-sm font-medium">{c.label}</p>
                      <p className="text-xs text-muted-foreground">{c.test}</p>
                      {c.evidence_quote ? (
                        <div className="mt-2 flex flex-col gap-1.5">
                          <blockquote className="border-l-2 pl-2 text-sm text-foreground/90 italic">
                            &ldquo;{c.evidence_quote}&rdquo;
                          </blockquote>
                          <div className="flex flex-wrap items-center gap-2">
                            {c.source_url && (
                              <a
                                href={c.source_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-xs text-muted-foreground hover:underline"
                              >
                                {hostname(c.source_url)}
                              </a>
                            )}
                            <GroundingBadge grounding={c.grounding} />
                          </div>
                        </div>
                      ) : (
                        <p className="mt-2 text-xs text-muted-foreground">
                          No verified evidence found — not scored.
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </section>

              <section>
                <details open className="rounded-lg border">
                  <summary className="cursor-pointer px-3 py-2 text-sm font-semibold">
                    Facts ({detail.facts.length})
                  </summary>
                  <div className="flex flex-col gap-3 px-3 pb-3">
                    {detail.facts.map((f) => (
                      <div key={f.id} className="flex flex-col gap-1 border-t pt-2 first:border-t-0 first:pt-0">
                        <div className="flex items-center gap-2">
                          <span className={toneBadge({ tone: "blue" })}>{f.category}</span>
                          <GroundingBadge grounding={f.grounding} />
                        </div>
                        <p className="text-sm">{f.fact}</p>
                        {f.evidence_quote && (
                          <p className="text-xs text-muted-foreground italic">
                            &ldquo;{f.evidence_quote}&rdquo;
                          </p>
                        )}
                        {f.source_url && (
                          <a
                            href={f.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="w-fit text-xs text-muted-foreground hover:underline"
                          >
                            {hostname(f.source_url)}
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </details>
              </section>

              <section className="rounded-lg border p-3">
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-semibold">Outreach note</h3>
                  {detail.outreach_note && (
                    <Button size="sm" variant="outline" onClick={handleCopyNote}>
                      <Copy />
                      Copy
                    </Button>
                  )}
                </div>
                {detail.outreach_note ? (
                  <p className="text-sm">{detail.outreach_note}</p>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    {detail.note_status === "unverified"
                      ? "No note — the draft referenced something not in the verified facts, so it was discarded"
                      : "No note — fewer than two verified facts"}
                  </p>
                )}
                <p className="mt-3 text-xs text-muted-foreground">
                  fast: {detail.model_versions.fast ?? "Unknown"} · smart:{" "}
                  {detail.model_versions.smart ?? "Unknown"} · finished{" "}
                  {relativeTime(detail.finished_at)}
                </p>
              </section>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
