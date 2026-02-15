"""Legacy Brain — DEPRECATED. Utilisez src.brain.brain_engine.BrainEngine à la place.

Ce module est conservé uniquement pour compatibilité avec les exemples de test.
Il ne fait PAS partie du pipeline principal (main.py → listener.py → BrainEngine).
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any

from .chroma_client import ChromaClient
from .tts_client import TTSClient
from .gui_face import FaceController, FaceState

logger = logging.getLogger(__name__)

# Client OpenAI standard (pas Azure SDK inexistant)
try:
    from openai import AsyncOpenAI  # type: ignore
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    logger.warning("openai SDK non disponible")


class Brain:
    """Legacy Brain — wrapper simplifié pour les exemples.

    DEPRECATED: Utiliser BrainEngine pour le pipeline principal.
    """

    def __init__(self,
                 chroma_collection: str = "personal_context",
                 face: Optional[FaceController] = None):
        self.chroma = ChromaClient(collection_name=chroma_collection)

        # HomeAssistantClient conditionnel (ne crashe plus sans HA_TOKEN)
        self.ha = None
        try:
            from .home_assistant_client import HomeAssistantClient
            self.ha = HomeAssistantClient()
        except Exception as e:
            logger.warning(f"HomeAssistantClient non disponible: {e}")

        self.tts = TTSClient()
        self.face = face or FaceController()

        # OpenAI standard (pas Azure)
        self.openai_key = os.environ.get("OPENAI_API_KEY", "")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

        self._client: Optional[AsyncOpenAI] = None
        if HAS_OPENAI and self.openai_key:
            self._client = AsyncOpenAI(api_key=self.openai_key)

    async def handle_text(self, text: str):
        await self.face.set_state(FaceState.LISTENING)
        await asyncio.sleep(0.05)
        await self.face.set_state(FaceState.PROCESSING)

        context_snippets = await self.chroma.query(text, top_k=3)

        messages = [
            {"role": "system", "content": "You are a home assistant. Use function calls to control Home Assistant lights when appropriate."},
            {"role": "user", "content": text},
        ]

        if context_snippets:
            messages.append({"role": "system", "content": "Context from user memory:\n" + "\n".join(context_snippets)})

        response = await self._call_gpt(messages)

        # Handle function call if present
        if isinstance(response, dict) and response.get("function_call"):
            await self._handle_function_call(response["function_call"])
            reply_text = response.get("content") or "D'accord, j'ai exécuté la commande." 
        else:
            reply_text = response if isinstance(response, str) else response.get("content", "")

        await self.face.set_state(FaceState.RESPONDING)
        await self._speak_with_retry(reply_text)
        await asyncio.sleep(0.1)
        await self.face.set_state(FaceState.IDLE)

    async def _speak_with_retry(self, text: str, max_retries: int = 2) -> bool:
        """Speak text with retry logic and graceful degradation."""
        for attempt in range(max_retries + 1):
            try:
                await self.tts.speak(text)
                logger.info(f"✓ TTS succeeded (attempt {attempt + 1})")
                return True
            except Exception as e:
                logger.warning(f"TTS failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(0.5)
                else:
                    logger.error(f"TTS exhausted retries: {e}")
                    # Graceful degradation: continue without audio
                    return False
        return False

    async def _call_gpt(self, messages, retries: int = 2) -> Dict[str, Any] | str:
        """Call GPT-4o with retry logic on transient failures."""
        for attempt in range(retries + 1):
            try:
                if self._client:
                    completion = await self._client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        max_tokens=800,
                        temperature=0.6,
                    )
                    choice = completion.choices[0]
                    tool_calls = getattr(choice.message, "tool_calls", None)
                    if tool_calls:
                        tc = tool_calls[0]
                        return {
                            "function_call": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                            "content": choice.message.content,
                        }
                    return choice.message.content or ""

                # Fallback: REST direct via aiohttp
                import aiohttp
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.openai_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 800,
                    "temperature": 0.6,
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
                        r.raise_for_status()
                        data = await r.json()
                        msg = data["choices"][0]["message"]
                        if msg.get("function_call"):
                            return {"function_call": msg["function_call"], "content": msg.get("content")}
                        return msg.get("content", "")
            except asyncio.TimeoutError:
                logger.warning(f"GPT timeout (attempt {attempt + 1}/{retries + 1})")
                if attempt < retries:
                    await asyncio.sleep(1)
                else:
                    raise
            except Exception as e:
                logger.warning(f"GPT error (attempt {attempt + 1}/{retries + 1}): {e}")
                if attempt < retries:
                    await asyncio.sleep(1)
                else:
                    raise
        
        return "Désolé, je n'ai pas pu traiter votre demande."

    async def _handle_function_call(self, function_call: Dict[str, Any]):
        """Execute function calls from GPT with error handling."""
        name = function_call.get("name")
        args = function_call.get("arguments") or {}
        
        if not self.ha:
            logger.warning(f"Function call '{name}' ignoré — HomeAssistant non configuré")
            return
        
        try:
            # Basic mapping: light control
            if name in ("light.turn_on", "turn_on_light", "set_light"):
                entity = args.get("entity_id") or args.get("entity")
                on = True
                brightness = args.get("brightness")
                color = args.get("color_name")
                await self.ha.set_light(entity_id=entity, on=on, brightness=brightness, color_name=color)
                logger.info(f"✓ Function call executed: {name}")
            elif name in ("light.turn_off", "turn_off_light"):
                entity = args.get("entity_id") or args.get("entity")
                await self.ha.set_light(entity_id=entity, on=False)
                logger.info(f"✓ Function call executed: {name}")
            else:
                # Unknown function: log/ignore
                logger.debug(f"Unknown function call: {name}")
        except Exception as e:
            logger.error(f"Function call failed ({name}): {e}")

    async def update_face_state(self, state: FaceState):
        await self.face.set_state(state)
