import { z } from "zod";
import { ToolMessage } from "@langchain/core/messages";
import { tool } from "@langchain/core/tools";
import {
  Command,
  MessagesAnnotation,
  getCurrentTaskInput,
} from "@langchain/langgraph";

export function createHandoffTool({
  agentName,
  description,
}: {
  agentName: string;
  description?: string;
}) {
  const name = `transfer_to_${agentName.replace(/\s+/g, "_").toLowerCase()}`;
  return tool(
    async (_args, cfg) => {
      const state =
        getCurrentTaskInput() as (typeof MessagesAnnotation)["State"];
      const tm = new ToolMessage({
        content: `Transferred to ${agentName}`,
        name,
        tool_call_id: cfg.toolCall.id,
      });
      return new Command({
        goto: agentName,
        graph: Command.PARENT,
        update: { messages: state.messages.concat(tm), activeAgent: agentName },
      });
    },
    {
      name,
      description: description ?? `Ask ${agentName} for help`,
      schema: z.object({}),
    }
  );
}
