"use client";

import { useMemo, useRef, useState } from "react";
import { flexRender, type Row, type SortingState } from "@tanstack/react-table";
import {
  useLegacyTable,
  legacyCreateColumnHelper,
  getCoreRowModel,
  getSortedRowModel,
  type LegacyFeatures,
} from "@tanstack/react-table/legacy";
import { cn } from "cn";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Minus,
  RadarIcon,
  XCircle,
} from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ScoreBadge } from "@/components/leads/score-badge";
import { toneBadge } from "@/lib/badge-tones";
import { formatLocation, relativeTime, toHref } from "@/lib/format";
import type { CompanyRow } from "@/lib/api";
import { AlertTriangle, Upload } from "lucide-react";

const columnHelper = legacyCreateColumnHelper<CompanyRow>();

function sortNullableNumber(getter: (row: CompanyRow) => number | null) {
  return (rowA: Row<LegacyFeatures, CompanyRow>, rowB: Row<LegacyFeatures, CompanyRow>) => {
    const a = getter(rowA.original) ?? -1;
    const b = getter(rowB.original) ?? -1;
    return a - b;
  };
}

interface LeadsTableProps {
  companies: CompanyRow[];
  totalCount: number;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  selectedIds: Set<number>;
  onToggleSelect: (id: number) => void;
  onToggleSelectAll: () => void;
  scanningIds: Set<number>;
  onScanRow: (company: CompanyRow) => void;
  onOpenDrawer: (companyId: number) => void;
  scanDisabled: boolean;
  onImportFile: (file: File) => void;
}

