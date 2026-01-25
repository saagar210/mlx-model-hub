# Project 2: LangGraph Agent Platform

## Overview
A production-grade multi-agent orchestration platform using LangGraph, replacing CrewAI's flawed architecture with stateful graph-based workflows.

## Why LangGraph Over CrewAI

| Issue | CrewAI | LangGraph |
|-------|--------|-----------|
| **Execution** | Sequential despite "hierarchical" config | True parallel/conditional execution |
| **Error Recovery** | No built-in rollback | Checkpoint & rollback native |
| **Observability** | Limited | LangSmith integration |
| **Downloads** | 1.38M/month | 6.17M/month |
| **Bugs** | "THINKING" freezes reported | Stable API (1.0 guarantee) |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  CLI (Typer) │  │  REST API    │  │  MCP Server  │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                    LangGraph Orchestrator                           │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                    StateGraph                               │    │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐ │    │
│  │  │ Planner │───▶│Executor │───▶│Validator│───▶│ Output  │ │    │
│  │  │  Node   │    │  Node   │    │  Node   │    │  Node   │ │    │
│  │  └─────────┘    └─────────┘    └─────────┘    └─────────┘ │    │
│  │       │              │              │                      │    │
│  │       └──────────────┴──────────────┘                      │    │
│  │              (conditional edges)                           │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│                       Tool Layer                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ Web Tool │  │File Tool │  │ Code Tool│  │ API Tool │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
└─────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│                       LLM Layer                                     │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Local: DeepSeek R1 14B / Qwen 2.5 14B (via Ollama)        │    │
│  │  Fallback: Claude API (via CCFlare)                         │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│                    Persistence Layer                                │
│  ┌──────────────────┐  ┌──────────────────┐                        │
│  │   PostgreSQL     │  │    LangSmith     │                        │
│  │ (State, History) │  │  (Observability) │                        │
│  └──────────────────┘  └──────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Component | Technology | Why |
|-----------|------------|-----|
| **Orchestration** | LangGraph 1.0 | Stateful graphs, lowest latency |
| **Observability** | LangSmith | Native integration, free tier |
| **LLM (Local)** | DeepSeek R1 14B | Best open-source reasoning |
| **LLM (Fallback)** | Claude via CCFlare | Load balanced API |
| **State Store** | PostgreSQL | Checkpoints, history |
| **API** | FastAPI | Async, typed |

## Implementation Phases

### Phase 1: Core Graph Infrastructure (Week 1)

#### Project Structure
```
agent-platform/
├── src/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py           # Base agent class
│   │   ├── planner.py        # Planning agent
│   │   ├── researcher.py     # Research agent
│   │   ├── coder.py          # Code generation agent
│   │   └── validator.py      # Validation agent
│   ├── graphs/
│   │   ├── __init__.py
│   │   ├── research_graph.py # Research workflow
│   │   ├── coding_graph.py   # Coding workflow
│   │   └── general_graph.py  # General task workflow
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── web.py            # Web search/scrape
│   │   ├── file.py           # File operations
│   │   ├── code.py           # Code execution
│   │   └── knowledge.py      # Knowledge Engine integration
│   ├── state/
│   │   ├── __init__.py
│   │   └── schemas.py        # Pydantic state schemas
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   └── routes/
│   ├── config.py
│   └── main.py
├── tests/
├── pyproject.toml
└── docker-compose.yml
```

#### Core State Schema
```python
# src/state/schemas.py
from typing import Annotated, TypedDict, Literal
from langgraph.graph import add_messages
from pydantic import BaseModel

class AgentState(TypedDict):
    """State that flows through the graph"""
    messages: Annotated[list, add_messages]
    task: str
    plan: list[str] | None
    current_step: int
    results: list[dict]
    errors: list[str]
    status: Literal["planning", "executing", "validating", "complete", "failed"]
    metadata: dict

class TaskInput(BaseModel):
    """Input schema for tasks"""
    task: str
    context: str | None = None
    max_steps: int = 10
    require_validation: bool = True
```

