"""LocalCrew API adapter for research and task decomposition."""

from typing import Any

import httpx

from ..config import settings


class Subtask:
    """A subtask from task decomposition."""

    def __init__(
        self,
        id: str,
        description: str,
        priority: int = 0,
        dependencies: list[str] | None = None,
        estimated_complexity: str = "medium",
    ):
        self.id = id
        self.description = description
        self.priority = priority
        self.dependencies = dependencies or []
        self.estimated_complexity = estimated_complexity


class ExecutionStatus:
    """Status of a crew execution."""

    def __init__(
        self,
        execution_id: str,
        status: str,
        progress: float = 0.0,
        result: str | None = None,
        error: str | None = None,
    ):
        self.execution_id = execution_id
        self.status = status  # "pending", "running", "completed", "failed"
        self.progress = progress
        self.result = result
        self.error = error


class LocalCrewAdapter:
    """Adapter for LocalCrew API (localhost:8001)."""

    def __init__(self, base_url: str | None = None, timeout: float = 120.0):
        self.base_url = base_url or settings.localcrew_base_url
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def research(
        self,
        topic: str,
        depth: str = "medium",
        context: str | None = None,
    ) -> str:
        """Trigger research crew for a topic.

        Args:
            topic: The topic to research.
            depth: Research depth ("quick", "medium", "deep").
            context: Optional additional context.

        Returns:
            Research results as a string.
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/v1/crew/research",
                json={
                    "topic": topic,
                    "depth": depth,
                    "context": context or "",
                },
            )
            response.raise_for_status()
            data = response.json()

            # Handle both sync and async responses
            if data.get("status") == "completed":
                return data.get("result", "No results returned")
            elif data.get("execution_id"):
                # Poll for results if async
                return await self._wait_for_result(data["execution_id"])
            else:
                return data.get("result", str(data))
        except Exception as e:
            return f"Research failed: {e}"

    async def decompose(self, task: str, context: str | None = None) -> list[Subtask]:
        """Decompose a task into subtasks.

        Args:
            task: The task to decompose.
            context: Optional additional context.

        Returns:
            List of Subtask objects.
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/v1/crew/decompose",
                json={
                    "task": task,
                    "context": context or "",
                },
            )
            response.raise_for_status()
            data = response.json()

            subtasks = []
            for i, item in enumerate(data.get("subtasks", [])):
                if isinstance(item, str):
                    subtasks.append(Subtask(
                        id=f"subtask-{i+1}",
                        description=item,
                        priority=i,
                    ))
                else:
                    subtasks.append(Subtask(
                        id=item.get("id", f"subtask-{i+1}"),
                        description=item.get("description", str(item)),
                        priority=item.get("priority", i),
                        dependencies=item.get("dependencies", []),
                        estimated_complexity=item.get("complexity", "medium"),
                    ))
            return subtasks
        except Exception as e:
            # Return a single fallback subtask
            return [Subtask(
                id="error",
                description=f"Decomposition failed: {e}",
                priority=0,
            )]

    async def get_status(self, execution_id: str) -> ExecutionStatus:
        """Get status of a crew execution.

        Args:
            execution_id: The execution ID to check.

        Returns:
            ExecutionStatus object.
        """
        try:
            client = await self._get_client()
            response = await client.get(f"/api/v1/executions/{execution_id}")
            response.raise_for_status()
            data = response.json()

            return ExecutionStatus(
                execution_id=execution_id,
                status=data.get("status", "unknown"),
                progress=data.get("progress", 0.0),
                result=data.get("result"),
                error=data.get("error"),
            )
        except Exception as e:
            return ExecutionStatus(
                execution_id=execution_id,
                status="error",
                error=str(e),
            )

    async def _wait_for_result(
        self,
        execution_id: str,
        max_polls: int = 30,
        poll_interval: float = 2.0,
    ) -> str:
        """Wait for an async execution to complete.

        Args:
            execution_id: The execution ID to wait for.
            max_polls: Maximum number of polling attempts.
            poll_interval: Seconds between polls.

        Returns:
            The execution result.
        """
        import asyncio

        for _ in range(max_polls):
            status = await self.get_status(execution_id)
            if status.status == "completed":
                return status.result or "Completed (no result)"
            elif status.status == "failed":
                return f"Execution failed: {status.error}"
            elif status.status == "error":
                return f"Status check failed: {status.error}"

            await asyncio.sleep(poll_interval)

        return f"Execution timed out after {max_polls * poll_interval}s"

    async def health(self) -> dict[str, Any]:
        """Check LocalCrew health.

        Returns:
            Health status dictionary.
        """
        try:
            client = await self._get_client()
            response = await client.get("/health")
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "details": response.json() if response.text else {},
                }
            return {
                "status": "unhealthy",
                "error": f"HTTP {response.status_code}",
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Default adapter instance
localcrew_adapter = LocalCrewAdapter()
