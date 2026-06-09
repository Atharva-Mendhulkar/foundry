from pydantic import BaseModel, UUID4
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: UUID4
    username: str
    role: str
    
    class Config:
        from_attributes = True
