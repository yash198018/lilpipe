import pytest
import logging
from tinypipe.engine import Pipeline
from tinypipe.step import Step, pipestep
from tinypipe.models import PipelineContext
from tinypipe.enums import PipelineSignal


@pipestep(name="signal_setter")
def signal_setter(ctx: PipelineContext) -> PipelineContext:
    # Record which step ran
    ctx.seq = getattr(ctx, "seq", []) + [getattr(ctx, "setter_name", "signal_setter")]
    # Only trigger once unless caller changes the flag
    if not getattr(ctx, "has_triggered", False):
        signal = getattr(ctx, "set_signal", PipelineSignal.CONTINUE)
        if signal is PipelineSignal.ABORT_PASS:
            ctx.abort_pass()
        elif signal is PipelineSignal.ABORT_PIPELINE:
            ctx.abort_pipeline()
        # CONTINUE => do nothing
        ctx.has_triggered = True
    return ctx


@pipestep(name="record")
def record(ctx: PipelineContext) -> PipelineContext:
    ctx.seq = getattr(ctx, "seq", []) + [getattr(ctx, "record_name", "record")]
    return ctx


@pipestep(name="calibrate", fingerprint_keys=("data",))
def calibrate(ctx: PipelineContext) -> PipelineContext:
    ctx.calibrated = [round(x * 1.5, 2) for x in ctx.data]
    return ctx


@pipestep(name="validate", fingerprint_keys=("calibrated",))
def validate(ctx: PipelineContext) -> PipelineContext:
    ctx.attempt = getattr(ctx, "attempt", 0) + 1
    # If any negative values exist, ask for another pass (abort current pass)
    if any(x < 0 for x in ctx.calibrated) and ctx.attempt < 2:
        ctx.abort_pass()
    return ctx


@pipestep(name="load_assay")
def load_assay(ctx: PipelineContext) -> PipelineContext:
    ctx.attempt = getattr(ctx, "attempt", 0) + 1
    ctx.data = [0.1, 0.2, 0.3]
    return ctx


class NestedStep(Step):
    def logic(self, ctx: PipelineContext) -> PipelineContext:
        return ctx


class TestPipeline:
    @pytest.mark.usefixtures("caplog")
    def test_sequence_order(self, caplog):
        caplog.set_level(logging.INFO)
        steps = [signal_setter, record]
        ctx = PipelineContext(seq=[], setter_name="signal", record_name="record")
        Pipeline(steps, name="my_pipe").run(ctx)
        assert ctx.seq == ["signal", "record"]
        assert "▶️  my_pipe pass" in caplog.text
        assert "✅  my_pipe finished after 1 pass(es)" in caplog.text

    def test_abort_pass_triggers_rerun(self):
        steps = [signal_setter, record]
        ctx = PipelineContext(
            seq=[],
            set_signal=PipelineSignal.ABORT_PASS,
            setter_name="signal",
            record_name="record",
        )
        Pipeline(steps, max_passes=3).run(ctx)
        # First pass: signal_setter runs & aborts pass -> no record
        # Second pass: signal_setter (has_triggered=True) then record
        assert ctx.seq == ["signal", "signal", "record"]

    def test_abort_pipeline(self):
        steps = [signal_setter, record]
        ctx = PipelineContext(
            seq=[], set_signal=PipelineSignal.ABORT_PIPELINE, setter_name="abort"
        )
        Pipeline(steps).run(ctx)
        assert ctx.seq == ["abort"]

    def test_max_passes_exceeded(self):
        @pipestep(name="persistent_retry")
        def persistent_retry(ctx: PipelineContext) -> PipelineContext:
            ctx.seq = getattr(ctx, "seq", []) + ["retry"]
            ctx.abort_pass()
            return ctx

        steps = [persistent_retry]
        ctx = PipelineContext(seq=[])
        with pytest.raises(RuntimeError, match="exceeded 3 passes"):
            Pipeline(steps, max_passes=3).run(ctx)
        assert len(ctx.seq) == 3

    @pytest.mark.usefixtures("caplog")
    def test_nested_steps(self, caplog):
        caplog.set_level(logging.INFO)
        nested = NestedStep("nested", children=[calibrate, validate])
        pipeline = Pipeline([nested], name="nested_pipe")
        ctx = PipelineContext(data=[1.0, 2.0, 3.0])
        pipeline.run(ctx)
        assert ctx.calibrated == [1.5, 3.0, 4.5]
        assert ctx.attempt == 1
        assert "▶️  nested" in caplog.text
        assert "✅ nested" in caplog.text
        assert ctx.step_meta["nested"]["status"] == "ok"

    def test_lba_workflow(self):
        process = NestedStep("process", children=[load_assay, calibrate, validate])
        pipeline = Pipeline([process], name="lba_pipe", max_passes=3)
        ctx = PipelineContext()
        pipeline.run(ctx)
        assert ctx.calibrated == [0.15, 0.3, 0.45]
        # load_assay increments attempt; validate increments once
        assert ctx.attempt == 2
        assert ctx.step_meta["process"]["status"] == "ok"
        assert ctx.step_meta["load_assay"]["status"] == "ok"
        assert ctx.step_meta["calibrate"]["status"] == "ok"
        assert ctx.step_meta["validate"]["status"] == "ok"
