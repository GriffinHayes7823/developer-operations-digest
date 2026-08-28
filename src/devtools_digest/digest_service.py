"""Developer-tools digest decisions and HTTP request models."""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr, Field, HttpUrl

from .infrai_client import InfraiClient, InfraiError


class BuildEvent(BaseModel):
    project: str
    status: Literal["passed", "failed"]


class ReleaseOperation(BaseModel):
    package: str
    version: str


class Diagnostic(BaseModel):
    component: str
    message: str
    severity: Literal["info", "warning", "critical"]


class DigestRequest(BaseModel):
    recipient: EmailStr
    week: str = Field(pattern=r"^\d{4}-W\d{2}$")
    builds: list[BuildEvent] = Field(default_factory=list)
    releases: list[ReleaseOperation] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class DigestDecision(BaseModel):
    action: Literal["send", "skip"]
    subject: str | None
    lines: list[str]


class ScheduleRequest(BaseModel):
    task_url: HttpUrl
    cron_expr: str = "0 9 * * 1"


class ScheduleResponse(BaseModel):
    job_id: str


def decide_digest(request: DigestRequest) -> DigestDecision:
    failed = [item for item in request.builds if item.status == "failed"]
    notable_diagnostics = [item for item in request.diagnostics if item.severity != "info"]
    if not request.releases and not failed and not notable_diagnostics:
        return DigestDecision(action="skip", subject=None, lines=[])

    lines = [f"Release: {item.package} {item.version}" for item in request.releases]
    lines += [f"Build failed: {item.project}" for item in failed]
    lines += [
        f"Diagnostic ({item.severity}): {item.component} - {item.message}"
        for item in notable_diagnostics
    ]
    return DigestDecision(
        action="send",
        subject=f"Developer operations digest - {request.week}",
        lines=lines,
    )


app = FastAPI(title="Developer operations digest")


@app.post("/digest", response_model=DigestDecision)
def build_digest(request: DigestRequest) -> DigestDecision:
    """Return the concrete delivery decision used by the mail boundary."""
    return decide_digest(request)


@app.post("/schedule", response_model=ScheduleResponse)
def schedule_digest(request: ScheduleRequest) -> ScheduleResponse:
    key = f"developer-digest:{request.cron_expr}:{request.task_url}"
    try:
        job_id = InfraiClient().cron_create(
            cron_expr=request.cron_expr,
            task=str(request.task_url),
            idempotency_key=key,
        )
    except InfraiError as error:
        status = error.status_code if 400 <= error.status_code < 500 else 502
        raise HTTPException(status_code=status, detail=error.detail) from error
    return ScheduleResponse(job_id=job_id)
