"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { AlertTriangle, Loader2, Plus, Sparkles, X } from "lucide-react";
import {
  ApiError,
  compileIcp,
  createIcp,
  updateIcp,
  type Criterion,
  type IcpProfile,
} from "@/lib/api";
import { cn } from "cn";

const PRESET_NAMES = ["Search-fund buy-box", "B2B sales ICP"];

function criteriaEqual(a: Criterion[], b: Criterion[]): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

interface IcpPanelProps {
  icps: IcpProfile[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  selectedIcpId: number | null;
  onSelectIcp: (id: number) => void;
  onIcpUpdated: (icp: IcpProfile) => void;
  onIcpCreated: (icp: IcpProfile) => void;
}

export function IcpPanel({
  icps,
  loading,
  error,
  onRetry,
  selectedIcpId,
  onSelectIcp,
  onIcpUpdated,
  onIcpCreated,
}: IcpPanelProps) {
  const [creating, setCreating] = useState(false);

  async function handleCreate() {
    const name = window.prompt("Name for the new ICP", "My ICP")?.trim();
    if (!name) return;
    setCreating(true);
    try {
      const icp = await createIcp({ name, description_text: "" });
      onIcpCreated(icp);
      toast.success(`Created "${icp.name}" — describe it, then compile`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to create ICP");
    } finally {
      setCreating(false);
    }
  }

  const selected = icps.find((i) => i.id === selectedIcpId) ?? null;
  const isPreset = selected !== null && PRESET_NAMES.includes(selected.name);

  const [draftDescription, setDraftDescription] = useState(selected?.description_text ?? "");
  const [draftCriteria, setDraftCriteria] = useState<Criterion[]>(selected?.criteria ?? []);
  const [compiling, setCompiling] = useState(false);
  const [saving, setSaving] = useState(false);

  // Reset the editable drafts when the *selected ICP itself* changes (switching
  // presets/dropdown). This adjusts state during render instead of in an effect —
  // compile/save already push their own fresh values into the drafts directly.
  const [syncedIcpId, setSyncedIcpId] = useState<number | null>(selected?.id ?? null);
  if ((selected?.id ?? null) !== syncedIcpId) {
    setSyncedIcpId(selected?.id ?? null);
    setDraftDescription(selected?.description_text ?? "");
    setDraftCriteria(selected?.criteria ?? []);
  }

  const dirtyDescription = selected !== null && draftDescription !== selected.description_text;
  const dirtyCriteria = selected !== null && !criteriaEqual(draftCriteria, selected.criteria);

  async function handleCompile() {
    if (!selected) return;
    setCompiling(true);
    try {
      let target = selected;
      if (dirtyDescription) {
        target = await updateIcp(selected.id, { description_text: draftDescription });
        onIcpUpdated(target);
      }
      const compiled = await compileIcp(target.id);
      onIcpUpdated(compiled);
      setDraftCriteria(compiled.criteria);
      toast.success(`Compiled ${compiled.criteria.length} criteria`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to compile criteria");
    } finally {
      setCompiling(false);
    }
  }

  async function handleSaveCriteria() {
    if (!selected) return;
    setSaving(true);
    try {
      const updated = await updateIcp(selected.id, { criteria: draftCriteria });
      onIcpUpdated(updated);
      setDraftCriteria(updated.criteria);
      toast.success("Criteria saved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to save criteria");
    } finally {
      setSaving(false);
    }
  }

  function updateCriterion(index: number, patch: Partial<Criterion>) {
    setDraftCriteria((prev) => prev.map((c, i) => (i === index ? { ...c, ...patch } : c)));
  }

  function removeCriterion(index: number) {
    setDraftCriteria((prev) => prev.filter((_, i) => i !== index));
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-3 p-4">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-start gap-3 p-4 text-sm">
        <div className="flex items-center gap-2 text-destructive">
          <AlertTriangle className="size-4" />
          Failed to load ICPs
        </div>
        <p className="text-muted-foreground">{error}</p>
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
      <div>
        <h2 className="text-sm font-semibold">Ideal Customer Profile</h2>
        <p className="text-xs text-muted-foreground">
          Describe your ICP in plain English, compile it into weighted criteria, then scan leads
          against it.
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label className="text-xs text-muted-foreground">Presets</Label>
        <div className="flex flex-wrap gap-1.5">
          {PRESET_NAMES.map((name) => {
            const icp = icps.find((i) => i.name === name);
            return (
              <Button
                key={name}
                size="sm"
                variant={selected?.name === name ? "default" : "outline"}
                disabled={!icp}
                onClick={() => icp && onSelectIcp(icp.id)}
              >
                {name}
              </Button>
            );
          })}
          <Button size="sm" variant="outline" onClick={handleCreate} disabled={creating} aria-label="New ICP">
            {creating ? <Loader2 className="animate-spin" /> : <Plus />}
            New ICP
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="icp-select" className="text-xs text-muted-foreground">
          Other ICP
        </Label>
        <Select
          value={selectedIcpId ? String(selectedIcpId) : undefined}
          onValueChange={(v) => onSelectIcp(Number(v))}
        >
          <SelectTrigger id="icp-select" className="w-full">
            <SelectValue placeholder="Select an ICP">
              {(value: string | null) =>
                icps.find((i) => String(i.id) === value)?.name ?? "Select an ICP"
              }
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {icps.map((icp) => (
              <SelectItem key={icp.id} value={String(icp.id)}>
                {icp.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {selected ? (
        <>
          {isPreset && (
            <p className="rounded-md border bg-muted/40 px-2.5 py-2 text-xs text-muted-foreground">
              Presets are shared in this demo and read-only, so the pre-warmed scans stay valid. Use{" "}
              <span className="font-medium text-foreground">New ICP</span> to write and compile your own.
            </p>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="icp-description" className="text-xs text-muted-foreground">
              Description
            </Label>
            <Textarea
              id="icp-description"
              value={draftDescription}
              onChange={(e) => setDraftDescription(e.target.value)}
              rows={6}
              className="text-sm"
              readOnly={isPreset}
            />
            {!isPreset && (
              <Button
                onClick={handleCompile}
                disabled={compiling || draftDescription.trim() === ""}
                className="mt-1 self-start"
              >
                {compiling ? <Loader2 className="animate-spin" /> : <Sparkles />}
                Compile criteria
              </Button>
            )}
          </div>

          <Separator />

          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs text-muted-foreground">
                Criteria ({draftCriteria.length})
              </Label>
              {dirtyCriteria && (
                <span className="text-xs font-medium text-amber-700 dark:text-amber-400">
                  Unsaved changes
                </span>
              )}
            </div>

            {draftCriteria.length === 0 ? (
              <p className="rounded-lg border border-dashed p-4 text-center text-xs text-muted-foreground">
                Compile to generate 4–8 weighted criteria
              </p>
            ) : (
              <fieldset disabled={isPreset} className="flex flex-col gap-2 disabled:opacity-80">
                {draftCriteria.map((c, i) => (
                  <div key={c.key || i} className="flex flex-col gap-1.5 rounded-lg border p-2.5">
                    <div className="flex items-center gap-1.5">
                      <Input
                        value={c.label}
                        aria-label={`Criterion ${i + 1} label`}
                        onChange={(e) => updateCriterion(i, { label: e.target.value })}
                        className="h-7 flex-1 text-sm font-medium"
                      />
                      <Input
                        type="number"
                        min={1}
                        max={5}
                        value={c.weight}
                        onChange={(e) =>
                          updateCriterion(i, { weight: Number(e.target.value) || 1 })
                        }
                        className="h-7 w-14 text-center"
                        aria-label="Weight"
                      />
                      <Button
                        type="button"
                        size="xs"
                        variant={c.polarity === "negative" ? "destructive" : "outline"}
                        onClick={() =>
                          updateCriterion(i, {
                            polarity: c.polarity === "negative" ? "positive" : "negative",
                          })
                        }
                        className={cn("shrink-0")}
                      >
                        {c.polarity === "negative" ? "Avoid" : "Match"}
                      </Button>
                      <Button
                        type="button"
                        size="icon-xs"
                        variant="ghost"
                        onClick={() => removeCriterion(i)}
                        aria-label="Remove criterion"
                      >
                        <X />
                      </Button>
                    </div>
                    <Input
                      value={c.test}
                      aria-label={`Criterion ${i + 1} test question`}
                      onChange={(e) => updateCriterion(i, { test: e.target.value })}
                      className="h-6 border-none bg-transparent px-0 text-xs text-muted-foreground shadow-none focus-visible:ring-0"
                    />
                  </div>
                ))}
              </fieldset>
            )}

            <Button
              variant="outline"
              onClick={handleSaveCriteria}
              disabled={isPreset || saving || draftCriteria.length === 0 || !dirtyCriteria}
              className="self-start"
            >
              {saving ? <Loader2 className="animate-spin" /> : null}
              Save criteria
            </Button>
          </div>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">Select an ICP to get started.</p>
      )}
    </div>
  );
}
