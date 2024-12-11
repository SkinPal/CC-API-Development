from pydantic import BaseModel, validator
from typing import Optional
from fastapi import UploadFile, File, HTTPException

# register
class UserCreate(BaseModel):
    user_id: str 
    nama: str
    email: str
    password: str

    @validator('password')
    def validate_password(cls, password):
        if len(password) < 8:
            raise HTTPException(
                status_code=400,
                detail="Password harus minimal 8 karakter"
            )
        return password

class ImageUpload(BaseModel):
    user_id: str
    week: str  # 'pekan1', 

class ImageUploadProfile(BaseModel):
    user_id: str

class UserLogin(BaseModel):
    user_id: str
    password: str