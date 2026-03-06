import os
import json
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field, ValidationError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_MODEL = os.getenv("DO_INFERENCE_MODEL", "gpt-5-mini")
API_KEY = os.getenv("DIGITALOCEAN_INFERENCE_KEY")
# DigitalOcean provides a generic endpoint for serverless inference; this is the typical base.
BASE_ENDPOINT = os.getenv(
    "AI_MODEL_ENDPOINT",
    "https://api.digitalocean.com/v1/ai/inference",
)  # can be overridden via env for testing

if not API_KEY:
    raise RuntimeError("DIGITALOCEAN_INFERENCE_KEY environment variable is required")

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# ---------------------------------------------------------------------------
# Helper Pydantic models – they give us strict JSON validation on the client side.
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the message – either 'system', 'user', or 'assistant'")
    content: str = Field(..., description="The text of the message")

class InferenceResponseChoice(BaseModel):
    message: ChatMessage

class InferenceResponse(BaseModel):
    choices: List[InferenceResponseChoice]

# ---------------------------------------------------------------------------
# Core AI service class – all interactions with the DO inference API happen here.
# ---------------------------------------------------------------------------
class AIService:
    """Encapsulates calls to the DigitalOcean Serverless Inference API.

    The service is deliberately lightweight – it just forwards a chat‑completion request
    and extracts the `content` field from the first choice.
    """

    def __init__(self, model: str = DEFAULT_MODEL, endpoint: str = BASE_ENDPOINT) -> None:
        self.model = model
        # Ensure the endpoint ends without a trailing slash for predictable URL building
        self.endpoint = endpoint.rstrip("/")

    async def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.endpoint}/chat/completions"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=HEADERS, json=payload)
            response.raise_for_status()
            return response.json()

    async def _parse_response(self, raw: Dict[str, Any]) -> str:
        try:
            parsed = InferenceResponse(**raw)
            return parsed.choices[0].message.content.strip()
        except (ValidationError, IndexError) as exc:
            raise RuntimeError(f"Unexpected inference response format: {exc}") from exc

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """Send a list of messages to the model and return the generated text.

        Parameters
        ----------
        messages: List[dict]
            Each dict must contain ``role`` and ``content`` keys.
        """
        payload = {"model": self.model, "messages": messages}
        raw = await self._post(payload)
        return await self._parse_response(raw)

    # ---------------------------------------------------------------------
    # Domain‑specific helpers used by the QueueBite endpoints.
    # ---------------------------------------------------------------------
    async def predict_wait_time(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Ask the LLM to predict a wait time in minutes.

        The prompt is intentionally simple; the model is expected to return a JSON string
        like ``{"wait_minutes": 12, "confidence": 0.91}``.
        """
        system_msg = {
            "role": "system",
            "content": (
                "You are a restaurant wait‑time prediction model. Given the input features, "
                "respond with a JSON object containing `wait_minutes` (int) and `confidence` "
                "(float 0‑1). Do NOT add any extra text."
            ),
        }
        user_msg = {"role": "user", "content": json.dumps(features)}
        response_text = await self.chat([system_msg, user_msg])
        try:
            data = json.loads(response_text)
            return {"predicted_wait_minutes": int(data["wait_minutes"]), "confidence": float(data["confidence"]) }
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            raise RuntimeError(f"Failed to parse wait‑time prediction: {exc}") from exc

    async def forecast_demand(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Ask the LLM to forecast demand for the next 24 h.

        Expected output JSON example:
        ``{"peak_hour": "19:00", "expected_party_increase": 35}``
        """
        system_msg = {
            "role": "system",
            "content": (
                "You are a demand‑forecasting assistant for a restaurant. "
                "Given recent foot‑fall, local events, and weather, respond with a JSON object "
                "containing `peak_hour` (HH:MM) and `expected_party_increase` (percentage integer). "
                "Only return the JSON."
            ),
        }
        user_msg = {"role": "user", "content": json.dumps(features)}
        response_text = await self.chat([system_msg, user_msg])
        try:
            data = json.loads(response_text)
            return {
                "peak_hour": str(data["peak_hour"]),
                "expected_party_increase_percent": int(data["expected_party_increase"]),
            }
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            raise RuntimeError(f"Failed to parse demand forecast: {exc}") from exc

# Export a singleton for easy import in route handlers
ai_service = AIService()
