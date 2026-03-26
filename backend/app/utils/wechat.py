import httpx
from app.core.config import settings
from fastapi import HTTPException

async def get_openid_from_code(code: str):
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.WX_APPID,
        "secret": settings.WX_SECRET,
        "js_code": code,
        "grant_type": "authorization_code"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        data = resp.json()

    if "openid" not in data:
        raise HTTPException(status_code=400, detail="获取 openid 失败：" + data.get("errmsg", "未知错误"))
    
    return data["openid"], data["session_key"]
