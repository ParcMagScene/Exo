#!/usr/bin/env python3
"""
Test d'une conversation complète de bout en bout.

Simule une interaction utilisateur avec le BrainEngine optimisé pour les conversations.
Montre comment le système:
1. Récupère le contexte RAG
2. Construit le prompt système enrichi
3. Appelle GPT-4o avec les paramètres optimisés
4. Parse la réponse et extrait les function calls
"""

import asyncio
import sys
import json
from pathlib import Path

# Ajouter racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.brain.brain_engine import BrainEngine
from src.config import Config
from src.utils import async_timed
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class ConversationTester:
    """Testeur de conversations pour démontrer les capacités."""
    
    def __init__(self):
        """Initialise le testeur."""
        self.config = Config()
        self.brain = BrainEngine(self.config)
        
    async def run_test_suite(self):
        """Exécute une suite de tests de conversation."""
        logger.info("=" * 80)
        logger.info("🧠 TEST DE CONVERSATION - Assistant Personnel Haut de Gamme")
        logger.info("=" * 80)
        
        # Simuler des conversations variées
        conversations = [
            {
                "room": "salon",
                "messages": [
                    ("Qu'est-ce que tu penses de la conscience? Est-ce une propriété émergente?", 
                     "philo_conscience"),
                    ("Peux-tu me parler de la mécanique quantique vs déterminisme?", 
                     "philo_science"),
                    ("Allume les lumières du salon à 50%", 
                     "commande_pratique"),
                ]
            }
        ]
        
        for conversation in conversations:
            room = conversation["room"]
            logger.info(f"\n📍 Pièce: {room}")
            logger.info("-" * 80)
            
            for prompt, category in conversation["messages"]:
                await self._test_single_prompt(prompt, room, category)
                print("\n")
    
    @async_timed
    async def _test_single_prompt(
        self, 
        prompt: str, 
        room: str, 
        category: str
    ) -> None:
        """Teste un prompt unique."""
        logger.info(f"\n👤 Input [{category}]: {prompt}")
        logger.info("-" * 40)
        
        try:
            # Appel au BrainEngine avec les paramètres optimisés
            result = await self.brain.process_command(
                text=prompt,
                room=room,
                context={"category": category}
            )
            
            # Affichage de la réponse
            response_text = result.get("text", "")
            if response_text:
                logger.info(f"🤖 Réponse: {response_text[:300]}...")
                
                # Montre la longueur de la réponse
                token_estimate = len(response_text.split()) * 1.3  # Approximation
                logger.info(f"   📊 Longueur: ~{int(token_estimate)} tokens")
            
            # Montre les function calls si présents
            function_calls = result.get("function_calls", [])
            if function_calls:
                logger.info(f"🔧 Fonction(s) détectée(s):")
                for call in function_calls:
                    logger.info(f"   • {call.get('name')}: {call.get('arguments')}")
            
            # Confiance du système
            confidence = result.get("confidence", 0)
            logger.info(f"   ✓ Confiance: {confidence * 100:.0f}%")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du traitement: {e}", exc_info=True)
    
    def print_config_summary(self):
        """Affiche un résumé de la configuration optimisée."""
        logger.info("\n" + "=" * 80)
        logger.info("⚙️  CONFIGURATION OPTIMISÉE POUR CONVERSATIONS")
        logger.info("=" * 80)
        logger.info(f"LLM Temperature: 0.6 (balance nuance/cohérence)")
        logger.info(f"LLM Max Tokens: 2000 (long-form responses)")
        logger.info(f"Conversation History: 50 messages (contexte étendu)")
        logger.info(f"RAG Top-K: 5 (profil personnalisé)")
        logger.info("\n[PROMPT SYSTÈME]")
        logger.info("• Assistant domotique (HUE, IKEA, Samsung, etc.)")
        logger.info("• Compagnon conversationnel (philo, science, empathie)")
        logger.info("• Honnête sur ses limites")
        logger.info("• Reconnaît l'ambiguïté et l'incertitude")


async def main():
    """Fonction principale."""
    tester = ConversationTester()
    
    # Afficher la configuration
    tester.print_config_summary()
    
    # Exécuter les tests
    try:
        await tester.run_test_suite()
        logger.info("\n" + "=" * 80)
        logger.info("✅ SESSION DE TEST TERMINÉE")
        logger.info("=" * 80)
    except KeyboardInterrupt:
        logger.info("\n⏸️  Test interrompu par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur lors du test: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
