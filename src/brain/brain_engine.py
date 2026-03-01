"""brain_engine.py - Moteur IA (LLM + RAG + Function Calling).

Responsabilités:
- Appels à GPT-4o via OpenAI SDK (standard ou Azure)
- Injection du contexte ChromaDB (animaux, plan maison, préférences)
- Identification et exécution des outils (Function Calling)
- Gestion de l'historique de conversation
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

try:
    from openai import AsyncOpenAI, AsyncAzureOpenAI  # type: ignore
    HAS_OPENAI_SDK = True
except ImportError:
    HAS_OPENAI_SDK = False
    logger.warning("⚠️ openai SDK non disponible - fallback REST")

try:
    import chromadb  # type: ignore
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False
    logger.warning("⚠️ ChromaDB non disponible")

import aiohttp

from src.brain.local_info import LocalInfo


class BrainEngine:
    """Cerveau IA avec contexte RAG et Function Calling."""

    def __init__(self, config: Optional[object] = None):
        """
        Initialise le moteur IA.
        
        Args:
            config: Configuration optionnelle (ignorée si Config passée)
        """
        # Infos locales (heure, météo, localisation)
        self.local_info = LocalInfo()

        # OpenAI standard (prioritaire)
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        # Azure OpenAI (fallback)
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_key = os.getenv("AZURE_OPENAI_KEY")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        
        # Déterminer le mode
        self._use_openai_standard = bool(self.openai_key and self.openai_key.startswith("sk-"))
        self._use_azure = bool(self.azure_key and self.azure_key != "your-azure-api-key-here")
        
        self._client = None
        self._chroma_client = None
        self._conversation_history: List[Dict[str, str]] = []
        
        # Outils disponibles (Function Calling)
        self.tools = self._define_tools()
        
        logger.info("✅ BrainEngine initialisé")

    async def initialize(self):
        """Initialisation asynchrone."""
        if HAS_OPENAI_SDK:
            try:
                if self._use_openai_standard:
                    self._client = AsyncOpenAI(api_key=self.openai_key)
                    logger.info(f"✅ Client OpenAI standard connecté (modèle: {self.model})")
                elif self._use_azure:
                    self._client = AsyncAzureOpenAI(
                        api_key=self.azure_key,
                        api_version=self.api_version,
                        azure_endpoint=self.azure_endpoint
                    )
                    logger.info("✅ Client Azure OpenAI connecté")
                else:
                    logger.warning("⚠️ Aucune clé API configurée (OPENAI_API_KEY ou AZURE_OPENAI_KEY)")
            except Exception as e:
                logger.error(f"Erreur connexion OpenAI: {e}")
        
        # Initialiser ChromaDB
        if HAS_CHROMA:
            try:
                self._chroma_client = chromadb.PersistentClient(
                    path="./data/chroma"
                )
                # Créer/récupérer les collections
                self._collection_animals = self._chroma_client.get_or_create_collection(
                    name="animals",
                    metadata={"description": "Informations sur les animaux"}
                )
                self._collection_house = self._chroma_client.get_or_create_collection(
                    name="house_plan",
                    metadata={"description": "Plan et pièces de la maison"}
                )
                self._collection_preferences = self._chroma_client.get_or_create_collection(
                    name="user_preferences",
                    metadata={"description": "Préférences utilisateur"}
                )
                logger.info("✅ ChromaDB initialisé avec 3 collections")
            except Exception as e:
                logger.error(f"Erreur ChromaDB: {e}")

    def _define_tools(self) -> List[Dict[str, Any]]:
        """Définit les outils disponibles pour le Function Calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "control_light",
                    "description": "Contrôle l'éclairage (Philips Hue / IKEA)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["on", "off", "dim"],
                                "description": "Action: allumer, éteindre ou dimmer"
                            },
                            "room": {
                                "type": "string",
                                "description": "Pièce cible (salon, chambre, cuisine, etc.)"
                            },
                            "brightness": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                                "description": "Luminosité 0-100%"
                            },
                            "color": {
                                "type": "string",
                                "description": "Couleur (red, blue, warm, cool, etc.)"
                            }
                        },
                        "required": ["action", "room"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "control_media",
                    "description": "Contrôle TV/Soundbar Samsung",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "device": {
                                "type": "string",
                                "enum": ["tv", "soundbar"],
                                "description": "Appareil cible"
                            },
                            "action": {
                                "type": "string",
                                "enum": ["on", "off", "volume", "channel"],
                                "description": "Action"
                            },
                            "value": {
                                "type": "integer",
                                "description": "Valeur (volume, numéro de chaîne)"
                            }
                        },
                        "required": ["device", "action"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "play_music",
                    "description": "Lance une chanson/playlist TIDAL via Mopidy",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Chanson, artiste ou playlist à rechercher"
                            },
                            "action": {
                                "type": "string",
                                "enum": ["play", "pause", "next", "previous"],
                                "description": "Action de contrôle"
                            }
                        },
                        "required": ["query", "action"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_camera",
                    "description": "Récupère le flux vidéo EZWIZ ou contrôle la caméra",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "camera_id": {
                                "type": "string",
                                "description": "ID de la caméra"
                            },
                            "action": {
                                "type": "string",
                                "enum": ["view", "record", "stop"],
                                "description": "Action caméra"
                            }
                        },
                        "required": ["camera_id", "action"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_petkit",
                    "description": "Requête statut litière Petkit (états, alertes)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "ID du dispositif Petkit"
                            },
                            "metric": {
                                "type": "string",
                                "enum": ["litter_level", "last_use", "health", "all"],
                                "description": "Métrique à récupérer"
                            }
                        },
                        "required": ["device_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "store_memory",
                    "description": "Stocke une information dans la mémoire long terme (ChromaDB)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": ["animal", "house", "preference"],
                                "description": "Catégorie"
                            },
                            "content": {
                                "type": "string",
                                "description": "Information à mémoriser"
                            }
                        },
                        "required": ["category", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_local_info",
                    "description": "Récupère les informations locales en temps réel : heure actuelle, date, météo, lever/coucher du soleil, prévisions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "info_type": {
                                "type": "string",
                                "enum": ["time", "weather", "all"],
                                "description": "Type d'info : time (heure/date), weather (météo), all (tout)"
                            }
                        },
                        "required": ["info_type"]
                    }
                }
            }
        ]

    async def process_command(
        self,
        text: str,
        room: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Traite une commande utilisateur avec contexte enrichi.
        
        Gère à la fois:
        - Commandes pratiques (allumer lumière)
        - Conversations philosophiques/scientifiques
        
        Args:
            text: Texte de l'utilisateur
            room: Pièce source (si applicable)
            context: Contexte additionnel (timestamp, etc.)
        
        Returns:
            Dict avec 'text' (réponse), 'function_calls', 'confidence'
        """
        logger.info(f"💬 Conversation: '{text}' (pièce: {room})")
        
        # Récupération contexte RAG + local EN PARALLÈLE (gain ~0.5-1s)
        rag_context, local_context = await asyncio.gather(
            self._fetch_rag_context(text, room),
            self.local_info.get_context_summary(),
        )
        
        # Construction du prompt système enrichi
        system_prompt = self._build_system_prompt(room, rag_context, local_context)
        
        # Ajouter à l'historique (garder les 50 derniers messages)
        self._conversation_history.append({"role": "user", "content": text})
        
        # Limiter l'historique à CONVERSATION_HISTORY_SIZE
        max_history = 50  # from config à utiliser
        if len(self._conversation_history) > max_history * 2:  # Garder buffer
            self._conversation_history = self._conversation_history[-max_history:]
        
        # Déterminer si des outils domotiques sont nécessaires
        # (skip tools = prompt plus léger = réponse GPT ~2x plus rapide)
        _ACTION_KW = (
            "allume", "éteins", "éteindre", "lumière", "lampe", "lamp",
            "tv", "télé", "volume", "musique", "joue", "play", "pause",
            "caméra", "camera", "litière", "petkit",
            "mémorise", "retiens", "souviens", "rappelle",
            "heure", "météo", "temps qu'il", "température",
        )
        text_lower = text.lower()
        needs_tools = any(kw in text_lower for kw in _ACTION_KW)
        tools_to_send = self.tools if needs_tools else []

        # Appel à GPT-4o avec température basse pour réponses directes
        response = await self._call_gpt4o(
            messages=self._build_messages(system_prompt),
            tools=tools_to_send,
            temperature=0.5,
            max_tokens=80    # Ultra court : 2 phrases max pour réponse vocale
        )
        
        # Parser réponse et extraire function calls
        result = self._parse_response(response)
        
        # Ajouter réponse à l'historique
        if result.get("text"):
            self._conversation_history.append({
                "role": "assistant",
                "content": result["text"]
            })
        
        return result

    async def _fetch_rag_context(self, text: str, room: Optional[str]) -> str:
        """Récupère le contexte pertinent depuis ChromaDB (requêtes parallèles)."""
        if not HAS_CHROMA or not self._chroma_client:
            return ""
        
        context_parts = []
        
        try:
            loop = asyncio.get_running_loop()
            
            # Lancer les 3 requêtes ChromaDB en parallèle (gain ~2x)
            animals_fut = loop.run_in_executor(
                None, lambda: self._collection_animals.query(query_texts=[text], n_results=2)
            )
            house_fut = loop.run_in_executor(
                None, lambda: self._collection_house.query(query_texts=[text], n_results=2)
            )
            prefs_fut = loop.run_in_executor(
                None, lambda: self._collection_preferences.query(query_texts=[text], n_results=2)
            )
            
            results_animals, results_house, results_prefs = await asyncio.gather(
                animals_fut, house_fut, prefs_fut,
                return_exceptions=True,
            )
            
            if not isinstance(results_animals, Exception):
                if results_animals.get("documents") and results_animals["documents"][0]:
                    context_parts.append("🐾 Infos animaux: " + ", ".join(results_animals["documents"][0]))
            
            if not isinstance(results_house, Exception):
                if results_house.get("documents") and results_house["documents"][0]:
                    context_parts.append("🏠 Plan maison: " + ", ".join(results_house["documents"][0]))
            
            if not isinstance(results_prefs, Exception):
                if results_prefs.get("documents") and results_prefs["documents"][0]:
                    context_parts.append("⚙️ Préférences: " + ", ".join(results_prefs["documents"][0]))
        
        except Exception as e:
            logger.error(f"Erreur RAG: {e}")
        
        return "\n".join(context_parts)

    def _build_system_prompt(self, room: Optional[str], rag_context: str, local_context: str = "") -> str:
        """Construit le prompt système pour conversations enrichies."""
        prompt = """Tu es EXO, un interlocuteur personnel haut de gamme - à la fois:

[ASSISTANT DOMOTIQUE]
- Gère une domotique complète (HUE, IKEA, Samsung, EZWIZ, Petkit)
- Identifie les commandes requérant des outils et les exécute
- Actions immédiate pour besoins pratiques

[COMPAGNON CONVERSATIONNEL]
- Philosophe: débats éthiques, existentiels, questions de sens
- Scientifique: explique concepts complexes, analyse théories
- Empathique: comprends contexte émotionnel, réponds avec nuance
- Curieux: pose des questions de suivi, offres perspectives multiples

[PRINCIPES FONDAMENTAUX]
1. Sois honnête sur tes limites: tu es IA, pas conscience
2. Reconnais l'ambiguïté: peu de réponses absolues en philo/science
3. Nuancé: différencie certitude vs speculation
4. Engageant: conversationnel, pas pédant
5. Contexte: utilise les infos personnalisées pour intimité

[STYLE]
- Naturel et conversationnel (évite jargon sauf pertinent)
- Références concrètes quand possible
- Reconnaître l'incertitude plutôt que faux absolus
- Balance entre action pratique et réflexion

[IMPÉRATIF — LONGUEUR]
- Tu es un assistant VOCAL : tes réponses sont LUES À VOIX HAUTE.
- MAXIMUM 2 phrases courtes par réponse. Jamais plus.
- Va droit au but. Pas de listes, pas d'énumérations, pas de détails superflus.
- Si l'utilisateur veut plus de détails, il demandera."""
        
        if local_context:
            prompt += f"\n\n[SITUATION ACTUELLE — TEMPS RÉEL]\n{local_context}\n\nUtilise ces données pour répondre aux questions sur l'heure, la date, la météo, le lever/coucher du soleil, etc. Ces infos sont EN TEMPS RÉEL, fais-y confiance."
        
        if room:
            prompt += f"\n\n[PIÈCE ACTIVE]\nL'utilisateur est dans : {room}"
        
        if rag_context:
            prompt += f"\n\n[PROFIL PERSONNEL]\n{rag_context}\n\nUtilise ces infos pour personnaliser tes reponses (intimite, comprehension du contexte utilisateur)."
        
        return prompt

    def _build_messages(self, system_prompt: str) -> List[Dict[str, str]]:
        """Construit la liste des messages."""
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self._conversation_history[-6:])  # 6 derniers messages (moins de tokens)
        return messages

    async def _call_gpt4o(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        temperature: float = 0.5,
        max_tokens: int = 300
    ) -> Dict[str, Any]:
        """Appelle GPT-4o via OpenAI SDK (standard ou Azure).
        
        Args:
            messages: Conversation history
            tools: Available function calls
            temperature: Contrôle créativité (0.5 pour réponses directes)
            max_tokens: Longueur max réponse (300 pour réponses vocales courtes)
        """
        
        if HAS_OPENAI_SDK and self._client:
            try:
                # Utiliser le bon nom de modèle selon le mode
                model_name = self.model if self._use_openai_standard else self.deployment
                
                # Ne pas envoyer tools vide (erreur API + tokens gaspillés)
                kwargs = dict(
                    model=model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=30.0,
                )
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"
                
                response = await self._client.chat.completions.create(**kwargs)
                # Convertir en dict pour compatibilité _parse_response
                return response.model_dump()
            except Exception as e:
                logger.error(f"Erreur OpenAI SDK: {e}")
                return await self._call_gpt4o_rest(messages, tools, temperature, max_tokens)
        else:
            return await self._call_gpt4o_rest(messages, tools, temperature, max_tokens)

    async def _call_gpt4o_rest(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        temperature: float = 0.5,
        max_tokens: int = 300
    ) -> Dict[str, Any]:
        """Appel REST direct (OpenAI standard ou Azure)."""
        
        if self._use_openai_standard:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            params = None
        else:
            url = f"{self.azure_endpoint.rstrip('/')}/openai/deployments/{self.deployment}/chat/completions"
            headers = {
                "api-key": self.azure_key,
                "Content-Type": "application/json"
            }
            payload = {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            params = {"api-version": self.api_version}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30.0)
                ) as resp:
                    if resp.status >= 400:
                        error = await resp.text()
                        raise RuntimeError(f"OpenAI error {resp.status}: {error}")
                    
                    return await resp.json()
        
        except Exception as e:
            logger.error(f"Erreur appel REST: {e}")
            return {"choices": [{"message": {"content": "Erreur de traitement"}}]}

    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse la réponse GPT-4o."""
        result = {"text": "", "function_calls": [], "confidence": 0.95}
        
        try:
            if isinstance(response, dict) and "choices" in response:
                choice = response["choices"][0]
                message = choice.get("message", {})
                
                # Texte de réponse
                if isinstance(message, dict):
                    content = message.get("content")
                    result["text"] = (content or "").strip()
                    
                    # Tool calls
                    tool_calls = message.get("tool_calls")
                    if tool_calls:
                        for tool_call in tool_calls:
                            result["function_calls"].append({
                                "name": tool_call.get("function", {}).get("name"),
                                "arguments": json.loads(
                                    tool_call.get("function", {}).get("arguments", "{}")
                                )
                            })
        
        except Exception as e:
            logger.error(f"Erreur parse réponse: {e}")
        
        return result

    async def add_memory(self, category: str, content: str):
        """Ajoute une information à la mémoire ChromaDB."""
        if not HAS_CHROMA or not self._chroma_client:
            return
        
        try:
            collection_map = {
                "animal": self._collection_animals,
                "house": self._collection_house,
                "preference": self._collection_preferences
            }
            
            collection = collection_map.get(category)
            if collection:
                doc_id = f"{category}_{int(datetime.now().timestamp())}"
                collection.add(
                    ids=[doc_id],
                    documents=[content],
                    metadatas=[{"timestamp": datetime.now().isoformat()}]
                )
                logger.info(f"💾 Mémoire ajoutée: {category}")
        
        except Exception as e:
            logger.error(f"Erreur ajout mémoire: {e}")

    async def close(self):
        """Ferme les connexions."""
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
        logger.info("🔌 BrainEngine fermé")
