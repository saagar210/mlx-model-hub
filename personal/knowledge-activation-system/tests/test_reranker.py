"""Tests for the local reranker module.

Tests cover:
- Model loading behavior (lazy load, preload)
- Synchronous and asynchronous prediction
- Reranking logic and score handling
- Fallback behavior when model unavailable
- Global instance management
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from knowledge.search import SearchResult


class TestLocalReranker:
    """Tests for LocalReranker class."""

    def test_init_without_loading_model(self):
        """Test reranker initialization doesn't load model immediately."""
        from knowledge.reranker import LocalReranker

        with patch("sentence_transformers.CrossEncoder", MagicMock()) as mock_ce:
            reranker = LocalReranker(model_name="test-model")

            # Model should not be loaded yet
            mock_ce.assert_not_called()
            assert reranker._model is None

    def test_lazy_loading_on_first_use(self):
        """Test model is loaded on first prediction call."""
        from knowledge.reranker import LocalReranker
        import numpy as np

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.5])

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model) as mock_ce, \
             patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=False):

            reranker = LocalReranker(model_name="test-model")

            # First prediction should trigger load
            reranker._predict_sync([["query", "doc"]])

            mock_ce.assert_called_once()
            assert reranker._model is not None

    def test_preload_explicit(self):
        """Test explicit model preloading."""
        from knowledge.reranker import LocalReranker

        mock_model = MagicMock()

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model) as mock_ce, \
             patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=False):

            reranker = LocalReranker(model_name="test-model")
            reranker.preload()

            mock_ce.assert_called_once()

    def test_device_detection_mps(self):
        """Test device detection selects MPS on Apple Silicon."""
        from knowledge.reranker import LocalReranker

        mock_model = MagicMock()

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model) as mock_ce, \
             patch("torch.backends.mps.is_available", return_value=True):

            reranker = LocalReranker(model_name="test-model")
            reranker._load_model()

            # Check MPS device was used
            mock_ce.assert_called_once()
            call_kwargs = mock_ce.call_args.kwargs
            assert call_kwargs.get("device") == "mps"

    def test_device_detection_cuda(self):
        """Test device detection selects CUDA when available."""
        from knowledge.reranker import LocalReranker

        mock_model = MagicMock()

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model) as mock_ce, \
             patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=True):

            reranker = LocalReranker(model_name="test-model")
            reranker._load_model()

            call_kwargs = mock_ce.call_args.kwargs
            assert call_kwargs.get("device") == "cuda"

    def test_device_detection_cpu_fallback(self):
        """Test device detection falls back to CPU."""
        from knowledge.reranker import LocalReranker

        mock_model = MagicMock()

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model) as mock_ce, \
             patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=False):

            reranker = LocalReranker(model_name="test-model")
            reranker._load_model()

            call_kwargs = mock_ce.call_args.kwargs
            assert call_kwargs.get("device") == "cpu"

    def test_explicit_device_override(self):
        """Test explicit device parameter overrides auto-detection."""
        from knowledge.reranker import LocalReranker

        mock_model = MagicMock()

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model) as mock_ce:
            # Even if MPS/CUDA available, explicit device should be used
            reranker = LocalReranker(model_name="test-model", device="cpu")
            reranker._load_model()

            call_kwargs = mock_ce.call_args.kwargs
            assert call_kwargs.get("device") == "cpu"


