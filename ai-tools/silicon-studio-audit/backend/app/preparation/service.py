import pandas as pd
import json
import os
from typing import List, Dict, Any

class DataPreparationService:
    def __init__(self):
        self._shield = None

    @property
    def shield(self):
        if self._shield is None:
            # Lazy import and init
            from app.shield.service import PIIShieldService
            self._shield = PIIShieldService()
        return self._shield

    def preview_csv(self, file_path: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Read a CSV and return a preview of the data.
        """
        try:
            df = pd.read_csv(file_path)
            # Replace NaN with None for JSON compatibility
            df = df.where(pd.notnull(df), None)
            return df.head(limit).to_dict(orient="records")
        except Exception as e:
            raise ValueError(f"Failed to read CSV: {str(e)}")

    def apply_prompt_template(self, instruction: str, input_text: str, output_text: str, family: str) -> str:
        """
        Formats the data into a single string based on the model family's chat template.
        """
        # --- Llama 3 / 4 ---
        if "llama" in family.lower():
            # Format: <|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n{content}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n{response}<|eot_id|>
            user_content = f"{instruction}\n\n{input_text}".strip()
            return f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n{user_content}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n{output_text}<|eot_id|>"
        
        # --- Mistral / Mixtral ---
        elif "mistral" in family.lower() or "mixtral" in family.lower():
            # Format: <s>[INST] {instruction} {input} [/INST] {output}</s>
            user_content = f"{instruction} {input_text}".strip()
            return f"<s>[INST] {user_content} [/INST] {output_text}</s>"
            
        # --- Qwen 2.5 ---
        elif "qwen" in family.lower():
            # Format: <|im_start|>user\n{content}<|im_end|>\n<|im_start|>assistant\n{response}<|im_end|>\n
            user_content = f"{instruction}\n{input_text}".strip()
            return f"<|im_start|>user\n{user_content}<|im_end|>\n<|im_start|>assistant\n{output_text}<|im_end|>\n"
            
        # --- Gemma 2 / 3 ---
        elif "gemma" in family.lower():
            # Format: <start_of_turn>user\n{content}<end_of_turn>\n<start_of_turn>model\n{response}<end_of_turn>
            user_content = f"{instruction}\n{input_text}".strip()
            return f"<start_of_turn>user\n{user_content}<end_of_turn>\n<start_of_turn>model\n{output_text}<end_of_turn>"
        
        # --- Phi 3 ---
        elif "phi" in family.lower():
             # Format: <|user|>\n{content}<|end|>\n<|assistant|>\n{response}<|end|>
             user_content = f"{instruction}\n{input_text}".strip()
             return f"<|user|>\n{user_content}<|end|>\n<|assistant|>\n{output_text}<|end|>"

        # --- Base / Default (Text Completion) ---
        else:
            # Fallback for base models or unknown families
            return f"### Instruction:\n{instruction}\n\n### Input:\n{input_text}\n\n### Response:\n{output_text}"

    def convert_csv_to_jsonl(self, file_path: str, output_path: str, instruction_col: str, input_col: str, output_col: str, strip_pii: bool = False, model_family: str = "Llama"):
        """
        Convert CSV to JSONL data for MLX training.
        Includes PII stripping and Prompt Templating.
        """
        try:
            df = pd.read_csv(file_path)
            
            with open(output_path, 'w') as f:
                for _, row in df.iterrows():
                    instruction = str(row.get(instruction_col, ""))
                    input_text = str(row.get(input_col, "")) if input_col else ""
                    output_text = str(row.get(output_col, ""))

                    # 1. PII Stripping (Optional)
                    if strip_pii:
                        # We analyze and anonymize each field independently to preserve structure
                        # Note: This effectively calls Presidio 3 times per row, which can be slow for large datasets.
                        # For production, batching would be better.
                        instruction = self.shield.anonymize_text(instruction)["text"]
                        if input_text:
                            input_text = self.shield.anonymize_text(input_text)["text"]
                        output_text = self.shield.anonymize_text(output_text)["text"]

                    # 2. Prompt Templating
                    # MLX-LM trainer typically expects a "text" field containing the full training example
                    formatted_text = self.apply_prompt_template(instruction, input_text, output_text, model_family)
                    
                    record = {
                        "text": formatted_text
                    }
                    f.write(json.dumps(record) + "\n")
            
            return {"status": "success", "rows": len(df), "output_path": output_path}
        except Exception as e:
            raise ValueError(f"Conversion failed: {str(e)}")
