from fastapi import APIRouter, UploadFile, File, Body, HTTPException
from schemas import IngestResponse
from typing import Optional
from services.ingest import IngestionService
from services.categorizer import CategorizerService
from services.db_service import DBService
import os

router = APIRouter(prefix="/ingest", tags=["Ingest"])

# Maximum allowed file size: 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024
CHUNK_SIZE = 64 * 1024  # 64 KB read buffer


@router.post("/file", response_model=IngestResponse)
async def ingest_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    if extension not in ("csv", "pdf", "txt", "sms"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{extension}'. Supported: csv, pdf, txt.",
        )

    chunks = []
    total_bytes = 0

    try:
        # Stream file in chunks, terminating immediately if the size limit is exceeded
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail="File too large. Maximum size is 10 MB.",
                )
            chunks.append(chunk)

        content = b"".join(chunks)

        if extension == "csv":
            txs = IngestionService.process_csv(content)
        elif extension == "pdf":
            txs = IngestionService.process_pdf(content)
        else:  # txt / sms — treated as a single SMS text
            tx = IngestionService.process_sms(content.decode("utf-8"))
            txs = [tx] if tx else []

        # Categorize and store
        categorized_txs = CategorizerService.categorize_batch(txs)
        count = IngestionService.ingest(categorized_txs)

        return IngestResponse(
            message=f"Processed {len(txs)} transactions, {count} new ones added",
            transactions_count=count,
        )

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File encoding error. Use UTF-8 encoded files.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
    finally:
        await file.close()


@router.post("/sms", response_model=IngestResponse)
async def ingest_sms(payload: dict = Body(...)):
    text = payload.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="No SMS text provided")

    tx = IngestionService.process_sms(text)
    if not tx:
        raise HTTPException(status_code=400, detail="Could not parse SMS content")

    # Categorize and store
    tx["category"] = CategorizerService.categorize(tx["merchant"], tx["description"])
    tx_id = DBService.add_transaction(tx)

    amount = tx["amount"] if tx_id else None
    return IngestResponse(message="SMS processed", detected_amount=amount)


@router.post("/sample", response_model=IngestResponse)
async def ingest_sample():
    """Load the bundled sample CSV data. Useful for demos and testing."""
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sample_statement.csv")
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="Sample data file not found")

    with open(csv_path, "rb") as f:
        content = f.read()

    txs = IngestionService.process_csv(content)
    categorized_txs = CategorizerService.categorize_batch(txs)
    count = IngestionService.ingest(categorized_txs)
    return IngestResponse(
        message=f"Sample data loaded: {count} transactions added",
        transactions_count=count,
    )
