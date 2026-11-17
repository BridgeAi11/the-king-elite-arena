
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_db, require_admin
from app.refund_service import process_refund, check_refund_status


router = APIRouter(
    prefix="/api/admin/refunds",
    tags=["Admin Refunds"],
)


@router.post("/{refund_id}/process")
def admin_process_refund(
    refund_id: int,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    result = process_refund(refund_id, db)
    status = result["status"]

    if status == "not_found":
        raise HTTPException(404, "Refund not found.")

    if status in (
        "payment_not_confirmed",
        "missing_payment_id",
        "invalid_refund_amount",
        "missing_idempotency_key",
    ):
        raise HTTPException(409, result.get("message", status))

    if status == "credentials_not_configured":
        raise HTTPException(503, "Razorpay credentials are not configured.")

    if status == "failed":
        raise HTTPException(502, result.get("message", "Refund processing failed."))

    if status == "pending":
        return {
            **result,
            "message": result.get(
                "message",
                "Refund is pending. Check its status before retrying.",
            ),
        }

    return result


@router.get("/{refund_id}/status")
def admin_check_refund_status(
    refund_id: int,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    result = check_refund_status(refund_id, db)
    status = result["status"]

    if status == "not_found":
        raise HTTPException(404, "Refund not found.")

    if status == "payment_not_confirmed":
        raise HTTPException(409, "Payment is not confirmed.")

    if status == "credentials_not_configured":
        raise HTTPException(503, "Razorpay credentials are not configured.")

    if status == "invalid_refund_amount":
        raise HTTPException(409, result.get("message", status))

    return result