class TestRerankerPrediction:
    """Tests for reranker prediction methods."""

    def test_sync_prediction(self):
        """Test synchronous prediction returns scores."""
        from knowledge.reranker import LocalReranker
        import numpy as np

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.9, 0.5, 0.3])

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model), \
             patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=False):

            reranker = LocalReranker(model_name="test-model")

            pairs = [
                ["query", "doc1"],
                ["query", "doc2"],
                ["query", "doc3"],
            ]
            scores = reranker._predict_sync(pairs)

            assert len(scores) == 3
            assert scores[0] == 0.9
            assert scores[1] == 0.5
            assert scores[2] == 0.3

    @pytest.mark.asyncio
    async def test_async_prediction(self):
        """Test async prediction doesn't block event loop."""
        from knowledge.reranker import LocalReranker
        import numpy as np

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.8, 0.6])

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model), \
             patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=False):

            reranker = LocalReranker(model_name="test-model")

            pairs = [["query", "doc1"], ["query", "doc2"]]
            scores = await reranker._predict_async(pairs)

            assert len(scores) == 2
            assert scores[0] == 0.8

    def test_rerank_empty_results(self):
        """Test reranking with empty results returns empty list."""
        from knowledge.reranker import LocalReranker

        reranker = LocalReranker(model_name="test-model")
        results = reranker.rerank("query", [])

        assert results == []

    def test_rerank_with_results(self):
        """Test reranking reorders results by score."""
        from knowledge.reranker import LocalReranker, RerankResult
        import numpy as np

        mock_model = MagicMock()
        # Return scores in reverse order to test sorting
        mock_model.predict.return_value = np.array([0.3, 0.9, 0.6])

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model), \
             patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=False):

            reranker = LocalReranker(model_name="test-model")

            results = [
                SearchResult(content_id=uuid4(), title="First", content_type="note", score=0.5, chunk_text="doc1"),
                SearchResult(content_id=uuid4(), title="Second", content_type="note", score=0.6, chunk_text="doc2"),
                SearchResult(content_id=uuid4(), title="Third", content_type="note", score=0.7, chunk_text="doc3"),
            ]

            reranked = reranker.rerank("query", results)

            # Should be reordered: Second (0.9), Third (0.6), First (0.3)
            assert len(reranked) == 3
            assert reranked[0].rerank_score == 0.9
            assert reranked[0].result.title == "Second"
            assert reranked[1].rerank_score == 0.6
            assert reranked[2].rerank_score == 0.3

    def test_rerank_with_top_k(self):
        """Test reranking respects top_k limit."""
        from knowledge.reranker import LocalReranker
        import numpy as np

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.3, 0.9, 0.6, 0.4])

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model), \
             patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=False):

            reranker = LocalReranker(model_name="test-model")

            results = [
                SearchResult(content_id=uuid4(), title=f"Doc{i}", content_type="note", score=0.5, chunk_text=f"doc{i}")
                for i in range(4)
            ]

            reranked = reranker.rerank("query", results, top_k=2)

            assert len(reranked) == 2
            assert reranked[0].rerank_score == 0.9
            assert reranked[1].rerank_score == 0.6

    def test_rerank_uses_chunk_text_over_title(self):
        """Test reranking uses chunk_text when available."""
        from knowledge.reranker import LocalReranker
        import numpy as np

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.8])

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model), \
             patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=False):

            reranker = LocalReranker(model_name="test-model")

            results = [
                SearchResult(
                    content_id=uuid4(),
                    title="Short Title",
                    content_type="note",
                    score=0.5,
                    chunk_text="This is the full chunk text that should be used for reranking",
                ),
            ]

            reranker.rerank("query", results)

            # Check that predict was called with chunk_text, not title
            call_args = mock_model.predict.call_args[0][0]
            assert call_args[0][1] == "This is the full chunk text that should be used for reranking"

    def test_rerank_falls_back_to_title(self):
        """Test reranking falls back to title when chunk_text is None."""
        from knowledge.reranker import LocalReranker
        import numpy as np

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.8])

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model), \
             patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=False):

            reranker = LocalReranker(model_name="test-model")

            results = [
                SearchResult(
                    content_id=uuid4(),
                    title="This Title Should Be Used",
                    content_type="note",
                    score=0.5,
                    chunk_text=None,  # No chunk text
                ),
            ]

            reranker.rerank("query", results)

            call_args = mock_model.predict.call_args[0][0]
            assert call_args[0][1] == "This Title Should Be Used"


class TestAsyncReranking:
    """Tests for async reranking methods."""

    @pytest.mark.asyncio
    async def test_rerank_async_empty_results(self):
        """Test async reranking with empty results."""
        from knowledge.reranker import LocalReranker

        reranker = LocalReranker(model_name="test-model")
        results = await reranker.rerank_async("query", [])

        assert results == []

    @pytest.mark.asyncio
    async def test_rerank_async_returns_sorted(self):
        """Test async reranking returns sorted results."""
        from knowledge.reranker import LocalReranker
        import numpy as np

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.2, 0.8])

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model), \
             patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=False):

            reranker = LocalReranker(model_name="test-model")

            results = [
                SearchResult(content_id=uuid4(), title="Low", content_type="note", score=0.5, chunk_text="doc1"),
                SearchResult(content_id=uuid4(), title="High", content_type="note", score=0.5, chunk_text="doc2"),
            ]

            reranked = await reranker.rerank_async("query", results)

            assert reranked[0].result.title == "High"
            assert reranked[0].rerank_score == 0.8

    @pytest.mark.asyncio
    async def test_rerank_async_with_top_k(self):
        """Test async reranking respects top_k."""
        from knowledge.reranker import LocalReranker
        import numpy as np

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.3, 0.9, 0.6])

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model), \
             patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=False):

            reranker = LocalReranker(model_name="test-model")

            results = [
                SearchResult(content_id=uuid4(), title=f"Doc{i}", content_type="note", score=0.5, chunk_text=f"doc{i}")
                for i in range(3)
            ]

            reranked = await reranker.rerank_async("query", results, top_k=1)

            assert len(reranked) == 1
            assert reranked[0].rerank_score == 0.9


