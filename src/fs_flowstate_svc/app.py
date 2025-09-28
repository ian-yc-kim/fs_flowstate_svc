import logging
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from fs_flowstate_svc.api.auth_router import auth_router
from fs_flowstate_svc.api.event_router import event_router
from fs_flowstate_svc.api.inbox_router import inbox_router
from fs_flowstate_svc.api.websocket_router import websocket_router

# Set up logger for this module
logger = logging.getLogger("fs_flowstate_svc.app")

# Create FastAPI app with debug disabled so exception handlers run in tests
app = FastAPI(debug=False)

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}", exc_info=True)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    logger.error(f"Validation Error: {exc.errors()}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "message": "Validation Error"
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc: Exception):
    logger.critical(f"Unhandled Exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error"}
    )

# add routers
app.include_router(auth_router)
app.include_router(event_router, prefix="/api")
app.include_router(inbox_router, prefix="/api")
# websocket router mounted under /ws
app.include_router(websocket_router, prefix="/ws")
