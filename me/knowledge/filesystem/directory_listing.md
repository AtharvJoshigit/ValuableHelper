# Directory Listing Skill

This document details the capability to inspect and list the contents (files and subdirectories) of any specified directory or the current working directory within the file system.

## Tool: `list_directory`

### Purpose
The `list_directory` tool is designed to provide visibility into the file system structure. It allows for the enumeration of items (files and directories) present within a given path. This is crucial for navigating the workspace, identifying existing resources, and understanding the organizational layout.

### Usage
The tool is called directly with an optional `path` argument.

#### Arguments

*   **`path`** (string, optional):
    *   **Description**: The directory path to list.
    *   **Default**: If no `path` is provided, the tool will list the contents of the current working directory.
    *   **Example**: `path="src/my_project"`

### Return Value
The `list_directory` tool returns a dictionary containing the following keys:
*   **`items`** (list of strings): A list where each string represents the name of a file or directory found within the specified `path`.
*   **`path`** (string): The actual path that was listed. This will be the `path` provided in the argument, or the current working directory if no `path` was specified.

### Example Usage

```python
# List the current directory
print(default_api.list_directory())

# List a specific directory
print(default_api.list_directory(path="me/knowledge"))
```

### Technical Details/Implementation Notes
*   This tool interacts with the underlying operating system's file system to retrieve directory contents.
*   It does not differentiate between files and directories in its `items` list; it simply provides their names. Further actions (like `read_file`) would be needed to inspect individual items.
*   Error handling for non-existent paths or permission issues is managed internally by the tool, and appropriate responses are provided.