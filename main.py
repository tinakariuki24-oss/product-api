from contextlib import asynccontextmanager
from datetime import datetime, timezone
import time
import logging
from typing import List, Optional, Generator

from fastapi import FastAPI, HTTPException, Request, status, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from sqlmodel import Field as SQLField, Session, SQLModel, create_engine, select

# Logging Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TechVault")

# Database Configuration
DATABASE_URL = "sqlite:///./techvault.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


# Database Dependency for FastAPI and Testing
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


# Database Models
class Supplier(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    name: str
    contact_person: str
    email: str
    contact_email: str
    phone: str


class Product(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    name: str
    description: str
    brand: str
    category: str
    sku: str
    price: float
    stock: int
    warranty_months: int
    supplier_id: Optional[int] = SQLField(default=None, foreign_key="supplier.id")


# Pydantic Request Schemas
class SupplierCreate(BaseModel):
    name: str
    contact_person: str
    email: str
    contact_email: str
    phone: str


class ProductCreate(BaseModel):
    name: str
    description: str
    brand: str
    category: str
    sku: str
    price: float
    stock: int
    warranty_months: int
    supplier_id: Optional[int] = None

    @field_validator("brand")
    @classmethod
    def validate_brand(cls, v: str) -> str:
        allowed = [
            "HP",
            "Dell",
            "Lenovo",
            "Apple",
            "Samsung",
            "Intel",
            "AMD",
            "Corsair",
            "Logitech",
            "Other",
        ]
        if v not in allowed:
            raise ValueError(
                f"Brand '{v}' is not allowed. Choose from: {allowed}"
            )
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = [
            "Laptops",
            "Monitors",
            "Storage",
            "Processors",
            "Memory",
            "Keyboards",
            "Mice",
            "Accessories",
        ]
        if v not in allowed:
            raise ValueError(
                f"Category '{v}' is invalid. Allowed categories: {allowed}"
            )
        return v

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, v: str) -> str:
        import re

        pattern = r"^[A-Z]{3}-[A-Z]{3,4}-\d{4}$"
        if not re.match(pattern, v):
            raise ValueError(
                "SKU must match format CAT-BRAND-XXXX (e.g., LAP-DEL-0001)."
            )
        return v


# Modern FastAPI Lifespan Handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="TechVault Product API", lifespan=lifespan)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - Status: {response.status_code} - {process_time:.3f}s"
    )
    return response


# Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "status_code": exc.status_code,
            "message": exc.detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": request.url.path,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    errors = []
    for error in exc.errors():
        field = error.get("loc", [])[-1] if error.get("loc") else "unknown"
        errors.append({"field": field, "message": error.get("msg")})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "status_code": 422,
            "message": "Validation failed for incoming request body/parameters.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": request.url.path,
            "errors": errors,
        },
    )


# API Endpoints
@app.post(
    "/suppliers", response_model=Supplier, status_code=status.HTTP_201_CREATED
)
def create_supplier(
    supplier: SupplierCreate, session: Session = Depends(get_session)
):
    db_supplier = Supplier.model_validate(supplier)
    session.add(db_supplier)
    session.commit()
    session.refresh(db_supplier)
    return db_supplier


@app.post(
    "/products", response_model=Product, status_code=status.HTTP_201_CREATED
)
def create_product(
    product: ProductCreate, session: Session = Depends(get_session)
):
    db_product = Product.model_validate(product)
    session.add(db_product)
    session.commit()
    session.refresh(db_product)
    return db_product


@app.get("/products", response_model=List[Product])
def get_products(session: Session = Depends(get_session)):
    return session.exec(select(Product)).all()


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }