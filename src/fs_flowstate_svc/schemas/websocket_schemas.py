from pydantic import BaseModel, Field
from typing import Dict, Any


class WebSocketMessage(BaseModel):
    """Standardized websocket message format.

    type: message type string (e.g., ping, pong, event_update, ack, error)
    payload: free-form dict for message body
    """

    type: str = Field(...)
    payload: Dict[str, Any] = Field(default_factory=dict)
