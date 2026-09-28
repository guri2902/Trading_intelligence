from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..realtime import realtime_pipeline

router = APIRouter(prefix="/pipeline", tags=["realtime-pipeline"])


class StartRequest(BaseModel):
    interval_seconds: int = Field(default=30, ge=5, le=300)


@router.get("/status")
def pipeline_status():
    return realtime_pipeline.status()


@router.post("/start")
async def pipeline_start(request: StartRequest):
    return realtime_pipeline.start(request.interval_seconds)


@router.post("/stop")
async def pipeline_stop():
    return await realtime_pipeline.stop()