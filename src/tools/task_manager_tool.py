# import os
# from engine.registry.library.base_tool import BaseTool

# TODO_FILE = "tasks/todo.md"

# @register_tool
# class TaskManagerTool(BaseTool):
#     """A tool to manage a todo list in a markdown file."""

#     def __init__(self):
#         super().__init__()
#         self.todo_file = TODO_FILE
#         # Ensure the directory for the todo file exists.
#         os.makedirs(os.path.dirname(self.todo_file), exist_ok=True)

#     def create_plan(self, steps: list[str]) -> str:
#         """
#         Creates a new tasks/todo.md file with the given steps.
#         Each step is formatted as a markdown checklist item.
        
#         Args:
#             steps: A list of strings, where each string is a task.
            
#         Returns:
#             A success or error message string.
#         """
#         content = ""
#         for step in steps:
#             content += f"- [ ] {step}\n"

#         try:
#             with open(self.todo_file, "w") as f:
#                 f.write(content)
#             return f"Plan created successfully at {self.todo_file}."
#         except IOError as e:
#             return f"Error creating plan: {e}"

#     def read_plan(self) -> str:
#         """
#         Reads and returns the content of the tasks/todo.md file.
        
#         Returns:
#             The content of the todo file or an error message.
#         """
#         try:
#             with open(self.todo_file, "r") as f:
#                 return f.read()
#         except FileNotFoundError:
#             return "No plan found. Please create one first."
#         except IOError as e:
#             return f"Error reading plan: {e}"

#     def mark_step_completed(self, step_index: int) -> str:
#         """
#         Marks a step in the todo list as complete by changing '- [ ]' to '- [x]'.
        
#         Args:
#             step_index: The 1-based index of the step to mark as complete.
            
#         Returns:
#             The updated plan content or an error message.
#         """
#         try:
#             with open(self.todo_file, "r") as f:
#                 lines = f.readlines()
#         except FileNotFoundError:
#             return "No plan found. Cannot mark step as complete."
#         except IOError as e:
#             return f"Error reading plan: {e}"

#         if not (1 <= step_index <= len(lines)):
#             return f"Error: Invalid step index {step_index}. Plan has {len(lines)} steps."

#         line_index = step_index - 1
#         line = lines[line_index].strip()

#         if line.startswith("- [ ]"):
#             lines[line_index] = line.replace("- [ ]", "- [x]", 1) + "\n"
#         elif line.startswith("- [x]"):
#             return "Step already marked as complete. No changes made."
#         else:
#             return f"Error: Step {step_index} is not a valid checklist item."

#         try:
#             with open(self.todo_file, "w") as f:
#                 f.writelines(lines)
#             return "".join(lines)
#         except IOError as e:
#             return f"Error updating plan: {e}"

#     def update_plan(self, new_plan: str) -> str:
#         """
#         Overwrites the tasks/todo.md file with new content.
        
#         Args:
#             new_plan: The new string content to write to the file.
            
#         Returns:
#             A success or error message string.
#         """
#         try:
#             with open(self.todo_file, "w") as f:
#                 f.write(new_plan)
#             return f"Plan updated successfully at {self.todo_file}."
#         except IOError as e:
#             return f"Error updating plan: {e}"
