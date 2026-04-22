from pydantic import BaseModel
from typing import Optional, Any, Dict
from datetime import datetime


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list
    usage: Optional[Dict[str, int]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Hello! How can I help you today?"
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": 9,
                    "completion_tokens": 12,
                    "total_tokens": 21
                }
            }
        }


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "Rate limit exceeded",
                "detail": "Too many requests",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        }


class HealthResponse(BaseModel):
    status: str
    version: str
    redis_connected: bool
    timestamp: datetime


class RateLimitResponse(BaseModel):
    allowed: bool
    remaining: int
    reset_in: Optional[int] = None
