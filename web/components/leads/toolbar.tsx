"use client";

import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Download, Loader2, RadarIcon, Search, Upload } from "lucide-react";

export type MinScoreFilter = "any" | "40" | "70";

interface ToolbarProps {
  search: string;
  onSearchChange: (value: string) => void;
  minScore: MinScoreFilter;
  onMinScoreChange: (value: MinScoreFilter) => void;
  scannedOnly: boolean;
  onScannedOnlyChange: (value: boolean) => void;
  onImportFile: (file: File) => void;
  importing: boolean;
  selectedCount: number;
  onScanSelected: () => void;
  scanSelectedDisabled: boolean;
  scanningInProgress: boolean;
  exportHref: string | null;
}

export function Toolbar({
  search,
  onSearchChange,
  minScore,
  onMinScoreChange,
  scannedOnly,
  onScannedOnlyChange,
  onImportFile,
  importing,
  selectedCount,
  onScanSelected,
  scanSelectedDisabled,
  scanningInProgress,
  exportHref,
}: ToolbarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex flex-wrap items-center gap-2 border-b bg-background px-4 py-3">
      <div className="relative w-full max-w-xs">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search name or domain…"
          className="pl-8"
          aria-label="Search leads"
        />
      </div>

      <Select value={minScore} onValueChange={(v) => onMinScoreChange(v as MinScoreFilter)}>
        <SelectTrigger className="w-36" aria-label="Minimum score filter">
          <SelectValue placeholder="Min score">
            {(value: MinScoreFilter | null) =>
              value === "40" ? "Score ≥ 40" : value === "70" ? "Score ≥ 70" : "Any score"
            }
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="any">Any score</SelectItem>
          <SelectItem value="40">Score ≥ 40</SelectItem>
          <SelectItem value="70">Score ≥ 70</SelectItem>
        </SelectContent>
      </Select>

      <div className="flex items-center gap-2 rounded-lg border px-2.5 py-1.5">
        <Switch id="scanned-only" checked={scannedOnly} onCheckedChange={onScannedOnlyChange} size="sm" />
        <Label htmlFor="scanned-only" className="text-xs font-normal text-muted-foreground">
          Scanned only
        </Label>
      </div>

      <Separator orientation="vertical" className="h-6" />

      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onImportFile(file);
          e.target.value = "";
        }}
      />
      <Button
        variant="outline"
        onClick={() => fileInputRef.current?.click()}
        disabled={importing}
      >
        {importing ? <Loader2 className="animate-spin" /> : <Upload />}
        Import CSV
      </Button>

      <Button onClick={onScanSelected} disabled={scanSelectedDisabled}>
        {scanningInProgress ? <Loader2 className="animate-spin" /> : <RadarIcon />}
        Scan selected {selectedCount > 0 ? `(${selectedCount})` : ""}
      </Button>

      {exportHref ? (
        <Button variant="outline" render={<a href={exportHref} />}>
          <Download />
          Export CSV
        </Button>
      ) : (
        <Button variant="outline" disabled>
          <Download />
          Export CSV
        </Button>
      )}

      <div className="ml-auto text-xs text-muted-foreground">
        {selectedCount > 0 ? `${selectedCount} selected` : null}
      </div>
    </div>
  );
}
