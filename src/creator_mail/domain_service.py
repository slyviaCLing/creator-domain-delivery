from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .creator_delivery import (
    CreatorDispatchRequest,
    DispatchResult,
    DomainNotReady,
    DomainOnboardingRequest,
    dispatch_creator_message,
)
from .infrai_email import InfraiClient, InfraiError

app = FastAPI(title="Creator sending domain")


@app.exception_handler(InfraiError)
def infrai_error_response(_request: Request, exc: InfraiError) -> JSONResponse:
    client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
    return JSONResponse(
        status_code=client_status,
        content={"detail": {"code": exc.code, "message": str(exc)}},
    )


def get_infrai() -> InfraiClient:
    return InfraiClient()


@app.post("/domains", status_code=201)
def onboard_domain(request: DomainOnboardingRequest, client: InfraiClient = Depends(get_infrai)) -> dict:
    return client.verify_domain(request.domain)


@app.post("/deliveries", response_model=DispatchResult)
def create_delivery(
    request: CreatorDispatchRequest,
    client: InfraiClient = Depends(get_infrai),
) -> DispatchResult:
    try:
        return dispatch_creator_message(request, client)
    except DomainNotReady as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
