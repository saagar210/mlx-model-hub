"""MLX training runner with LoRA support."""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_flatten

from mlx_hub.config import Settings, get_settings
from mlx_hub.db.models import Dataset, Model

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Training configuration with LoRA parameters."""

    lora_rank: int = 16
    lora_alpha: int = 32
    learning_rate: float = 5e-5
    epochs: int = 3
    batch_size: int = 4
    seed: int = 42
    gradient_accumulation_steps: int = 1
    max_seq_length: int = 512
    warmup_steps: int = 100
    weight_decay: float = 0.01
    lora_dropout: float = 0.0
    lora_layers: int = -1  # -1 means all layers

    @classmethod
    def from_dict(cls, d: dict) -> "TrainingConfig":
        """Create config from dictionary, ignoring unknown keys."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known_fields})

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "lora_rank": self.lora_rank,
            "lora_alpha": self.lora_alpha,
            "learning_rate": self.learning_rate,
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "seed": self.seed,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "max_seq_length": self.max_seq_length,
            "warmup_steps": self.warmup_steps,
            "weight_decay": self.weight_decay,
            "lora_dropout": self.lora_dropout,
            "lora_layers": self.lora_layers,
        }


@dataclass
class TrainingResult:
    """Result of a training run."""

    run_id: str | None = None
    artifact_path: str | None = None
    final_loss: float = 0.0
    total_steps: int = 0
    metrics: dict = field(default_factory=dict)


