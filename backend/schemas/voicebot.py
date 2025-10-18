from typing import Optional
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    session_id: str
    input_type: Optional[str] = "text" 