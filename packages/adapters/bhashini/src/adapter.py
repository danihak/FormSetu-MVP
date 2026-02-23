"""
BHASHINI Channel Adapter
=========================
Integrates FormSetu with BHASHINI Pipeline APIs for voice-based form filling.
Uses standard BHASHINI ULCA endpoints — no custom APIs needed.

Flow:
  1. Citizen speaks → audio sent to BHASHINI ASR → text
  2. Text (in citizen's language) → NMT → translate to engine language if needed
  3. FormSetu engine processes text → generates response text
  4. Response text → NMT → citizen's language → TTS → audio
  5. Audio sent back to citizen
"""

import os
import json
import logging
from typing import Optional
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class BhashiniConfig:
    user_id: str
    api_key: str
    pipeline_id: str = "64392f96daac500b55c543cd"
    ulca_base_url: str = "https://meity-auth.ulcacontrib.org"
    pipeline_endpoint: str = "/ulca/apis/v0/model/getModelsPipeline"

    @classmethod
    def from_env(cls) -> "BhashiniConfig":
        return cls(
            user_id=os.environ["BHASHINI_USER_ID"],
            api_key=os.environ["BHASHINI_API_KEY"],
            pipeline_id=os.environ.get("BHASHINI_PIPELINE_ID", cls.pipeline_id),
        )


