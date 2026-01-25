import { llm } from "./llm";
import { add, multiply, echo } from "./tools";
import { makeAgent } from "./agent-factory";
import { makeSupervisor } from "./supervisor";

const math = makeAgent({
  name: "math_expert",
  llm,
  tools: [add, multiply],
  system: "You are a math expert. Use one tool at a time.",
});
const writer = makeAgent({
  name: "writer",
  llm,
  tools: [echo],
  system: "You write crisp, structured answers.",
});

export const supervisorApp = makeSupervisor({
  agents: [math, writer],
  llm,
  outputMode: "last_message",
  supervisorName: "supervisor",
});
