import asyncio
import os
import threading
from typing import Dict, Any, List
from pathlib import Path
from mlx_lm import load, generate
from mlx_lm.tuner import train, TrainingArgs
from mlx_lm.utils import load_adapters

# Define a curated list of supported models for the UI
# Default curated list (MLX Community only, as requested)
DEFAULT_MODELS = []

class MLXEngineService:
    def __init__(self):
        self.active_jobs = {}
        self.active_downloads = set() # Track active downloads logic
        self.loaded_models = {}
        self.models_dir = Path("models")
        self.models_dir.mkdir(exist_ok=True)
        self.adapters_dir = Path("adapters")
        self.adapters_dir.mkdir(exist_ok=True)
        
        # PROD FIX: Check multiple locations for models.json
        possible_paths = [
            Path("models.json"), # Default CWD
            Path("_internal/models.json"), # PyInstaller one-dir default
        ]
        
        # Check sys._MEIPASS if frozen
        import sys
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
             possible_paths.append(Path(sys._MEIPASS) / "models.json")
             
        self.models_config_path = Path("models.json") # Default fallback
        for p in possible_paths:
            if p.exists():
                self.models_config_path = p
                print(f"Found models.config at: {p.absolute()}")
                break
                
        self.models_config = self._load_models_config()

    def _load_models_config(self):
        # Load directly from models.json as the source of truth
        if self.models_config_path.exists():
            try:
                with open(self.models_config_path, "r") as f:
                    import json
                    return json.load(f)
            except Exception as e:
                print(f"Error loading models.json: {e}")
                return []
        else:
            return []

    def _save_models_config(self):
        with open(self.models_config_path, "w") as f:
            import json
            json.dump(self.models_config, f, indent=4)
            
    def get_supported_models(self):
        return self.models_config

    def _get_dir_size_str(self, path: Path):
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    # skip if it is symbolic link
                    if not os.path.islink(fp):
                        total_size += os.path.getsize(fp)
            
            gb = total_size / (1024 * 1024 * 1024)
            if gb < 1:
                return f"{gb:.2f}GB"
            return f"{gb:.1f}GB"
        except Exception as e:
            print(f"Error calculating size for {path}: {e}")
            return "Unknown"

    def register_model(self, name: str, path: str, url: str = ""):
        """
        Registers a custom model.
        Path should be the absolute path to the local model folder.
        """
        for m in self.models_config:
             if m['name'] == name:
                 raise ValueError(f"Model with name {name} already exists.")
        
        # Calculate size immediately
        size_str = self._get_dir_size_str(Path(path))

        new_model = {
            "id": path, # Use absolute path as ID for local loading
            "name": name,
            "size": size_str,
            "family": "Custom",
            "url": url,
            "external": False, 
            "is_custom": True
        }
        
        self.models_config.append(new_model)
        self._save_models_config()
        return new_model

    def list_models(self):
        # Kept for compatibility if used elsewhere, but internally we use models_config
        return self.models_config

    async def get_model_and_tokenizer(self, model_id: str):
        if model_id not in self.loaded_models:
            print(f"Loading model: {model_id}")
            
            path_to_load = model_id
            
            # 1. Is it an absolute path? (Custom Model)
            if Path(model_id).is_absolute() and Path(model_id).exists():
                 path_to_load = model_id
            else:
                # 2. Local standard cache
                sanitized_name = model_id.replace("/", "--")
                local_path = self.models_dir / sanitized_name
                # Only load if it's fully downloaded (marked completed)
                if (local_path / ".completed").exists():
                    path_to_load = str(local_path)
            
            print(f"Loading from: {path_to_load}")

            # This loads the model weights into memory. API calls might timeout if this takes too long.
            # ideally this should be async or backgrounded, but for MVP we wait.
            # Running in an executor to avoid blocking the event loop entirely
            loop = asyncio.get_running_loop()
            model, tokenizer = await loop.run_in_executor(None, load, path_to_load)
            self.loaded_models[model_id] = (model, tokenizer)
        return self.loaded_models[model_id]

    async def generate_response(self, model_id: str, messages: list):
        try:
            model, tokenizer = await self.get_model_and_tokenizer(model_id)
            
            # Simple prompt construction for MVP (chat template handling varies by model)
            # For simplicity, we just concatenate or use apply_chat_template if available.
            # Using tokenizer.apply_chat_template is preferred if supported.
            if hasattr(tokenizer, "apply_chat_template"):
                prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            else:
                 # Fallback for models without chat template config
                prompt = messages[-1]['content']

            # Run generation in executor
            loop = asyncio.get_running_loop()
            response_text = await loop.run_in_executor(
                None, 
                lambda: generate(model, tokenizer, prompt=prompt, max_tokens=200, verbose=True)
            )

            return {
                "role": "assistant",
                "content": response_text,
                "usage": {"total_tokens": len(response_text)} # Placeholder usage
            }
        except Exception as e:
            print(f"Generation error: {e}")
            return {"role": "assistant", "content": f"Error generating response: {str(e)}"}

    async def start_finetuning(self, job_id: str, config: Dict[str, Any]):
        job_name = config.get("job_name", "")
        print(f"DEBUG SERVICE: start_finetuning job_name='{job_name}' for job_id={job_id}")
        self.active_jobs[job_id] = {
            "status": "starting", 
            "progress": 0, 
            "job_name": job_name,
            "job_id": job_id # Store ID as well for easy access
        }
        
        # Spawn a thread for training so we don't block the API
        thread = threading.Thread(target=self._run_training_job, args=(job_id, config))
        thread.start()
        
        return {"job_id": job_id, "status": "started", "job_name": job_name}

    def _run_training_job(self, job_id: str, config: Dict):
        """
        Executed in a separate thread.
        """
        try:
            self.active_jobs[job_id]["status"] = "training"
            model_id = config.get("model_id")
            dataset_path = config.get("dataset_path")
            epochs = int(config.get("epochs", 3))
            lr = float(config.get("learning_rate", 1e-4))
            
            # New Params
            batch_size = int(config.get("batch_size", 1))
            lora_rank = int(config.get("lora_rank", 8))
            lora_alpha = float(config.get("lora_alpha", 16))
            max_seq_length = int(config.get("max_seq_length", 512))
            lora_dropout = float(config.get("lora_dropout", 0.0))
            lora_layers = int(config.get("lora_layers", 8))
            
            # Create dedicated directory for this job
            job_adapter_dir = self.adapters_dir / job_id
            job_adapter_dir.mkdir(parents=True, exist_ok=True)
            
            adapter_file = job_adapter_dir / "adapters.safetensors"

            print(f"Starting training job {job_id} for model {model_id}...")
            print(f"Params: Epochs={epochs}, BS={batch_size}, Rank={lora_rank}, Alpha={lora_alpha}, LR={lr}, Dropout={lora_dropout}")

            # 1. Load Model (fresh load for training recommended to avoid state issues)
            # For efficiency we could reuse, but freezing/lora modification happens in-place.
            # RENAME config -> model_config to avoid shadowing the function argument 'config'
            model, tokenizer, model_config = load(model_id, return_config=True)
            
            # Freeze the base model
            model.freeze()

            # 2. Setup Training Arguments
            from mlx_lm.tuner.datasets import load_local_dataset, CacheDataset
            import shutil

            # Fix: load_local_dataset expects a directory containing 'train.jsonl'.
            # It ignores the filename of dataset_path if we just pass the parent directory.
            # We must create a temporary directory for this job and copy the user's file to 'train.jsonl' there.
            
            job_data_dir = job_adapter_dir / "data"
            job_data_dir.mkdir(exist_ok=True, parents=True)
            
            target_train_path = job_data_dir / "train.jsonl"
            try:
                shutil.copy(dataset_path, target_train_path)
                print(f"Staged dataset {dataset_path} to {target_train_path}")
            except Exception as e:
                print(f"Error copying dataset: {e}")
                # Fallback? No, likely fatal.
            
            # Note: load_local_dataset returns (train, val, test) tuple
            train_set, val_set, test_set = load_local_dataset(job_data_dir, tokenizer, model_config)
            
            # --- FIX FOR EMPTY VALIDATION SET ---
            # If user provides only train.jsonl, val_set is empty list. Train loop crashes.
            if len(val_set) == 0:
                print("Validation set empty. Splitting train set...")
                # Access raw data: load_local_dataset returns [ChatDataset(...), ...]
                # ChatDataset wraps a list in self._data
                if hasattr(train_set, "_data"):
                    raw_data = train_set._data
                else:
                    raw_data = train_set # Fallback if list
                
                # Split logic
                if len(raw_data) > 1:
                    split_idx = int(len(raw_data) * 0.9)
                    if split_idx == len(raw_data): split_idx = len(raw_data) - 1
                    
                    train_raw = raw_data[:split_idx]
                    val_raw = raw_data[split_idx:]
                    
                    # Re-create datasets
                    from mlx_lm.tuner.datasets import create_dataset
                    train_set = create_dataset(train_raw, tokenizer, model_config)
                    val_set = create_dataset(val_raw, tokenizer, model_config)
                else:
                    # Too small to split, duplicate
                    print("Train set too small (<=1). Duplicating for validation.")
                    # Note: Using same object might cause issues if modified? Safe to reuse for MVP
                    train_set = train_set
                    val_set = train_set 

            # IMPORTANT: ChatDataset returns raw dicts. Trainer expects processed tuples.
            # We must wrap them in CacheDataset which calls .process()
            train_set = CacheDataset(train_set)
            val_set = CacheDataset(val_set)
            
            # Calculate total iterations
            # Steps per epoch = len(train_set) / batch_size
            steps_per_epoch = len(train_set) // batch_size
            if steps_per_epoch < 1: steps_per_epoch = 1
            total_iters = steps_per_epoch * epochs
            
            print(f"Training Plan: {len(train_set)} samples, {steps_per_epoch} steps/epoch, {total_iters} total iters.")

            args = TrainingArgs(
                batch_size=batch_size, 
                iters=total_iters, 
                adapter_file=str(adapter_file),
                max_seq_length=max_seq_length
            )

            # Define a callback class to update progress
            class ProgressCallback:
                def on_train_loss_report(self_, train_info):
                    if "iteration" in train_info:
                        step = train_info["iteration"]
                        prog = int((step / args.iters) * 100)
                        self.active_jobs[job_id]["progress"] = prog

                def on_val_loss_report(self_, val_info):
                    # We can log validation loss if we want, or just ignore
                    pass

            progress_callback = ProgressCallback()

            # 3. Run Training
            # Note: mlx_lm.tuner.train signature: 
            # train(model, optimizer, train_dataset, val_dataset, args, training_callback=...)
            
            # We need to construction the optimizer
            import mlx.optimizers as optim
            optimizer = optim.Adam(learning_rate=lr)
            
            # We need to convert to LoRA
            from mlx_lm.tuner.utils import linear_to_lora_layers

            # Define LoRA config
            # Use user-defined layers count
            
            lora_config = {
                "rank": lora_rank,
                "alpha": lora_alpha,
                "scale": float(lora_alpha / lora_rank), # alpha / rank
                "dropout": lora_dropout,
                "keys": ["self_attn.q_proj", "self_attn.v_proj"], # Common keys for LoRA
                "num_layers": lora_layers # User defined
            }
            
            # Note: num_layers=N means adapt the last N layers
            # linear_to_lora_layers modifies model in-place and returns None!
            linear_to_lora_layers(model, lora_config["num_layers"], lora_config)
            
            # Print model to confirm
            print("Model converted to LoRA.")

            train(
                model=model,
                optimizer=optimizer,
                train_dataset=train_set,
                val_dataset=val_set,
                args=args,
                training_callback=progress_callback
            )

            self.active_jobs[job_id]["status"] = "completed"
            self.active_jobs[job_id]["model_path"] = str(adapter_file)
            self.active_jobs[job_id]["progress"] = 100
            
            # --- Auto-Register Fine-Tuned Model ---
            job_name = config.get("job_name")
            if not job_name or not job_name.strip():
                job_name = f"Fine-Tune {job_id[:8]}"
            
            # --- SAVE METADATA TO ADAPTER DIR (User Request) ---
            metadata_path = job_adapter_dir / "metadata.json"
            metadata = {
                "job_name": job_name,
                "job_id": job_id,
                "base_model": model_id,
                "params": config
            }
            
            # --- SAVE ADAPTER CONFIG (Required for Inference) ---
            adapter_config_path = job_adapter_dir / "adapter_config.json"
            
            # Enrich lora_config with base model info
            base_model_type = "llama" # Default
            if hasattr(model_config, "model_type"):
                base_model_type = model_config.model_type
            elif isinstance(model_config, dict) and "model_type" in model_config:
                base_model_type = model_config["model_type"]

            # MLX-LM expects a specific structure for adapter config
            # Based on errors: needs 'num_layers' and 'lora_parameters'
            final_adapter_config = {
                "num_layers": lora_config["num_layers"],
                "model_type": base_model_type,
                "base_model_name_or_path": model_id,
                "lora_parameters": {
                    "rank": lora_config["rank"],
                    "alpha": lora_config["alpha"],
                    "scale": lora_config["scale"],
                    "dropout": lora_config["dropout"],
                    "keys": lora_config["keys"]
                }
            }

            try:
                import json
                # Save metadata
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=4)
                    
                # Save adapter config
                with open(adapter_config_path, 'w') as f:
                    json.dump(final_adapter_config, f, indent=4)
                    
            except Exception as e:
                print(f"Failed to save metadata or adapter config: {e}")

            ft_model_entry = {
                "id": f"ft-{job_id}", # Unique ID for the fine-tuned model
                "name": job_name,
                "base_model": model_id,
                "adapter_path": str(job_adapter_dir), # Point to directory for MLX load
                "size": "Adapter", # Or calculate size?
                "family": "Custom",
                "is_custom": True,
                "is_finetuned": True,
                "params": {
                    "epochs": epochs,
                    "batch_size": batch_size,
                    "lora_rank": lora_rank,
                    "lora_alpha": lora_alpha,
                    "learning_rate": lr,
                    "max_seq_len": max_seq_length,
                    "dropout": lora_dropout,
                    "lora_layers": lora_layers
                }
            }
            self.models_config.append(ft_model_entry)
            self._save_models_config()
            print(f"Registered fine-tuned model: {ft_model_entry['name']}")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Training failed: {e}")
            self.active_jobs[job_id]["status"] = "failed"
            self.active_jobs[job_id]["error"] = str(e)

    def get_job_status(self, job_id: str):
        return self.active_jobs.get(job_id, {"status": "not_found"})

    def _get_model_config_by_id(self, model_id: str):
        for m in self.models_config:
            if m["id"] == model_id:
                return m
        return None

    async def get_model_and_tokenizer(self, model_id: str):
        if model_id not in self.loaded_models:
            print(f"Loading model: {model_id}")
            
            path_to_load = model_id
            adapter_path = None
            
            # Check if it's a known config first
            config_entry = self._get_model_config_by_id(model_id)
            
            if config_entry:
                if config_entry.get("is_finetuned"):
                    # loading fine-tuned model: base + adapter
                    path_to_load = config_entry["base_model"]
                    adapter_path = config_entry["adapter_path"]
                    print(f"Identified fine-tuned model. Base: {path_to_load}, Adapter: {adapter_path}")
                elif Path(config_entry["id"]).is_absolute():
                     path_to_load = config_entry["id"]
                else:
                    # Standard model, check for local download
                    sanitized_name = model_id.replace("/", "--")
                    local_path = self.models_dir / sanitized_name
                    if (local_path / ".completed").exists():
                         path_to_load = str(local_path)
            else:
                # Fallback logic for raw IDs passed directly
                if Path(model_id).is_absolute() and Path(model_id).exists():
                     path_to_load = model_id
                else:
                    sanitized_name = model_id.replace("/", "--")
                    local_path = self.models_dir / sanitized_name
                    if (local_path / ".completed").exists():
                        path_to_load = str(local_path)
            
            print(f"Loading from: {path_to_load} (Adapter: {adapter_path})")

            # This loads the model weights into memory.
            loop = asyncio.get_running_loop()
            
            if adapter_path:
                 # Load with adapter
                 model, tokenizer = await loop.run_in_executor(
                    None, 
                    lambda: load(path_to_load, adapter_path=adapter_path)
                )
            else:
                model, tokenizer = await loop.run_in_executor(None, load, path_to_load)
                
            self.loaded_models[model_id] = (model, tokenizer)
        return self.loaded_models[model_id]

    def get_models_status(self):
        """
        Returns the list of supported models with their local download status.
        Uses self.models_config which includes custom registered models.
        """
        models = []
        for m in self.models_config:
            # Check if model exists locally
            
            is_downloaded = False
            model_path = None
            is_downloading = m["id"] in self.active_downloads
            
            # 1. Custom Path? (Legacy custom registration)
            if "is_finetuned" in m and m["is_finetuned"]:
                 is_downloaded = True # Always "downloaded" if it's a local fine-tune
            elif Path(m["id"]).is_absolute():
                if Path(m["id"]).exists():
                    is_downloaded = True
                    model_path = str(Path(m["id"]))
                    
                    # Backfill size if missing or 'Custom'
                    if m.get("size") == "Custom":
                        print(f"Backfilling size for {m['name']}")
                        new_size = self._get_dir_size_str(Path(m["id"]))
                        m["size"] = new_size # Update in memory
                        # We should save this back to JSON so we don't recalc every second
                        # But loop overhead to save inside loop is bad. 
                        # We can defer save? For now just in-memory update is visible to UI.
                        
            else:
                # 2. Standard Downloaded Model
                sanitized_name = m["id"].replace("/", "--")
                local_path = self.models_dir / sanitized_name
                # Only check for follow-up .completed file
                if (local_path / ".completed").exists():
                    is_downloaded = True
                    model_path = str(local_path)
            
            entry = {
                **m,
                "downloaded": is_downloaded,
                "downloading": is_downloading, 
                "local_path": model_path
            }
            
            # --- Metadata Recovery Logic ---
            # If name looks like generic ID and it's a fine-tune, try to read metadata.json
            if entry["name"].startswith("Fine-Tune ") and "adapter_path" in m:
                try:
                    # adapter_path points to .safetensors file. Parent is the dir.
                    adapter_file = Path(m["adapter_path"])
                    meta_path = adapter_file.parent / "metadata.json"
                    if meta_path.exists():
                        import json
                        with open(meta_path, 'r') as f:
                            meta = json.load(f)
                            if "job_name" in meta and meta["job_name"]:
                                entry["name"] = meta["job_name"]
                                # Optional: update config in memory to persist next save
                                m["name"] = meta["job_name"] 
                except Exception:
                    pass

            models.append(entry)
        return models

    def download_model(self, model_id: str):
        """
        Downloads a model to the local models directory.
        This is a blocking operation (run in Bg Task), handles markers.
        """
        if model_id in self.active_downloads:
            print(f"Model {model_id} already downloading.")
            return

        self.active_downloads.add(model_id)
        try:
            from huggingface_hub import snapshot_download
            
            print(f"Downloading {model_id} to {self.models_dir}...")
            sanitized_name = model_id.replace("/", "--")
            local_dir = self.models_dir / sanitized_name
            
            # Remove partial .completed if it exists (shouldn't, but safety)
            marker_file = local_dir / ".completed"
            if marker_file.exists():
                os.remove(marker_file)
            
            snapshot_download(
                repo_id=model_id,
                local_dir=local_dir,
                local_dir_use_symlinks=False,
                # Force allowing patterns if needed? Default is all.
            )
            
            # Write marker file
            with open(marker_file, 'w') as f:
                f.write("ok")
                
            print(f"Successfully downloaded {model_id}")
            return True
        except Exception as e:
            print(f"Failed to download {model_id}: {e}")
            raise e
        finally:
            self.active_downloads.discard(model_id)
            
    def delete_model(self, model_id: str):
        """
        Deletes a local model from disk.
        Handles both standard downloaded models and custom registered models.
        """
        try:
            # Check if it's a custom/finetuned model in config
            config_entry = self._get_model_config_by_id(model_id)
            
            if config_entry and config_entry.get("is_custom"):
                print(f"Deleting custom model: {model_id} ({config_entry['name']})")
                
                # 1. Remove from config
                self.models_config = [m for m in self.models_config if m["id"] != model_id]
                self._save_models_config()
                
                # 2. Delete files if it's a fine-tune (adapter path)
                if config_entry.get("is_finetuned") and "adapter_path" in config_entry:
                    adapter_path = Path(config_entry["adapter_path"])
                    if adapter_path.exists() and adapter_path.is_dir():
                        import shutil
                        print(f"Removing adapter directory: {adapter_path}")
                        shutil.rmtree(adapter_path)
                
                # 3. Delete files if it's a User Added Foundation Model (Absolute Path)
                elif Path(model_id).is_absolute() and Path(model_id).exists():
                     target_path = Path(model_id)
                     # SAFETY CHECK: Only delete if path contains 'models' to prevent system damage
                     if "models" in str(target_path).lower() and target_path.is_dir():
                         import shutil
                         print(f"Removing user model directory: {target_path}")
                         shutil.rmtree(target_path)
                     else:
                         print(f"Skipping disk deletion for safety (not in 'models' folder?): {target_path}")

                return True

            # Standard Downloaded Model Logic
            sanitized_name = model_id.replace("/", "--")
            local_dir = self.models_dir / sanitized_name
            
            if local_dir.exists():
                print(f"Deleting foundation model {model_id} at {local_dir}")
                import shutil
                shutil.rmtree(local_dir)
                return True
            else:
                print(f"Model {model_id} not found at {local_dir}")
                return False
        except Exception as e:
            print(f"Failed to delete {model_id}: {e}")
            raise e