#### Base Agent Class
```python
# src/agents/base.py
from abc import ABC, abstractmethod
from langchain_core.messages import HumanMessage, AIMessage
from langchain_ollama import ChatOllama

class BaseAgent(ABC):
    """Base class for all agents"""

    def __init__(
        self,
        model: str = "deepseek-r1:14b",
        temperature: float = 0.1
    ):
        self.llm = ChatOllama(
            model=model,
            temperature=temperature
        )
        self.name = self.__class__.__name__

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent"""
        pass

    async def invoke(self, state: AgentState) -> dict:
        """Invoke the agent with current state"""
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            *state["messages"]
        ]
        response = await self.llm.ainvoke(messages)
        return {"messages": [response]}
```

#### Basic Graph Definition
```python
# src/graphs/general_graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from src.state.schemas import AgentState
from src.agents import PlannerAgent, ExecutorAgent, ValidatorAgent

def create_general_graph():
    """Create a general-purpose task execution graph"""

    # Initialize agents
    planner = PlannerAgent()
    executor = ExecutorAgent()
    validator = ValidatorAgent()

    # Define the graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("planner", planner.invoke)
    graph.add_node("executor", executor.invoke)
    graph.add_node("validator", validator.invoke)
    graph.add_node("output", lambda s: s)  # Pass-through

    # Add edges
    graph.add_edge("planner", "executor")
    graph.add_conditional_edges(
        "executor",
        should_validate,
        {
            "validate": "validator",
            "complete": "output"
        }
    )
    graph.add_conditional_edges(
        "validator",
        check_validation,
        {
            "retry": "executor",
            "complete": "output",
            "fail": END
        }
    )

    # Set entry point
    graph.set_entry_point("planner")

    return graph.compile()

def should_validate(state: AgentState) -> str:
    """Decide if validation is needed"""
    if state.get("require_validation", True):
        return "validate"
    return "complete"

def check_validation(state: AgentState) -> str:
    """Check validation results"""
    if state["status"] == "failed":
        if len(state["errors"]) < 3:  # Max retries
            return "retry"
        return "fail"
    return "complete"
```

### Phase 2: Agent Implementation (Week 2)

#### Planner Agent
```python
# src/agents/planner.py
from src.agents.base import BaseAgent

class PlannerAgent(BaseAgent):
    """Breaks down tasks into executable steps"""

    def get_system_prompt(self) -> str:
        return """You are a task planning agent. Your job is to:
1. Analyze the given task
2. Break it down into clear, actionable steps
3. Identify dependencies between steps
4. Estimate complexity for each step

Output your plan as a JSON array of steps:
[
  {"step": 1, "action": "...", "tool": "...", "depends_on": []},
  {"step": 2, "action": "...", "tool": "...", "depends_on": [1]}
]

Available tools: web_search, file_read, file_write, code_execute, knowledge_query
"""

    async def invoke(self, state: AgentState) -> dict:
        result = await super().invoke(state)

        # Parse plan from response
        plan = self._extract_plan(result["messages"][-1].content)

        return {
            "messages": result["messages"],
            "plan": plan,
            "status": "executing",
            "current_step": 0
        }

    def _extract_plan(self, content: str) -> list[dict]:
        """Extract plan JSON from LLM response"""
        import json
        import re

        # Find JSON array in response
        match = re.search(r'\[[\s\S]*\]', content)
        if match:
            return json.loads(match.group())
        return []
```

#### Executor Agent
```python
# src/agents/executor.py
from src.agents.base import BaseAgent
from src.tools import get_tool

class ExecutorAgent(BaseAgent):
    """Executes plan steps using tools"""

    def get_system_prompt(self) -> str:
        return """You are an execution agent. Given a plan step:
1. Determine the appropriate tool to use
2. Format the tool call correctly
3. Execute and report results

Be precise and follow the plan exactly."""

    async def invoke(self, state: AgentState) -> dict:
        current_step = state["current_step"]
        plan = state["plan"]

        if current_step >= len(plan):
            return {"status": "complete"}

        step = plan[current_step]
        tool = get_tool(step["tool"])

        try:
            result = await tool.execute(step["action"], state)
            return {
                "results": state["results"] + [result],
                "current_step": current_step + 1,
                "status": "executing" if current_step + 1 < len(plan) else "validating"
            }
        except Exception as e:
            return {
                "errors": state["errors"] + [str(e)],
                "status": "failed"
            }
```

