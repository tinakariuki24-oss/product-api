import logging
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Request, status, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy.exc import IntegrityError

from models import (
    Product, ProductCreate, ProductRead,
    Supplier, SupplierCreate, SupplierRead,
    StockAdjustment, ALLOWED_CATEGORIES
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TechVault")

sqlite_url = "sqlite:///techvault.db"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

app = FastAPI(title="TechVault Inventory API", version="1.0.0")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# ============================================================
# EXERCISE 5: GLOBAL EXCEPTION HANDLERS
# ============================================================

def make_error_response(status_code: int, message: str, path: str, errors: Optional[list] = None):
    payload = {
        "success": False,
        "status_code": status_code,
        "message": message,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "path": path
    }
    if errors is not None:
        payload["errors"] = errors
    return JSONResponse(status_code=status_code, content=payload)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP Exception: {exc.detail} on path {request.url.path}")
    return make_error_response(
        status_code=exc.status_code,
        message=str(exc.detail),
        path=request.url.path
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    formatted_errors = []
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        formatted_errors.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"]
        })
    return make_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message="Validation failed for incoming request body/parameters.",
        path=request.url.path,
        errors=formatted_errors
    )

@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.error(f"Integrity Error: {exc}")
    err_msg = "Database integrity constraint violated (e.g., duplicate SKU, Email, or missing Foreign Key)."
    if "UNIQUE constraint failed" in str(exc):
        err_msg = "Duplicate entry detected. A record with this unique field already exists."
    elif "FOREIGN KEY constraint failed" in str(exc):
        err_msg = "Invalid foreign key reference. The specified relation ID does not exist."
        
    return make_error_response(
        status_code=status.HTTP_409_CONFLICT,
        message=err_msg,
        path=request.url.path
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled Server Error: {exc}", exc_info=True)
    return make_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="An unexpected internal server error occurred.",
        path=request.url.path
    )

# ============================================================
# API ENDPOINTS
# ============================================================

# Supplier Endpoint
@app.post("/suppliers", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(supplier: SupplierCreate, session: Session = Depends(get_session)):
    db_supplier = Supplier.from_orm(supplier)
    session.add(db_supplier)
    session.commit()
    session.refresh(db_supplier)
    return db_supplier

# Product Endpoint
@app.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(product: ProductCreate, session: Session = Depends(get_session)):
    if product.supplier_id:
        supplier = session.get(Supplier, product.supplier_id)
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supplier with ID {product.supplier_id} not found."
            )
    
    db_product = Product.from_orm(product)
    session.add(db_product)
    session.commit()
    session.refresh(db_product)
    return db_product

# Exercise 3: Bulk Update Endpoint
@app.patch("/products/bulk-update")
def bulk_update_price(
    category: str,
    discount_percent: float = Query(..., gt=0, le=100, description="Discount percentage between 0 and 100"),
    session: Session = Depends(get_session)
):
    key = category.strip().lower()
    if key not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category '{category}'.")
    std_category = ALLOWED_CATEGORIES[key][0]

    products = session.exec(select(Product).where(Product.category == std_category)).all()
    if not products:
        raise HTTPException(status_code=404, detail=f"No products found in category '{std_category}'.")

    updated_count = 0
    skipped_count = 0
    details = []

    for prod in products:
        discount_amount = prod.price * (discount_percent / 100.0)
        new_price = round(prod.price - discount_amount, 2)

        if new_price < 100:
            skipped_count += 1
            details.append({
                "product_id": prod.id,
                "sku": prod.sku,
                "status": "SKIPPED",
                "reason": f"New price ({new_price} KSh) falls below min price of 100 KSh."
            })
        else:
            prod.price = new_price
            prod.updated_at = datetime.utcnow()
            session.add(prod)
            updated_count += 1
            details.append({
                "product_id": prod.id,
                "sku": prod.sku,
                "status": "UPDATED",
                "new_price": new_price
            })

    session.commit()
    logger.info(f"Bulk discount applied: Category='{std_category}', Updated={updated_count}, Skipped={skipped_count}")

    return {
        "category": std_category,
        "discount_percent": discount_percent,
        "total_found": len(products),
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "details": details
    }

# Exercise 4: Stock Adjustment Endpoint
@app.patch("/products/adjust-stock")
def adjust_stock(
    adjustments: List[StockAdjustment],
    session: Session = Depends(get_session)
):
    successful_updates = []
    failed_updates = []

    for adj in adjustments:
        product = session.get(Product, adj.product_id)
        if not product:
            failed_updates.append({
                "product_id": adj.product_id,
                "reason": "Product ID not found"
            })
            continue

        new_stock = product.stock + adj.quantity_to_add
        if new_stock > 5000:
            failed_updates.append({
                "product_id": adj.product_id,
                "current_stock": product.stock,
                "attempted_add": adj.quantity_to_add,
                "reason": f"Resulting stock ({new_stock}) exceeds maximum cap of 5,000 units."
            })
            continue

        product.stock = new_stock
        product.updated_at = datetime.utcnow()
        session.add(product)
        successful_updates.append({
            "product_id": product.id,
            "sku": product.sku,
            "previous_stock": product.stock - adj.quantity_to_add,
            "new_stock": product.stock
        })

    session.commit()

    return {
        "processed": len(adjustments),
        "successful_count": len(successful_updates),
        "failed_count": len(failed_updates),
        "successful_updates": successful_updates,
        "failed_updates": failed_updates
    }