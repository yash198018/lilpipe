import pytest
import logging
from tinypipe.engine import Pipeline
from tinypipe.step import Step, PipelineContext, pipestep
from tinypipe.enums import PipelineSignal


@pipestep(name="signal_setter")
def signal_setter(ctx: PipelineContext) -> PipelineContext:
    ctx.seq = getattr(ctx, "seq", []) + [getattr(ctx, "setter_name", "signal_setter")]
    if not getattr(ctx, "has_triggered", False):
        signal = getattr(ctx, "set_signal", PipelineSignal.CONTINUE)
        method_name = signal.name.lower()
        if method_name == "continue":
            method_name = "continue_"
        getattr(ctx, method_name)()
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
    if any(x < 0 for x in ctx.calibrated) and ctx.attempt < 2:
        ctx.start_another_pass()
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

    def test_start_another_pass(self):
        steps = [signal_setter, record]
        ctx = PipelineContext(
            seq=[],
            set_signal=PipelineSignal.START_ANOTHER_PASS,
            setter_name="signal",
            record_name="record",
        )
        Pipeline(steps, max_passes=3).run(ctx)
        assert ctx.seq == ["signal", "record", "signal", "record"]

    def test_skip_rest_of_pass(self):
        steps = [signal_setter, record]
        ctx = PipelineContext(
            seq=[], set_signal=PipelineSignal.SKIP_REST_OF_PASS, setter_name="skip"
        )
        Pipeline(steps).run(ctx)
        assert ctx.seq == ["skip"]

    def test_abort_pipeline(self):
        steps = [signal_setter, record]
        ctx = PipelineContext(
            seq=[], set_signal=PipelineSignal.ABORT_PIPELINE, setter_name="abort"
        )
        Pipeline(steps).run(ctx)
        assert ctx.seq == ["abort"]

    def test_start_another_pass_with_skip(self):
        steps = [signal_setter, signal_setter, record]
        ctx = PipelineContext(
            seq=[], set_signal=PipelineSignal.SKIP_REST_OF_PASS, setter_name="skip"
        )
        Pipeline(steps, max_passes=3).run(ctx)
        assert ctx.seq == ["skip"]

        ctx = PipelineContext(
            seq=[],
            set_signal=PipelineSignal.START_ANOTHER_PASS,
            setter_name="signal1",
            record_name="record",
        )
        Pipeline(steps, max_passes=3).run(ctx)
        assert ctx.seq == [
            "signal1",
            "signal1",
            "record",
            "signal1",
            "signal1",
            "record",
        ]

    def test_max_passes_exceeded(self):
        @pipestep(name="persistent_retry")
        def persistent_retry(ctx: PipelineContext) -> PipelineContext:
            ctx.seq = getattr(ctx, "seq", []) + ["retry"]
            method_name = "start_another_pass"
            getattr(ctx, method_name)()
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
        assert ctx.attempt == 2  # Incremented in load_assay and validate
        assert ctx.step_meta["process"]["status"] == "ok"
        assert ctx.step_meta["load_assay"]["status"] == "ok"
        assert ctx.step_meta["calibrate"]["status"] == "ok"
        assert ctx.step_meta["validate"]["status"] == "ok"
