import re
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from pydantic import field_validator, ValidationInfo, EmailStr

# Standardized Allowed Brands
ALLOWED_BRANDS = {
    "HP": "HP", "DELL": "Dell", "LENOVO": "Lenovo", "APPLE": "Apple",
    "SAMSUNG": "Samsung", "INTEL": "Intel", "AMD": "AMD",
    "CORSAIR": "Corsair", "LOGITECH": "Logitech", "OTHER": "Other"
}

# Standardized Allowed Categories & SKU Prefixes
ALLOWED_CATEGORIES = {
    "laptops": ("Laptops", "LAP"),
    "monitors": ("Monitors", "MON"),
    "storage": ("Storage", "STO"),
    "processors": ("Processors", "PRO"),
    "memory": ("Memory", "MEM"),
    "keyboards": ("Keyboards", "KEY"),
    "mice": ("Mice", "MOU"),
    "accessories": ("Accessories", "ACC")
}

# ==========================================
# EXERCISE 2: SUPPLIER MODELS
# ==========================================

class SupplierBase(SQLModel):
    name: str = Field(unique=True, index=True)
    contact_person: str
    email: EmailStr = Field(unique=True)
    phone: str
    is_active: bool = Field(default=True)

    @field_validator("phone")
    def validate_phone(cls, v: str) -> str:
        pattern = r"^(?:\+254|0)?(7|1)\d{8}$"
        clean_phone = v.replace(" ", "").replace("-", "")
        if not re.match(pattern, clean_phone):
            raise ValueError("Invalid phone number format. Expected Kenyan format (e.g., +254712345678 or 0712345678).")
        return clean_phone

class Supplier(SupplierBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    products: List["Product"] = Relationship(back_populates="supplier")

class SupplierCreate(SupplierBase):
    pass

class SupplierRead(SupplierBase):
    id: int

# ==========================================
# EXERCISE 1: PRODUCT MODELS & VALIDATIONS
# ==========================================

class ProductBase(SQLModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=10, max_length=500)
    brand: str = Field(index=True)
    category: str = Field(index=True)
    price: float = Field(gt=0)
    stock: int = Field(ge=0, le=10000)
    warranty_months: int = Field(ge=0)
    sku: str = Field(unique=True, index=True)
    supplier_id: Optional[int] = Field(default=None, foreign_key="supplier.id")

    @field_validator("name")
    def validate_name(cls, v: str) -> str:
        if not v[0].isupper():
            raise ValueError("Product name must start with a capital letter.")
        if re.search(r'[^a-zA-Z0-9\s\-]', v):
            raise ValueError("Product name can only contain alphanumeric characters, spaces, and hyphens.")
        if not v.strip():
            raise ValueError("Product name must contain at least one valid word.")
        return v

    @field_validator("brand")
    def validate_brand(cls, v: str) -> str:
        key = v.strip().upper()
        if key in ALLOWED_BRANDS:
            return ALLOWED_BRANDS[key]
        raise ValueError(f"Brand '{v}' is not allowed. Choose from: {list(ALLOWED_BRANDS.values())}")

    @field_validator("category")
    def validate_category(cls, v: str) -> str:
        key = v.strip().lower()
        if key in ALLOWED_CATEGORIES:
            return ALLOWED_CATEGORIES[key][0]
        valid_cats = [cat[0] for cat in ALLOWED_CATEGORIES.values()]
        raise ValueError(f"Category '{v}' is invalid. Allowed categories: {valid_cats}")

    @field_validator("price")
    def validate_price(cls, v: float) -> float:
        if v < 100:
            raise ValueError("Price cannot be less than 100 KSh.")
        if v > 500000:
            raise ValueError("Price cannot exceed 500,000 KSh.")
        if round(v, 2) != v:
            raise ValueError("Price must have at most 2 decimal places.")
        return round(v, 2)

    @field_validator("sku")
    def validate_sku(cls, v: str, info: ValidationInfo) -> str:
        pattern = r"^[A-Z]{3,4}-[A-Z]{2,4}-[0-9]{4}$"
        if not re.match(pattern, v):
            raise ValueError("SKU must match format CAT-BRAND-XXXX (e.g., LAP-DEL-0001).")
        
        cat_abbr = v.split("-")[0]
        valid_abbrs = [item[1] for item in ALLOWED_CATEGORIES.values()]
        if cat_abbr not in valid_abbrs:
            raise ValueError(f"Invalid category abbreviation in SKU. Allowed: {valid_abbrs}")
        return v

    @field_validator("warranty_months")
    def validate_warranty(cls, v: int, info: ValidationInfo) -> int:
        if v < 0 or v > 36:
            raise ValueError("Warranty must be between 0 and 36 months.")
        
        price = info.data.get("price")
        if price and price > 50000 and v < 12:
            raise ValueError("Products priced above 50,000 KSh must have at least 12 months warranty.")
        return v

class Product(ProductBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    supplier: Optional[Supplier] = Relationship(back_populates="products")

class ProductCreate(ProductBase):
    pass

class ProductRead(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime

# DTO for Exercise 4
class StockAdjustment(SQLModel):
    product_id: int
    quantity_to_add: int = Field(gt=0, description="Quantity must be greater than zero")