class TrainingRunner:
    """MLX training runner with LoRA support.

    Handles the full training pipeline:
    1. Load base model from HuggingFace
    2. Apply LoRA adapters
    3. Run training loop
    4. Save adapter weights
    5. Log to MLflow
    """

    def __init__(
        self,
        model: Model,
        dataset: Dataset,
        config: dict,
        settings: Settings | None = None,
    ):
        """Initialize the training runner.

        Args:
            model: Model database record with base_model HF ID.
            dataset: Dataset database record with file path.
            config: Training configuration dictionary.
            settings: Application settings (optional, uses default if not provided).
        """
        self.model_info = model
        self.dataset_info = dataset
        self.config = TrainingConfig.from_dict(config)
        self.settings = settings or get_settings()

        # Will be set during training
        self.mlx_model: Any = None
        self.tokenizer: Any = None
        self.optimizer: optim.Optimizer | None = None

    async def run(self) -> dict:
        """Execute the training loop.

        Returns:
            Dictionary with run_id, artifact_path, final_loss, total_steps.
        """
        logger.info(f"Starting training for model {self.model_info.name}")
        logger.info(f"Config: {self.config.to_dict()}")

        # Set seed for reproducibility
        mx.random.seed(self.config.seed)

        # Load model and tokenizer
        await self._load_model()

        # Load dataset
        train_data = await self._load_dataset()

        if not train_data:
            raise ValueError("Dataset is empty or could not be loaded")

        # Setup optimizer
        self._setup_optimizer()

        # Try to use MLflow if available
        mlflow_run_id = None
        try:
            import mlflow

            mlflow.set_tracking_uri(self.settings.mlflow_tracking_uri)

            if self.model_info.mlflow_experiment_id:
                mlflow.set_experiment(experiment_id=self.model_info.mlflow_experiment_id)

            with mlflow.start_run(
                run_name=f"train-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
            ) as run:
                mlflow_run_id = run.info.run_id
                result = await self._train_with_mlflow(train_data, mlflow)

        except Exception as e:
            logger.warning(f"MLflow unavailable, training without tracking: {e}")
            result = await self._train_without_mlflow(train_data)

        result["run_id"] = mlflow_run_id
        return result

    async def _train_with_mlflow(self, train_data: list[dict], mlflow: Any) -> dict:
        """Run training with MLflow logging."""
        # Log parameters
        mlflow.log_params(self.config.to_dict())
        mlflow.log_param("base_model", self.model_info.base_model)
        mlflow.log_param("dataset_checksum", self.dataset_info.checksum)
        mlflow.log_param("dataset_size", len(train_data))

        # Run training loop
        result = await self._training_loop(
            train_data,
            log_fn=lambda metrics, step: mlflow.log_metrics(metrics, step=step),
        )

        # Log artifact
        if result.get("artifact_path"):
            mlflow.log_artifact(result["artifact_path"])

        return result

    async def _train_without_mlflow(self, train_data: list[dict]) -> dict:
        """Run training without MLflow (fallback)."""
        return await self._training_loop(train_data, log_fn=None)

    async def _training_loop(
        self,
        train_data: list[dict],
        log_fn: Any | None = None,
    ) -> dict:
        """Core training loop.

        Args:
            train_data: List of training examples.
            log_fn: Optional function to log metrics (step) -> None.

        Returns:
            Training result dictionary.
        """
        total_loss = 0.0
        step = 0
        all_metrics: list[dict] = []

        num_batches = max(1, len(train_data) // self.config.batch_size)
        total_steps = num_batches * self.config.epochs

        logger.info(
            f"Training for {self.config.epochs} epochs, "
            f"{num_batches} batches per epoch, "
            f"{total_steps} total steps"
        )

        for epoch in range(self.config.epochs):
            epoch_loss = 0.0
            epoch_steps = 0

            for batch in self._batch_iterator(train_data):
                loss, grads = self._train_step(batch)

                # Check for NaN/Inf
                if self._check_nan_inf(loss):
                    error_msg = f"NaN/Inf loss detected at step {step}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                # Update model
                self.optimizer.update(self.mlx_model, grads)
                mx.eval(self.mlx_model.parameters(), self.optimizer.state)

                loss_val = loss.item()
                epoch_loss += loss_val
                total_loss += loss_val
                step += 1
                epoch_steps += 1

                # Log metrics periodically
                if step % 10 == 0:
                    metrics = {
                        "loss": loss_val,
                        "epoch": epoch,
                        "step": step,
                        "progress": step / total_steps,
                    }
                    all_metrics.append(metrics)

                    if log_fn:
                        try:
                            log_fn(metrics, step)
                        except Exception as e:
                            logger.warning(f"Failed to log metrics: {e}")

                    logger.debug(f"Step {step}/{total_steps}, Loss: {loss_val:.4f}")

            avg_epoch_loss = epoch_loss / max(1, epoch_steps)
            logger.info(
                f"Epoch {epoch + 1}/{self.config.epochs} complete, Avg Loss: {avg_epoch_loss:.4f}"
            )

        # Save adapter
        artifact_path = await self._save_adapter()

        final_loss = total_loss / max(1, step)
        logger.info(f"Training complete. Final loss: {final_loss:.4f}")

        return {
            "artifact_path": str(artifact_path),
            "final_loss": final_loss,
            "total_steps": step,
            "metrics": {
                "epochs_completed": self.config.epochs,
                "final_loss": final_loss,
                "total_steps": step,
            },
        }

    async def _load_model(self) -> None:
        """Load the base model with LoRA adapters."""
        from mlx_lm import load

        logger.info(f"Loading base model: {self.model_info.base_model}")

        try:
            self.mlx_model, self.tokenizer = load(
                self.model_info.base_model,
                tokenizer_config={"trust_remote_code": True},
            )
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise ValueError(f"Failed to load base model: {e}") from e

        # Apply LoRA adapters
        self._apply_lora()

        # Log parameter counts
        total_params = sum(p.size for _, p in tree_flatten(self.mlx_model.parameters()))
        trainable_params = sum(
            p.size for name, p in tree_flatten(self.mlx_model.trainable_parameters())
        )
        logger.info(
            f"Model loaded. Total params: {total_params:,}, "
            f"Trainable params: {trainable_params:,} "
            f"({100 * trainable_params / total_params:.2f}%)"
        )

    def _apply_lora(self) -> None:
        """Apply LoRA adapters to the model."""
        from mlx_lm.tuner.utils import apply_lora_layers

        # Determine which layers to adapt
        num_layers = len(self.mlx_model.model.layers)
        if self.config.lora_layers == -1:
            # Apply to all layers
            lora_layers = num_layers
        else:
            lora_layers = min(self.config.lora_layers, num_layers)

        logger.info(f"Applying LoRA to {lora_layers} layers")

        # Apply LoRA using mlx-lm utilities
        apply_lora_layers(
            self.mlx_model,
            num_lora_layers=lora_layers,
            lora_parameters={
                "rank": self.config.lora_rank,
                "alpha": self.config.lora_alpha,
                "dropout": self.config.lora_dropout,
                "scale": self.config.lora_alpha / self.config.lora_rank,
            },
        )

        # Freeze base model, only train LoRA
        self.mlx_model.freeze()

        # Unfreeze LoRA parameters
        for name, module in self.mlx_model.named_modules():
            if "lora" in name.lower():
                module.unfreeze()

    async def _load_dataset(self) -> list[dict]:
        """Load and preprocess the training dataset."""
        dataset_path = Path(self.dataset_info.path)

        if not dataset_path.exists():
            raise ValueError(f"Dataset file not found: {dataset_path}")

        data = []
        with open(dataset_path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    item = json.loads(line)
                    # Expect chat format: {"messages": [{"role": "...", "content": "..."}]}
                    if "messages" in item and isinstance(item["messages"], list):
                        data.append(item)
                    else:
                        logger.warning(f"Line {line_num}: Missing or invalid 'messages' field")
                except json.JSONDecodeError as e:
                    logger.warning(f"Line {line_num}: Invalid JSON - {e}")

        logger.info(f"Loaded {len(data)} training examples from {dataset_path}")
        return data

    def _setup_optimizer(self) -> None:
        """Setup the optimizer with warmup schedule."""
        # Create learning rate schedule with warmup
        if self.config.warmup_steps > 0:
            warmup_scheduler = optim.linear_schedule(
                init=1e-7,
                end=self.config.learning_rate,
                steps=self.config.warmup_steps,
            )
            lr_schedule = optim.join_schedules(
                [warmup_scheduler],
                [self.config.warmup_steps],
            )
        else:
            lr_schedule = self.config.learning_rate

        self.optimizer = optim.AdamW(
            learning_rate=lr_schedule,
            weight_decay=self.config.weight_decay,
        )

    def _batch_iterator(self, data: list[dict]):
        """Iterate over data in batches."""
        # Shuffle data for each epoch
        import random

        shuffled = data.copy()
        random.shuffle(shuffled)

        for i in range(0, len(shuffled), self.config.batch_size):
            batch = shuffled[i : i + self.config.batch_size]
            yield self._prepare_batch(batch)

    def _prepare_batch(self, batch: list[dict]) -> dict:
        """Prepare a batch for training."""
        texts = []
        for item in batch:
            text = self._format_chat(item["messages"])
            texts.append(text)

        # Tokenize
        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.config.max_seq_length,
            return_tensors="np",
        )

        return {
            "input_ids": mx.array(encoded["input_ids"]),
            "attention_mask": mx.array(encoded.get("attention_mask", None)),
        }

    def _format_chat(self, messages: list[dict]) -> str:
        """Format chat messages for training."""
        # Use tokenizer's chat template if available
        if hasattr(self.tokenizer, "apply_chat_template"):
            try:
                return self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=False,
                )
            except Exception:
                pass

        # Fallback formatting
        text = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            text += f"<|{role}|>\n{content}\n"
        return text

    def _train_step(self, batch: dict) -> tuple[mx.array, dict]:
        """Execute a single training step."""

        def loss_fn(model):
            logits = model(batch["input_ids"])
            # Shift for causal LM loss
            shift_logits = logits[:, :-1, :]
            shift_labels = batch["input_ids"][:, 1:]

            loss = nn.losses.cross_entropy(
                shift_logits.reshape(-1, shift_logits.shape[-1]),
                shift_labels.reshape(-1),
                reduction="mean",
            )
            return loss

        loss_and_grad_fn = nn.value_and_grad(self.mlx_model, loss_fn)
        loss, grads = loss_and_grad_fn(self.mlx_model)

        return loss, grads

    def _check_nan_inf(self, loss: mx.array) -> bool:
        """Check if loss contains NaN or Inf."""
        loss_val = loss.item()
        return loss_val != loss_val or abs(loss_val) == float("inf")

    async def _save_adapter(self) -> Path:
        """Save the LoRA adapter weights."""
        # Create versioned directory
        version = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        adapter_dir = (
            self.settings.storage_models_path / self.model_info.name / "versions" / version
        )
        adapter_dir.mkdir(parents=True, exist_ok=True)

        adapter_path = adapter_dir / "adapter.safetensors"

        # Extract LoRA weights
        lora_weights = {}
        for name, param in tree_flatten(self.mlx_model.trainable_parameters()):
            lora_weights[name] = param

        if not lora_weights:
            logger.warning("No LoRA weights found to save")

        # Save with atomic write (temp file + rename)
        temp_path = adapter_path.with_suffix(".tmp")
        mx.save_safetensors(str(temp_path), lora_weights)
        temp_path.rename(adapter_path)

        # Calculate and save checksum
        checksum = self._calculate_checksum(adapter_path)
        checksum_path = adapter_dir / "checksum.sha256"
        checksum_path.write_text(checksum)

        # Save config
        config_path = adapter_dir / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "lora_rank": self.config.lora_rank,
                    "lora_alpha": self.config.lora_alpha,
                    "base_model": self.model_info.base_model,
                    "dataset_checksum": self.dataset_info.checksum,
                    "seed": self.config.seed,
                    "training_config": self.config.to_dict(),
                },
                indent=2,
            )
        )

        logger.info(f"Saved adapter to {adapter_path}")
        return adapter_path

    def _calculate_checksum(self, path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
