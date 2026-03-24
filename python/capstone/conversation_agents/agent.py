import asyncio
import inspect
import json
from typing import Callable

from langsmith import traceable, get_current_run_tree
from openai import AsyncOpenAI


class Agent:
    """Generic tool-calling agent backed by the OpenAI Chat Completions API."""

    def __init__(
        self,
        client: AsyncOpenAI,
        model: str,
        system_prompt: str,
        tools: list[dict],
        tool_executors: dict[str, Callable],
        thread_store: dict[str, list],
        thread_id: str,
        name: str = "Agent",
    ):
        self.client = client
        self.model = model
        self.system_prompt = system_prompt
        self.tools = tools
        self.tool_executors = tool_executors
        self.thread_store = thread_store
        self.thread_id = thread_id
        self.name = name

    @traceable(run_type="llm", name="chat_completion")
    async def _call_llm(self, messages: list, tool_kwargs: dict) -> dict:
        """Traced LLM call — works with any provider, no wrap_openai needed."""
        run = get_current_run_tree()
        if run:
            run.extra = {
                **(run.extra or {}),
                "metadata": {
                    **(run.extra or {}).get("metadata", {}),
                    "ls_provider": "openai",
                    "ls_model_name": self.model,
                },
            }
        response = await self.client.chat.completions.create(model=self.model, messages=messages, **tool_kwargs)
        return response

    @traceable(name="Agent")
    async def chat(self, question: str, langsmith_extra: dict | None = None) -> dict:
        """Process a user question through the agentic tool-calling loop."""
        run = get_current_run_tree()
        run_id = str(run.id) if run else None
        history_messages = self.thread_store.get(self.thread_id, [])

        messages = [{"role": "system", "content": self.system_prompt}] + history_messages + [{"role": "user", "content": question}]

        tool_kwargs = {"tools": self.tools, "tool_choice": "auto"} if self.tools else {}

        response = await self._call_llm(messages, tool_kwargs)
        response_message = response.choices[0].message

        while response_message.tool_calls:
            messages.append({"role": "assistant", "content": response_message.content or "", "tool_calls": [{"id": tc.id, "type": tc.type, "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in response_message.tool_calls]})

            for tool_call in response_message.tool_calls:
                function_args = json.loads(tool_call.function.arguments)
                executor = self.tool_executors.get(tool_call.function.name)

                try:
                    if executor is None:
                        result = f"Error: Unknown tool {tool_call.function.name}"
                    elif asyncio.iscoroutinefunction(executor) or inspect.iscoroutinefunction(executor):
                        result = await executor(**function_args)
                    else:
                        result = executor(**function_args)
                except Exception as e:
                    result = f"Error calling {tool_call.function.name}: {e}"

                messages.append({"role": "tool", "tool_call_id": tool_call.id, "name": tool_call.function.name, "content": result})

            response = await self._call_llm(messages, tool_kwargs)
            response_message = response.choices[0].message

        final_content = response_message.content
        messages.append({"role": "assistant", "content": final_content})

        self.thread_store[self.thread_id] = messages[1:]

        return {"messages": messages, "output": final_content, "run_id": run_id}
