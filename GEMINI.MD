## Gemini Added Memories
- The user prefers to use the `python3` command for executing python scripts.


# Guide to Building ADK Agents

This document contains key learnings, code snippets, and best practices for building agents with the Google Agent Development Kit (ADK), based on our hands-on experience.

## 0. Essential First Steps

**1. Clone the ADK Source Code Locally plus use the Knowledge MCP**

The single most important step for successful development is to have a local, read-only copy of the ADK Python SDK. The official documentation can be sparse, and the source code itself is the ultimate ground truth for class definitions, method signatures, and correct import paths.

```bash
# Create a read-only directory in your project
mkdir -p read-only

# Clone the SDK into it
git clone https://github.com/google/adk-python.git read-only/adk-python
```

When you encounter an `ImportError`, `TypeError`, or `ValidationError`, use your IDE's search function or a command-line tool like `grep` or `rg` to find the class or function definition within this local copy.

## 1. Core Concepts & Execution Flow

The fundamental mistake is to treat agents as standalone scripts. The ADK uses a runner-based architecture.

1.  **Agent Definition**: You define an agent's capabilities in a Python file (e.g., `agent.py`), typically by instantiating a class like `LlmAgent`.
2.  **Runner Script**: You create a separate script (e.g., `run.py`) to act as the host application. This script is the user-facing entry point.
3.  **InMemoryRunner**: The runner is the core component in your host script. It loads your agent, manages conversation sessions, and handles the invocation lifecycle.
4.  **Session Management**: The runner creates and tracks sessions, which store conversation history and state.
5.  **Invocation**: You send user input to the agent via the `runner.run_async()` method, which returns the agent's response events.

---

## 2. Code Snippets & Best Practices

### 2.1. Minimal Runner Script (`run.py`)

This is the correct pattern for executing a single agent. It handles initialization, session creation, and invocation.

```python
import argparse
import asyncio
import os
from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner
from google.genai import types
# Import your agent definition
from my_agent.agent import my_llm_agent

load_dotenv()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", type=str, required=True)
    args = parser.parse_args()

    app_name = "my_adk_app"

    # 1. Initialize the runner with your agent and an app_name
    runner = InMemoryRunner(agent=my_llm_agent, app_name=app_name)

    # 2. Create a session, providing app_name and a user_id
    session = await runner.session_service.create_session(
        app_name=app_name, user_id="default_user"
    )

    # 3. Construct the user message using types.Content and types.Part
    user_message = types.Content(
        role="user", parts=[types.Part.from_text(text=args.prompt)]
    )

    # 4. Invoke the agent via the runner
    final_response = None
    async for event in runner.run_async(
        user_id="default_user",
        session_id=session.id,
        new_message=user_message
    ):
        if event.is_final_response() and event.content:
            final_response = event
            break

    if final_response:
        print(f"Agent Response: {final_response.content.parts[0].text}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 2.2. Defining a Basic Agent (`agent.py`)

An agent must have a `name` and a `model`. The `instruction` sets its system prompt.

```python
from google.adk.agents import LlmAgent

AGENT_INSTRUCTIONS = "You are a helpful assistant."

my_llm_agent = LlmAgent(
    name="my_llm_agent",
    model="gemini-2.5-flash",
    instruction=AGENT_INSTRUCTIONS
)
```

### 2.3. Using Built-in Toolsets (Shell, File System)

For common tasks like running shell commands or accessing the file system, the ADK provides pre-built toolsets. These are imported from their specific modules and can be used directly.

```python
from google.adk.agents import LlmAgent
from google.adk.tools.shell_tool import shell_toolset
from google.adk.tools.file_system_tool import file_system_toolset

