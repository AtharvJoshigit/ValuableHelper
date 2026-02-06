# Advanced System Operations Skill

This document details the capability to delegate complex system-level tasks to a specialized sub-agent, encompassing advanced file manipulations and shell command execution.

## Tool: `system_operator`

### Purpose
The `system_operator` tool acts as an interface to a powerful sub-agent designed to handle a wide range of system-level tasks that might involve multiple steps, conditional logic, or direct interaction with the operating system's shell. Its purpose is to offload complex file operations (create, modify, delete) and general shell command execution, allowing for sophisticated control over the environment.

### Usage
The tool is called with a single `task_input` argument, which is a string containing the specific task or question for the sub-agent to handle.

#### Arguments

*   **`task_input`** (string, required):
    *   **Description**: A clear, concise instruction or question for the `system_operator` sub-agent. This can range from a simple file creation request to a complex multi-step command sequence or a query about system status.
    *   **Example**: `task_input="create a file named 'temp.txt' with content 'hello world'"`
    *   **Example**: `task_input="list all python files in the current directory and their sizes"`
    *   **Example**: `task_input="delete the directory 'old_logs' recursively"`

### Return Value
The `system_operator` tool returns a dictionary containing the following keys:
*   **`result`** (dictionary or string): The outcome of the task performed by the sub-agent. This can vary widely depending on the `task_input`. It might contain:
    *   A string summarizing the operation's success or failure.
    *   A dictionary with more structured results, such as lists of files, command outputs, or status messages.
*   **`status`** (string): Indicates the overall status of the `system_operator`'s execution (e.g., "success", "error", "completed").

### Example Usage

```python
# Create a file
print(default_api.system_operator(task_input="create a file named 'example.txt' in the current directory with content 'This is a test file.'"))

# List directory contents with a shell command
print(default_api.system_operator(task_input="run the shell command 'ls -l' in the current directory"))

# Read a file through the system_operator (though read_file is more direct for simple reads)
print(default_api.system_operator(task_input="read the content of 'me/skills.md'"))
```

### Technical Details/Implementation Notes
*   This tool acts as an orchestrator, delegating the `task_input` to a dedicated sub-agent. The sub-agent then interprets the instruction and executes the necessary underlying file operations or shell commands.
*   The `system_operator` is designed to handle complex, multi-step tasks, reducing the need for the main agent to break down intricate instructions into granular tool calls.
*   The capabilities of the `system_operator` are largely defined by its own internal system prompt and available tools. *(Note: The system prompt for the `system_operator` agent was not directly accessible during the creation of this documentation due to a permission error when attempting to read `me/my_agents`. Further details on its specific instructions and internal logic would be available by inspecting that file if permissions are granted.)*
*   It provides a powerful abstraction for interacting with the operating system, allowing for flexible and robust system management tasks.