# Pydantic v1 to v2 Migration Guide

Pydantic v2 is a complete rewrite with significant performance improvements and API changes. This guide covers the key differences.

## Key Differences Overview

| Feature | Pydantic v1 | Pydantic v2 |
|---------|-------------|-------------|
| Config | `class Config` | `model_config = ConfigDict()` |
| Validators | `@validator` | `@field_validator` |
| Root validators | `@root_validator` | `@model_validator` |
| Field aliases | `Field(alias=...)` | Same, but `validation_alias` and `serialization_alias` available |
| JSON schema | `schema()` | `model_json_schema()` |
| Dict export | `.dict()` | `.model_dump()` |
| JSON export | `.json()` | `.model_dump_json()` |
| ORM mode | `orm_mode = True` | `from_attributes = True` |

## Configuration Changes

### Pydantic v1

```python
from pydantic import BaseModel

class User(BaseModel):
    name: str
    email: str

    class Config:
        orm_mode = True
        validate_assignment = True
        extra = "forbid"
```

### Pydantic v2

```python
from pydantic import BaseModel, ConfigDict

class User(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        extra="forbid",
    )

    name: str
    email: str
```

## Validator Changes

### Field Validators

**Pydantic v1:**
```python
from pydantic import BaseModel, validator

class User(BaseModel):
    name: str
    email: str

    @validator('name')
    def name_must_be_capitalized(cls, v):
        return v.title()

    @validator('email')
    def email_must_contain_at(cls, v):
        if '@' not in v:
            raise ValueError('must contain @')
        return v.lower()
```

**Pydantic v2:**
```python
from pydantic import BaseModel, field_validator

class User(BaseModel):
    name: str
    email: str

    @field_validator('name')
    @classmethod
    def name_must_be_capitalized(cls, v: str) -> str:
        return v.title()

    @field_validator('email')
    @classmethod
    def email_must_contain_at(cls, v: str) -> str:
        if '@' not in v:
            raise ValueError('must contain @')
        return v.lower()
```

### Model Validators (Root Validators)

**Pydantic v1:**
```python
from pydantic import BaseModel, root_validator

class DateRange(BaseModel):
    start: date
    end: date

    @root_validator
    def check_dates(cls, values):
        start = values.get('start')
        end = values.get('end')
        if start and end and start > end:
            raise ValueError('start must be before end')
        return values
```

**Pydantic v2:**
```python
from pydantic import BaseModel, model_validator

class DateRange(BaseModel):
    start: date
    end: date

    @model_validator(mode='after')
    def check_dates(self) -> 'DateRange':
        if self.start > self.end:
            raise ValueError('start must be before end')
        return self
```

### Before vs After Validation

```python
from pydantic import BaseModel, model_validator

class User(BaseModel):
    name: str
    email: str

    @model_validator(mode='before')
    @classmethod
    def preprocess(cls, data: dict) -> dict:
        """Run before field validation."""
        if isinstance(data, dict) and 'full_name' in data:
            data['name'] = data.pop('full_name')
        return data

    @model_validator(mode='after')
    def postprocess(self) -> 'User':
        """Run after field validation."""
        self.email = self.email.lower()
        return self
```

## Field Changes

### Pydantic v1

```python
from pydantic import BaseModel, Field

class Item(BaseModel):
    name: str = Field(..., min_length=1)
    price: float = Field(..., gt=0)
    description: str = Field(None, max_length=500)
```

### Pydantic v2

```python
from pydantic import BaseModel, Field

class Item(BaseModel):
    name: str = Field(min_length=1)
    price: float = Field(gt=0)
    description: str | None = Field(default=None, max_length=500)
```

## Method Renames

### Dict/JSON Export

**Pydantic v1:**
```python
user = User(name="John", email="john@example.com")
user.dict()  # {'name': 'John', 'email': 'john@example.com'}
user.dict(exclude={'email'})
user.json()  # '{"name": "John", "email": "john@example.com"}'
```

**Pydantic v2:**
```python
user = User(name="John", email="john@example.com")
user.model_dump()  # {'name': 'John', 'email': 'john@example.com'}
user.model_dump(exclude={'email'})
user.model_dump_json()  # '{"name": "John", "email": "john@example.com"}'
```

### Schema Generation

**Pydantic v1:**
```python
User.schema()
User.schema_json()
```

**Pydantic v2:**
```python
User.model_json_schema()
import json
json.dumps(User.model_json_schema())
```

### Copy/Update

**Pydantic v1:**
```python
user2 = user.copy(update={'name': 'Jane'})
```

**Pydantic v2:**
```python
user2 = user.model_copy(update={'name': 'Jane'})
```

## New Features in Pydantic v2

### Computed Fields

```python
from pydantic import BaseModel, computed_field

class Rectangle(BaseModel):
    width: float
    height: float

    @computed_field
    @property
    def area(self) -> float:
        return self.width * self.height
```

### Strict Mode

```python
from pydantic import BaseModel, ConfigDict

class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True)

    value: int  # Won't accept "123", only 123
```

### Validation Aliases

```python
from pydantic import BaseModel, Field

class User(BaseModel):
    name: str = Field(validation_alias='userName')  # Accept 'userName' on input
    email: str = Field(serialization_alias='emailAddress')  # Output as 'emailAddress'
```

### TypeAdapter for Non-Model Validation

```python
from pydantic import TypeAdapter

adapter = TypeAdapter(list[int])
adapter.validate_python(['1', '2', '3'])  # [1, 2, 3]
adapter.validate_json('[1, 2, 3]')  # [1, 2, 3]
```

## Performance Improvements

Pydantic v2 uses a Rust core (pydantic-core) for validation:

- 5-50x faster validation
- Reduced memory usage
- Better error messages
- Improved JSON serialization

## Migration Script

Pydantic provides a migration tool:

```bash
pip install bump-pydantic
bump-pydantic your_project/
```

## References

- Pydantic v2 Migration Guide: https://docs.pydantic.dev/latest/migration/
- Pydantic v2 Concepts: https://docs.pydantic.dev/latest/concepts/
- bump-pydantic Tool: https://github.com/pydantic/bump-pydantic
