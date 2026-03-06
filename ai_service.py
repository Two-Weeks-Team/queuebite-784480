import os
import json
from typing import Any, Dict, List

import httpx
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = os.getenv("DO_INFERENCE_MODEL", "openai-gpt-oss-120b")
API_KEY = os.getenv("DIGITALOCEAN_INFERENCE_KEY")
BASE_ENDPOINT = os.getenv("AI_MODEL_ENDPOINT", "https://inference.do-ai.run/v1")

if not API_KEY:
    raise RuntimeError("DIGITALOCEAN_INFERENCE_KEY environment variable is required")

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


class ChatMessage(BaseModel):
    role: str
    content: str


class InferenceResponseChoice(BaseModel):
    message: ChatMessage


class InferenceResponse(BaseModel):
    choices: List[InferenceResponseChoice]


class AIService:
    def __init__(
        self, model: str = DEFAULT_MODEL, endpoint: str = BASE_ENDPOINT
    ) -> None:
        self.model = model
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
        payload = {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": 512,
        }
        raw = await self._post(payload)
        return await self._parse_response(raw)

    async def predict_wait_time(self, features: Dict[str, Any]) -> Dict[str, Any]:
        system_msg = {
            "role": "system",
            "content": (
                "You are a restaurant wait-time prediction model. Given the input features, "
                "respond with a JSON object containing `wait_minutes` (int) and `confidence` "
                "(float 0-1). Do NOT add any extra text."
            ),
        }
        user_msg = {"role": "user", "content": json.dumps(features)}
        response_text = await self.chat([system_msg, user_msg])
        try:
            data = json.loads(response_text)
            return {
                "predicted_wait_minutes": int(data["wait_minutes"]),
                "confidence": float(data["confidence"]),
            }
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            raise RuntimeError(f"Failed to parse wait-time prediction: {exc}") from exc

    async def forecast_demand(self, features: Dict[str, Any]) -> Dict[str, Any]:
        system_msg = {
            "role": "system",
            "content": (
                "You are a demand-forecasting assistant for a restaurant. "
                "Given recent foot-fall, local events, and weather, respond with a JSON object "
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


ai_service = AIService()
