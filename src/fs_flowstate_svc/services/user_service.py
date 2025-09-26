"""User service logic for authentication, CRUD operations, and password reset."""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fs_flowstate_svc.auth import security, jwt_handler
from fs_flowstate_svc.models.flowstate_models import Users
from fs_flowstate_svc.schemas import user_schemas

logger = logging.getLogger(__name__)


def get_user_by_username_or_email(db: Session, identifier: str) -> Optional[Users]:
    """Fetch user by username or email.
    
    Args:
        db: Database session
        identifier: Username or email to search for
        
    Returns:
        User object if found, None otherwise
    """
    try:
        stmt = select(Users).where(
            or_(Users.username == identifier, Users.email == identifier)
        )
        result = db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error fetching user by username or email: {e}", exc_info=True)
        raise


def create_user(db: Session, user: user_schemas.UserCreate) -> Users:
    """Create a new user with hashed password.
    
    Args:
        db: Database session
        user: User creation data
        
    Returns:
        Created user object
        
    Raises:
        ValueError: If username or email already exists
    """
    try:
        # Hash the password
        hashed_password = security.hash_password(user.password)
        
        # Create new user instance
        db_user = Users(
            username=user.username,
            email=user.email,
            password_hash=hashed_password
        )
        
        # Add to database
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        return db_user
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating user: {e}", exc_info=True)
        raise ValueError("Username or email already exists")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {e}", exc_info=True)
        raise


def update_user(db: Session, user_id: uuid.UUID, user_update: user_schemas.UserUpdate) -> Users:
    """Update user profile information.
    
    Args:
        db: Database session
        user_id: UUID of the user to update
        user_update: User update data
        
    Returns:
        Updated user object
        
    Raises:
        HTTPException: If user not found
        ValueError: If username or email already exists
    """
    try:
        # Fetch user by ID
        stmt = select(Users).where(Users.id == user_id)
        result = db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        
        changed = False
        
        # Update username if provided and different
        if user_update.username is not None and user_update.username != user.username:
            user.username = user_update.username
            try:
                db.commit()
                changed = True
            except IntegrityError as e:
                db.rollback()
                logger.error(f"Integrity error updating username: {e}", exc_info=True)
                raise ValueError("Username already exists")
        
        # Update email if provided and different
        if user_update.email is not None and user_update.email != user.email:
            user.email = user_update.email
            try:
                db.commit()
                changed = True
            except IntegrityError as e:
                db.rollback()
                logger.error(f"Integrity error updating email: {e}", exc_info=True)
                raise ValueError("Email already exists")
        
        # Refresh user object to reflect any onupdate changes
        if changed:
            db.refresh(user)
        
        return user
        
    except HTTPException:
        raise
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {e}", exc_info=True)
        raise


def authenticate_user(db: Session, identifier: str, password: str) -> Optional[Users]:
    """Authenticate user by username/email and password.
    
    Args:
        db: Database session
        identifier: Username or email
        password: Plain text password
        
    Returns:
        User object if authenticated, None otherwise
    """
    try:
        user = get_user_by_username_or_email(db, identifier)
        if not user:
            return None
            
        if not security.verify_password(password, user.password_hash):
            return None
            
        return user
    except Exception as e:
        logger.error(f"Error authenticating user: {e}", exc_info=True)
        raise


def login_for_access_token(db: Session, identifier: str, password: str) -> Optional[user_schemas.Token]:
    """Login user and generate access token.
    
    Args:
        db: Database session
        identifier: Username or email
        password: Plain text password
        
    Returns:
        Token object if authentication successful, None otherwise
    """
    try:
        user = authenticate_user(db, identifier, password)
        if not user:
            return None
            
        # Create access token with user ID as subject
        access_token = jwt_handler.create_access_token(
            data={"sub": str(user.id)}
        )
        
        return user_schemas.Token(
            access_token=access_token,
            token_type="bearer"
        )
    except Exception as e:
        logger.error(f"Error generating access token: {e}", exc_info=True)
        raise


def get_current_user(db: Session, token: str) -> Users:
    """Get current user from JWT token.
    
    Args:
        db: Database session
        token: JWT access token
        
    Returns:
        User object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the token
        payload = jwt_handler.decode_token(token)
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise credentials_exception
            
        # Convert string UUID back to UUID object
        user_uuid = uuid.UUID(user_id)
        
        # Fetch user from database
        stmt = select(Users).where(Users.id == user_uuid)
        result = db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user is None:
            raise credentials_exception
            
        return user
        
    except (jwt_handler.JWTError, jwt_handler.ExpiredSignatureError) as e:
        logger.error(f"JWT token validation error: {e}", exc_info=True)
        raise credentials_exception
    except ValueError as e:
        logger.error(f"Invalid UUID in token: {e}", exc_info=True)
        raise credentials_exception
    except Exception as e:
        logger.error(f"Error getting current user: {e}", exc_info=True)
        raise credentials_exception


def generate_password_reset_token(db: Session, email: str) -> Optional[str]:
    """Generate password reset token for user.
    
    Args:
        db: Database session
        email: User's email address
        
    Returns:
        Reset token if user found, None otherwise
    """
    try:
        # Find user by email
        stmt = select(Users).where(Users.email == email)
        result = db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            return None
            
        # Generate reset token and expiration
        reset_token = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        # Update user with reset token
        user.password_reset_token = reset_token
        user.password_reset_expires_at = expires_at
        
        db.commit()
        
        return reset_token
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error generating password reset token: {e}", exc_info=True)
        raise


def reset_user_password(db: Session, token: str, new_password: str) -> bool:
    """Reset user password using reset token.
    
    Args:
        db: Database session
        token: Password reset token
        new_password: New plain text password
        
    Returns:
        True if password was reset successfully, False otherwise
    """
    try:
        # Find user by reset token
        stmt = select(Users).where(Users.password_reset_token == token)
        result = db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            return False
            
        # Check if token has expired
        if not user.password_reset_expires_at or user.password_reset_expires_at < datetime.utcnow():
            return False
            
        # Hash new password
        new_password_hash = security.hash_password(new_password)
        
        # Update user password and clear reset fields
        user.password_hash = new_password_hash
        user.password_reset_token = None
        user.password_reset_expires_at = None
        
        db.commit()
        
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error resetting user password: {e}", exc_info=True)
        raise