#### Validator Agent
```python
# src/agents/validator.py
from src.agents.base import BaseAgent

class ValidatorAgent(BaseAgent):
    """Validates execution results"""

    def get_system_prompt(self) -> str:
        return """You are a validation agent. Review the execution results:
1. Check if the original task is satisfied
2. Identify any errors or incomplete work
3. Suggest corrections if needed

Output JSON:
{
  "valid": true/false,
  "issues": ["..."],
  "suggestions": ["..."]
}
"""

    async def invoke(self, state: AgentState) -> dict:
        result = await super().invoke(state)
        validation = self._parse_validation(result["messages"][-1].content)

        if validation["valid"]:
            return {"status": "complete"}
        else:
            return {
                "errors": state["errors"] + validation["issues"],
                "status": "failed"
            }
```

### Phase 3: Tools Integration (Week 3)

#### Tool Registry
```python
# src/tools/__init__.py
from src.tools.web import WebSearchTool, WebScrapeTool
from src.tools.file import FileReadTool, FileWriteTool
from src.tools.code import CodeExecuteTool
from src.tools.knowledge import KnowledgeQueryTool

TOOL_REGISTRY = {
    "web_search": WebSearchTool(),
    "web_scrape": WebScrapeTool(),
    "file_read": FileReadTool(),
    "file_write": FileWriteTool(),
    "code_execute": CodeExecuteTool(),
    "knowledge_query": KnowledgeQueryTool(),
}

def get_tool(name: str):
    """Get tool by name"""
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {name}")
    return TOOL_REGISTRY[name]
```

#### Knowledge Engine Tool
```python
# src/tools/knowledge.py
from src.tools.base import BaseTool
import httpx

class KnowledgeQueryTool(BaseTool):
    """Query the Knowledge Engine (Project 1)"""

    name = "knowledge_query"
    description = "Search personal knowledge base"

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def execute(self, query: str, state: dict) -> dict:
        """Execute knowledge search"""
        response = await self.client.get(
            f"{self.base_url}/api/search",
            params={"q": query, "top_k": 5}
        )
        results = response.json()
        return {
            "tool": self.name,
            "query": query,
            "results": results
        }
```

### Phase 4: Checkpointing & State (Week 4)

#### PostgreSQL Checkpointer
```python
# src/state/checkpointer.py
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy.ext.asyncio import create_async_engine

async def create_checkpointer(database_url: str):
    """Create PostgreSQL checkpointer for state persistence"""
    engine = create_async_engine(database_url)

    # Create tables if needed
    async with engine.begin() as conn:
        await conn.run_sync(PostgresSaver.create_tables)

    return PostgresSaver(engine)
```

#### Graph with Checkpointing
```python
# src/graphs/research_graph.py
from langgraph.graph import StateGraph
from src.state.checkpointer import create_checkpointer

async def create_research_graph(database_url: str):
    """Create research graph with persistence"""

    checkpointer = await create_checkpointer(database_url)

    graph = StateGraph(ResearchState)
    # ... add nodes and edges ...

    return graph.compile(checkpointer=checkpointer)

# Usage with thread_id for conversation persistence
async def run_research(task: str, thread_id: str):
    graph = await create_research_graph(DATABASE_URL)

    config = {"configurable": {"thread_id": thread_id}}

    result = await graph.ainvoke(
        {"task": task, "messages": []},
        config=config
    )

    return result
```

### Phase 5: API & CLI (Week 5)

