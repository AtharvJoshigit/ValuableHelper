import json
import os
import logging
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

class ModelPreferences:
    """
    Manages persistent model preferences for agents.
    Stores data in config/model_preferences.json
    """
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.config_file = os.path.join(config_dir, "model_preferences.json")
        self._preferences: Dict[str, Dict[str, str]] = {}
        self._load()

    def _load(self):
        """Loads preferences from disk."""
        if not os.path.exists(self.config_file):
            logger.info("No model preferences file found. Starting empty.")
            return

        try:
            with open(self.config_file, 'r') as f:
                self._preferences = json.load(f)
            logger.info(f"Loaded model preferences for {len(self._preferences)} agents.")
        except Exception as e:
            logger.error(f"Failed to load model preferences: {e}")
            self._preferences = {}

    def _save(self):
        """Saves preferences to disk."""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self._preferences, f, indent=2)
            logger.info("Model preferences saved.")
        except Exception as e:
            logger.error(f"Failed to save model preferences: {e}")

    def get_preference(self, agent_id: str) -> Optional[Dict[str, str]]:
        """
        Returns model config for an agent if set.
        Returns dict with keys: 'model_id', 'provider', etc.
        """
        return self._preferences.get(agent_id)

    def set_preference(self, agent_id: str, model_id: str, provider: str, **kwargs):
        """
        Sets a preference for an agent.
        """
        self._preferences[agent_id] = {
            "model_id": model_id,
            "provider": provider,
            **kwargs
        }
        self._save()

    def delete_preference(self, agent_id: str):
        if agent_id in self._preferences:
            del self._preferences[agent_id]
            self._save()

# Global Instance
_instance = None

def get_model_preferences() -> ModelPreferences:
    global _instance
    if _instance is None:
        # Assuming run from root, so 'config' is at ./config
        _instance = ModelPreferences()
    return _instance
