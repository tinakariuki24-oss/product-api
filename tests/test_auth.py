import pytest

def test_404_error_handler(client):
    """Test response status code for non-existent routes."""
    response = client.get("/non-existent-route")
    assert response.status_code == 404

def test_validation_error_handler(client):
    """Test response status code for invalid payload formats."""
    response = client.post("/products", json={"name": "Invalid Product"})
    assert response.status_code == 422