class BhashiniAdapter:
    """
    Adapter for BHASHINI voice pipeline.
    Handles ASR, TTS, NMT, and combined pipelines.
    """

    def __init__(self, config: BhashiniConfig):
        self.config = config
        self._callback_url: Optional[str] = None
        self._inference_key: Optional[str] = None
        self._service_ids: dict = {}
        self._configured = False

    async def configure(self):
        """Fetch pipeline config from BHASHINI. Must be called before inference."""
        body = {
            "pipelineTasks": [
                {"taskType": "asr"},
                {"taskType": "translation"},
                {"taskType": "tts"},
            ],
            "pipelineRequestConfig": {
                "pipelineId": self.config.pipeline_id
            },
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.config.ulca_base_url}{self.config.pipeline_endpoint}",
                json=body,
                headers={
                    "userID": self.config.user_id,
                    "ulcaApiKey": self.config.api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        api_endpoint = data["pipelineInferenceAPIEndPoint"]
        self._callback_url = api_endpoint["callbackUrl"]
        self._inference_key = api_endpoint["inferenceApiKey"]["value"]

        for task_config in data.get("pipelineResponseConfig", []):
            task_type = task_config["taskType"]
            if task_type not in self._service_ids:
                self._service_ids[task_type] = {}
            configs = task_config.get("config", [])
            if isinstance(configs, dict):
                configs = [configs]
            for cfg in configs:
                if cfg and "language" in cfg:
                    lang = cfg["language"].get("sourceLanguage", "")
                    sid = cfg.get("serviceId", "")
                    if lang and sid:
                        self._service_ids[task_type][lang] = sid

        self._configured = True
        logger.info("BHASHINI configured. Tasks: %s",
                     {k: list(v.keys()) for k, v in self._service_ids.items()})

    # ---- Core API Methods ----

    async def speech_to_text(self, audio_base64: str, source_lang: str,
                             audio_format: str = "wav", sample_rate: int = 16000) -> str:
        """ASR: audio → text in source language."""
        self._ensure_configured()
        payload = {
            "pipelineTasks": [{
                "taskType": "asr",
                "config": {
                    "language": {"sourceLanguage": source_lang},
                    "serviceId": self._get_service_id("asr", source_lang),
                    "audioFormat": audio_format,
                    "samplingRate": sample_rate,
                },
            }],
            "inputData": {
                "audio": [{"audioContent": audio_base64}],
            },
        }
        result = await self._inference(payload)
        return result["pipelineResponse"][0]["output"][0]["source"]

    async def text_to_speech(self, text: str, lang: str,
                             gender: str = "female") -> str:
        """TTS: text → base64 audio (WAV)."""
        self._ensure_configured()
        payload = {
            "pipelineTasks": [{
                "taskType": "tts",
                "config": {
                    "language": {"sourceLanguage": lang},
                    "serviceId": self._get_service_id("tts", lang),
                    "gender": gender,
                },
            }],
            "inputData": {
                "input": [{"source": text}],
            },
        }
        result = await self._inference(payload)
        return result["pipelineResponse"][0]["audio"][0]["audioContent"]

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """NMT: translate text between languages."""
        self._ensure_configured()
        payload = {
            "pipelineTasks": [{
                "taskType": "translation",
                "config": {
                    "language": {
                        "sourceLanguage": source_lang,
                        "targetLanguage": target_lang,
                    },
                    "serviceId": self._get_service_id("translation", source_lang),
                },
            }],
            "inputData": {
                "input": [{"source": text}],
            },
        }
        result = await self._inference(payload)
        return result["pipelineResponse"][0]["output"][0]["target"]

    async def speech_to_text_translated(self, audio_base64: str,
                                         source_lang: str, target_lang: str,
                                         audio_format: str = "wav",
                                         sample_rate: int = 16000) -> dict:
        """
        Combined ASR + NMT: audio in one language → text in another.
        Returns both source transcription and translated text.
        """
        self._ensure_configured()
        payload = {
            "pipelineTasks": [
                {
                    "taskType": "asr",
                    "config": {
                        "language": {"sourceLanguage": source_lang},
                        "serviceId": self._get_service_id("asr", source_lang),
                        "audioFormat": audio_format,
                        "samplingRate": sample_rate,
                    },
                },
                {
                    "taskType": "translation",
                    "config": {
                        "language": {
                            "sourceLanguage": source_lang,
                            "targetLanguage": target_lang,
                        },
                        "serviceId": self._get_service_id("translation", source_lang),
                    },
                },
            ],
            "inputData": {
                "audio": [{"audioContent": audio_base64}],
            },
        }
        result = await self._inference(payload)
        responses = result["pipelineResponse"]
        return {
            "source_text": responses[0]["output"][0]["source"],
            "translated_text": responses[1]["output"][0]["target"],
        }

    async def translate_and_speak(self, text: str, source_lang: str,
                                   target_lang: str, gender: str = "female") -> dict:
        """
        Combined NMT + TTS: text in one language → audio in another.
        Returns translated text and audio.
        """
        self._ensure_configured()
        payload = {
            "pipelineTasks": [
                {
                    "taskType": "translation",
                    "config": {
                        "language": {
                            "sourceLanguage": source_lang,
                            "targetLanguage": target_lang,
                        },
                        "serviceId": self._get_service_id("translation", source_lang),
                    },
                },
                {
                    "taskType": "tts",
                    "config": {
                        "language": {"sourceLanguage": target_lang},
                        "serviceId": self._get_service_id("tts", target_lang),
                        "gender": gender,
                    },
                },
            ],
            "inputData": {
                "input": [{"source": text}],
            },
        }
        result = await self._inference(payload)
        responses = result["pipelineResponse"]
        return {
            "translated_text": responses[0]["output"][0]["target"],
            "audio_base64": responses[1]["audio"][0]["audioContent"],
        }

    # ---- High-Level FormSetu Integration ----

    async def process_voice_turn(self, audio_base64: str, citizen_lang: str,
                                  engine_lang: str = "en") -> str:
        """
        Full voice input processing for FormSetu engine.
        
        1. ASR in citizen's language
        2. Translate to engine language (if different)
        3. Return text for engine to process
        
        Args:
            audio_base64: Citizen's voice recording
            citizen_lang: Citizen's language (e.g., "as" for Assamese)
            engine_lang: Engine's processing language (default "en")
            
        Returns:
            Text in engine_lang ready for engine processing
        """
        if citizen_lang == engine_lang:
            return await self.speech_to_text(audio_base64, citizen_lang)
        
        result = await self.speech_to_text_translated(
            audio_base64, citizen_lang, engine_lang
        )
        return result["translated_text"]

    async def generate_voice_response(self, text: str, citizen_lang: str,
                                       engine_lang: str = "en",
                                       gender: str = "female") -> dict:
        """
        Full voice output generation for FormSetu engine.
        
        1. Translate engine response to citizen's language (if needed)
        2. Generate TTS audio
        
        Args:
            text: Engine's response text (in engine_lang)
            citizen_lang: Target language for citizen
            engine_lang: Language of input text
            
        Returns:
            {"text": translated_text, "audio": base64_audio}
        """
        if citizen_lang == engine_lang:
            audio = await self.text_to_speech(text, citizen_lang, gender)
            return {"text": text, "audio": audio}
        
        result = await self.translate_and_speak(
            text, engine_lang, citizen_lang, gender
        )
        return {
            "text": result["translated_text"],
            "audio": result["audio_base64"],
        }

    # ---- Utility ----

    def get_supported_languages(self, task_type: str = "asr") -> list[str]:
        """Get list of language codes supported for a given task."""
        self._ensure_configured()
        return list(self._service_ids.get(task_type, {}).keys())

    def _get_service_id(self, task_type: str, lang: str) -> str:
        services = self._service_ids.get(task_type, {})
        if lang not in services:
            available = list(services.keys())
            raise ValueError(
                f"Language '{lang}' not available for {task_type}. "
                f"Available: {available}"
            )
        return services[lang]

    def _ensure_configured(self):
        if not self._configured:
            raise RuntimeError(
                "BhashiniAdapter not configured. Call await adapter.configure() first."
            )

    async def _inference(self, payload: dict) -> dict:
        """Make inference call to BHASHINI pipeline compute endpoint."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self._callback_url,
                json=payload,
                headers={"Authorization": self._inference_key},
            )
            if resp.status_code != 200:
                logger.error("BHASHINI inference failed: %s %s", resp.status_code, resp.text)
                resp.raise_for_status()
            return resp.json()
