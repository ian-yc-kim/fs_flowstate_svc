"""JWT token creation and validation utilities."""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from jose import jwt, JWTError, ExpiredSignatureError

from fs_flowstate_svc.config import settings

logger = logging.getLogger(__name__)

# JWT algorithm
ALGORITHM = "HS256"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token.
    
    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token as string
    """
    try:
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            
        to_encode.update({"exp": expire})
        
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.JWT_SECRET_KEY.get_secret_value(), 
            algorithm=ALGORITHM
        )
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating access token: {e}", exc_info=True)
        raise


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token.
    
    Args:
        token: JWT token string to decode
        
    Returns:
        Dictionary containing the token claims
        
    Raises:
        JWTError: If the token is invalid
        ExpiredSignatureError: If the token has expired
    """
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY.get_secret_value(), 
            algorithms=[ALGORITHM]
        )
        return payload
    except ExpiredSignatureError as e:
        logger.error(f"Token has expired: {e}", exc_info=True)
        raise
    except JWTError as e:
        logger.error(f"Invalid token: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Error decoding token: {e}", exc_info=True)
        raise
