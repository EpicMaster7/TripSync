from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User
from ..auth import hash_password, verify_password, new_session, set_session_cookie, COOKIE_NAME, current_user, read_session
from ..schemas import Credentials, Register, UserOut

router = APIRouter()

@router.post('/auth/register', response_model=UserOut, status_code=201)
def register(data: Register, response: Response, db: Session=Depends(get_db)):
    if db.scalar(select(User.id).where(User.email == data.email)):
        raise HTTPException(409, 'Email already registered')
    user = User(name=data.name.strip(), email=data.email, password_hash=hash_password(data.password))
    db.add(user)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, 'Email already registered')
    db.refresh(user)
    token, _ = new_session(user.id); set_session_cookie(response, token)
    return user

@router.post('/auth/login', response_model=UserOut)
def login(data: Credentials, response: Response, db: Session=Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email))
    if not user or not verify_password(user.password_hash, data.password):
        raise HTTPException(401, 'Incorrect email or password')
    token, _ = new_session(user.id); set_session_cookie(response, token)
    return user

@router.post('/auth/logout')
def logout(response: Response, user: User=Depends(current_user)):
    response.delete_cookie(COOKIE_NAME, path='/'); return {'ok': True}

@router.get('/me')
def me(request: Request, user: User=Depends(current_user)):
    return {'user': UserOut.model_validate(user), 'csrf_token': read_session(request.cookies[COOKIE_NAME])['csrf']}
