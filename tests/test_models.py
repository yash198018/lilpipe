from tinypipe.models import PipelineContext
from tinypipe.enums import PipelineSignal


class TestPipelineContext:
    def test_signal_methods(self):
        ctx = PipelineContext()
        assert ctx.signal == PipelineSignal.CONTINUE

        ctx.start_another_pass()
        assert ctx.signal == PipelineSignal.START_ANOTHER_PASS

        ctx.skip_rest_of_pass()  # Overrides to SKIP
        assert ctx.signal == PipelineSignal.SKIP_REST_OF_PASS

        ctx.continue_()
        ctx.skip_rest_of_pass()
        assert ctx.signal == PipelineSignal.SKIP_REST_OF_PASS

        ctx.abort_pipeline()
        assert ctx.signal == PipelineSignal.ABORT_PIPELINE
        ctx.skip_rest_of_pass()  # Ignored due to ABORT
        assert ctx.signal == PipelineSignal.ABORT_PIPELINE

        ctx.continue_()
        assert ctx.signal == PipelineSignal.CONTINUE

    def test_extra_fields(self):
        ctx = PipelineContext()
        ctx.custom_field = [1, 2, 3]
        assert ctx.custom_field == [1, 2, 3]
        assert ctx.model_dump() == {
            "step_meta": {},
            "signal": PipelineSignal.CONTINUE,
            "custom_field": [1, 2, 3],
        }

    def test_step_meta_initialization(self):
        ctx = PipelineContext()
        assert ctx.step_meta == {}
        ctx.step_meta["test"] = {"status": "ok"}
        assert ctx.step_meta["test"] == {"status": "ok"}
