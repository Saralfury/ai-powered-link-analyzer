"""FastAPI application: AI-Powered Website Link Analysis API.

Run locally:
    uvicorn app.main:app --host 0.0.0.0 --port 4000

API docs: http://localhost:4000/docs
"""

import logging
from fastapi import FastAPI, Request
from fastapi.exception_handlers import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.errors import LinkAnalysisError, InvalidURLError, SSRFError, ExtractionError, LLMError
from app.schemas import ErrorResponse, LinkAnalysisRequest, LinkAnalysisResponse
from app.services.analysis_service import AnalysisService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("link-analysis")

app = FastAPI(
    title="AI-Powered Website Link Analysis API",
    description=(
        "Analyse a website URL with an LLM and return structured business, "
        "competitor, SEO, search-query and target-audience insights."
    ),
    version="1.0.0",
)

analysis_service = AnalysisService()

# Serve frontend static files (CSS, JS) at /static
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/", include_in_schema=False)
async def frontend_root():
    return FileResponse("frontend/index.html")


@app.get("/health")
async def health():
    return {
        "service": "AI-Powered Website Link Analysis API",
        "version": "1.0.0",
        "llm_provider": settings.LLM_PROVIDER,
        "mock_mode": settings.USE_MOCK_LLM,
        "docs": "/docs",
    }


@app.post(
    "/link-analysis",
    response_model=LinkAnalysisResponse,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
    tags=["Analysis"],
)
async def link_analysis(request: Request, payload: LinkAnalysisRequest):
    raw_url = str(payload.url)

    # 1. Validate URL + SSRF protection.
    try:
        clean_url = validate_url(raw_url)
    except (InvalidURLError, SSRFError) as exc:
        logger.warning("Rejected URL %s: %s", raw_url, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                success=False,
                website=raw_url,
                error={"code": exc.error_code, "message": exc.message},
                detail=exc.details,
            ).model_dump(),
        )

    # 2. Run analysis pipeline.
    try:
        result = await analysis_service.analyze(clean_url)
        return result
    except LinkAnalysisError as exc:
        logger.warning("Analysis failed for %s: %s", clean_url, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                success=False,
                website=clean_url,
                error={"code": exc.error_code, "message": exc.message},
                detail=exc.details,
            ).model_dump(),
        )
    except Exception as exc:
        logger.exception("Unexpected error analysing %s", clean_url)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                success=False,
                website=clean_url,
                error={"code": "INTERNAL_ERROR", "message": "Internal analysis error."},
                detail={"exception": str(exc)},
            ).model_dump(),
        )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            success=False,
            error={"code": "VALIDATION_ERROR", "message": "Request validation failed."},
            detail=exc.errors(),
        ).model_dump(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.HOST, port=settings.PORT)


from app.utils.validators import validate_url  # noqa: E402
