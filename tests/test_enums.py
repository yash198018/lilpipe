from tinypipe.enums import PipelineSignal


class TestPipelineSignal:
    def test_enum_values(self):
        assert len(PipelineSignal) == 4
        assert PipelineSignal.CONTINUE.value == 1
        assert PipelineSignal.SKIP_REST_OF_PASS.value == 2
        assert PipelineSignal.START_ANOTHER_PASS.value == 3
        assert PipelineSignal.ABORT_PIPELINE.value == 4

    def test_enum_names(self):
        assert PipelineSignal.CONTINUE.name == "CONTINUE"
        assert PipelineSignal.SKIP_REST_OF_PASS.name == "SKIP_REST_OF_PASS"
        assert PipelineSignal.START_ANOTHER_PASS.name == "START_ANOTHER_PASS"
        assert PipelineSignal.ABORT_PIPELINE.name == "ABORT_PIPELINE"
