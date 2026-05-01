"""
ISC Drawing Analyser — FastAPI Backend
Indo Shell Cast Pvt. Ltd.
"""

import io
import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from analyzer import analyze_drawing
from excel_generator import generate_excel

load_dotenv()

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ISC Drawing Analyser API",
    description="Extracts technical data from engineering drawing PDFs and generates ISC Contract Review Sheets.",
    version="1.0.0",
)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

APP_API_KEY = os.getenv("APP_API_KEY", "isc-change-me")


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


def verify_api_key(x_api_key: str = Header(..., description="App API key")):
    if x_api_key != APP_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
def health_check():
    """Liveness probe for Railway / Render."""
    return {"status": "ok", "service": "isc-drawing-analyser"}


@app.post(
    "/analyze",
    tags=["analysis"],
    summary="Upload a drawing PDF → receive a filled Contract Review Sheet (.xlsx)",
)
async def analyze(
    file: UploadFile = File(..., description="Engineering drawing PDF"),
    _: str = Depends(verify_api_key),
):
    _validate_pdf(file)
    pdf_bytes = await file.read()

    extracted = await analyze_drawing(pdf_bytes, file.filename or "drawing.pdf")
    excel_bytes = generate_excel(extracted)

    stem = (file.filename or "drawing").rsplit(".", 1)[0]
    download_name = f"{stem}_contract_review.xlsx"

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@app.post(
    "/analyze/preview",
    tags=["analysis"],
    summary="Upload a drawing PDF → receive extracted data as JSON (no Excel)",
)
async def analyze_preview(
    file: UploadFile = File(..., description="Engineering drawing PDF"),
    _: str = Depends(verify_api_key),
):
    _validate_pdf(file)
    pdf_bytes = await file.read()

    extracted = await analyze_drawing(pdf_bytes, file.filename or "drawing.pdf")
    return JSONResponse({"filename": file.filename, "data": extracted})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_pdf(file: UploadFile) -> None:
    name = (file.filename or "").lower()
    if not name.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
    if file.size and file.size > 20 * 1024 * 1024:  # 20 MB guard
        raise HTTPException(status_code=413, detail="File exceeds 20 MB limit.")
