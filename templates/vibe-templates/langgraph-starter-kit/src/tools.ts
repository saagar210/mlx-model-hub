import { z } from "zod";
import { tool } from "@langchain/core/tools";
export const add = tool(async (a) => a.a + a.b, {
  name: "add",
  description: "Add two numbers",
  schema: z.object({ a: z.number(), b: z.number() }),
});
export const multiply = tool(async (a) => a.a * a.b, {
  name: "multiply",
  description: "Multiply two numbers",
  schema: z.object({ a: z.number(), b: z.number() }),
});
export const echo = tool(async (a) => a.text, {
  name: "echo",
  description: "Echo text",
  schema: z.object({ text: z.string() }),
});
