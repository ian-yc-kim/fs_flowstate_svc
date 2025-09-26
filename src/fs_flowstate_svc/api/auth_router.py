"""FastAPI authentication endpoints for user registration, login, and password reset."""

import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from fs_flowstate_svc.models.base import get_db
from fs_flowstate_svc.schemas import user_schemas
from fs_flowstate_svc.services import user_service

logger = logging.getLogger(__name__)

# Create auth router
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

# Security scheme for bearer token
security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """FastAPI dependency to get current user from JWT token.
    
    Args:
        credentials: HTTP Bearer token credentials
        db: Database session
        
    Returns:
        Current user object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    return user_service.get_current_user(db, credentials.credentials)


@auth_router.post("/register", response_model=user_schemas.UserResponse)
def register(user: user_schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user.
    
    Args:
        user: User registration data
        db: Database session
        
    Returns:
        User response with user details
        
    Raises:
        HTTPException: If username or email already exists
    """
    try:
        created_user = user_service.create_user(db, user)
        return user_schemas.UserResponse.model_validate(created_user)
    except ValueError as e:
        logger.error(f"User registration failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists"
        )
    except Exception as e:
        logger.error(f"Unexpected error during user registration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@auth_router.post("/login", response_model=user_schemas.Token)
def login(user: user_schemas.UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return access token.
    
    Args:
        user: User login credentials
        db: Database session
        
    Returns:
        Access token on successful authentication
        
    Raises:
        HTTPException: If credentials are invalid
    """
    try:
        token = user_service.login_for_access_token(db, user.username_or_email, user.password)
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )
        return token
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@auth_router.get("/me", response_model=user_schemas.UserResponse)
def get_current_user_info(current_user=Depends(get_current_user)):
    """Get information about the current authenticated user.
    
    Args:
        current_user: Current authenticated user (injected dependency)
        
    Returns:
        Current user information
    """
    return user_schemas.UserResponse.model_validate(current_user)


@auth_router.post("/request-password-reset")
def request_password_reset(request: user_schemas.PasswordResetRequest, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Request password reset for a user email.
    
    Args:
        request: Password reset request with email
        db: Database session
        
    Returns:
        Generic success message to prevent email enumeration
    """
    try:
        user_service.generate_password_reset_token(db, request.email)
        # Always return generic message to prevent email enumeration
        return {"message": "If a user with that email exists, a password reset link has been sent."}
    except Exception as e:
        logger.error(f"Error during password reset request: {e}", exc_info=True)
        # Still return generic message even on error to prevent information disclosure
        return {"message": "If a user with that email exists, a password reset link has been sent."}


@auth_router.post("/reset-password")
def reset_password(request: user_schemas.PasswordResetConfirm, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Reset user password using reset token.
    
    Args:
        request: Password reset confirmation with token and new password
        db: Database session
        
    Returns:
        Success message if password was reset
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        success = user_service.reset_user_password(db, request.token, request.new_password)
        if success:
            return {"message": "Password has been reset successfully."}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset token"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during password reset: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