class TestGlobalRerankerInstance:
    """Tests for global reranker instance management."""

    def test_get_reranker_creates_singleton(self):
        """Test get_reranker returns same instance."""
        import knowledge.reranker as reranker_module
        from knowledge.reranker import get_reranker

        # Reset global state
        reranker_module._reranker = None

        reranker1 = get_reranker("model1")
        reranker2 = get_reranker("model2")  # Model name ignored after first call

        assert reranker1 is reranker2

    @pytest.mark.asyncio
    async def test_preload_reranker_creates_task(self):
        """Test preload_reranker creates background task."""
        import knowledge.reranker as reranker_module
        from knowledge.reranker import preload_reranker

        # Reset global state
        reranker_module._reranker = None
        reranker_module._preload_task = None

        with patch.object(reranker_module, "get_reranker") as mock_get_reranker:
            mock_reranker = MagicMock()
            mock_reranker.preload = MagicMock()
            mock_get_reranker.return_value = mock_reranker

            await preload_reranker("test-model")

            # Give the background task time to run
            await asyncio.sleep(0.1)

            assert reranker_module._preload_task is not None

    @pytest.mark.asyncio
    async def test_close_local_reranker_cleans_up(self):
        """Test close_local_reranker cleans up resources."""
        import knowledge.reranker as reranker_module
        from knowledge.reranker import close_local_reranker

        # Set up some state
        reranker_module._reranker = MagicMock()
        reranker_module._preload_task = asyncio.create_task(asyncio.sleep(10))

        await close_local_reranker()

        assert reranker_module._reranker is None
        assert reranker_module._preload_task is None


class TestRerankResultsConvenience:
    """Tests for rerank_results convenience function."""

    @pytest.mark.asyncio
    async def test_rerank_results_returns_search_results(self):
        """Test rerank_results returns updated SearchResult objects."""
        import knowledge.reranker as reranker_module
        from knowledge.reranker import rerank_results
        import numpy as np

        # Reset global state
        reranker_module._reranker = None

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.95, 0.75])

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model), \
             patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=False):

            input_results = [
                SearchResult(content_id=uuid4(), title="First", content_type="note", score=0.5, chunk_text="doc1"),
                SearchResult(content_id=uuid4(), title="Second", content_type="note", score=0.6, chunk_text="doc2"),
            ]

            output = await rerank_results("query", input_results)

            # Should return SearchResult objects (not RerankResult)
            assert all(isinstance(r, SearchResult) for r in output)

            # Scores should be updated to rerank scores
            assert output[0].score == 0.95
            assert output[1].score == 0.75

            # Should be sorted by rerank score
            assert output[0].score >= output[1].score

    @pytest.mark.asyncio
    async def test_rerank_results_preserves_metadata(self):
        """Test rerank_results preserves all result metadata."""
        import knowledge.reranker as reranker_module
        from knowledge.reranker import rerank_results
        import numpy as np

        reranker_module._reranker = None

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.9])

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model), \
             patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=False):

            content_id = uuid4()
            input_results = [
                SearchResult(
                    content_id=content_id,
                    title="Test Title",
                    content_type="youtube",
                    score=0.5,
                    chunk_text="Test chunk",
                    source_ref="timestamp:1:23",
                    bm25_rank=1,
                    vector_rank=2,
                ),
            ]

            output = await rerank_results("query", input_results)

            assert output[0].content_id == content_id
            assert output[0].title == "Test Title"
            assert output[0].content_type == "youtube"
            assert output[0].chunk_text == "Test chunk"
            assert output[0].source_ref == "timestamp:1:23"
            assert output[0].bm25_rank == 1
            assert output[0].vector_rank == 2


class TestErrorHandling:
    """Tests for error handling and fallback behavior."""

    def test_import_error_when_sentence_transformers_missing(self):
        """Test proper error when sentence-transformers not installed."""
        from knowledge.reranker import LocalReranker
        import sys

        # Remove the module from sys.modules to simulate not installed
        saved_module = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = None

        try:
            reranker = LocalReranker(model_name="test-model")

            with pytest.raises(ImportError) as exc_info:
                reranker._load_model()

            assert "sentence-transformers" in str(exc_info.value)
        finally:
            # Restore module
            if saved_module is not None:
                sys.modules["sentence_transformers"] = saved_module
            else:
                sys.modules.pop("sentence_transformers", None)

    def test_model_already_loaded_skips_reload(self):
        """Test _load_model doesn't reload if already loaded."""
        from knowledge.reranker import LocalReranker

        mock_model = MagicMock()

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model) as mock_ce, \
             patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=False):

            reranker = LocalReranker(model_name="test-model")
            reranker._load_model()
            reranker._load_model()  # Second call

            # CrossEncoder should only be called once
            assert mock_ce.call_count == 1

    @pytest.mark.asyncio
    async def test_preload_handles_failure_gracefully(self):
        """Test preload_reranker handles failures without crashing."""
        import knowledge.reranker as reranker_module
        from knowledge.reranker import preload_reranker

        reranker_module._reranker = None
        reranker_module._preload_task = None

        with patch("sentence_transformers.CrossEncoder", side_effect=Exception("Model load failed")), \
             patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=False):

            # Should not raise exception
            await preload_reranker("test-model")

            # Give task time to fail
            await asyncio.sleep(0.1)

            # Task should complete (with warning logged)
            assert reranker_module._preload_task is not None
