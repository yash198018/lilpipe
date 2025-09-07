import pytest
import logging
from tinypipe.step import Step, pipestep
from tinypipe.models import PipelineContext


@pipestep(name="always_run")
def always_run(ctx: PipelineContext) -> PipelineContext:
    ctx.foo = getattr(ctx, "foo", 0) + 1
    return ctx


@pipestep(name="cacheable", fingerprint_keys=("control",))
def cacheable(ctx: PipelineContext) -> PipelineContext:
    ctx.calls = getattr(ctx, "calls", 0) + 1
    return ctx


@pipestep(name="calibrate", fingerprint_keys=("data",))
def calibrate(ctx: PipelineContext) -> PipelineContext:
    ctx.calibrated = [x * 1.5 for x in ctx.data]
    return ctx


@pipestep(name="validate", fingerprint_keys=("calibrated",))
def validate(ctx: PipelineContext) -> PipelineContext:
    # if any value negative, request another pass
    if any(x < 0 for x in ctx.calibrated):
        ctx.abort_pass()
    return ctx


@pipestep(name="error_step")
def error_step(ctx: PipelineContext) -> PipelineContext:
    raise ValueError("bang")


class NestedStep(Step):
    def __init__(self, name: str, children: list[Step]):
        super().__init__(name, children=children)

    def logic(self, ctx: PipelineContext) -> PipelineContext:
        return ctx  # No-op for parents with children


class TestStep:
    @pytest.mark.usefixtures("caplog")
    def test_always_run_no_cache(self, caplog):
        caplog.set_level(logging.INFO)
        ctx = PipelineContext(foo=0)
        ctx = always_run.run(ctx)
        ctx = always_run.run(ctx)
        assert ctx.foo == 2
        assert "▶️  always_run" in caplog.text
        assert "✅ always_run" in caplog.text
        assert ctx.step_meta["always_run"]["duration"] >= 0
        assert ctx.step_meta["always_run"]["input_hash"] is None

    @pytest.mark.usefixtures("caplog")
    def test_cache_hit(self, caplog):
        caplog.set_level(logging.INFO)
        ctx = PipelineContext(control="CONST")
        ctx = cacheable.run(ctx)
        assert ctx.calls == 1
        assert ctx.step_meta["cacheable"]["status"] == "ok"
        first_hash = ctx.step_meta["cacheable"]["input_hash"]

        caplog.clear()
        ctx = cacheable.run(ctx)
        assert ctx.calls == 1
        assert "Skipping cacheable (cache hit)" in caplog.text
        # On a cache hit, we don't modify duration; assert hash unchanged and status ok
        assert ctx.step_meta["cacheable"]["input_hash"] == first_hash
        assert ctx.step_meta["cacheable"]["status"] == "ok"

    def test_fingerprint_none(self):
        ctx = PipelineContext()
        step = always_run
        assert step._fingerprint(ctx) is None
        ctx = step.run(ctx)
        assert ctx.step_meta["always_run"]["input_hash"] is None

    def test_error_handling(self):
        ctx = PipelineContext()
        with pytest.raises(ValueError, match="bang"):
            error_step.run(ctx)
        meta = ctx.step_meta["error_step"]
        assert meta["status"] == "error"
        assert "bang" in meta["error"]
        assert meta["duration"] >= 0

    @pytest.mark.usefixtures("caplog")
    def test_nested_steps(self, caplog):
        caplog.set_level(logging.INFO)
        nested = NestedStep("nested", children=[calibrate, validate])
        ctx = PipelineContext(data=[1.0, 2.0, 3.0])
        ctx = nested.run(ctx)
        assert ctx.calibrated == [1.5, 3.0, 4.5]
        assert "▶️  nested" in caplog.text
        assert "▶️  calibrate" in caplog.text
        assert "✅ validate" in caplog.text
        assert ctx.step_meta["nested"]["status"] == "ok"
        assert ctx.step_meta["calibrate"]["status"] == "ok"
        assert ctx.step_meta["validate"]["status"] == "ok"

    @pytest.mark.usefixtures("caplog")
    def test_nested_caching(self, caplog):
        caplog.set_level(logging.INFO)
        nested = NestedStep("nested", children=[calibrate, validate])
        ctx = PipelineContext(data=[1.0, 2.0, 3.0])
        ctx = nested.run(ctx)
        assert ctx.calibrated == [1.5, 3.0, 4.5]
        first_calibrate_hash = ctx.step_meta["calibrate"]["input_hash"]

        caplog.clear()
        ctx = nested.run(ctx)
        assert ctx.calibrated == [1.5, 3.0, 4.5]
        assert "Skipping calibrate (cache hit)" in caplog.text
        assert "Skipping validate (cache hit)" in caplog.text
        assert ctx.step_meta["calibrate"]["input_hash"] == first_calibrate_hash

    @pytest.mark.usefixtures("caplog")
    def test_nested_signal_stop(self, caplog):
        caplog.set_level(logging.INFO)

        @pipestep(name="stopper")
        def stopper(ctx: PipelineContext) -> PipelineContext:
            ctx.abort_pass()
            return ctx

        nested = NestedStep("nested", children=[stopper, validate])
        ctx = PipelineContext(data=[1.0, 2.0, 3.0])
        ctx = nested.run(ctx)
        assert "calibrated" not in ctx
        assert ctx.step_meta["stopper"]["status"] == "ok"
        assert "validate" not in ctx.step_meta
        assert "▶️  stopper" in caplog.text
