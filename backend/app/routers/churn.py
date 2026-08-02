"""Churn-risk scoring for customer/subscriber exports -- a separate,
free-to-test capability from the licensed lead-scoring product
(routers/leads.py), since it's a different data shape (individual
subscribers, not B2B companies) and not the thing this product is sold as.
No license gating here.
"""

from fastapi import APIRouter, HTTPException, Request, UploadFile

from ..config import RATE_LIMIT_UPLOAD
from ..middleware import limiter
from ..models import ChurnScoredCustomer
from ..services.churn_scoring import parse_churn_file, score_churn_customer
from ..services.upload_validation import enforce_row_cap, validate_upload_file

router = APIRouter(prefix="/api/churn", tags=["churn"])


# No license gating on this endpoint (see module docstring), so the rate
# limit below is this endpoint's only real defense against abuse.
@router.post("/upload", response_model=list[ChurnScoredCustomer])
@limiter.limit(RATE_LIMIT_UPLOAD)
async def upload_churn(request: Request, file: UploadFile):
    content = await file.read()
    validate_upload_file(file.filename, content)
    try:
        customers = parse_churn_file(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc

    if not customers:
        raise HTTPException(status_code=400, detail="No customer rows found in file.")
    enforce_row_cap(len(customers))

    return [score_churn_customer(c) for c in customers]
