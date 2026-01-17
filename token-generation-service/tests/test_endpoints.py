"""
Basic tests for Token Generation Service endpoints
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.token_service.api.main import app
from src.token_service.core.database import Base, get_db
from src.token_service.models.database import Client, Token


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def test_db():
    """Create a test database"""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield SessionLocal()
    
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(test_db):
    """Create test client"""
    return TestClient(app)


class TestHealthCheck:
    """Test health check endpoint"""
    
    def test_health_check(self, client):
        """Test health check returns 200"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestClientCreation:
    """Test client registration endpoint"""
    
    def test_create_client_success(self, client):
        """Test successful client creation"""
        payload = {
            "client_id": "test-google-client-id",
            "client_secret": "test-google-secret",
            "redirect_uri": "http://localhost:8002/auth/callback",
            "branch_id": "uuid-branch-123",
            "workspace_email": "test@company.com",
            "workspace_name": "Test Workspace"
        }
        
        response = client.post("/clients", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["client_id"] == 1
        assert data["branch_identifier"] == "uuid-branch-123"
    
    def test_create_duplicate_client_id(self, client):
        """Test duplicate client_id returns 400"""
        payload = {
            "client_id": "test-google-client-id",
            "client_secret": "test-google-secret",
            "redirect_uri": "http://localhost:8002/auth/callback",
            "branch_id": "uuid-branch-123",
            "workspace_email": "test@company.com",
            "workspace_name": "Test Workspace"
        }
        
        # First creation should succeed
        client.post("/clients", json=payload)
        
        # Second with same client_id should fail
        payload["branch_id"] = "uuid-branch-456"
        response = client.post("/clients", json=payload)
        assert response.status_code == 400
