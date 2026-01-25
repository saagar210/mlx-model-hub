from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any
import uuid
from app.engine.service import MLXEngineService

router = APIRouter()
service = MLXEngineService()

class FineTuneRequest(BaseModel):
    model_id: str
    dataset_path: str
    epochs: int = 3
    learning_rate: float = 1e-4
    batch_size: int = 1
    lora_rank: int = 8
    lora_alpha: float = 16.0
    max_seq_length: int = 512
    lora_dropout: float = 0.0
    lora_layers: int = 8
    job_name: str = "" # Optional user provided name

@router.post("/finetune")
async def start_finetune(request: FineTuneRequest):
    """
    Start a fine-tuning job.
    """
    job_id = str(uuid.uuid4())
    print(f"DEBUG API: Received finetune request. Job Name: '{request.job_name}'")
    config = request.model_dump()
    print(f"DEBUG API: Config dump: {config}")
    result = await service.start_finetuning(job_id, config)
    return result

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Get status of a fine-tuning job.
    """
    status = service.get_job_status(job_id)
    if status["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Job not found")
    return status

@router.get("/models")
async def list_models():
    """
    List supported base models with their local download status.
    """
    return service.get_models_status()

class DownloadRequest(BaseModel):
    model_id: str

@router.post("/models/download")
async def download_model(request: DownloadRequest, background_tasks: BackgroundTasks):
    """
    Trigger a model download in the background.
    """
    background_tasks.add_task(service.download_model, request.model_id)
    return {"status": "download_started", "model_id": request.model_id}

@router.post("/models/delete")
async def delete_model(request: DownloadRequest):
    """
    Delete a locally downloaded model.
    """
    success = service.delete_model(request.model_id)
    if not success:
         raise HTTPException(status_code=404, detail="Model not found or could not be deleted")
    return {"status": "deleted", "model_id": request.model_id}

class RegisterRequest(BaseModel):
    name: str
    path: str
    url: str = ""

@router.post("/models/register")
async def register_model(request: RegisterRequest):
    """
    Register a custom model from a local path.
    """
    try:
        new_model = service.register_model(request.name, request.path, request.url)
        return new_model
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ChatRequest(BaseModel):
    model_id: str
    messages: list
    temperature: float = 0.7

@router.post("/chat")
async def chat_generation(request: ChatRequest):
    """
    Generate a response from the model.
    """
    response = await service.generate_response(request.model_id, request.messages)
    return response
