from lilpipe.models import PipelineContext
from lilpipe.enums import PipelineSignal


class TestPipelineContext:
    def test_signal_methods(self):
        ctx = PipelineContext()
        assert ctx.signal == PipelineSignal.CONTINUE

        ctx.abort_pass()
        assert ctx.signal == PipelineSignal.ABORT_PASS

        # abort_pipeline overrides everything
        ctx.abort_pipeline()
        assert ctx.signal == PipelineSignal.ABORT_PIPELINE

        # further abort_pass() should be ignored after abort_pipeline()
        ctx.abort_pass()
        assert ctx.signal == PipelineSignal.ABORT_PIPELINE

    def test_extra_fields(self):
        ctx = PipelineContext()
        ctx.custom_field = [1, 2, 3]
        dumped = ctx.model_dump()
        assert dumped["custom_field"] == [1, 2, 3]
        assert dumped["signal"] == PipelineSignal.CONTINUE
        assert dumped["step_meta"] == {}

    def test_step_meta_initialization(self):
        ctx = PipelineContext()
        assert ctx.step_meta == {}
        ctx.step_meta["test"] = {"status": "ok"}
        assert ctx.step_meta["test"] == {"status": "ok"}
