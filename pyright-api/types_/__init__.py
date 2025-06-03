from typing import Literal, NotRequired, TypedDict

__all__ = ("PyrightPayload", "PyrightResponse")


class PyrightSummary(TypedDict):
    filesAnalyzed: int
    errorCount: int
    warningCount: int
    informationCount: int
    timeInSec: float


class Range(TypedDict):
    line: int
    character: int


class PyrightRange(TypedDict):
    start: Range
    end: Range


class PyrightDiagnostics(TypedDict):
    file: str
    severity: Literal["error", "warning"]
    message: str
    range: PyrightRange
    rule: str


class PyrightOutput(TypedDict):
    version: str
    time: str
    generalDiagnostics: list[PyrightDiagnostics]
    summary: PyrightSummary


class PyrightPayload(TypedDict):
    content: str
    version: NotRequired[str]


class _Versions(TypedDict):
    node_version: str
    pyright_version: str
    python_version: str


class PyrightResponse(_Versions):
    result: PyrightOutput
