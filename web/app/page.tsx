"use client";

import { useEffect, useState } from "react";

type Health = { ok: boolean; db: boolean };

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setHealth)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 p-8 font-sans">
      <h1 className="text-3xl font-semibold tracking-tight">ICP Signal Scanner</h1>
      <p className="text-zinc-500">AI Web Scanner for SaaSquatch Leads — hello world</p>
      <div className="rounded-lg border px-6 py-4 font-mono text-sm">
        <div className="mb-2 text-xs uppercase tracking-wide text-zinc-500">GET /api/health</div>
        {error ? (
          <span className="text-red-600">error: {error}</span>
        ) : health ? (
          <pre>{JSON.stringify(health)}</pre>
        ) : (
          <span className="text-zinc-400">loading…</span>
        )}
      </div>
      {health && (
        <div className="flex gap-3 text-sm">
          <Badge ok={health.ok} label="api" />
          <Badge ok={health.db} label="neon db" />
        </div>
      )}
    </main>
  );
}

function Badge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`rounded-full px-3 py-1 font-medium ${
        ok ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"
      }`}
    >
      {label}: {ok ? "ok" : "down"}
    </span>
  );
}
