from typing import Any, Dict
from pydantic import BaseModel, Field
from .enums import PipelineSignal


class PipelineContext(BaseModel):
    step_meta: Dict[str, Any] = Field(
        default_factory=dict, description="Per-step diagnostics and cache metadata."
    )
    signal: PipelineSignal = Field(
        default=PipelineSignal.CONTINUE,
        description="Pipeline control signal for the current pass.",
    )

    def continue_(self) -> None:
        self.signal = PipelineSignal.CONTINUE

    def skip_rest_of_pass(self) -> None:
        if self.signal != PipelineSignal.ABORT_PIPELINE:
            self.signal = PipelineSignal.SKIP_REST_OF_PASS

    def start_another_pass(self) -> None:
        if self.signal not in (
            PipelineSignal.ABORT_PIPELINE,
            PipelineSignal.SKIP_REST_OF_PASS,
        ):
            self.signal = PipelineSignal.START_ANOTHER_PASS

    def abort_pipeline(self) -> None:
        self.signal = PipelineSignal.ABORT_PIPELINE

    model_config = {"extra": "allow"}
