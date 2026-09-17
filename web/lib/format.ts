// Tiny formatting helpers — no date library, kept intentionally small.

/** "2h ago" / "3d ago" style relative time. Returns "—" for missing/invalid input. */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diffSec = Math.max(0, Math.round((Date.now() - then) / 1000));

  if (diffSec < 45) return "just now";
  if (diffSec < 3600) return `${Math.max(1, Math.floor(diffSec / 60))}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  if (diffSec < 2592000) return `${Math.floor(diffSec / 86400)}d ago`;
  if (diffSec < 31536000) return `${Math.floor(diffSec / 2592000)}mo ago`;
  return `${Math.floor(diffSec / 31536000)}y ago`;
}

/** Strips scheme/www for a compact display of a URL's host. */
export function hostname(url: string | null | undefined): string {
  if (!url) return "";
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** "example.com" -> "https://example.com" for building an external link. */
export function toHref(domainOrUrl: string): string {
  if (/^https?:\/\//i.test(domainOrUrl)) return domainOrUrl;
  return `https://${domainOrUrl}`;
}

export function formatLocation(city: string | null, state: string | null): string {
  const parts = [city, state].filter((p): p is string => Boolean(p && p.trim()));
  if (parts.length === 0) return "Unknown";
  return parts.join(", ");
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value)}%`;
}
