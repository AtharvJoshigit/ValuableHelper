
# Project File Structure Overview

This document provides an organized overview of the project's file and directory structure, aiding in navigation and understanding of different components.

## Directories

*   `.` (Root Directory)
    *   `me/`
    *   `my_cute_face/`
    *   `src/`
        *   `src/agents/`
            *   `src/agents/file_system_agent/`
                *   `src/agents/file_system_agent/prompts/`
                *   `src/agents/file_system_agent/tools/`
            *   `src/agents/research_agent/`
                *   `src/agents/research_agent/prompts/`
                *   `src/agents/research_agent/tools/`
        *   `src/client/`
        *   `src/handler/`
            *   `src/handler/providers/`
        *   `src/valuableHelper.egg-info/`
    *   `system/`
    *   `tele_bot/`
    *   `whatiwanttobe/`

## Files (by Directory)

### Root Directory
*   `__init__.py`
*   `dependency_links.txt`
*   `main.py`
*   `PKG-INFO`
*   `pyproject.toml`
*   `README.md`
*   `requires.txt`
*   `sampl.txt`
*   `sample.txt`
*   `SOURCES.txt`
*   `top_level.txt`
*   `uv.lock`

### `me/`
*   `me/skills.md`
*   `me/whoami.md`

### `my_cute_face/`
*   `my_cute_face/animated_face.py`
*   `my_cute_face/cartoon_face.py`
*   `my_cute_face/face_logic.py`
*   `my_cute_face/interactive_face.py`

### `src/agents/file_system_agent/`
*   `src/agents/file_system_agent/files_system_agent.py`
*   `src/agents/file_system_agent/files_system_handler.py`

### `src/agents/file_system_agent/prompts/`
*   `src/agents/file_system_agent/prompts/__init__.py`
*   `src/agents/file_system_agent/prompts/file_system_prompt.py`

### `src/agents/file_system_agent/tools/`
*   `src/agents/file_system_agent/tools/file_tools_executor.py`
*   `src/agents/file_system_agent/tools/filesystem_tools.py`

### `src/agents/research_agent/`
*   `src/agents/research_agent/ai_research_handler.py`
*   `src/agents/research_agent/config.py`

### `src/agents/research_agent/prompts/`
*   `src/agents/research_agent/prompts/__init__.py`
*   `src/agents/research_agent/prompts/research_propmts.py`

### `src/client/`
*   `src/client/__init__.py`
*   `src/client/universal_ai_client.py`

### `src/handler/`
*   `src/handler/__init__.py`
*   `src/handler/agent_handler.py`
*   `src/handler/main_agent_handler.py`

### `src/handler/providers/`
*   `src/handler/providers/antropic.py`
*   `src/handler/providers/google.py`
*   `src/handler/providers/openai.py`

### `src/valuableHelper.egg-info/`
*   `src/valuableHelper.egg-info/dependency_links.txt`
*   `src/valuableHelper.egg-info/PKG-INFO`
*   `src/valuableHelper.egg-info/requires.txt`
*   `src/valuableHelper.egg-info/SOURCES.txt`
*   `src/valuableHelper.egg-info/top_level.txt`

### `system/`
*   `system/filesystem_operations.md`

### `tele_bot/`
*   `tele_bot/__init__.py`
*   `tele_bot/bot.py`
*   `tele_bot/config.py`
*   `tele_bot/messages.py`

### `whatiwanttobe/`
*   `whatiwanttobe/agent_improvement_plan.md`
