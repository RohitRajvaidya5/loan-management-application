from pydantic import BaseModel, ConfigDict, Field


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class PageQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)