#### FastAPI Application
```python
# src/api/app.py
from fastapi import FastAPI, BackgroundTasks
from src.graphs import create_general_graph, create_research_graph
from src.state.schemas import TaskInput

app = FastAPI(title="Agent Platform")

@app.post("/api/tasks")
async def create_task(task: TaskInput, background_tasks: BackgroundTasks):
    """Create and execute a new task"""
    task_id = str(uuid4())

    # Run in background
    background_tasks.add_task(
        execute_task,
        task_id,
        task
    )

    return {"task_id": task_id, "status": "started"}

@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """Get task status and results"""
    # Retrieve from checkpointer
    pass

@app.get("/api/tasks/{task_id}/stream")
async def stream_task(task_id: str):
    """Stream task execution updates"""
    # Server-sent events
    pass
```

#### Typer CLI
```python
# src/main.py
import typer
from rich.console import Console
from src.graphs import create_general_graph

app = typer.Typer()
console = Console()

@app.command()
def run(task: str, model: str = "deepseek-r1:14b"):
    """Execute a task with the agent platform"""
    import asyncio

    async def execute():
        graph = await create_general_graph()
        result = await graph.ainvoke({"task": task, "messages": []})
        return result

    result = asyncio.run(execute())
    console.print(result)

@app.command()
def research(topic: str):
    """Run a research task"""
    # Research-specific graph
    pass

if __name__ == "__main__":
    app()
```

### Phase 6: LangSmith Integration

#### Observability Setup
```python
# src/config.py
import os

# Enable LangSmith tracing
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "agent-platform"
# LANGCHAIN_API_KEY should be set in environment

# Optional: Custom callbacks
from langchain_core.callbacks import BaseCallbackHandler

class AgentCallback(BaseCallbackHandler):
    """Custom callback for agent events"""

    def on_llm_start(self, *args, **kwargs):
        print(f"LLM started...")

    def on_tool_start(self, *args, **kwargs):
        print(f"Tool started...")
```

---

## Workflow Examples

### Research Workflow
```
User: "Research the latest developments in MLX for Apple Silicon"
           │
           ▼
    ┌─────────────┐
    │   Planner   │ ──▶ Creates 5-step research plan
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │ Web Search  │ ──▶ Searches for MLX news, papers
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │ Knowledge   │ ──▶ Checks existing knowledge
    │   Query     │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │ Synthesizer │ ──▶ Combines findings
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │  Validator  │ ──▶ Checks completeness
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │   Output    │ ──▶ Formatted report
    └─────────────┘
```

### Code Generation Workflow
```
User: "Create a Python script to analyze CSV files"
           │
           ▼
    ┌─────────────┐
    │   Planner   │ ──▶ Defines requirements
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │   Coder     │ ──▶ Generates code
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │  Executor   │ ──▶ Tests code
    └──────┬──────┘
           │
    ┌──────┴──────┐
    │ Pass? ──────┼─▶ Validator ──▶ Output
    │      │      │
    │      ▼      │
    │   Retry     │
    └─────────────┘
```

---

## Configuration

```yaml
# config.yaml
llm:
  default_model: "deepseek-r1:14b"
  fallback_model: "claude-3-sonnet"
  temperature: 0.1
  max_tokens: 4096

database:
  url: "postgresql://user:pass@localhost:5432/agent_platform"

langsmith:
  project: "agent-platform"
  tracing: true

tools:
  knowledge_engine:
    url: "http://localhost:8000"
  web_search:
    provider: "brave"  # or "serper", "tavily"

limits:
  max_steps: 20
  max_retries: 3
  timeout_seconds: 300
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Task completion rate | > 85% |
| Average execution time | < 60s |
| Retry rate | < 20% |
| LLM cost per task | < $0.10 |

---

## Timeline

| Week | Phase | Deliverable |
|------|-------|-------------|
| 1 | Core | Graph infrastructure, state management |
| 2 | Agents | Planner, Executor, Validator |
| 3 | Tools | Web, file, code, knowledge tools |
| 4 | State | PostgreSQL checkpointing |
| 5 | API | FastAPI + CLI |

**Total: 5 weeks**
