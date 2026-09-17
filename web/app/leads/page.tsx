"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { PanelLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { IcpPanel } from "@/components/leads/icp-panel";
import { Toolbar, type MinScoreFilter } from "@/components/leads/toolbar";
import { LeadsTable } from "@/components/leads/leads-table";
import { ScanDrawer } from "@/components/leads/scan-drawer";
import { cn } from "cn";
import {
  ApiError,
  exportCsvUrl,
  getHealth,
  getScan,
  importCompanies,
  listCompanies,
  listIcps,
  scanCompany,
  summarizeScan,
  type CompanyRow,
  type HealthResponse,
  type IcpProfile,
  type ScanDetail,
} from "@/lib/api";
import { createScanLimiter, runScanQueue } from "@/lib/scan-queue";

const MAX_PARALLEL_SCANS = 3;

const ICP_STORAGE_KEY = "icp-signal-scanner:selected-icp-id";

function readStoredIcpId(): number | null {
  try {
    const raw = window.localStorage.getItem(ICP_STORAGE_KEY);
    return raw ? Number(raw) : null;
  } catch {
    return null;
  }
}

function writeStoredIcpId(id: number) {
  try {
    window.localStorage.setItem(ICP_STORAGE_KEY, String(id));
  } catch {
    // ignore (private mode / disabled storage)
  }
}

