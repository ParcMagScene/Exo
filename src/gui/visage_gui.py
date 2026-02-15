"""visage_gui.py - Interface 2D animée (Pygame 144Hz).

Avatar expressif avec:
- Yeux réactifs au contexte
- Animations de clignotement fluides
- Spectrogramme audio temps réel
- États synchronisés avec le Brain
"""

import os
import logging
import asyncio
from typing import Optional, Callable
from enum import Enum
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

try:
    import pygame  # type: ignore
    import pygame.freetype  # type: ignore
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False
    logger.warning("⚠️ Pygame non disponible")


class FaceState(Enum):
    """États du visage."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"
    ERROR = "error"


class FaceGUI:
    """Interface graphique 2D avec Pygame."""

    def __init__(self, width: int = 800, height: int = 600, fps: int = 144):
        """Initialise l'interface."""
        self.width = width
        self.height = height
        self.target_fps = fps
        self.frame_time = 1.0 / fps
        
        self.state = FaceState.IDLE
        self.screen = None
        self.clock = None
        self.running = True
        
        # Variables d'animation
        self.blink_timer = 0
        self.blink_duration = 100
        self.blink_interval = 3000
        self.is_blinking = False
        
        # Audio spectrum
        self.audio_spectrum = [0] * 32
        
        logger.info(f"✅ FaceGUI initialisé ({width}x{height} @ {fps}Hz)")

    async def initialize(self):
        """Initialisation asynchrone."""
        if not HAS_PYGAME:
            logger.error("Pygame non disponible")
            return
        
        pygame.init()
        pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Assistant - Face GUI")
        
        self.screen = pygame.display.get_surface()
        self.clock = pygame.time.Clock()
        
        logger.info("✅ Pygame initialisé")

    async def set_state(self, new_state: Enum):
        """Change l'état du visage."""
        if isinstance(new_state, FaceState):
            self.state = new_state
            logger.info(f"😊 État visage: {new_state.value}")

    async def update_spectrum(self, audio_data: np.ndarray):
        """Met à jour le spectre audio."""
        if len(audio_data) > 0:
            # Calculer FFT (simplifié)
            spectrum = np.abs(np.fft.fft(audio_data[:512]))[:32]
            spectrum = np.log1p(spectrum) / 10
            self.audio_spectrum = spectrum.tolist()

    async def render_loop(self):
        """Boucle de rendu principale à 144Hz."""
        if not HAS_PYGAME or not self.screen:
            logger.warning("Rendu GUI non disponible")
            return
        
        try:
            frame_count = 0
            
            while self.running:
                start_time = datetime.now()
                
                # Vider l'écran
                self.screen.fill((20, 20, 30))
                
                # Rendu en fonction de l'état
                self._render_face()
                self._render_status()
                self._render_spectrum()
                
                # Affichage
                pygame.display.flip()
                
                # Limiter à 144fps
                elapsed = (datetime.now() - start_time).total_seconds()
                sleep_time = max(0, self.frame_time - elapsed)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                
                # Gestion des événements pygame
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                
                frame_count += 1
                
                if frame_count % (self.target_fps // 2) == 0:
                    logger.debug(f"Rendu: {self.target_fps/(elapsed + sleep_time if elapsed + sleep_time > 0 else 1):.0f} fps")
        
        except Exception as e:
            logger.error(f"Erreur rendu: {e}")
        
        finally:
            pygame.quit()

    def _render_face(self):
        """Rend le visage principal."""
        center_x = self.width // 2
        center_y = self.height // 2
        
        # Tête (cercle principal)
        pygame.draw.circle(self.screen, (80, 100, 140), (center_x, center_y), 120, 2)
        
        # Yeux
        eye_left_x = center_x - 40
        eye_right_x = center_x + 40
        eye_y = center_y - 30
        eye_radius = 15
        
        # Couleur yeux selon état
        eye_color = self._get_eye_color()
        
        # Vérifier si en train de cligner
        if self.is_blinking:
            # Ligne fermée
            pygame.draw.line(
                self.screen,
                eye_color,
                (eye_left_x - eye_radius, eye_y),
                (eye_left_x + eye_radius, eye_y),
                3
            )
            pygame.draw.line(
                self.screen,
                eye_color,
                (eye_right_x - eye_radius, eye_y),
                (eye_right_x + eye_radius, eye_y),
                3
            )
        else:
            # Yeux ouverts
            pygame.draw.circle(self.screen, eye_color, (eye_left_x, eye_y), eye_radius, 2)
            pygame.draw.circle(self.screen, eye_color, (eye_right_x, eye_y), eye_radius, 2)
            
            # Pupilles
            pygame.draw.circle(self.screen, eye_color, (eye_left_x - 5, eye_y), 6)
            pygame.draw.circle(self.screen, eye_color, (eye_right_x - 5, eye_y), 6)
        
        # Bouche (ligne horizontale)
        mouth_y = center_y + 40
        pygame.draw.arc(
            self.screen,
            (100, 100, 100),
            (center_x - 30, mouth_y - 10, 60, 20),
            0,
            3.14,
            2
        )
        
        # Animer le clignotement
        self.blink_timer += self.frame_time * 1000
        
        if self.blink_timer > self.blink_interval:
            self.is_blinking = True
            if self.blink_timer > self.blink_interval + self.blink_duration:
                self.is_blinking = False
                self.blink_timer = 0

    def _get_eye_color(self) -> tuple:
        """Retourne la couleur des yeux selon l'état."""
        colors = {
            FaceState.IDLE: (100, 150, 200),
            FaceState.LISTENING: (150, 200, 100),
            FaceState.PROCESSING: (200, 180, 100),
            FaceState.RESPONDING: (100, 200, 150),
            FaceState.ERROR: (200, 80, 80)
        }
        return colors.get(self.state, (100, 100, 100))

    def _render_status(self):
        """Affiche le statut actuel."""
        status_text = f"État: {self.state.value.upper()}"
        
        if HAS_PYGAME and pygame.freetype.init() and self.screen:
            font = pygame.freetype.SysFont("monospace", 14)
            text_surf, rect = font.render(status_text, (150, 150, 150))
            self.screen.blit(text_surf, (10, 10))

    def _render_spectrum(self):
        """Affiche le spectre audio animé."""
        spectrum_x = 50
        spectrum_y = self.height - 100
        bar_width = 20
        bar_spacing = 4
        
        for i, level in enumerate(self.audio_spectrum):
            x = spectrum_x + i * (bar_width + bar_spacing)
            height = int(level * 50)
            
            # Barre du spectre
            pygame.draw.rect(
                self.screen,
                (100 + int(level * 100), 150, 200),
                (x, spectrum_y - height, bar_width, height)
            )

    async def shutdown(self):
        """Ferme l'interface."""
        self.running = False
        logger.info("🔌 FaceGUI fermé")
