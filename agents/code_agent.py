from typing import Any

from .base_agent import BaseAgent


class CodeAgent(BaseAgent):
    name = "code_agent"
    description = "Generate or reason about code snippets"

    async def execute(self, task: str, context: dict[str, Any]) -> dict[str, Any]:
        workflow_id = str(context.get("workflow_id", ""))
        shared_context = await self.read_shared_context(workflow_id)
        incoming_messages = await self.receive_messages(workflow_id)

        selected_tool = context.get("tool")
        tool_results: list[dict[str, Any]] = []
        if selected_tool in {"file_reader", "sql_query"}:
            params = {"query": task, "context": shared_context, "workflow_id": workflow_id}
            if context.get("file_path"):
                params["path"] = context["file_path"]
            tool_results.append(await self.use_tool(selected_tool, params))

        prompt = (
            f"You are a code agent. Task: {task}. "
            f"Shared context: {shared_context}. Predecessor outputs: {context.get('predecessor_outputs', {})}. "
            f"Tool results: {tool_results}. Incoming messages: {incoming_messages}."
        )
        text = await self._llm_client.generate_text(prompt)

        await self.update_shared_context(workflow_id, {"code_output": text})
        sent_messages = await self._notify_successors(workflow_id, context, f"Code reasoning completed for task: {task}")
        return {
            "agent": self.name,
            "output": text,
            "tool_results": tool_results,
            "messages_received": incoming_messages,
            "messages_sent": sent_messages,
        }
