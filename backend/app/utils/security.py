from jose.exceptions import ExpiredSignatureError
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from app.core.config import settings
from app.utils.time import now_utc

# JWT 配置参数
JWT_SECRET = settings.JWT_SECRET
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = settings.JWT_EXPIRE_MINUTES


# 创建 token（返回值仍为字符串）
def create_jwt_token(user_id: int) -> str:
    expire_at = now_utc() + timedelta(minutes=JWT_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "exp": int(expire_at.timestamp())  # 转为 timestamp（jwt 要求）
    }

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# 解码 token
def decode_jwt_token(token: str) -> int:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload.get("sub"))
    except ExpiredSignatureError:
        raise ValueError("Token 已过期")
    except JWTError:
        raise ValueError("Token 无效")
