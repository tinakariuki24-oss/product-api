import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from main import app, get_session  # Imported get_session directly from main

TEST_DATABASE_URL = "sqlite:///./test.db"

@pytest.fixture
def client():
    """Create a clean, isolated SQLite database for each test run."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    
    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    yield TestClient(app)
    
    SQLModel.metadata.drop_all(engine)
    app.dependency_overrides.clear()

@pytest.fixture
def test_user():
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123",
        "full_name": "Test User"
    }

@pytest.fixture
def auth_headers(client, test_user):
    """Register, login, and return auth headers."""
    client.post("/register", json=test_user)
    response = client.post(
        "/login",
        data={"username": test_user["username"], "password": test_user["password"]}
    )
    token = response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}