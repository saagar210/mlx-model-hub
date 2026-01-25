import {
  MemorySaver,
  MessagesAnnotation,
  Annotation,
  StateGraph,
} from "@langchain/langgraph";
import { createSwarm } from "@langchain/langgraph-swarm";

export const SwarmState = Annotation.Root({
  ...MessagesAnnotation.spec,
  activeAgent: Annotation<string>(),
});

export function makeSwarm({
  agents,
  defaultActiveAgent,
  checkpointer = new MemorySaver(),
  store,
}: {
  agents: any[];
  defaultActiveAgent: string;
  checkpointer?: MemorySaver;
  store?: any;
}) {
  const graph = createSwarm({
    agents,
    defaultActiveAgent,
    stateSchema: SwarmState,
  });
  return graph.compile({ checkpointer, store });
}
