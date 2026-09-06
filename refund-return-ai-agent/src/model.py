"""Groq model integration for the refund processing system."""

import logging
import os
from typing import Any, Dict

import yaml
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()

logger = logging.getLogger(__name__)


class GroqModel:
    """Handles Groq model initialization and configuration.

    The API key is a secret and lives in the environment (.env locally, or the
    hosting platform's secret manager) - never in config.yaml, which is
    checked into git. config.yaml only holds non-secret settings like model
    name and temperature.
    """

    def __init__(self, config_path: str = "config.yaml"):
        """Initialize with configuration file."""
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not os.path.exists(self.config_path):
            self._create_default_config()

        with open(self.config_path, 'r') as file:
            config = yaml.safe_load(file)

        return config

    def _create_default_config(self):
        """Create a default configuration file."""
        default_config = {
            'credentials': {
                'groq': {
                    'model_name': 'llama-3.3-70b-versatile',
                    'temperature': 0.1,
                }
            },
            'email': {
                'sender_email': 'enter_email'
            }
        }

        with open(self.config_path, 'w') as file:
            yaml.dump(default_config, file, default_flow_style=False, indent=2)

        logger.info("Default configuration created at: %s", self.config_path)

    def get_model(self):
        """Get the configured Groq model."""
        credentials = self.config.get('credentials', {})
        groq_config = credentials.get('groq', {})
        model_name = groq_config.get('model_name', 'llama-3.3-70b-versatile')
        temperature = groq_config.get('temperature', 0.1)

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not set. Copy .env.example to .env and add your key "
                "(or set it in your hosting platform's secret manager). "
                "Get a free key at https://console.groq.com/keys"
            )

        return init_chat_model(
            model=f"groq:{model_name}",
            temperature=temperature
        )


def get_chat_model(config_path: str = "config.yaml"):
    """Convenience function to get configured Groq chat model."""
    model_handler = GroqModel(config_path)
    return model_handler.get_model()
