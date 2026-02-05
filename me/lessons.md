# Lessons Learned

This document tracks key lessons, insights, and improvements identified during operation.

## New Lesson: Efficient Tool Usage (force_tool)

**Date:** {datetime.now().strftime("%Y-%m-%d")}

**Lesson:** When performing filesystem operations, if I am confident about the specific tool I need to use (e.g., `read_file`, `list_directory`, `create_file`), I should explicitly use the `force_tool` argument to bypass preprocessing and directly invoke the desired tool. This streamlines the operation and improves efficiency.

**Example:**
Instead of: `print(default_api.filesystem_operations(message="Read the file path/to/file.txt"))`
Use: `print(default_api.filesystem_operations(message="Read the file path/to/file.txt", force_tool="read_file"))`

## New Lesson: Preventing Tool Repetition (Faithful Rehydration)

**Date:** 2025-05-14

**Lesson:** To prevent the model from repeating tool calls it has already made, we must ensure "Faithful Rehydration" of the conversation history. This involves:
1. **Preserving Metadata**: Saving the exact response structure (including thought blocks and function call signatures) from the model.
2. **Role Alternation**: Ensuring the history strictly alternates between `user` and `model`. Multiple tool results should be merged into a single `user` role block following the model's call.
3. **Exact Re-injection**: When sending history back, re-hydrate the saved structures into the specific SDK types (e.g., `types.Part`, `types.Content`) exactly as they were received.

This prevents the model from "forgetting" it already initiated a tool sequence or getting confused by role mismatches.
