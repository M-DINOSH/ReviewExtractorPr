#!/usr/bin/env python3
"""
Test unified token management database (single DB, two tables: clients + tokens)
Verifies FK relationship and CRUD operations
"""
import sys
import os
from datetime import datetime, timedelta

# Add app to path
sys.path.insert(0, '.')

from sqlalchemy import inspect, text
from app.token_management.database import get_db, Base, engine
from app.token_management.models import Client, Token


def test_unified_db():
    """Test unified database with clients and tokens tables"""
    print("\n" + "="*80)
    print("TESTING UNIFIED TOKEN MANAGEMENT DATABASE")
    print("="*80)
    
    # 1. Verify tables exist
    print("\n1. Checking tables in database...")
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"   ✓ Tables found: {sorted(tables)}")
    
    required_tables = {'clients', 'tokens', 'alembic_version'}
    if not required_tables.issubset(set(tables)):
        print(f"   ✗ Missing tables: {required_tables - set(tables)}")
        return False
    print(f"   ✓ All required tables present")
    
    # 2. Create test client
    print("\n2. Testing CLIENT insert...")
    db = next(get_db())
    try:
        client = Client(
            client_id="test-client-001",
            client_secret="test-secret-xyz",
            redirect_uri="https://example.com/callback",
            branch_id="branch-test-123",
            workspace_email="test@example.com",
            workspace_name="Test Workspace",
            is_active=True,
        )
        db.add(client)
        db.commit()
        db.refresh(client)
        print(f"   ✓ Client created: id={client.id}, client_id={client.client_id}, branch_id={client.branch_id}")
        client_id = client.id
    except Exception as e:
        print(f"   ✗ Failed to create client: {e}")
        db.rollback()
        return False
    finally:
        db.close()
    
    # 3. Create test token
    print("\n3. Testing TOKEN insert (with FK to client)...")
    db = next(get_db())
    try:
        expires_at = datetime.utcnow() + timedelta(hours=1)
        token = Token(
            client_id=client_id,
            access_token="ya29.test-access-token-xyz",
            refresh_token="1//test-refresh-token-abc",
            token_type="Bearer",
            scope="https://www.googleapis.com/auth/business.manage",
            expires_at=expires_at,
            is_valid=True,
            is_revoked=False,
        )
        db.add(token)
        db.commit()
        db.refresh(token)
        print(f"   ✓ Token created: id={token.id}, client_id={token.client_id}")
        print(f"     - access_token: {token.access_token[:20]}...")
        print(f"     - expires_at: {token.expires_at}")
        token_id = token.id
    except Exception as e:
        print(f"   ✗ Failed to create token: {e}")
        db.rollback()
        return False
    finally:
        db.close()
    
    # 4. Read client with relationship
    print("\n4. Testing CLIENT read with relationship...")
    db = next(get_db())
    try:
        fetched_client = db.query(Client).filter(Client.id == client_id).first()
        if not fetched_client:
            print(f"   ✗ Client not found by id={client_id}")
            return False
        print(f"   ✓ Client found: {fetched_client.client_id}")
        print(f"     - branch_id: {fetched_client.branch_id}")
        print(f"     - workspace_name: {fetched_client.workspace_name}")
        print(f"     - tokens relationship: {len(fetched_client.tokens)} token(s)")
        
        if len(fetched_client.tokens) > 0:
            print(f"   ✓ FK relationship works! Token linked to client:")
            for t in fetched_client.tokens:
                print(f"     - Token id={t.id}, valid={t.is_valid}")
        else:
            print(f"   ✗ No tokens found in relationship")
            return False
    except Exception as e:
        print(f"   ✗ Failed to read client: {e}")
        db.rollback()
        return False
    finally:
        db.close()
    
    # 5. Read token with client relationship
    print("\n5. Testing TOKEN read with client relationship...")
    db = next(get_db())
    try:
        fetched_token = db.query(Token).filter(Token.id == token_id).first()
        if not fetched_token:
            print(f"   ✗ Token not found by id={token_id}")
            return False
        print(f"   ✓ Token found: id={fetched_token.id}")
        print(f"     - client_id: {fetched_token.client_id}")
        print(f"     - is_valid: {fetched_token.is_valid}")
        
        if fetched_token.client:
            print(f"   ✓ Reverse FK relationship works! Client:")
            print(f"     - client_id: {fetched_token.client.client_id}")
            print(f"     - branch_id: {fetched_token.client.branch_id}")
        else:
            print(f"   ✗ Client not found in token relationship")
            return False
    except Exception as e:
        print(f"   ✗ Failed to read token: {e}")
        db.rollback()
        return False
    finally:
        db.close()
    
    # 6. Update token
    print("\n6. Testing TOKEN update...")
    db = next(get_db())
    try:
        token_to_update = db.query(Token).filter(Token.id == token_id).first()
        token_to_update.is_valid = False
        db.commit()
        print(f"   ✓ Token updated: is_valid={token_to_update.is_valid}")
    except Exception as e:
        print(f"   ✗ Failed to update token: {e}")
        db.rollback()
        return False
    finally:
        db.close()
    
    # 7. Query with FK filter
    print("\n7. Testing query with FK filter...")
    db = next(get_db())
    try:
        valid_tokens = db.query(Token).filter(
            Token.client_id == client_id,
            Token.is_valid == True
        ).all()
        print(f"   ✓ Query returned: {len(valid_tokens)} valid token(s) for client_id={client_id}")
        
        # Should be 0 now since we set is_valid=False
        if len(valid_tokens) == 0:
            print(f"   ✓ Correct: Token is no longer valid")
        else:
            print(f"   ⚠ Expected 0 valid tokens, found {len(valid_tokens)}")
    except Exception as e:
        print(f"   ✗ Failed to query tokens: {e}")
        db.rollback()
        return False
    finally:
        db.close()
    
    # 8. Cleanup - delete token and client
    print("\n8. Testing CASCADE delete (delete client, tokens should auto-delete)...")
    db = next(get_db())
    try:
        client_to_delete = db.query(Client).filter(Client.id == client_id).first()
        db.delete(client_to_delete)
        db.commit()
        print(f"   ✓ Client deleted")
        
        # Check if tokens are also deleted (CASCADE)
        remaining_tokens = db.query(Token).filter(Token.client_id == client_id).all()
        if len(remaining_tokens) == 0:
            print(f"   ✓ CASCADE delete works! All tokens for this client removed")
        else:
            print(f"   ✗ Expected 0 tokens, found {len(remaining_tokens)}")
            return False
    except Exception as e:
        print(f"   ✗ Failed to delete: {e}")
        db.rollback()
        return False
    finally:
        db.close()
    
    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED - Unified DB with FK relationships works perfectly!")
    print("="*80 + "\n")
    return True


if __name__ == "__main__":
    try:
        success = test_unified_db()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
