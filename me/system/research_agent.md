# Research Agent Documentation

This document serves as a comprehensive and precise reference for the AI Research Agent. It details its purpose, core components, functionalities, and configuration to facilitate future understanding and modification.

## 1. Purpose

The AI Research Agent is designed to autonomously conduct various types of research queries using configured AI models. Its primary goal is to provide accurate, well-structured, and easy-to-understand information on diverse topics, trends, and daily updates.

## 2. Core Components

The Research Agent is built around the following key Python files and classes:

*   **`src/agents/research_agent/ai_research_handler.py`**:
    *   **Class:** `AIResearchHandler`
    *   **Role:** The main orchestrator. It initializes the configuration, creates AI clients, manages image generation, and executes the different research methods. It acts as the central hub for all research operations.
    *   **Class:** `ResearchOutput`
    *   **Role:** A data structure to encapsulate research results, including text content, a list of image URLs/paths, and associated metadata (topic, method, provider, model, timestamp, output format).

*   **`src/agents/research_agent/config.py`**:
    *   **Class:** `AIConfig`
    *   **Role:** Configuration manager for AI providers, models, temperatures, and token limits. It loads default settings, allows for file-based overrides (`ai_config.json`), and provides methods to get, set, and reset configurations for individual research methods and image generation.
    *   **Function:** `get_config()`: A singleton function to retrieve the global `AIConfig` instance.

*   **`src/agents/research_agent/prompts/research_propmts.py`**:
    *   **Variable:** `research_topic_system_prompt`
    *   **Role:** Contains the system prompt specifically crafted for the `handle_research` method. This prompt guides the AI to act as a "Research Expert and Master Educator," focusing on clarity, correctness, conceptual depth, and precise, post-ready output without unnecessary formatting or meta-commentary.
    *   **Note:** Prompts for `handle_research_on_trend` and `todays_research` are defined directly within `ai_research_handler.py`.

*   **`src/agents/research_agent/tools/`**: (Not explicitly detailed in the provided code, but typically would contain actual tool definitions if they were separate from the handler methods.)
    *   **Note:** The research functionalities (general, trends, daily digest) are implemented as methods within `AIResearchHandler`, effectively acting as internal tools orchestrated by the handler.

## 3. Functionalities & Tools

The `AIResearchHandler` exposes the following primary research functionalities:

### 3.1. `handle_research` (General Research)

*   **Purpose:** Conducts comprehensive research on any given topic.
*   **Arguments:**
    *   `topic` (str): The subject for the research.
    *   `include_images` (bool): If `True`, generates a single illustrative image related to the topic.
    *   `output_format` (Literal["text", "json"]): Specifies the desired output format for the research content.
*   **AI Interaction:** Uses `rp.research_topic_system_prompt` and a user prompt to the configured AI model.
*   **Image Generation:** Generates a "professional, informative illustration."
*   **Returns:** A `ResearchOutput` object.

### 3.2. `handle_research_on_trend` (Trend Research)

*   **Purpose:** Analyzes current and emerging trends related to a specific topic.
*   **Arguments:**
    *   `topic` (str): The trend subject.
    *   `include_images` (bool): If `True`, generates a single trend visualization image.
    *   `output_format` (Literal["text", "json"]): Specifies the desired output format.
*   **AI Interaction:** Uses an inline system prompt focused on trend analysis (predictions, implications, data-driven insights).
*   **Image Generation:** Generates a "modern, dynamic visualization."
*   **Returns:** A `ResearchOutput` object.

### 3.3. `todays_research` (Daily Research Digest)

*   **Purpose:** Generates a summary of important topics and developments across multiple categories for the current day.
*   **Arguments:**
    *   `include_images` (bool): If `True`, generates a cover image for the digest.
    *   `output_format` (Literal["text", "json"]): Specifies the desired output format.
    *   `categories` (Optional[List[str]]): A list of categories to include. Defaults to ["Technology", "Science", "Business", "Health", "Environment"] if not provided.
*   **AI Interaction:** Uses an inline system prompt for a "daily research digest creator" and a user prompt structured to cover key topics, explanations, and relevance per category.
*   **Image Generation:** Generates a "professional daily digest cover image."
*   **Returns:** A `ResearchOutput` object.

