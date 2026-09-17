"""LangFuse tracing for scans. Optional: no keys => no-op. Flushes before the request returns (Vercel: nothing runs after)."""

from __future__ import annotations

import asyncio
import logging
from contextlib import AbstractAsyncContextManager
from functools import lru_cache

from app.config import get_settings

log = logging.getLogger("icp.tracing")


@lru_cache
def get_langfuse():
    s = get_settings()
    if not (s.langfuse_public_key and s.langfuse_secret_key):
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(public_key=s.langfuse_public_key, secret_key=s.langfuse_secret_key, host=s.langfuse_host, flush_at=50, flush_interval=1.0)
    except Exception as e:  # noqa: BLE001
        log.warning("langfuse disabled: %s", e)
        return None


class ScanTrace(AbstractAsyncContextManager):
    """`async with ScanTrace(scan_id, domain, icp_id) as t:` -> pass `t.callbacks` to the graph; call `t.set_output(...)`."""

    def __init__(self, scan_id: int, domain: str, icp_id: int, icp_name: str | None = None):
        self.callbacks: list = []
        self._lf = get_langfuse()
        self._span_cm = None
        self._attr_cm = None
        self._span = None
        self._tags = [f"scan_id:{scan_id}", f"domain:{domain}", f"icp_id:{icp_id}"]
        self._meta = {"scan_id": scan_id, "domain": domain, "icp_id": icp_id, "icp_name": icp_name}
        self._name = f"scan {domain}"

    async def __aenter__(self):
        if self._lf is None:
            return self
        try:
            from langfuse import propagate_attributes
            from langfuse.langchain import CallbackHandler

            # langfuse >= 4: trace-level attributes propagate via context; the root observation is a "chain".
            self._attr_cm = propagate_attributes(
                trace_name=self._name,
                session_id=f"icp-{self._meta['icp_id']}",
                tags=self._tags,
                metadata={k: str(v) for k, v in self._meta.items() if v is not None},
            )
            self._attr_cm.__enter__()
            self._span_cm = self._lf.start_as_current_observation(name=self._name, as_type="chain", input=self._meta)
            self._span = self._span_cm.__enter__()
            self.callbacks = [CallbackHandler()]
        except Exception as e:  # noqa: BLE001 - tracing must never break a scan
            log.warning("langfuse trace setup failed: %s", e)
            self._span_cm = self._span = None
            self.callbacks = []
        return self

    def set_output(self, output: dict) -> None:
        if self._span is not None:
            try:
                self._span.update(output=output)
                self._lf.set_current_trace_io(output=output)
            except Exception:  # noqa: BLE001
                pass

    async def __aexit__(self, exc_type, exc, tb):
        for cm in (self._span_cm, self._attr_cm):
            if cm is not None:
                try:
                    cm.__exit__(exc_type, exc, tb)
                except Exception:  # noqa: BLE001
                    pass
        if self._lf is not None:
            try:
                await asyncio.wait_for(asyncio.to_thread(self._lf.flush), timeout=10)
            except Exception as e:  # noqa: BLE001
                log.warning("langfuse flush failed: %s", e)
        return False
