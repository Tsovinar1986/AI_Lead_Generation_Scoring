"""Churn-risk scoring for customer/subscriber exports -- a separate,
free-to-test capability from the licensed lead-scoring product
(routers/leads.py), since it's a different data shape (individual
subscribers, not B2B companies) and not the thing this product is sold as.
No license gating here.
"""

from fastapi import APIRouter, HTTPException, UploadFile

from ..models import ChurnScoredCustomer
from ..services.churn_scoring import parse_churn_file, score_churn_customer

router = APIRouter(prefix="/api/churn", tags=["churn"])


@router.post("/upload", response_model=list[ChurnScoredCustomer])
async def upload_churn(file: UploadFile):
    content = await file.read()
    try:
        customers = parse_churn_file(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc

    if not customers:
        raise HTTPException(status_code=400, detail="No customer rows found in file.")

    return [score_churn_customer(c) for c in customers]
