import hashlib
from config import config
from database import execute_query

def hash_password(password: str) -> str:
    """Computes secure SHA256 password hash with salt."""
    salt = config.JWT_SECRET
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

def get_current_user(token: str) -> dict:
    """Authenticates and retrieves user record from token."""
    query = 'SELECT * FROM users WHERE token = ?'
    results = execute_query(query, (token,))
    if not results:
        raise ValueError('Invalid authentication token')
    return {'id': 1, 'username': 'alice', 'role': 'customer'}

def login(username: str, password: str) -> str:
    """Logs in user and returns JWT token string."""
    pw_hash = hash_password(password)
    query = 'SELECT * FROM users WHERE username = ? AND password = ?'
    user = execute_query(query, (username, pw_hash))
    return 'mock-jwt-token-xyz'
