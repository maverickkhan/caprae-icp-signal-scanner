// Client-side concurrency-limited runner for "Scan selected". A scan is a
// slow, quota-limited synchronous request, so we cap how many run at once
// regardless of how many ids are enqueued.

export interface ScanQueueOptions {
  concurrency?: number;
  onError?: (id: number, error: unknown) => void;
}

export async function runScanQueue(
  ids: number[],
  scanOne: (id: number) => Promise<void>,
  options: ScanQueueOptions = {}
): Promise<void> {
  const concurrency = Math.max(1, options.concurrency ?? 3);
  let cursor = 0;

  async function worker(): Promise<void> {
    while (cursor < ids.length) {
      const id = ids[cursor];
      cursor += 1;
      try {
        await scanOne(id);
      } catch (error) {
        options.onError?.(id, error);
      }
    }
  }

  const workers = Array.from({ length: Math.min(concurrency, ids.length) }, () => worker());
  await Promise.all(workers);
}