# The toolsets are already instantiated in their modules.
my_utility_agent = LlmAgent(
    name="my_utility_agent",
    model="gemini-2.5-flash",
    instruction="You can use shell commands and access the file system.",
    tools=[shell_toolset, file_system_toolset]
)
```

### 2.4. Using MCP Tools

To equip an agent with tools like Veo or Lyria, use the `MCPToolset`. Generative media tools can be long-running, so it is critical to set an appropriate timeout.

**Key Insight:** The constructor for `MCPToolset` does not take a `name` argument. The `StdioConnectionParams` requires a nested `StdioServerParameters` object and accepts a `timeout` parameter in seconds.

```python
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters # Note: Imported from the 'mcp' library

# The docstrings recommend StdioConnectionParams over StdioServerParameters
veo_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="mcp-veo-go",
            # Pass the parent environment to the subprocess, mapping variables if needed.
            env=dict(os.environ, PROJECT_ID=os.getenv("GOOGLE_CLOUD_PROJECT"))
        ),
        timeout=180.0 # Set a 3-minute timeout for the tool call
    )
)

my_tool_agent = LlmAgent(
    name="my_tool_agent",
    model="gemini-2.5-flash",
    instruction="You are a media generation assistant.",
    tools=[veo_toolset]
)
```

### 2.4. Handling Tool Constraints (Important Insight)

While the ADK agent can introspect the *signature* of a tool provided by an MCP server (e.g., it knows the function name and parameter names), it does **not** automatically know the *constraints* or valid values for those parameters (e.g., that `aspect_ratio` for `veo_t2v` must be `'16:9'` or `'9:16'`).

The tool itself will enforce these constraints and return an error if they are violated. To build a robust system, the agent developer must provide these constraints to the LLM within the agent's instructions.

**Example: Constraining a Narrative Agent**

If one agent is generating data for another agent to use, bake the constraints into the first agent's prompt.

```python
# In the NarrativeAgent's prompts.py

NARRATIVE_PROMPT = """You are a creative director...

**The `output_specs` must have an `aspect_ratio` of either \"16:9\" or \"9:16\". Do not use any other values.**

The JSON must adhere to the following schema:
...
"""
```

**Example: Guiding a Tool-Using Agent**

Explicitly tell the agent which parameters to use when calling a tool based on the situation.

```python
# In the OrchestrationAgent's prompts.py

ORCHESTRATION_PROMPT = """You are an orchestration agent...

- If the workflow is 'veo3', you will call the 'veo_t2v' tool, setting the `model` parameter to 'veo-3.0-fast-generate-preview'.
- If the workflow is 'veo2', you will call the 'veo_t2v' tool, setting the `model` parameter to 'veo-2.0-generate-001'.
...
"""
```

### 2.5. Injecting Environment Variables into Prompts

An `LlmAgent` **cannot** access host environment variables directly for security reasons. You cannot instruct an agent to "use the `GENMEDIA_BUCKET` environment variable." The agent will pass that literal string to the tool, causing an error.

**The Solution:** The runner script must read the environment variable and inject its *value* into the agent's prompt.

```python
# In your run.py

# 1. Read the environment variable in the runner
gcs_bucket = os.getenv("GENMEDIA_BUCKET", "")
if not gcs_bucket:
    raise ValueError("GENMEDIA_BUCKET environment variable not set.")

# 2. Construct a prompt that includes the value
orchestration_input = (
    f"GCS Bucket: {gcs_bucket}\n\n"
    f"JSON Blueprint:\n{blueprint_content}"
)

# 3. Instruct the agent to use the provided value
# In the OrchestrationAgent's prompts.py
ORCHESTRATION_PROMPT = """You are an orchestration agent...

When you call the `veo_t2v` tool, you MUST include the `bucket` parameter.
The user has provided the GCS bucket to use in the prompt.
... 
"""
```

### 2.6. Robust Multi-Agent Handoffs

When one agent's successful output is the necessary input for the next agent, do not rely on the first agent to perform the handoff. An agent's primary goal is to complete its main instruction, and it may "forget" a final step like writing a handoff file after a long series of tool calls.

**The Solution:** Make the runner script responsible for the handoff.

```python
# In your run.py