### 3.4. Utility Methods

*   **`_create_client(method: str)`**: Internal method to instantiate `UniversalAIClient` based on the AI provider and model configured for the specific `method`.
*   **`_generate_image(prompt: str)`**: Internal method to generate images. **Currently hardcoded to use OpenAI DALL-E**, but its `model`, `size`, and `quality` parameters are configurable via the `image_generation` section in `AIConfig`. Requires `OPENAI_API_KEY` environment variable.
*   **`save_output(output: ResearchOutput, filepath: str)`**: Saves a `ResearchOutput` object to a specified JSON file.
*   **`print_output(output: ResearchOutput)`**: Prints a formatted representation of the `ResearchOutput` to the console.

## 4. Configuration (`AIConfig` Details)

The `AIConfig` class is central to customizing the Research Agent's behavior:

*   **Default Settings:** Defined in `DEFAULT_CONFIG` for `handle_research`, `handle_research_on_trend`, `todays_research`, and `image_generation`. Each method can have its own `provider`, `model`, `temperature`, and `max_tokens`.
*   **Loading:** Attempts to load configuration from `ai_config.json` (or a specified `config_file`). If the file doesn't exist or an error occurs, it falls back to `DEFAULT_CONFIG`.
*   **Saving:** Configuration changes made via the `set` methods are automatically saved back to `ai_config.json`.
*   **Key Configuration Points:**
    *   **Provider/Model per Method:** Each research method can be configured to use a different AI provider (e.g., "groq", "openai", "anthropic", "google") and model. This allows for flexibility and optimization.
    *   **Image Generation Provider:** While `_generate_image` explicitly uses `OpenAI`, the *parameters* for DALL-E (`model`, `size`, `quality`) are configurable under the `image_generation` section in `AIConfig`. To change the image generation *provider*, a code change in `_generate_image` would be required.
    *   **Parameters:** `temperature` and `max_tokens` are configurable for each text-based research method.
*   **Methods:**
    *   `get(method)`: Retrieves the configuration dictionary for a given method.
    *   `set(method, provider, model, **kwargs)`: Updates the configuration for a specific method and saves it.
    *   `get_provider(method)`: Returns the AI provider for a method.
    *   `get_model(method)`: Returns the AI model for a method.
    *   `get_temperature(method)`: Returns the temperature setting for a method.
    *   `get_max_tokens(method)`: Returns the max_tokens setting for a method.
    *   `reset(method=None)`: Resets configuration for a specific method or all methods to defaults.
    *   `set_all(provider, model, temperature, max_tokens)`: Applies the same provider and model (and optionally temperature/max_tokens) to all primary research methods.

## 5. Potential Improvements & Considerations

*   **Centralized Prompt Management:** Currently, `handle_research` uses `research_propmts.py`, while `handle_research_on_trend` and `todays_research` define their prompts inline. For better organization and easier modification, all system and user prompts could be centralized in `research_propmts.py`.
*   **Configurable Image Generation Provider:** The `_generate_image` method is hardcoded to use OpenAI DALL-E. To enhance flexibility, the image generation provider could also be made configurable through `AIConfig`, requiring a more abstract interface for image generation services.
*   **Error Handling for Image Generation:** The `_generate_image` method has a broad `except Exception as e`. More specific error handling could provide clearer feedback on why image generation might fail.
*   **Detailed Tool Descriptions in `src/agents/research_agent/tools/`**: If the intention is to have actual "tools" for the research agent, their implementations could be moved into `src/agents/research_agent/tools/` and referenced by the `AIResearchHandler`, making the `AIResearchHandler` more of an orchestrator and less of an implementer of the actual research logic.
*   **Input Validation:** Adding input validation for the `AIResearchHandler` methods could make the agent more robust by ensuring topics, categories, and formats are valid before processing.
*   **Asynchronous Operations:** For potentially long-running research tasks or image generation, implementing asynchronous operations could improve responsiveness.

This documentation provides a solid foundation for understanding the Research Agent's inner workings and will be invaluable for any future development or debugging.
