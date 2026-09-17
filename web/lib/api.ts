// Typed fetch helpers for the ICP Signal Scanner API. All calls hit relative
// `/api/...` paths — in dev, next.config.ts rewrites these to the FastAPI
// server; on Vercel, vercel.json routes them directly.

export type Polarity = "positive" | "negative";
export type Verdict = "met" | "not_met" | "unknown";
export type Grounding = "exact" | "fuzzy" | "record" | "none";
export type ScanStatus = "done" | "error";
export type NoteStatus = "ok" | "unverified" | "skipped";

export interface Criterion {
  key: string;
  label: string;
  weight: number;
  test: string;
  polarity: Polarity;
}

export interface CriterionResult extends Criterion {
  verdict: Verdict;
  evidence_quote: string | null;
  source_url: string | null;
  grounding: Grounding;
  confidence: number | null;
}

export interface Fact {
  id: number;
  category: string;
  fact: string;
  evidence_quote: string | null;
  source_url: string | null;
  confidence: number | null;
  grounding: Grounding;
}

export interface IcpProfile {
  id: number;
  name: string;
  description_text: string;
  description_hash: string;
  criteria: Criterion[];
}

export interface ScanSummary {
  scan_id: number;
  status: ScanStatus;
  score: number | null;
  coverage: number | null;
  met_criteria: string[];
  finished_at: string | null;
  error: string | null;
}

export interface CompanyRow {
  id: number;
  domain: string;
  name: string;
  industry: string | null;
  city: string | null;
  state: string | null;
  employee_range: string | null;
  revenue_estimate: string | null;
  phone: string | null;
  linkedin_url: string | null;
  source: string | null;
  reachable: boolean | null;
  created_at: string;
  scan: ScanSummary | null;
}

export interface ScanCompanyRef {
  id: number;
  name: string;
  domain: string;
  reachable: boolean | null;
}

export interface ModelVersions {
  fast: string | null;
  smart: string | null;
}

export interface ScanDetail {
  scan_id: number;
  company_id: number;
  company: ScanCompanyRef;
  icp_id: number;
  icp_name: string;
  status: ScanStatus;
  score: number | null;
  coverage: number | null;
  outreach_note: string | null;
  model_versions: ModelVersions;
  pages_fetched: number | null;
  fallback_used: boolean | null;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  criteria: CriterionResult[];
  facts: Fact[];
  note_status?: NoteStatus | null;
  breakdown?: unknown;
  // Present on the POST /api/scan response only.
  timings?: Record<string, number> | null;
}

export interface ImportResult {
  inserted: number;
  duplicates_skipped: number;
  no_domain_skipped: number;
  total_rows: number;
}

export interface HealthResponse {
  ok: boolean;
  db: boolean;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail: string | undefined;
    try {
      const body = (await res.json()) as { detail?: string };
      detail = body?.detail;
    } catch {
      // response had no JSON body
    }
    throw new ApiError(detail ?? `Request failed with status ${res.status}`, res.status);
  }
  return (await res.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return fetch("/api/health").then((r) => handle<HealthResponse>(r));
}

export function listIcps(): Promise<IcpProfile[]> {
  return fetch("/api/icp").then((r) => handle<IcpProfile[]>(r));
}

export function createIcp(body: { name: string; description_text: string }): Promise<IcpProfile> {
  return fetch("/api/icp", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => handle<IcpProfile>(r));
}

export interface UpdateIcpBody {
  name?: string;
  description_text?: string;
  criteria?: Criterion[];
}

export function updateIcp(id: number, body: UpdateIcpBody): Promise<IcpProfile> {
  return fetch(`/api/icp/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => handle<IcpProfile>(r));
}

export function compileIcp(id: number): Promise<IcpProfile> {
  return fetch(`/api/icp/${id}/compile`, { method: "POST" }).then((r) => handle<IcpProfile>(r));
}

export function listCompanies(icpId: number): Promise<CompanyRow[]> {
  return fetch(`/api/companies?icp_id=${icpId}`).then((r) => handle<CompanyRow[]>(r));
}

export function importCompanies(file: File): Promise<ImportResult> {
  const form = new FormData();
  form.append("file", file);
  return fetch("/api/companies/import", { method: "POST", body: form }).then((r) =>
    handle<ImportResult>(r)
  );
}

export function scanCompany(companyId: number, icpId: number, force = false): Promise<ScanDetail> {
  return fetch(`/api/scan/${companyId}?icp_id=${icpId}&force=${force}`, {
    method: "POST",
  }).then((r) => handle<ScanDetail>(r));
}

export function getScan(scanId: number): Promise<ScanDetail> {
  return fetch(`/api/scans/${scanId}`).then((r) => handle<ScanDetail>(r));
}

export function exportCsvUrl(icpId: number): string {
  return `/api/export.csv?icp_id=${icpId}`;
}

/** Builds the row-summary shape from a full scan detail, for updating a table row in place. */
export function summarizeScan(detail: ScanDetail): ScanSummary {
  // Chips mean "fits": a met *negative* criterion is a disqualifier, not a fit signal.
  const met = detail.criteria
    .filter((c) => c.verdict === "met" && c.polarity !== "negative")
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 3)
    .map((c) => c.label);
  return {
    scan_id: detail.scan_id,
    status: detail.status,
    score: detail.score,
    coverage: detail.coverage,
    met_criteria: met,
    finished_at: detail.finished_at,
    error: detail.error,
  };
}
