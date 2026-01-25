from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.preparation.service import DataPreparationService

router = APIRouter()
_service = None

def get_service():
    global _service
    if _service is None:
        try:
            print("DEBUG: Initializing DataPreparationService...", flush=True)
            _service = DataPreparationService()
            print("DEBUG: DataPreparationService initialized", flush=True)
        except Exception as e:
            print(f"CRITICAL: Failed to init DataPreparationService: {e}", flush=True)
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail="Preparation service failed to initialize")
    return _service

class PreviewRequest(BaseModel):
    file_path: str
    limit: int = 5

class ConversionRequest(BaseModel):
    file_path: str
    output_path: str
    instruction_col: str
    input_col: Optional[str] = None
    output_col: str
    strip_pii: bool = False
    model_family: str = "Llama"

@router.post("/preview")
async def preview_csv(request: PreviewRequest):
    """
    Preview the first N rows of a CSV file.
    """
    try:
        svc = get_service()
        data = svc.preview_csv(request.file_path, request.limit)
        return {"data": data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/convert")
async def convert_to_jsonl(request: ConversionRequest):
    """
    Convert a CSV file to JSONL format for LLM fine-tuning.
    """
    try:
        svc = get_service()
        result = svc.convert_csv_to_jsonl(
            request.file_path,
            request.output_path,
            request.instruction_col,
            request.input_col,
            request.output_col,
            request.strip_pii,
            request.model_family
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
