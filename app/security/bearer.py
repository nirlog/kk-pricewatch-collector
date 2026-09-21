"""Bearer-token authentication boundary."""

import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.settings import Settings


def authenticate_bearer(
    authorization: Annotated[str | None, Header()] = None,
    *,
    settings: Settings,
) -> None:
    """Validate a bearer credential without exposing either token."""

    scheme, separator, supplied_token = (authorization or "").partition(" ")
    valid_shape = bool(separator and scheme.lower() == "bearer" and supplied_token)
    valid_token = valid_shape and hmac.compare_digest(supplied_token, settings.api_token)
    if not valid_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
