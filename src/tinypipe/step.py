from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable, Optional, Callable
import time
import logging
from .utils import _deep_hash
from .enums import PipelineSignal
from .models import PipelineContext

log = logging.getLogger(__name__)


class Step(ABC):
    """Base class for pipeline steps, supporting both logic and nested children."""

    name: str = "<unnamed>"
    fingerprint_keys: Iterable[str] | None = None
    children: Optional[list[Step]] = None

    def __init__(self, name: str, children: Optional[Iterable[Step]] = None):
        self.name = name
        self.children = list(children) if children is not None else None

    def run(self, ctx: PipelineContext, depth: int = 1) -> PipelineContext:
        meta = ctx.step_meta.setdefault(self.name, {})
        indent = "    " * depth

        log.info("%s▶️  %s", indent, self.name)

        fp = self._fingerprint(ctx)
        if (
            fp is not None
            and meta.get("input_hash") == fp
            and meta.get("status") == "ok"
        ):
            log.info("%s⤵  Skipping %s (cache hit)", indent, self.name)
            return ctx

        meta["input_hash"] = fp
        t0 = time.perf_counter()

        try:
            if self.children:
                for child in self.children:
                    ctx = child.run(ctx, depth + 1)
                    if ctx.signal in (
                        PipelineSignal.SKIP_REST_OF_PASS,
                        PipelineSignal.ABORT_PIPELINE,
                        PipelineSignal.START_ANOTHER_PASS,
                    ):
                        break
            else:
                ctx = self.logic(ctx)
            meta["status"] = "ok"
        except Exception as exc:
            meta.update(status="error", error=str(exc))
            raise
        finally:
            meta["duration"] = round(time.perf_counter() - t0, 3)
            log.info("%s⏱️  %s finished in %.3f s", indent, self.name, meta["duration"])

        log.info("%s✅ %s", indent, self.name)
        return ctx

    def _fingerprint(self, ctx: PipelineContext) -> str | None:
        if self.fingerprint_keys is None:
            return None
        payload = {k: getattr(ctx, k, None) for k in self.fingerprint_keys}
        return _deep_hash(payload)

    @abstractmethod
    def logic(self, ctx: PipelineContext) -> PipelineContext: ...


def pipestep(name: str, fingerprint_keys: Optional[Iterable[str]] = None) -> Callable:
    """Decorator to turn a function into a Step."""

    def decorator(func: Callable[[PipelineContext], PipelineContext]) -> Step:
        class DecoratedStep(Step):
            def __init__(self):
                super().__init__(name=name, children=None)
                self.fingerprint_keys = fingerprint_keys

            def logic(self, ctx: PipelineContext) -> PipelineContext:
                return func(ctx)

        DecoratedStep.__name__ = f"Step_{name}"
        return DecoratedStep()

    return decorator
