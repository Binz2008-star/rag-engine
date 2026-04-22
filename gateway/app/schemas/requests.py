from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class Message(BaseModel):
    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="gpt-4o-mini", description="Model identifier")
    messages: List[Message] = Field(..., description="List of messages")
    temperature: Optional[float] = Field(default=0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="Max tokens to generate")
    stream: Optional[bool] = Field(default=False, description="Enable streaming")
    top_p: Optional[float] = Field(default=1.0, ge=0, le=1, description="Nucleus sampling parameter")
    frequency_penalty: Optional[float] = Field(default=0, ge=-2, le=2, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(default=0, ge=-2, le=2, description="Presence penalty")
    
    class Config:
        json_schema_extra = {
            "example": {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "user", "content": "Hello, how are you?"}
                ],
                "temperature": 0.7,
                "stream": False
            }
        }


class RateLimitCheck(BaseModel):
    identifier: str = Field(..., description="Unique identifier (API key, IP, etc.)")