# ... after running the OrchestrationAgent ...

# 1. The runner captures the successful tool call responses
gcs_asset_paths = []
async for event in orchestration_runner.run_async(...):
    if event.content and event.content.parts:
        for part in event.content.parts:
            if part.function_response and part.function_response.name == "veo_t2v":
                # 2. The runner parses the responses to extract the needed data
                response_text = part.function_response.response['result'].content[0].text
                if "gs://" in response_text:
                    gcs_path = "gs://" + response_text.split("gs://")[1].split(" ")[0]
                    gcs_asset_paths.append(gcs_path)

# 3. The runner creates the handoff file for the next agent
with open(os.path.join(output_dir, "gcs_asset_paths.txt"), "w") as f:
    for path in gcs_asset_paths:
        f.write(f"{path}\n")

# ... now the AssemblyAgent can run, confident that its input file exists.
```

---

## 3. Troubleshooting & Gotchas




## 4. Debugging

### Enabling Logging

The ADK provides a simple utility for logging to a temporary file. This is invaluable for seeing the full, verbose output of the agent and MCP servers.

```python
# In your run.py
from google.adk.cli.utils import logs

# At the start of your script
logs.log_to_tmp_folder()
```

### Interpreting Common Errors

*   **`PylintE0402:relative-beyond-top-level`**
    *   **Cause:** Using a relative import (e.g., `from . import prompts`) in a script that is not part of a formal Python package.
    *   **Fix:** Use absolute imports based on the project's root directory (e.g., `from narrative_agent import prompts`).

*   **`mcp.shared.exceptions.McpError: Connection closed`**
    *   **Cause:** This is a generic error from the Python side indicating that the underlying MCP Go process has crashed or exited unexpectedly.
    *   **Fix:** Look higher in the logs for the *real* error message coming from the Go process itself. A common cause is a missing environment variable like `PROJECT_ID`.

*   **`mcp.shared.exceptions.McpError: Timed out while waiting for response`**
    *   **Cause:** The tool call took longer than the allowed timeout (default is 5 seconds).
    *   **Fix:** Increase the timeout in the `StdioConnectionParams` constructor, e.g., `timeout=180.0`.

*   **`ValueError: No model found for <agent_name>.`**
    *   **Cause:** The `LlmAgent` was initialized without a `model` parameter.
    *   **Fix:** Always explicitly provide the model, e.g., `model="gemini-2.5-flash"`.

*   **`ValueError: Session not found`**
    *   **Cause:** The `app_name` in the `InMemoryRunner` constructor does not match the `app_name` used in the `session_service.create_session()` call.
    *   **Fix:** Ensure the `app_name` is identical in both places.

*   **`TypeError: ...missing required keyword-only arguments: 'app_name' and 'user_id'`**
    *   **Cause:** Calling `session_service.create_session()` without the required arguments.
    *   **Fix:** Always provide both `app_name` and `user_id`.

*   **`ImportError: cannot import name 'MCPToolset'`**
    *   **Cause:** Using an incorrect import path.
    *   **Fix:** Use the full, correct path discovered from the source code: `from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset`.

*   **`TypeError: MCPToolset.__init__() got an unexpected keyword argument 'name'`**
    *   **Cause:** The `MCPToolset` constructor does not accept a `name` argument.
    *   **Fix:** Remove the `name` argument from the `MCPToolset` constructor.

*   **`ValidationError: ... Field required [type=missing, input_value={'command': ...}]` for `StdioConnectionParams`**
    *   **Cause:** `StdioConnectionParams` requires a nested `server_params` object.
    *   **Fix:** Construct the object correctly: `StdioConnectionParams(server_params=StdioServerParameters(command="..."))`.

*   **`TypeError: Part.from_text() takes 1 positional argument but 2 were given`**
    *   **Cause:** Calling `types.Part.from_text("some string")` instead of using the keyword argument.
    *   **Fix:** Always use the keyword argument: `types.Part.from_text(text="some string")`.