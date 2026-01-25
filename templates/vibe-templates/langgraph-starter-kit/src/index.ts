import "./env";
import { swarmApp } from "./app-swarm";
import { supervisorApp } from "./app-supervisor";

const cfg = { configurable: { thread_id: "demo" } } as const;

const run = async () => {
  const a = await swarmApp.invoke(
    { messages: [{ role: "user", content: "talk to bob then add 5 and 7" }] },
    cfg
  );
  const b = await swarmApp.invoke(
    { messages: [{ role: "user", content: "now multiply result by 3" }] },
    cfg
  );
  const c = await supervisorApp.invoke(
    {
      messages: [
        {
          role: "user",
          content: "sum 10 and 15, then write a one-line summary",
        },
      ],
    },
    cfg
  );
  console.log("swarm#1", a.messages.at(-1)?.content);
  console.log("swarm#2", b.messages.at(-1)?.content);
  console.log("supervisor", c.messages.at(-1)?.content);
};

run();