export function LeadsTable({
  companies,
  totalCount,
  loading,
  error,
  onRetry,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
  scanningIds,
  onScanRow,
  onOpenDrawer,
  scanDisabled,
  onImportFile,
}: LeadsTableProps) {
  // Rank by score, then by coverage: a 100 with 14% of criteria known ranks below a 100 with 57%.
  const [sorting, setSorting] = useState<SortingState>([
    { id: "score", desc: true },
    { id: "coverage", desc: true },
  ]);
  const importInputRef = useRef<HTMLInputElement>(null);

  const allSelected = companies.length > 0 && companies.every((c) => selectedIds.has(c.id));
  const someSelected = companies.some((c) => selectedIds.has(c.id));

  const columns = useMemo(
    () =>
      columnHelper.columns([
      columnHelper.display({
        id: "select",
        enableSorting: false,
        header: () => (
          <Checkbox
            checked={allSelected}
            indeterminate={someSelected && !allSelected}
            onCheckedChange={() => onToggleSelectAll()}
            aria-label="Select all rows"
          />
        ),
        cell: ({ row }) => (
          <span onClick={(e) => e.stopPropagation()}>
            <Checkbox
              checked={selectedIds.has(row.original.id)}
              onCheckedChange={() => onToggleSelect(row.original.id)}
              aria-label={`Select ${row.original.name}`}
            />
          </span>
        ),
      }),
      columnHelper.accessor("name", {
        id: "company",
        header: "Company",
        enableSorting: true,
        cell: ({ row }) => (
          <div className="flex flex-col">
            <span className="font-medium text-foreground">{row.original.name}</span>
            <a
              href={toHref(row.original.domain)}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex w-fit items-center gap-1 text-xs text-muted-foreground hover:text-foreground hover:underline"
            >
              {row.original.domain}
              <ExternalLink className="size-3" />
            </a>
          </div>
        ),
      }),
      columnHelper.accessor("industry", {
        id: "industry",
        header: "Industry",
        enableSorting: false,
        cell: ({ getValue }) => (
          <span className="text-muted-foreground">{getValue() || "Unknown"}</span>
        ),
      }),
      columnHelper.display({
        id: "location",
        header: "Location",
        enableSorting: false,
        cell: ({ row }) => (
          <span className="text-muted-foreground">
            {formatLocation(row.original.city, row.original.state)}
          </span>
        ),
      }),
      columnHelper.accessor("reachable", {
        id: "reachable",
        header: "Reachable",
        enableSorting: false,
        cell: ({ getValue }) => {
          const value = getValue();
          if (value === true) {
            return (
              <Tooltip>
                <TooltipTrigger render={<span className="inline-flex" />}>
                  <CheckCircle2 className="size-4 text-emerald-600" />
                </TooltipTrigger>
                <TooltipContent>Reachable</TooltipContent>
              </Tooltip>
            );
          }
          if (value === false) {
            return (
              <Tooltip>
                <TooltipTrigger render={<span className="inline-flex" />}>
                  <XCircle className="size-4 text-rose-600" />
                </TooltipTrigger>
                <TooltipContent>Not reachable</TooltipContent>
              </Tooltip>
            );
          }
          return (
            <Tooltip>
              <TooltipTrigger render={<span className="inline-flex" />}>
                <Minus className="size-4 text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent>Not checked yet</TooltipContent>
            </Tooltip>
          );
        },
      }),
      columnHelper.accessor((row) => row.scan?.score ?? null, {
        id: "score",
        header: "Fit Score",
        enableSorting: true,
        // Sorting requires an accessorFn on the column; nulls (unscored) sort
        // as -1 so they land last in the default descending order.
        sortFn: sortNullableNumber((c) => c.scan?.score ?? null),
        cell: ({ row }) => {
          if (scanningIds.has(row.original.id)) {
            return <Loader2 className="size-4 animate-spin text-muted-foreground" />;
          }
          return (
            <ScoreBadge
              score={row.original.scan?.score ?? null}
              status={row.original.scan?.status}
              error={row.original.scan?.error}
            />
          );
        },
      }),
      columnHelper.accessor((row) => row.scan?.coverage ?? null, {
        id: "coverage",
        header: "Coverage",
        enableSorting: true,
        sortFn: sortNullableNumber((c) => c.scan?.coverage ?? null),
        cell: ({ row }) => {
          const coverage = row.original.scan?.coverage ?? null;
          if (coverage === null) return <span className="text-muted-foreground">—</span>;
          return (
            <Tooltip>
              <TooltipTrigger render={<div className="flex w-20 flex-col gap-1" />}>
                <span className="text-xs tabular-nums text-muted-foreground">
                  {Math.round(coverage)}%
                </span>
                <Progress value={coverage} className="h-1" />
              </TooltipTrigger>
              <TooltipContent>Share of criteria with a known verdict</TooltipContent>
            </Tooltip>
          );
        },
      }),
      columnHelper.display({
        id: "criteria",
        header: "Criteria",
        enableSorting: false,
        cell: ({ row }) => {
          const met = row.original.scan?.met_criteria ?? [];
          if (met.length === 0) return <span className="text-muted-foreground">—</span>;
          return (
            <div className="flex max-w-52 flex-wrap gap-1">
              {met.map((label) => (
                <span key={label} className={toneBadge({ tone: "emerald" })}>
                  {label}
                </span>
              ))}
            </div>
          );
        },
      }),
      columnHelper.display({
        id: "scanned",
        header: "Scanned",
        enableSorting: false,
        cell: ({ row }) => (
          <span className="text-xs text-muted-foreground">
            {relativeTime(row.original.scan?.finished_at)}
          </span>
        ),
      }),
      columnHelper.display({
        id: "actions",
        header: "",
        enableSorting: false,
        cell: ({ row }) => {
          const scanning = scanningIds.has(row.original.id);
          return (
            <span onClick={(e) => e.stopPropagation()}>
              <Button
                size="sm"
                variant="outline"
                disabled={scanning || scanDisabled}
                onClick={() => onScanRow(row.original)}
              >
                {scanning ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <RadarIcon />
                )}
                {row.original.scan ? "Rescan" : "Scan"}
              </Button>
            </span>
          );
        },
      }),
      ]),
    [allSelected, someSelected, selectedIds, scanningIds, scanDisabled, onToggleSelect, onToggleSelectAll, onScanRow]
  );

  const table = useLegacyTable({
    data: companies,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getRowId: (row) => String(row.id),
  });

  if (loading) {
    return (
      <div className="flex flex-col gap-2 p-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-start gap-3 p-8 text-sm">
        <div className="flex items-center gap-2 text-destructive">
          <AlertTriangle className="size-4" />
          Failed to load leads
        </div>
        <p className="text-muted-foreground">{error}</p>
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      </div>
    );
  }

  if (totalCount === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-12 text-center">
        <p className="text-sm text-muted-foreground">Import a CSV to get started</p>
        <input
          ref={importInputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onImportFile(file);
            e.target.value = "";
          }}
        />
        <Button onClick={() => importInputRef.current?.click()}>
          <Upload />
          Import CSV
        </Button>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-background">
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id} className="border-b">
              {headerGroup.headers.map((header) => {
                const canSort = header.column.getCanSort();
                const sorted = header.column.getIsSorted();
                return (
                  <th
                    key={header.id}
                    className={cn(
                      "px-3 py-2 text-left text-xs font-medium text-muted-foreground",
                      canSort && "cursor-pointer select-none"
                    )}
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <span className="inline-flex items-center gap-1">
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                      {canSort &&
                        (sorted === "asc" ? (
                          <ArrowUp className="size-3" />
                        ) : sorted === "desc" ? (
                          <ArrowDown className="size-3" />
                        ) : (
                          <ArrowUpDown className="size-3 opacity-40" />
                        ))}
                    </span>
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="p-8 text-center text-sm text-muted-foreground">
                No leads match the current filters.
              </td>
            </tr>
          ) : (
            table.getRowModel().rows.map((row, idx) => (
              <tr
                key={row.id}
                tabIndex={0}
                aria-label={`Open details for ${row.original.name}`}
                onClick={() => onOpenDrawer(row.original.id)}
                onKeyDown={(e) => {
                  if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
                    e.preventDefault();
                    onOpenDrawer(row.original.id);
                  }
                }}
                className={cn(
                  "cursor-pointer border-b transition-colors hover:bg-muted/60 focus-visible:bg-muted/60 focus-visible:outline-none",
                  idx % 2 === 1 && "bg-muted/20"
                )}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-2 align-middle">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
