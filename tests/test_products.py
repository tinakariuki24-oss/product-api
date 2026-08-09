import pytest

def test_create_supplier(client):
    """Test creating a supplier with all required schema fields."""
    supplier_data = {
        "name": "Tech Supplier Ltd",
        "contact_person": "Jane Doe",
        "email": "contact@techsupplier.com",
        "contact_email": "contact@techsupplier.com",
        "phone": "+254700000000"
    }
    response = client.post("/suppliers", json=supplier_data)
    assert response.status_code in [200, 201]

def test_create_product(client):
    """Test creating a product with allowed brand, category, and matching SKU."""
    # 1. Create supplier first to get a valid foreign key
    sup_response = client.post("/suppliers", json={
        "name": "Main Supplier",
        "contact_person": "John Smith",
        "email": "supplier@example.com",
        "contact_email": "supplier@example.com",
        "phone": "+254711111111"
    })
    
    assert sup_response.status_code in [200, 201]
    supplier_id = sup_response.json().get("id") or sup_response.json().get("data", {}).get("id", 1)

    # 2. Use allowed brand ('Dell') and category ('Laptops')
    product_data = {
        "name": "Gaming Laptop",
        "description": "High performance gaming laptop",
        "brand": "Dell",
        "category": "Laptops",
        "sku": "LAP-DEL-0001",
        "price": 120000.0,
        "stock": 15,
        "warranty_months": 12,
        "supplier_id": supplier_id
    }
    response = client.post("/products", json=product_data)

    assert response.status_code in [200, 201]

def test_health_check(client):
    """Test the Lab 10 monitoring endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"