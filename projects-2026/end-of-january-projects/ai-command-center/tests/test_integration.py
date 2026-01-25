"""
Integration tests for AI Command Center.

These tests require running services:
- Smart Router on port 4000
- LiteLLM on port 4001
- Ollama on port 11434
"""

import os

import httpx
import pytest

# Configuration
ROUTER_URL = "http://localhost:4000"
LITELLM_URL = "http://localhost:4001"
API_KEY = os.getenv("AICC_MASTER_KEY", "sk-command-center-local")


@pytest.fixture
def client():
    """HTTP client with auth headers."""
    return httpx.Client(
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        timeout=60.0,
    )


class TestSmartRouter:
    """Integration tests for Smart Router."""

    def test_health(self, client):
        """Router health endpoint responds."""
        response = client.get(f"{ROUTER_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_simple_completion(self, client):
        """Simple chat completion works."""
        response = client.post(
            f"{ROUTER_URL}/v1/chat/completions",
            json={
                "model": "llama-fast",
                "messages": [{"role": "user", "content": "Say hi"}],
                "max_tokens": 10,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0

    def test_routing_metadata(self, client):
        """Response includes routing metadata."""
        response = client.post(
            f"{ROUTER_URL}/v1/chat/completions",
            json={
                "model": "qwen-local",
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 10,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "_routing" in data
        assert "routed_model" in data["_routing"]

    def test_sensitive_routing(self, client):
        """Sensitive content routes to local model."""
        response = client.post(
            f"{ROUTER_URL}/v1/chat/completions",
            json={
                "model": "deepseek-local",
                "messages": [{"role": "user", "content": "My password is secret"}],
                "max_tokens": 10,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["_routing"]["is_sensitive"]
        assert data["_routing"]["routed_model"] == "llama-fast"

    def test_complex_routing(self, client):
        """Complex prompts route to powerful model."""
        response = client.post(
            f"{ROUTER_URL}/v1/chat/completions",
            json={
                "model": "llama-fast",
                "messages": [
                    {"role": "user", "content": "Explain step by step why water boils"}
                ],
                "max_tokens": 20,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["_routing"]["complexity"] == "complex"

    def test_list_models(self, client):
        """Models endpoint works."""
        response = client.get(f"{ROUTER_URL}/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_metrics_endpoint(self, client):
        """Metrics endpoint returns valid JSON schema."""
        response = client.get(f"{ROUTER_URL}/metrics")
        assert response.status_code == 200
        data = response.json()
        # Validate schema matches desktop/src/lib/types.ts Metrics interface
        assert "requests" in data
        assert "total" in data["requests"]
        assert isinstance(data["requests"]["total"], int)
        assert "by_model" in data["requests"]
        assert isinstance(data["requests"]["by_model"], dict)
        assert "by_complexity" in data["requests"]
        assert "latency" in data
        assert "p50_ms" in data["latency"]
        assert "p95_ms" in data["latency"]
        assert "p99_ms" in data["latency"]
        assert "avg_ms" in data["latency"]
        assert "errors" in data
        assert "total" in data["errors"]
        assert "rate" in data["errors"]
        assert "security" in data
        assert "sensitive_requests" in data["security"]
        assert "injection_attempts" in data["security"]
        assert "cache" in data
        assert "hits" in data["cache"]
        assert "misses" in data["cache"]
        assert "hit_rate" in data["cache"]
        assert "timestamp" in data

    def test_metrics_history_endpoint(self, client):
        """Metrics history endpoint returns latency data."""
        response = client.get(f"{ROUTER_URL}/metrics/history?minutes=60")
        assert response.status_code == 200
        data = response.json()
        assert "history" in data
        assert "minutes" in data
        assert isinstance(data["history"], list)
        # Each entry should have timestamp and latency_ms
        if len(data["history"]) > 0:
            entry = data["history"][0]
            assert "timestamp" in entry
            assert "latency_ms" in entry


class TestLiteLLM:
    """Integration tests for LiteLLM proxy."""

    def test_health(self, client):
        """LiteLLM health endpoint responds."""
        response = client.get(f"{LITELLM_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert "healthy_count" in data

    def test_direct_completion(self, client):
        """Direct LiteLLM completion works."""
        response = client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            json={
                "model": "llama-fast",
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 10,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "choices" in data


class TestEndToEnd:
    """End-to-end workflow tests."""

    def test_full_flow(self, client):
        """Complete request through Smart Router -> LiteLLM -> Ollama."""
        # 1. Check router health
        health = client.get(f"{ROUTER_URL}/health").json()
        assert health["status"] == "healthy"

        # 2. Make a chat request
        response = client.post(
            f"{ROUTER_URL}/v1/chat/completions",
            json={
                "model": "qwen-local",
                "messages": [
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "What is 2+2?"},
                ],
                "max_tokens": 20,
            },
        )
        assert response.status_code == 200

        data = response.json()

        # 3. Verify response structure
        assert "id" in data
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
        assert "content" in data["choices"][0]["message"]

        # 4. Verify routing metadata
        assert "_routing" in data
        assert data["_routing"]["original_model"] == "qwen-local"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
