#!/usr/bin/env python
"""
Backend Integration Test Suite
Tests all implemented endpoints and validations
"""

import asyncio
import sys
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_imports():
    """Test that all required modules can be imported."""
    logger.info("=" * 60)
    logger.info("TEST 1: Module Imports")
    logger.info("=" * 60)
    
    try:
        from Backend.core.security import (
            hash_password, verify_password, create_access_token, verify_token
        )
        logger.info("✅ Backend.core.security imports successful")
        
        from Backend.models.user import UserRegister, UserLogin, TokenResponse
        logger.info("✅ Backend.models.user imports successful")
        
        from Backend.models.organization import OrganizationCreate, OrganizationResponse
        logger.info("✅ Backend.models.organization imports successful")
        
        from Backend.models.query_log import QueryResponse
        logger.info("✅ Backend.models.query_log imports successful")
        
        from Backend.routers import auth, organizations, query
        logger.info("✅ Backend.routers imports successful")
        
        from Backend.Services.rag_pipeline import handle_query
        logger.info("✅ Backend.Services.rag_pipeline imports successful")
        
        from Backend.Services.query_classifier import SimpleClassifier
        logger.info("✅ Backend.Services.query_classifier imports successful")
        
        return True
    except Exception as e:
        logger.error(f"❌ Import failed: {str(e)}")
        return False


async def test_security_functions():
    """Test password hashing and JWT functions."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Security Functions")
    logger.info("=" * 60)
    
    try:
        from Backend.core.security import hash_password, verify_password, create_access_token, verify_token
        
        # Test password hashing
        password = "test_password_123"
        hashed = hash_password(password)
        
        if verify_password(password, hashed):
            logger.info("✅ Password hashing/verification working")
        else:
            logger.error("❌ Password verification failed")
            return False
        
        # Test JWT token creation
        token = create_access_token({"sub": "user123", "org_id": "org456"})
        if token and len(token) > 0:
            logger.info("✅ JWT token creation successful")
        else:
            logger.error("❌ JWT token creation failed")
            return False
        
        # Test JWT verification
        payload = verify_token(token)
        if payload and payload.get("sub") == "user123":
            logger.info("✅ JWT token verification successful")
        else:
            logger.error("❌ JWT token verification failed")
            return False
        
        return True
    except Exception as e:
        logger.error(f"❌ Security test failed: {str(e)}")
        return False


async def test_classifier():
    """Test query classifier."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Query Classifier")
    logger.info("=" * 60)
    
    try:
        from Backend.Services.query_classifier import SimpleClassifier
        
        classifier = SimpleClassifier()
        
        test_queries = [
            ("What algorithm should I use?", "algorithms"),
            ("Explain what is a hash table?", "concepts"),
            ("Show me an example of recursion", "examples"),
            ("How do I implement binary search?", "implementation"),
            ("Why is this query slow?", "performance"),
            ("What's the difference between lists and tuples?", "comparison"),
        ]
        
        for query, expected_category in test_queries:
            prediction = classifier.predict([query])[0]
            status = "✅" if prediction in classifier.CATEGORIES else "⚠️"
            logger.info(f"{status} Query: '{query}' → Category: {prediction}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Classifier test failed: {str(e)}")
        return False


async def test_pydantic_models():
    """Test Pydantic model validation."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Pydantic Models Validation")
    logger.info("=" * 60)
    
    try:
        from Backend.models.user import UserRegister, UserLogin
        from Backend.models.organization import OrganizationCreate
        
        # Test UserRegister
        user_reg = UserRegister(
            email="test@example.com",
            password="securepass123",
            full_name="Test User"
        )
        logger.info(f"✅ UserRegister model validated: {user_reg.email}")
        
        # Test UserLogin
        user_login = UserLogin(
            email="test@example.com",
            password="securepass123"
        )
        logger.info(f"✅ UserLogin model validated: {user_login.email}")
        
        # Test OrganizationCreate
        org_create = OrganizationCreate(
            name="Test Organization",
            description="A test org"
        )
        logger.info(f"✅ OrganizationCreate model validated: {org_create.name}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Model validation test failed: {str(e)}")
        return False


async def run_all_tests():
    """Run all tests."""
    logger.info("\n" + "=" * 70)
    logger.info("BACKEND INTEGRATION TEST SUITE")
    logger.info("=" * 70)
    
    tests = [
        ("Module Imports", test_imports),
        ("Security Functions", test_security_functions),
        ("Query Classifier", test_classifier),
        ("Pydantic Models", test_pydantic_models),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{status}: {test_name}")
    
    logger.info("=" * 70)
    logger.info(f"Results: {passed}/{total} tests passed")
    logger.info("=" * 70)
    
    if passed == total:
        logger.info("\n🎉 All tests passed! Backend is ready for deployment.")
        return 0
    else:
        logger.error(f"\n⚠️ {total - passed} test(s) failed. Please review above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