export default function LeadsPage() {
  // --- health -------------------------------------------------------------
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth({ ok: false, db: false }));
  }, []);

  // --- ICPs -----------------------------------------------------------------
  const [icps, setIcps] = useState<IcpProfile[]>([]);
  const [icpsLoading, setIcpsLoading] = useState(true);
  const [icpsError, setIcpsError] = useState<string | null>(null);
  const [selectedIcpId, setSelectedIcpId] = useState<number | null>(null);

  const loadIcps = useCallback(() => {
    setIcpsLoading(true);
    listIcps()
      .then((data) => {
        setIcps(data);
        setIcpsError(null);
        setSelectedIcpId((current) => {
          if (current !== null && data.some((i) => i.id === current)) return current;
          const stored = readStoredIcpId();
          const restored = stored !== null && data.some((i) => i.id === stored) ? stored : null;
          return restored ?? data[0]?.id ?? null;
        });
      })
      .catch((err) => setIcpsError(err instanceof ApiError ? err.message : "Failed to load ICPs"))
      .finally(() => setIcpsLoading(false));
  }, []);

  useEffect(() => {
    // Fetch-on-mount, per the documented pattern at
    // https://react.dev/learn/synchronizing-with-effects#fetching-data — the
    // "set-state-in-effect" rule flags the synchronous loading flag it sets,
    // but there's no local prop/state to derive this from during render.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadIcps();
  }, [loadIcps]);

  // Latest ICP id for async work started under an earlier selection (scan results, refetches).
  const selectedIcpRef = useRef<number | null>(null);
  useEffect(() => {
    selectedIcpRef.current = selectedIcpId;
  }, [selectedIcpId]);

  const selectedIcp = icps.find((i) => i.id === selectedIcpId) ?? null;
  const hasCriteria = (selectedIcp?.criteria.length ?? 0) > 0;

  function onSelectIcp(id: number) {
    selectedIcpRef.current = id;
    setSelectedIcpId(id);
    writeStoredIcpId(id);
    setSelectedIds(new Set());
  }

  function onIcpUpdated(icp: IcpProfile) {
    setIcps((prev) => prev.map((i) => (i.id === icp.id ? icp : i)));
  }

  // --- companies --------------------------------------------------------
  const [companies, setCompanies] = useState<CompanyRow[]>([]);
  const [companiesLoading, setCompaniesLoading] = useState(true);
  const [companiesError, setCompaniesError] = useState<string | null>(null);

  const refreshCompanies = useCallback(() => {
    if (selectedIcpId === null) {
      setCompaniesLoading(false);
      return;
    }
    setCompaniesLoading(true);
    listCompanies(selectedIcpId)
      .then((data) => {
        setCompanies(data);
        setCompaniesError(null);
      })
      .catch((err) =>
        setCompaniesError(err instanceof ApiError ? err.message : "Failed to load companies")
      )
      .finally(() => setCompaniesLoading(false));
  }, [selectedIcpId, setCompanies]);

  useEffect(() => {
    // Re-fetch leads whenever the selected ICP changes — synchronizing with
    // the backend, the textbook case for an effect. See the fetch-on-mount
    // note above re: the "set-state-in-effect" rule.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshCompanies();
  }, [refreshCompanies]);

  // --- filters ------------------------------------------------------------
  const [search, setSearch] = useState("");
  const [minScore, setMinScore] = useState<MinScoreFilter>("any");
  const [scannedOnly, setScannedOnly] = useState(false);

  const filteredCompanies = useMemo(() => {
    const q = search.trim().toLowerCase();
    return companies.filter((c) => {
      if (q && !(c.name.toLowerCase().includes(q) || c.domain.toLowerCase().includes(q))) {
        return false;
      }
      if (scannedOnly && !c.scan) return false;
      if (minScore !== "any" && Math.round(c.scan?.score ?? -1) < Number(minScore)) return false;
      return true;
    });
  }, [companies, search, scannedOnly, minScore]);

  // --- selection ------------------------------------------------------------
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    setSelectedIds((prev) => {
      const allSelected =
        filteredCompanies.length > 0 && filteredCompanies.every((c) => prev.has(c.id));
      const next = new Set(prev);
      for (const c of filteredCompanies) {
        if (allSelected) next.delete(c.id);
        else next.add(c.id);
      }
      return next;
    });
  }

  // --- scanning ------------------------------------------------------------
  const [scanningIds, setScanningIds] = useState<Set<number>>(new Set());
  const [scanQueueRunning, setScanQueueRunning] = useState(false);

  const limiterRef = useRef(createScanLimiter(MAX_PARALLEL_SCANS));

  const performScan = useCallback(
    async (companyId: number, force: boolean): Promise<ScanDetail> => {
      const icpId = selectedIcpRef.current;
      if (icpId === null) throw new Error("No ICP selected");
      const detail = await limiterRef.current.run(() => scanCompany(companyId, icpId, force));
      // The user may have switched ICP meanwhile: never write another ICP's result into this table.
      if (selectedIcpRef.current === icpId) {
        const summary = summarizeScan(detail);
        setCompanies((prev) =>
          prev.map((c) =>
            c.id === companyId ? { ...c, reachable: detail.company.reachable, scan: summary } : c
          )
        );
      }
      return detail;
    },
    [setCompanies]
  );

  const doScanOne = useCallback(
    async (companyId: number, force: boolean) => {
      setScanningIds((prev) => new Set(prev).add(companyId));
      try {
        await performScan(companyId, force);
      } catch (err) {
        const company = companies.find((c) => c.id === companyId);
        const message = err instanceof ApiError ? err.message : "Scan request failed";
        toast.error(`${company?.name ?? "Scan"}: ${message}`);
      } finally {
        setScanningIds((prev) => {
          const next = new Set(prev);
          next.delete(companyId);
          return next;
        });
      }
    },
    [performScan, companies]
  );

  function onScanRow(company: CompanyRow) {
    if (selectedIcpId === null) return;
    void doScanOne(company.id, Boolean(company.scan));
  }

  async function onScanSelected() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0 || !hasCriteria || selectedIcpId === null) return;
    const icpAtStart = selectedIcpId;
    setScanQueueRunning(true);
    try {
      // force=false: the backend returns the 7-day cached result unless the criteria changed.
      await runScanQueue(ids, (id) => doScanOne(id, false), { concurrency: MAX_PARALLEL_SCANS });
    } finally {
      setScanQueueRunning(false);
      if (selectedIcpRef.current === icpAtStart) refreshCompanies();
    }
  }

  // --- import ------------------------------------------------------------
  const [importing, setImporting] = useState(false);

  async function handleImportFile(file: File) {
    setImporting(true);
    try {
      const result = await importCompanies(file);
      toast.success(
        `Imported ${result.inserted} leads (${result.duplicates_skipped} duplicates, ${result.no_domain_skipped} without a domain skipped)`
      );
      refreshCompanies();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  }

  // --- drawer ------------------------------------------------------------
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerCompanyId, setDrawerCompanyId] = useState<number | null>(null);
  const [drawerDetail, setDrawerDetail] = useState<ScanDetail | null>(null);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [drawerError, setDrawerError] = useState<string | null>(null);
  const [drawerScanning, setDrawerScanning] = useState(false);

  const drawerCompanyRef = useRef<number | null>(null);
  useEffect(() => {
    drawerCompanyRef.current = drawerCompanyId;
  }, [drawerCompanyId]);

  const drawerCompany = companies.find((c) => c.id === drawerCompanyId) ?? null;

  function openDrawer(companyId: number) {
    drawerCompanyRef.current = companyId;
    setDrawerCompanyId(companyId);
    setDrawerOpen(true);
    setDrawerDetail(null);
    setDrawerError(null);
    const company = companies.find((c) => c.id === companyId);
    if (company?.scan) {
      setDrawerLoading(true);
      getScan(company.scan.scan_id)
        .then((detail) => {
          if (drawerCompanyRef.current === companyId) setDrawerDetail(detail);
        })
        .catch((err) => {
          if (drawerCompanyRef.current === companyId)
            setDrawerError(err instanceof ApiError ? err.message : "Failed to load scan");
        })
        .finally(() => {
          if (drawerCompanyRef.current === companyId) setDrawerLoading(false);
        });
    }
  }

  async function drawerScanNow(force: boolean) {
    const companyId = drawerCompanyId;
    if (companyId === null) return;
    setDrawerScanning(true);
    setDrawerError(null);
    try {
      const detail = await performScan(companyId, force);
      if (drawerCompanyRef.current === companyId) setDrawerDetail(detail);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Scan failed";
      if (drawerCompanyRef.current === companyId) setDrawerError(message);
      toast.error(message);
    } finally {
      if (drawerCompanyRef.current === companyId) setDrawerScanning(false);
    }
  }

  // --- left panel collapse (small screens) --------------------------------
  // Defaults open so server-rendered HTML and the first client paint match
  // (avoiding a hydration mismatch); collapses right after mount on narrow
  // viewports, which is unavoidably an effect since `window` isn't available
  // during render on the server.
  const [icpPanelOpen, setIcpPanelOpen] = useState(true);
  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia("(max-width: 767px)").matches) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIcpPanelOpen(false);
    }
  }, []);

  const healthOk = Boolean(health?.ok && health?.db);

  return (
    <div className="flex h-dvh flex-col">
      <header className="sticky top-0 z-30 flex items-center gap-3 border-b bg-background px-4 py-3">
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => setIcpPanelOpen((v) => !v)}
          aria-label="Toggle ICP panel"
        >
          <PanelLeft />
        </Button>
        <div>
          <h1 className="text-sm font-semibold leading-tight">ICP Signal Scanner</h1>
          <p className="text-xs leading-tight text-muted-foreground">
            AI Web Scanner for SaaSquatch Leads
          </p>
        </div>
        <Tooltip>
          <TooltipTrigger render={<span className="ml-auto inline-flex items-center gap-1.5" />}>
            <span
              className={cn(
                "inline-block size-2.5 rounded-full",
                health ? (healthOk ? "bg-emerald-500" : "bg-rose-500") : "bg-muted-foreground/40"
              )}
            />
            <span className="text-xs text-muted-foreground">API</span>
          </TooltipTrigger>
          <TooltipContent>
            {health ? `api: ${health.ok ? "ok" : "down"} · db: ${health.db ? "ok" : "down"}` : "checking…"}
          </TooltipContent>
        </Tooltip>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside
          className={cn(
            "shrink-0 overflow-hidden border-r bg-background transition-[width]",
            icpPanelOpen ? "w-[360px]" : "w-0 border-r-0"
          )}
        >
          <div className="h-full w-[360px] overflow-y-auto">
            <IcpPanel
              icps={icps}
              loading={icpsLoading}
              error={icpsError}
              onRetry={loadIcps}
              selectedIcpId={selectedIcpId}
              onSelectIcp={onSelectIcp}
              onIcpUpdated={onIcpUpdated}
            />
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <Toolbar
            search={search}
            onSearchChange={setSearch}
            minScore={minScore}
            onMinScoreChange={setMinScore}
            scannedOnly={scannedOnly}
            onScannedOnlyChange={setScannedOnly}
            onImportFile={handleImportFile}
            importing={importing}
            selectedCount={selectedIds.size}
            onScanSelected={onScanSelected}
            scanSelectedDisabled={selectedIds.size === 0 || !hasCriteria || scanQueueRunning}
            scanningInProgress={scanQueueRunning}
            exportHref={selectedIcpId !== null ? exportCsvUrl(selectedIcpId) : null}
          />
          <div className="flex-1 overflow-hidden">
            <LeadsTable
              companies={filteredCompanies}
              totalCount={companies.length}
              loading={companiesLoading || icpsLoading}
              error={companiesError}
              onRetry={refreshCompanies}
              selectedIds={selectedIds}
              onToggleSelect={toggleSelect}
              onToggleSelectAll={toggleSelectAll}
              scanningIds={scanningIds}
              onScanRow={onScanRow}
              onOpenDrawer={openDrawer}
              scanDisabled={!hasCriteria}
              onImportFile={handleImportFile}
            />
          </div>
        </main>
      </div>

      <ScanDrawer
        open={drawerOpen}
        onOpenChange={(open) => {
          setDrawerOpen(open);
          if (!open) {
            drawerCompanyRef.current = null;
            setDrawerCompanyId(null);
          }
        }}
        company={drawerCompany}
        detail={drawerDetail}
        loading={drawerLoading}
        error={drawerError}
        scanning={drawerScanning}
        onScanNow={drawerScanNow}
      />
    </div>
  );
}
