from threading import Lock
from typing import Optional

from fastapi import Body, FastAPI, HTTPException, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI()

STATUSES = ["created", "in_transit", "delivered"]
deliveries = {}
next_id = 1
lock = Lock()


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request, exc):
    return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    return JSONResponse({"error": "invalid request"}, status_code=400)


def get_or_404(delivery_id: int):
    if delivery_id not in deliveries:
        raise HTTPException(404, "delivery not found")
    return deliveries[delivery_id]


def non_empty_string(value):
    return isinstance(value, str) and value.strip() != ""


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/deliveries", status_code=201)
def create_delivery(data: dict = Body(...)):
    global next_id
    recipient = data.get("recipient")
    address = data.get("address")
    if not non_empty_string(recipient) or not non_empty_string(address):
        raise HTTPException(400, "recipient and address must be non-empty strings")
    with lock:
        delivery = {
            "id": next_id,
            "recipient": recipient,
            "address": address,
            "status": "created",
        }
        deliveries[next_id] = delivery
        next_id += 1
    return delivery


@app.get("/deliveries")
def list_deliveries(status: Optional[str] = None):
    if status is not None and status not in STATUSES:
        raise HTTPException(400, "unknown status")
    return [d for d in deliveries.values() if status is None or d["status"] == status]


@app.get("/deliveries/{delivery_id}")
def get_delivery(delivery_id: int):
    return get_or_404(delivery_id)


@app.patch("/deliveries/{delivery_id}/status")
def update_status(delivery_id: int, data: dict = Body(...)):
    delivery = get_or_404(delivery_id)
    new_status = data.get("status")
    if new_status not in STATUSES:
        raise HTTPException(400, "unknown status")
    if STATUSES.index(new_status) != STATUSES.index(delivery["status"]) + 1:
        raise HTTPException(409, "invalid status transition")
    delivery["status"] = new_status
    return delivery


@app.delete("/deliveries/{delivery_id}")
def delete_delivery(delivery_id: int):
    delivery = get_or_404(delivery_id)
    if delivery["status"] != "created":
        raise HTTPException(409, "only created deliveries can be deleted")
    del deliveries[delivery_id]
    return Response(status_code=204)