from enum import Enum, auto


class PipelineSignal(Enum):
    CONTINUE = auto()
    SKIP_REST_OF_PASS = auto()
    START_ANOTHER_PASS = auto()
    ABORT_PIPELINE = auto()
