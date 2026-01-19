#!/usr/bin/env python3
"""Test token management integration"""
import sys
sys.path.insert(0, '.')

def test_imports():
    """Test all imports"""
    print("\n" + "=" * 70)
    print("TESTING TOKEN MANAGEMENT INTEGRATION")
    print("=" * 70)
    
    results = []
    
    # Test models
    try:
        from app.token_management.models import Client, Token
        print("✓ Models (Client, Token) imported")
        results.append(True)
    except Exception as e:
        print(f"✗ Models import failed: {e}")
        results.append(False)
    
    # Test schemas
    try:
        from app.token_management.models import schemas
        print("✓ Schemas imported")
        results.append(True)
    except Exception as e:
        print(f"✗ Schemas import failed: {e}")
        results.append(False)
    
    # Test database config
    try:
        from app.token_management.database.config import engine, get_db, DATABASE_URL
        print("✓ Database config imported (unified)")
        print(f"  Token Management DB URL: {DATABASE_URL}")
        results.append(True)
    except Exception as e:
        print(f"✗ Database config import failed: {e}")
        results.append(False)
    
    # Test services
    try:
        from app.token_management.services import oauth_service, client_service, token_service
        print("✓ Services imported (oauth, client, token)")
        results.append(True)
    except Exception as e:
        print(f"✗ Services import failed: {e}")
        results.append(False)
    
    # Test routes
    try:
        from app.token_management.routes import token_router
        print("✓ Routes imported (token_router)")
        print(f"  Routes count: {len(token_router.routes)}")
        for route in token_router.routes:
            print(f"    - {route.methods} {route.path}")
        results.append(True)
    except Exception as e:
        print(f"✗ Routes import failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)
    
    # Test main app
    try:
        from main import app
        print("✓ Main app imported (root-level)")
        results.append(True)
    except Exception as e:
        print(f"✗ Main app import failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)
    
    print("=" * 70)
    if all(results):
        print("✅ ALL TESTS PASSED - Token management integration is working!")
    else:
        print(f"❌ SOME TESTS FAILED - {results.count(False)} out of {len(results)}")
    print("=" * 70 + "\n")
    
    return all(results)

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
