from pydantic import BaseModel

class ReadRequest(BaseModel):
    from_user: str