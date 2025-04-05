from pydantic import BaseModel, Field

class ChapterOutline(BaseModel):
    title: str
    description: str

class BookOutline(BaseModel):
    chapters: list[ChapterOutline]= Field(default_factory=[])

class BookContent(BaseModel):
    chapter_title: str
    content: str

class Book(BaseModel):
    chapters: list[BookContent]= Field(default_factory=[])

