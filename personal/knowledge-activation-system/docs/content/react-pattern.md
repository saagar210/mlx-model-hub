# ReAct: Reasoning and Acting Pattern for LLM Agents

ReAct (Reasoning + Acting) is a prompting paradigm that combines chain-of-thought reasoning with action execution, enabling LLMs to solve complex tasks by interleaving thinking and doing.

## Core Concept

Traditional approaches separate reasoning (chain-of-thought) from acting (tool use). ReAct unifies them:

```
Thought: I need to find the population of France
Action: search("population of France 2024")
Observation: France has a population of approximately 68 million
Thought: Now I have the answer
Action: finish("France has approximately 68 million people")
```

## The ReAct Loop

1. **Thought**: The model reasons about what to do next
2. **Action**: The model selects and executes an action (tool call)
3. **Observation**: The environment returns the result
4. **Repeat**: Continue until task is complete

## ReAct Prompt Template

```python
REACT_PROMPT = """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:"""
```

## Python Implementation

```python
from langchain.agents import AgentType, initialize_agent, Tool
from langchain_openai import ChatOpenAI

# Define tools
tools = [
    Tool(
        name="Search",
        func=search_function,
        description="Useful for searching the web for current information"
    ),
    Tool(
        name="Calculator",
        func=calculator_function,
        description="Useful for mathematical calculations"
    )
]

# Create ReAct agent
llm = ChatOpenAI(model="gpt-4", temperature=0)
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

# Run
result = agent.run("What is the population of France divided by 1000?")
```

## ReAct vs Other Patterns

| Pattern | Reasoning | Acting | Use Case |
|---------|-----------|--------|----------|
| **ReAct** | Interleaved | Interleaved | Complex multi-step tasks |
| **Chain-of-Thought** | Yes | No | Reasoning-only tasks |
| **Act-Only** | No | Yes | Simple tool use |
| **Plan-and-Execute** | Upfront | Sequential | Known task structure |

## When to Use ReAct

**Good for:**
- Multi-step information retrieval
- Tasks requiring reasoning about tool outputs
- Dynamic problem-solving where next step depends on previous results
- Question answering with external knowledge

**Not ideal for:**
- Simple single-tool tasks
- Tasks with fixed execution plans
- Real-time latency-sensitive applications

## ReAct with LangGraph

```python
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic

# Modern LangGraph approach
model = ChatAnthropic(model="claude-3-5-sonnet-20241022")
agent = create_react_agent(model, tools)

# Execute
result = agent.invoke({
    "messages": [("user", "Find the weather in Paris and convert to Fahrenheit")]
})
```

## Key Benefits

1. **Interpretability**: Thought traces show reasoning process
2. **Error Recovery**: Can reason about failed actions
3. **Flexibility**: Adapts strategy based on observations
4. **Grounding**: Actions provide factual grounding for reasoning

## Common Pitfalls

1. **Infinite loops**: Model keeps trying same action
2. **Hallucinated tools**: Model invents non-existent actions
3. **Overthinking**: Too many thought steps before acting
4. **Context overflow**: Long traces exceed context window

## References

- Original Paper: "ReAct: Synergizing Reasoning and Acting in Language Models" (Yao et al., 2022)
- LangChain ReAct Agent Documentation
- LangGraph Agent Documentation
