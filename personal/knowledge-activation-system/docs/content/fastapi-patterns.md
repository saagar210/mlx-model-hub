# FastAPI Patterns: Dependencies, Streaming, and Best Practices

FastAPI is a modern Python web framework for building APIs with automatic OpenAPI documentation and type validation.

## Dependency Injection

FastAPI's dependency injection system uses `Depends()` to create reusable, composable components.

### Basic Dependency

```python
from fastapi import Depends, FastAPI

app = FastAPI()

def get_db():
    """Database connection dependency."""
    db = DatabaseSession()
    try:
        yield db
    finally:
        db.close()

@app.get("/items")
async def read_items(db = Depends(get_db)):
    return db.query(Item).all()
```

### Dependency with Parameters

```python
def get_pagination(skip: int = 0, limit: int = 100):
    """Pagination parameters as a dependency."""
    return {"skip": skip, "limit": limit}

@app.get("/items")
async def list_items(pagination: dict = Depends(get_pagination)):
    return get_items(**pagination)
```

### Class-Based Dependencies

```python
class CommonQueryParams:
    def __init__(self, q: str | None = None, skip: int = 0, limit: int = 100):
        self.q = q
        self.skip = skip
        self.limit = limit

@app.get("/items")
async def read_items(commons: CommonQueryParams = Depends()):
    return {"q": commons.q, "skip": commons.skip, "limit": commons.limit}
```

### Nested Dependencies

```python
def get_settings():
    return Settings()

def get_db(settings: Settings = Depends(get_settings)):
    return Database(settings.database_url)

def get_user_service(db = Depends(get_db)):
    return UserService(db)

@app.get("/users/{user_id}")
async def get_user(user_id: int, service = Depends(get_user_service)):
    return service.get(user_id)
```

### Dependency Overrides for Testing

```python
def override_get_db():
    return TestDatabase()

app.dependency_overrides[get_db] = override_get_db
```

## Streaming Responses with LLMs

FastAPI supports Server-Sent Events (SSE) for streaming LLM responses.

### Basic SSE Streaming

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio

app = FastAPI()

async def generate_stream():
    """Async generator for streaming."""
    for i in range(10):
        yield f"data: chunk {i}\n\n"
        await asyncio.sleep(0.1)
    yield "data: [DONE]\n\n"

@app.get("/stream")
async def stream_response():
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream"
    )
```

### Streaming with Anthropic Claude

```python
from anthropic import AsyncAnthropic
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()
client = AsyncAnthropic()

async def stream_claude(prompt: str):
    """Stream response from Claude."""
    async with client.messages.stream(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        async for text in stream.text_stream:
            yield f"data: {text}\n\n"
    yield "data: [DONE]\n\n"

@app.post("/chat/stream")
async def chat_stream(prompt: str):
    return StreamingResponse(
        stream_claude(prompt),
        media_type="text/event-stream"
    )
```

### Streaming with OpenAI

```python
from openai import AsyncOpenAI
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()
client = AsyncOpenAI()

async def stream_openai(prompt: str):
    """Stream response from OpenAI."""
    stream = await client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield f"data: {chunk.choices[0].delta.content}\n\n"
    yield "data: [DONE]\n\n"

@app.post("/openai/stream")
async def openai_stream(prompt: str):
    return StreamingResponse(
        stream_openai(prompt),
        media_type="text/event-stream"
    )
```

### Client-Side SSE Consumption

```javascript
const eventSource = new EventSource('/stream');

eventSource.onmessage = (event) => {
    if (event.data === '[DONE]') {
        eventSource.close();
        return;
    }
    console.log('Received:', event.data);
};

eventSource.onerror = (error) => {
    console.error('SSE Error:', error);
    eventSource.close();
};
```

## Request Validation with Pydantic

FastAPI uses Pydantic for automatic request/response validation.

```python
from pydantic import BaseModel, Field, field_validator

class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., gt=0)
    tags: list[str] = []

    @field_validator('name')
    @classmethod
    def name_must_be_alphanumeric(cls, v: str) -> str:
        if not v.replace(' ', '').isalnum():
            raise ValueError('must be alphanumeric')
        return v.title()

@app.post("/items")
async def create_item(item: ItemCreate):
    return {"name": item.name, "price": item.price}
```

## Background Tasks

```python
from fastapi import BackgroundTasks

def send_notification(email: str, message: str):
    """Background task for sending notifications."""
    # Simulate email sending
    print(f"Sending {message} to {email}")

@app.post("/items")
async def create_item(item: ItemCreate, background_tasks: BackgroundTasks):
    background_tasks.add_task(send_notification, "admin@example.com", f"New item: {item.name}")
    return item
```

## Error Handling

```python
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

class ItemNotFoundError(Exception):
    def __init__(self, item_id: int):
        self.item_id = item_id

@app.exception_handler(ItemNotFoundError)
async def item_not_found_handler(request, exc: ItemNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": f"Item {exc.item_id} not found"}
    )

@app.get("/items/{item_id}")
async def get_item(item_id: int):
    item = db.get(item_id)
    if not item:
        raise ItemNotFoundError(item_id)
    return item
```

## References

- FastAPI Documentation: https://fastapi.tiangolo.com
- Pydantic v2 Documentation: https://docs.pydantic.dev
- Starlette (ASGI framework): https://www.starlette.io
