"""
Tests for Token Service
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.token_service.core.database import Base
from src.token_service.models.database import Client, Branch, Token, OAuthState
from src.token_service.services.client_service import client_service, branch_service
from src.token_service.services.token_service import token_service
from src.token_service.models.schemas import ClientCreate, BranchCreate


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create a test database session"""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_client_data():
    """Sample client data for testing"""
    return ClientCreate(
        client_id="test_client_id",
        client_secret="test_client_secret",
        redirect_uri="http://localhost:8002/auth/callback"
    )


@pytest.fixture
def sample_branch_data():
    """Sample branch data for testing"""
    return BranchCreate(
        branch_id="test_branch_001",
        client_id=1,
        branch_name="Test Branch",
        account_id="accounts/123",
        location_id="locations/456",
        email="test@example.com"
    )


class TestClientService:
    """Test client service operations"""
    
    def test_create_client(self, db_session, sample_client_data):
        """Test creating a new client"""
        client = client_service.create_client(db_session, sample_client_data)
        
        assert client.id is not None
        assert client.client_id == sample_client_data.client_id
        assert client.client_secret == sample_client_data.client_secret
        assert client.is_active is True
    
    def test_get_client_by_id(self, db_session, sample_client_data):
        """Test retrieving client by internal ID"""
        created_client = client_service.create_client(db_session, sample_client_data)
        
        retrieved_client = client_service.get_client_by_id(db_session, created_client.id)
        
        assert retrieved_client is not None
        assert retrieved_client.id == created_client.id
    
    def test_get_client_by_client_id(self, db_session, sample_client_data):
        """Test retrieving client by OAuth client_id"""
        created_client = client_service.create_client(db_session, sample_client_data)
        
        retrieved_client = client_service.get_client_by_client_id(
            db_session, 
            sample_client_data.client_id
        )
        
        assert retrieved_client is not None
        assert retrieved_client.client_id == sample_client_data.client_id
    
    def test_list_clients(self, db_session, sample_client_data):
        """Test listing clients"""
        client_service.create_client(db_session, sample_client_data)
        
        clients = client_service.list_clients(db_session)
        
        assert len(clients) >= 1
    
    def test_delete_client(self, db_session, sample_client_data):
        """Test deleting a client"""
        client = client_service.create_client(db_session, sample_client_data)
        
        success = client_service.delete_client(db_session, client.id)
        
        assert success is True
        assert client_service.get_client_by_id(db_session, client.id) is None


class TestBranchService:
    """Test branch service operations"""
    
    def test_create_branch(self, db_session, sample_client_data, sample_branch_data):
        """Test creating a new branch"""
        # Create client first
        client = client_service.create_client(db_session, sample_client_data)
        sample_branch_data.client_id = client.id
        
        branch = branch_service.create_branch(db_session, sample_branch_data)
        
        assert branch.id is not None
        assert branch.branch_id == sample_branch_data.branch_id
        assert branch.client_id == client.id
        assert branch.is_active is True
    
    def test_get_branch_by_branch_id(self, db_session, sample_client_data, sample_branch_data):
        """Test retrieving branch by branch_id"""
        client = client_service.create_client(db_session, sample_client_data)
        sample_branch_data.client_id = client.id
        
        created_branch = branch_service.create_branch(db_session, sample_branch_data)
        
        retrieved_branch = branch_service.get_branch_by_branch_id(
            db_session,
            sample_branch_data.branch_id
        )
        
        assert retrieved_branch is not None
        assert retrieved_branch.branch_id == sample_branch_data.branch_id
    
    def test_list_branches_by_client(self, db_session, sample_client_data, sample_branch_data):
        """Test listing branches for a specific client"""
        client = client_service.create_client(db_session, sample_client_data)
        sample_branch_data.client_id = client.id
        
        branch_service.create_branch(db_session, sample_branch_data)
        
        branches = branch_service.list_branches(db_session, client_id=client.id)
        
        assert len(branches) >= 1
        assert all(b.client_id == client.id for b in branches)


class TestTokenService:
    """Test token service operations"""
    
    def test_create_token(self, db_session, sample_client_data):
        """Test creating a new token"""
        client = client_service.create_client(db_session, sample_client_data)
        
        token = token_service.create_token(
            db=db_session,
            client_id=client.id,
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_in=3600,
            token_type="Bearer",
            scope="test_scope"
        )
        
        assert token.id is not None
        assert token.access_token == "test_access_token"
        assert token.refresh_token == "test_refresh_token"
        assert token.is_valid is True
        assert token.expires_at is not None
    
    def test_get_valid_token(self, db_session, sample_client_data):
        """Test retrieving valid token"""
        client = client_service.create_client(db_session, sample_client_data)
        
        created_token = token_service.create_token(
            db=db_session,
            client_id=client.id,
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_in=3600
        )
        
        retrieved_token = token_service.get_valid_token(db_session, client.id)
        
        assert retrieved_token is not None
        assert retrieved_token.id == created_token.id
        assert retrieved_token.is_valid is True
    
    def test_invalidate_client_tokens(self, db_session, sample_client_data):
        """Test invalidating all client tokens"""
        client = client_service.create_client(db_session, sample_client_data)
        
        token_service.create_token(
            db=db_session,
            client_id=client.id,
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_in=3600
        )
        
        count = token_service.invalidate_client_tokens(db_session, client.id)
        
        assert count >= 1
        
        valid_token = token_service.get_valid_token(db_session, client.id)
        assert valid_token is None
    
    def test_token_expiry_calculation(self):
        """Test token expiry calculation"""
        from src.token_service.services.oauth_service import oauth_service
        
        expires_in = 3600  # 1 hour
        expiry = oauth_service.calculate_expiry(expires_in)
        
        expected_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
        
        # Allow 2 seconds tolerance for test execution time
        assert abs((expiry - expected_expiry).total_seconds()) < 2
    
    def test_is_token_expiring_soon(self):
        """Test token expiry check"""
        from src.token_service.services.oauth_service import oauth_service
        
        # Token expiring in 2 minutes (less than 5-minute buffer)
        soon_expiry = datetime.utcnow() + timedelta(minutes=2)
        assert oauth_service.is_token_expiring_soon(soon_expiry) is True
        
        # Token expiring in 10 minutes (more than 5-minute buffer)
        later_expiry = datetime.utcnow() + timedelta(minutes=10)
        assert oauth_service.is_token_expiring_soon(later_expiry) is False
        
        # No expiry time
        assert oauth_service.is_token_expiring_soon(None) is True


class TestOAuthState:
    """Test OAuth state management"""
    
    def test_create_oauth_state(self, db_session, sample_client_data):
        """Test creating OAuth state"""
        client = client_service.create_client(db_session, sample_client_data)
        
        state = OAuthState(
            state="test_state_123",
            client_id=client.id,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        
        db_session.add(state)
        db_session.commit()
        
        assert state.id is not None
        assert state.is_used is False
    
    def test_oauth_state_expiry(self, db_session, sample_client_data):
        """Test OAuth state expiry check"""
        client = client_service.create_client(db_session, sample_client_data)
        
        # Create expired state
        expired_state = OAuthState(
            state="expired_state",
            client_id=client.id,
            expires_at=datetime.utcnow() - timedelta(minutes=1)
        )
        db_session.add(expired_state)
        db_session.commit()
        
        # Query for valid (non-expired) states
        valid_state = db_session.query(OAuthState).filter(
            OAuthState.state == "expired_state",
            OAuthState.expires_at > datetime.utcnow()
        ).first()
        
        assert valid_state is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
