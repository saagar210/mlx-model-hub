"""Enum types for database status fields."""

from enum import Enum


class TaskType(str, Enum):
    """Types of ML tasks supported."""

    TEXT_GENERATION = "text-generation"
    CLASSIFICATION = "classification"
    SUMMARIZATION = "summarization"
    QUESTION_ANSWERING = "question-answering"
    CHAT = "chat"


class ModelVersionStatus(str, Enum):
    """Status of a model version."""

    TRAINING = "training"
    READY = "ready"
    ARCHIVED = "archived"
    FAILED = "failed"


class JobStatus(str, Enum):
    """Status of a training job."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
