from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.postgres import get_db
from app.core.security import verify_password, create_access_token
from app.models.orm.user import User
from app.models.schemas.auth import UserLogin, Token, UserResponse
from app.core.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=Token)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.username == login_data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(subject=user.username)
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/logout")
async def logout():
    return {"status": "ok"}
