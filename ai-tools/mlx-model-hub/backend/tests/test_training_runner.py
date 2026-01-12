"""Tests for training runner module."""

import pytest
from unittest.mock import MagicMock, patch

from mlx_hub.training.runner import TrainingConfig, TrainingResult


class TestTrainingConfig:
    """Tests for TrainingConfig dataclass."""

    def test_default_values(self):
        """Config should have sensible defaults."""
        config = TrainingConfig()

        assert config.lora_rank == 16
        assert config.lora_alpha == 32
        assert config.learning_rate == 5e-5
        assert config.epochs == 3
        assert config.batch_size == 4
        assert config.seed == 42
        assert config.max_seq_length == 512

    def test_from_dict_with_all_fields(self):
        """from_dict should create config from complete dictionary."""
        d = {
            "lora_rank": 32,
            "lora_alpha": 64,
            "learning_rate": 1e-4,
            "epochs": 5,
            "batch_size": 8,
            "seed": 123,
        }
        config = TrainingConfig.from_dict(d)

        assert config.lora_rank == 32
        assert config.lora_alpha == 64
        assert config.learning_rate == 1e-4
        assert config.epochs == 5
        assert config.batch_size == 8
        assert config.seed == 123

    def test_from_dict_with_partial_fields(self):
        """from_dict should use defaults for missing fields."""
        d = {"lora_rank": 64}
        config = TrainingConfig.from_dict(d)

        assert config.lora_rank == 64
        assert config.lora_alpha == 32  # default
        assert config.epochs == 3  # default

    def test_from_dict_ignores_unknown_keys(self):
        """from_dict should ignore unknown fields."""
        d = {
            "lora_rank": 32,
            "unknown_field": "ignored",
            "another_unknown": 999,
        }
        config = TrainingConfig.from_dict(d)

        assert config.lora_rank == 32
        assert not hasattr(config, "unknown_field")

    def test_from_dict_empty(self):
        """from_dict with empty dict should use all defaults."""
        config = TrainingConfig.from_dict({})

        assert config.lora_rank == 16
        assert config.epochs == 3

    def test_to_dict_roundtrip(self):
        """to_dict should be reversible with from_dict."""
        original = TrainingConfig(
            lora_rank=32,
            lora_alpha=64,
            epochs=10,
            batch_size=16,
        )

        d = original.to_dict()
        restored = TrainingConfig.from_dict(d)

        assert restored.lora_rank == original.lora_rank
        assert restored.lora_alpha == original.lora_alpha
        assert restored.epochs == original.epochs
        assert restored.batch_size == original.batch_size

    def test_to_dict_contains_all_fields(self):
        """to_dict should include all configurable fields."""
        config = TrainingConfig()
        d = config.to_dict()

        expected_keys = {
            "lora_rank", "lora_alpha", "learning_rate", "epochs",
            "batch_size", "seed", "gradient_accumulation_steps",
            "max_seq_length", "warmup_steps", "weight_decay",
            "lora_dropout", "lora_layers",
        }
        assert set(d.keys()) == expected_keys


class TestTrainingResult:
    """Tests for TrainingResult dataclass."""

    def test_default_values(self):
        """Result should have sensible defaults."""
        result = TrainingResult()

        assert result.run_id is None
        assert result.artifact_path is None
        assert result.final_loss == 0.0
        assert result.total_steps == 0
        assert result.metrics == {}

    def test_with_values(self):
        """Result should store provided values."""
        result = TrainingResult(
            run_id="abc123",
            artifact_path="/path/to/adapter",
            final_loss=0.5,
            total_steps=1000,
            metrics={"epoch_1_loss": 0.8},
        )

        assert result.run_id == "abc123"
        assert result.artifact_path == "/path/to/adapter"
        assert result.final_loss == 0.5
        assert result.total_steps == 1000
        assert result.metrics["epoch_1_loss"] == 0.8


class TestTrainingRunnerInit:
    """Tests for TrainingRunner initialization."""

    @pytest.fixture
    def mock_model(self):
        """Create mock model."""
        model = MagicMock()
        model.name = "test-model"
        model.base_model = "meta-llama/Llama-3.2-1B"
        model.mlflow_experiment_id = None
        return model

    @pytest.fixture
    def mock_dataset(self):
        """Create mock dataset."""
        dataset = MagicMock()
        dataset.name = "test-dataset"
        dataset.path = "/tmp/train.jsonl"
        dataset.checksum = "abc123"
        return dataset

    def test_runner_init_creates_config(self, mock_model, mock_dataset):
        """Runner should create TrainingConfig from dict."""
        from mlx_hub.training.runner import TrainingRunner

        runner = TrainingRunner(
            model=mock_model,
            dataset=mock_dataset,
            config={"lora_rank": 64, "epochs": 10},
        )

        assert runner.config.lora_rank == 64
        assert runner.config.epochs == 10
        assert runner.model_info == mock_model
        assert runner.dataset_info == mock_dataset

    def test_runner_init_with_empty_config(self, mock_model, mock_dataset):
        """Runner should use default config when empty dict provided."""
        from mlx_hub.training.runner import TrainingRunner

        runner = TrainingRunner(
            model=mock_model,
            dataset=mock_dataset,
            config={},
        )

        assert runner.config.lora_rank == 16
        assert runner.config.epochs == 3
