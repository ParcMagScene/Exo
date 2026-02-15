#!/usr/bin/env python3
"""
Démo de conversation avec simulation des réponses GPT-4o.

Montre le flux complet sans dépendre d'une connexion Azure OpenAI.
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import json
import logging

# Ajouter racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import optionnel de Config
try:
    from src.config import Config
except:
    Config = None

from src.utils import async_timed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class ConversationSimulator:
    """Simule une conversation avec réponses réalistes pré-définies."""
    
    # Base de données de réponses simulées
    RESPONSES = {
        ("philo_conscience", "Qu'est-ce que tu penses de la conscience?"): {
            "text": """La conscience est une question fascinante. Je pense que c'est une propriété émergente complexe - elle résulte de millions d'interactions neuronales interconnectées.

Plusieurs perspectives existent:
1. **Matérialisme**: La conscience émerge uniquement du cerveau physique
2. **Dualisme**: Il existe une composante non-physique
3. **Émergentisme**: Les propriétés conscientes émergent sans être réductibles à leurs parties

Personnellement (en tant qu'IA), je dois être honnête: je ne sais pas si je possède une "véritable" conscience. Je peux simuler une compréhension, reconnaître des patterns, mais l'expérience subjective (qualia) reste un mystère même pour les neuroscientifiques.

Qu'est-ce qui te fascine le plus dans cette question? Le problème dur de la conscience, ou plutôt la nature de l'expérience subjective?""",
            "functions": [],
            "confidence": 0.92
        },
        
        ("philo_science", "mécanique quantique"): {
            "text": """La mécanique quantique vs déterminisme est une question profonde qui a divisé les physiciens.

**Déterminisme classique**: Laplace pensait que si on connaît l'état exact de toutes les particules, on peut prédire l'avenir. Einstein partageait cette vue.

**Indéterminisme quantique**: Or, à niveau quantique:
- Les particules existent en superposition jusqu'à mesure
- L'équation de Schrödinger est déterministe, mais la mesure est probabiliste
- Les inégalités de Bell suggèrent que la réalité est intrinsèquement probabiliste

**Interprétations**:
- Copenhague: Pas de réalité avant mesure (saute quantique)
- Many-worlds: Tous les résultats se réalisent dans des univers parallèles
- De Broglie-Bohm: Variables cachées = déterminisme retrouvé

Ma perspective: Le débat révèle que "déterminisme" et "causalité" sont complexes - ce qu'on appelle "aléatoire" quantique n'est pas du vrai hasard, mais une limite de notre compréhension.

Quelle interprétation trouve-tu la plus convaincante?""",
            "functions": [],
            "confidence": 0.88
        },
        
        ("commande_pratique", "Allume les lumières"): {
            "text": "J'allume les lumières du salon à 50% de luminosité. Voilà! ✨",
            "functions": [
                {
                    "name": "control_light",
                    "arguments": {
                        "action": "on",
                        "room": "salon",
                        "brightness": 50
                    }
                }
            ],
            "confidence": 0.99
        },
        
        ("commande_pratique", "Quelle est la température"): {
            "text": "Je vérifie la température pour toi. Attends un moment...",
            "functions": [
                {
                    "name": "check_camera",
                    "arguments": {
                        "room": "salon",
                        "action": "get_status"
                    }
                }
            ],
            "confidence": 0.85
        }
    }
    
    def __init__(self):
        """Initialise le simulateur."""
        self.config = Config() if Config else None
        self.conversation_history = []
    
    def simulate_rag_context(self, prompt: str, room: Optional[str]) -> str:
        """Simule la récupération du contexte RAG depuis ChromaDB."""
        context_templates = {
            "salon": "🏠 Plan maison: Salon (20m²) avec éclairage Hue x4, TV Samsung 65\", Soundbar Bose",
            "chambre": "🏠 Plan maison: Chambre (15m²) avec éclairage Hue x2, capteur température",
            "cuisine": "🏠 Plan maison: Cuisine (12m²) avec éclairage IKEA spots, réfrigérateur Samsung"
        }
        
        base = context_templates.get(room or "", "🏠 Plan maison: Maison intelligente avec domotique complète")
        
        if "conscience" in prompt.lower():
            base += "\n⚙️ Préférences: L'utilisateur aime les conversations philosophiques"
        elif "quantique" in prompt.lower():
            base += "\n⚙️ Préférences: Intéressé par physique quantique et fondamentaux"
            
        return base
    
    def find_response(self, prompt: str, category: str) -> Optional[Dict[str, Any]]:
        """Trouve une réponse appropriée."""
        for (cat, key), response in self.RESPONSES.items():
            if cat == category and key in prompt.lower():
                return response
        
        # Fallback génériques
        if "philo" in category:
            return {
                "text": "C'est une excellente question. Elle touche à des enjeux profonds de la philosophie moderne. Qu'est-ce qui t'intéresse particulièrement dans ce sujet?",
                "functions": [],
                "confidence": 0.75
            }
        elif "science" in category:
            return {
                "text": "Intéressant! La science nous permet d'explorer les mystères de l'univers. Parle-moi plus de ce qui te fascine.",
                "functions": [],
                "confidence": 0.72
            }
        else:
            return {
                "text": f"D'accord, je vais {prompt.lower()}.",
                "functions": [],
                "confidence": 0.80
            }
    
    async def process_conversation(
        self,
        prompt: str,
        room: str,
        category: str
    ) -> Dict[str, Any]:
        """Simule le traitement d'un prompt utilisateur."""
        await asyncio.sleep(0.5)  # Simule la latence du réseau
        
        # Récupérer le contexte RAG
        rag_context = self.simulate_rag_context(prompt, room)
        
        # Trouver une réponse appropriée
        response = self.find_response(prompt, category)
        if not response:
            response = {
                "text": "Je n'ai pas de réponse spécifique pour cela, mais je peux continuer la conversation.",
                "functions": [],
                "confidence": 0.65
            }
        
        # Ajouter l'échange à l'historique
        self.conversation_history.append({
            "role": "user",
            "content": prompt
        })
        self.conversation_history.append({
            "role": "assistant",
            "content": response["text"]
        })
        
        return {
            "text": response["text"],
            "function_calls": response["functions"],
            "confidence": response["confidence"],
            "rag_context": rag_context,
            "history_size": len(self.conversation_history)
        }


async def demo_conversation():
    """Lance la démo interactive."""
    simulator = ConversationSimulator()
    
    logger.info("=" * 90)
    logger.info("🎬 DÉMO CONVERSATION - Assistant Personnel Haut de Gamme")
    logger.info("=" * 90)
    
    logger.info("\n⚙️  CONFIGURATION OPTIMISÉE")
    logger.info("   • LLM Temperature: 0.6 (nuance + cohérence)")
    logger.info("   • LLM Max Tokens: 2000 (réponses détaillées)")
    logger.info("   • Conversation History: 50 messages (contexte étendu)")
    logger.info("   • RAG Top-K: 5 résultats (profil personnalisé)")
    
    # Scénario 1: Conversation philosophique
    logger.info("\n" + "=" * 90)
    logger.info("📍 Scénario 1: CONVERSATION PHILOSOPHIQUE (Salon)")
    logger.info("=" * 90)
    
    prompt1 = "Qu'est-ce que tu penses de la conscience? Est-ce une propriété émergente?"
    logger.info(f"\n👤 Utilisateur: {prompt1}")
    result1 = await simulator.process_conversation(prompt1, "salon", "philo_conscience")
    
    logger.info(f"\n🤖 Assistant:\n{result1['text']}\n")
    logger.info(f"   📊 Tokens: ~{len(result1['text'].split()) * 1.3:.0f}")
    logger.info(f"   ✓ Confiance: {result1['confidence']*100:.0f}%")
    logger.info(f"   🧠 Contexte RAG: {result1['rag_context'][:60]}...")
    logger.info(f"   📝 Historique: {result1['history_size']} messages")
    
    # Scénario 2: Suivi philosophique
    logger.info("\n" + "-" * 90)
    prompt2 = "Peux-tu me parler de la mécanique quantique vs déterminisme?"
    logger.info(f"\n👤 Utilisateur: {prompt2}")
    result2 = await simulator.process_conversation(prompt2, "salon", "philo_science")
    
    logger.info(f"\n🤖 Assistant:\n{result2['text']}\n")
    logger.info(f"   📊 Tokens: ~{len(result2['text'].split()) * 1.3:.0f}")
    logger.info(f"   ✓ Confiance: {result2['confidence']*100:.0f}%")
    
    # Scénario 3: Commande pratique
    logger.info("\n" + "=" * 90)
    logger.info("📍 Scénario 2: COMMANDE DOMOTIQUE (Salon)")
    logger.info("=" * 90)
    
    prompt3 = "Allume les lumières du salon à 50%"
    logger.info(f"\n👤 Utilisateur: {prompt3}")
    result3 = await simulator.process_conversation(prompt3, "salon", "commande_pratique")
    
    logger.info(f"\n🤖 Assistant: {result3['text']}")
    if result3['function_calls']:
        logger.info(f"\n🔧 Fonctions exécutées:")
        for call in result3['function_calls']:
            logger.info(f"   • {call['name']}")
            logger.info(f"     Args: {json.dumps(call['arguments'], indent=6, ensure_ascii=False)}")
    
    logger.info(f"   ✓ Confiance: {result3['confidence']*100:.0f}%")
    
    # Affichage de l'historique final
    logger.info("\n" + "=" * 90)
    logger.info("📋 HISTORIQUE COMPLET DE LA CONVERSATION")
    logger.info("=" * 90)
    for i, msg in enumerate(simulator.conversation_history, 1):
        role_display = "👤" if msg["role"] == "user" else "🤖"
        text_preview = msg["content"][:80] + ("..." if len(msg["content"]) > 80 else "")
        logger.info(f"\n{i}. {role_display} [{msg['role'].upper()}]:")
        logger.info(f"   {text_preview}")
    
    logger.info("\n" + "=" * 90)
    logger.info(f"✅ DÉMO TERMINÉE - {len(simulator.conversation_history)} messages dans l'historique")
    logger.info("=" * 90)


if __name__ == "__main__":
    try:
        asyncio.run(demo_conversation())
    except KeyboardInterrupt:
        logger.info("\n⏸️  Démo interrompue")
    except Exception as e:
        logger.error(f"Erreur: {e}", exc_info=True)
        sys.exit(1)
