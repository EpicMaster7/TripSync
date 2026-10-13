import os, secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, WebSocket, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session
from .db import get_db
from .models import User

_hasher = PasswordHasher()
COOKIE_NAME = 'tripsync_session'
SESSION_SECONDS = 60 * 60 * 8

def _serializer():
    secret = os.environ.get('SESSION_SECRET', '')
    if len(secret) < 32 or 'REPLACE_WITH' in secret:
        raise RuntimeError('Configure SESSION_SECRET with at least 32 random characters')
    return URLSafeTimedSerializer(secret, salt='tripsync-v1')

def hash_password(password):
    return _hasher.hash(password)

def verify_password(hash_, password):
    try: return _hasher.verify(hash_, password)
    except (VerifyMismatchError, VerificationError): return False

def new_session(user_id):
    csrf = secrets.token_urlsafe(32)
    return _serializer().dumps({'uid': user_id, 'csrf': csrf}), csrf

def read_session(token):
    try: return _serializer().loads(token, max_age=SESSION_SECONDS)
    except (BadSignature, SignatureExpired): return None

def current_user(request: Request, db: Session = Depends(get_db)):
    info = read_session(request.cookies.get(COOKIE_NAME, ''))
    if not info: raise HTTPException(status_code=401, detail='Sign in required')
    user = db.get(User, info['uid'])
    if not user: raise HTTPException(status_code=401, detail='Session user no longer exists')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if not secrets.compare_digest(request.headers.get('x-csrf-token', ''), info['csrf']):
            raise HTTPException(status_code=403, detail='Missing or invalid CSRF token; reload and retry')
    return user

def ws_user(ws: WebSocket, db):
    allowed = os.environ.get('APP_ORIGIN', 'http://localhost:5173')
    if ws.headers.get('origin') != allowed: return None
    info = read_session(ws.cookies.get(COOKIE_NAME, ''))
    return db.get(User, info['uid']) if info else None

def set_session_cookie(response, token):
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=os.getenv('COOKIE_SECURE')=='true',
                        samesite='lax', max_age=SESSION_SECONDS, path='/')
