"""
granite_client.py — IBM WatsonX / Granite model client.

Wraps the ibm-watsonx-ai SDK to provide a clean interface for
text-generation requests used by the diagram agent.
"""

from __future__ import annotations

import logging
from typing import Any

from latex_diagram_agent.config import Config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import — ibm-watsonx-ai must be installed
# ---------------------------------------------------------------------------

def _get_model(config: Config) -> Any:
    """Instantiate and return a WatsonX ModelInference object."""
    try:
        from ibm_watsonx_ai import APIClient, Credentials
        from ibm_watsonx_ai.foundation_models import ModelInference
        from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
    except ImportError as exc:
        raise ImportError(
            "Package 'ibm-watsonx-ai' is required. "
            "Install it with: pip install ibm-watsonx-ai"
        ) from exc

    credentials = Credentials(
        url=config.watsonx_url,
        api_key=config.watsonx_api_key,
    )

    params = {
        GenParams.MAX_NEW_TOKENS: config.max_new_tokens,
        GenParams.MIN_NEW_TOKENS: config.min_new_tokens,
        GenParams.TEMPERATURE: config.temperature,
        GenParams.TOP_P: config.top_p,
        GenParams.TOP_K: config.top_k,
        GenParams.REPETITION_PENALTY: config.repetition_penalty,
        GenParams.STOP_SEQUENCES: ["```\n\n", "---END---"],
    }

    model = ModelInference(
        model_id=config.granite_model_id,
        credentials=credentials,
        project_id=config.watsonx_project_id,
        params=params,
    )

    logger.info("Granite model initialised: %s", config.granite_model_id)
    return model


# ---------------------------------------------------------------------------
# GraniteClient
# ---------------------------------------------------------------------------

class GraniteClient:
    """
    Thin wrapper around IBM Granite / WatsonX ModelInference.

    Parameters
    ----------
    config : Config
        Application configuration containing credentials and model settings.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._model = _get_model(config)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, prompt: str) -> str:
        """
        Send *prompt* to Granite and return the generated text.

        Parameters
        ----------
        prompt : str
            Fully-formatted prompt string.

        Returns
        -------
        str
            Raw text response from the model.
        """
        logger.debug("Sending prompt to Granite (%d chars).", len(prompt))
        response = self._model.generate_text(prompt=prompt)
        logger.debug("Received response (%d chars).", len(response))
        return response.strip()

    def generate_with_metadata(self, prompt: str) -> dict[str, Any]:
        """
        Like `generate` but returns the full response dict including
        token counts and stop reason — useful for debugging.
        """
        logger.debug("Sending prompt (with metadata) to Granite.")
        result = self._model.generate(prompt=prompt)
        return result
