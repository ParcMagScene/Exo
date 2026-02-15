import os
import asyncio
import logging
from typing import Optional, Dict, Any

from .chroma_client import ChromaClient
from .home_assistant_client import HomeAssistantClient
from .tts_client import TTSClient
from .gui_face import FaceController, FaceState

logger = logging.getLogger(__name__)

try:
    from azure.ai.openai.aio import OpenAIClient
except Exception:
    OpenAIClient = None


class Brain:
    """Central assistant 'Brain'.

    Responsibilities:
    - recevoir texte transcrit
    - enrichir avec contexte depuis ChromaDB
    - envoyer prompt à GPT-4o via Azure AI SDK (async)
    - gérer function-calls pour Home Assistant
    - envoyer texte au moteur TTS
    - mettre à jour l'état du visage 2D (IDLE, LISTENING, THINKING, SPEAKING)
    """

    def __init__(self,
                 chroma_collection: str = "personal_context",
                 face: Optional[FaceController] = None):
        self.chroma = ChromaClient(collection_name=chroma_collection)
        self.ha = HomeAssistantClient()
        self.tts = TTSClient()
        self.face = face or FaceController()

        self.azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        self.azure_key = os.environ.get("AZURE_OPENAI_KEY")
        self.deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

        if OpenAIClient is None:
            # graceful: we will try to call via httpx if SDK not installed
            self._use_sdk = False
        else:
            self._use_sdk = True
            self._client = OpenAIClient(self.azure_endpoint, credential=self.azure_key)

    async def handle_text(self, text: str):
        await self.face.set_state(FaceState.LISTENING)
        await asyncio.sleep(0.05)
        await self.face.set_state(FaceState.THINKING)

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

        await self.face.set_state(FaceState.SPEAKING)
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
                # Prefer SDK if available
                if self._use_sdk and self._client:
                    # sdk usage - simplified for clarity
                    completion = await self._client.chat.completions.create(
                        deployment=self.deployment,
                        messages=messages,
                        max_tokens=800,
                        temperature=0.6,
                        # request function-calling style payloads via instructions in system role
                    )
                    choice = completion.choices[0]
                    # Azure SDK chat response shape may vary; try to extract function_call
                    func_call = getattr(choice, "function_call", None)
                    if func_call:
                        return {"function_call": {"name": func_call.name, "arguments": func_call.arguments}, "content": choice.message.get("content")}
                    return choice.message.get("content")

                # Fallback: simple REST call using httpx
                import httpx
                url = f"{self.azure_endpoint.rstrip('/')}/openai/deployments/{self.deployment}/chat/completions?api-version=2023-05-15"
                headers = {"api-key": self.azure_key, "Content-Type": "application/json"}
                payload = {"messages": messages, "max_tokens": 800, "temperature": 0.6}
                async with httpx.AsyncClient() as client:
                    r = await client.post(url, json=payload, headers=headers, timeout=30.0)
                    r.raise_for_status()
                    data = r.json()
                    choice = data.get("choices", [])[0]
                    msg = choice.get("message", {})
                    # Some endpoints may include function_call inside message
                    if msg.get("function_call"):
                        return {"function_call": msg.get("function_call"), "content": msg.get("content")}
                    return msg.get("content")
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
