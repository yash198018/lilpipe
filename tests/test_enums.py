from lilpipe.enums import PipelineSignal


class TestPipelineSignal:
    def test_enum_values(self):
        assert len(PipelineSignal) == 3
        assert PipelineSignal.CONTINUE.value == 1
        assert PipelineSignal.ABORT_PASS.value == 2
        assert PipelineSignal.ABORT_PIPELINE.value == 3

    def test_enum_names(self):
        assert PipelineSignal.CONTINUE.name == "CONTINUE"
        assert PipelineSignal.ABORT_PASS.name == "ABORT_PASS"
        assert PipelineSignal.ABORT_PIPELINE.name == "ABORT_PIPELINE"
