"""display_detector.py - Détecte et gère les écrans disponibles."""

import logging
import os
import sys
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)

try:
    import pygame
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False


class DisplayInfo:
    """Informations sur un écran."""
    
    def __init__(self, index: int, width: int, height: int, x: int = 0, y: int = 0):
        self.index = index
        self.width = width
        self.height = height
        self.x = x
        self.y = y
    
    def __str__(self):
        return f"Display {self.index}: {self.width}x{self.height} at ({self.x}, {self.y})"
    
    @property
    def is_touchscreen(self) -> bool:
        """Heuristique: écran petit (<= 10\") est probablement tactile."""
        diagonal_px = (self.width**2 + self.height**2) ** 0.5
        # 96 DPI heuristique → moins de ~1000px de diagonale ≈ petit écran
        return diagonal_px < 1200 or (self.width <= 1024 and self.height <= 800)


def detect_displays() -> List[DisplayInfo]:
    """Détecte tous les écrans disponibles."""
    if not HAS_PYGAME:
        logger.warning("Pygame non disponible")
        return []
    
    try:
        pygame.init()
        
        # Récupérer les moniteurs
        displays = []
        
        # Méthode 1: pygame.display.get_surface().get_abs_offset() (moderne)
        try:
            display_surface = pygame.display.set_mode((1, 1))  # Dummy window
            
            # Sur Windows, on peut récupérer les moniteurs avec win32api
            if sys.platform.startswith('win'):
                try:
                    import win32api
                    monitor_count = win32api.GetSystemMetrics(80)  # SM_CMONITORS
                    
                    for i in range(monitor_count):
                        # Créer une window sur cet écran
                        from win32con import SWP_SHOWWINDOW
                        info = {
                            'index': i,
                            'width': 1024,
                            'height': 768,
                            'x': i * 1024,
                            'y': 0
                        }
                        displays.append(info)
                    
                    logger.info(f"Détecté {monitor_count} écrans via win32api")
                except ImportError:
                    logger.info("win32api non disponible, utilisation méthode Pygame")
                    pass
            
            # Fallback: utiliser Pygame
            if not displays:
                # Pygame 2.1+ a get_desktop_sizes()
                if hasattr(pygame.display, 'get_display_surface'):
                    try:
                        # Tester la détection multi-écran
                        info = pygame.display.Info()
                        displays.append({
                            'index': 0,
                            'width': info.current_w,
                            'height': info.current_h,
                            'x': 0,
                            'y': 0
                        })
                    except Exception:
                        pass
        except Exception:
            pass
        
        # Si rien détecté, utiliser les infos de Pygame standard
        if not displays:
            info = pygame.display.Info()
            displays.append({
                'index': 0,
                'width': info.current_w,
                'height': info.current_h,
                'x': 0,
                'y': 0
            })
        
        result = [DisplayInfo(**d) for d in displays]
        logger.info(f"Écrans détectés: {[str(d) for d in result]}")
        return result
        
    except Exception as e:
        logger.error(f"Erreur détection écrans: {e}")
        return []


def get_secondary_display() -> Optional[DisplayInfo]:
    """Récupère l'écran secondaire (tactile sur Pi)."""
    displays = detect_displays()
    
    if len(displays) > 1:
        # Retourner le second écran
        return displays[1]
    elif len(displays) == 1:
        logger.warning("Seul un écran détecté")
        return displays[0]
    else:
        logger.error("Aucun écran détecté")
        return None


def get_touchscreen_display() -> Optional[DisplayInfo]:
    """Détecte l'écran tactile (généralement le plus petit ou le secondary)."""
    displays = detect_displays()
    
    if len(displays) > 1:
        # Sur Raspberry Pi avec écran tactile externe, c'est usually le second
        return displays[1]
    elif len(displays) == 1:
        return displays[0]
    
    return None


def set_display_env(display: DisplayInfo):
    """Configure les variables d'environnement pour afficher sur cet écran."""
    # Sur Linux (Raspberry Pi)
    if sys.platform.startswith('linux'):
        # DISPLAY=:0.1 pour le second écran
        os.environ['SDL_VIDEODRIVER'] = 'fbcon'  # Framebuffer console
        if display.index > 0:
            os.environ['SDL_FBDEV'] = f'/dev/fb{display.index}'
            logger.info(f"Configuration framebuffer: /dev/fb{display.index}")
    
    # Sur Windows
    elif sys.platform.startswith('win'):
        os.environ['SDL_VIDEODRIVER'] = 'windib'
        if display.x > 0 or display.y > 0:
            # Pygame va créer la window à cette position
            logger.info(f"Configuration fenêtre à ({display.x}, {display.y})")


def create_fullscreen_surface(display: DisplayInfo, pygame_obj=None) -> 'pygame.Surface':
    """Crée une surface fullscreen sur l'écran spécifié."""
    if pygame_obj is None:
        import pygame
        pygame_obj = pygame
    
    # Configure les variables d'environnement pour le bon écran
    set_display_env(display)
    
    # Créer la surface
    flags = pygame_obj.FULLSCREEN | pygame_obj.HWSURFACE
    surface = pygame_obj.display.set_mode((display.width, display.height), flags)
    
    logger.info(f"Surface créée: {display.width}x{display.height} on display {display.index}")
    return surface


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n📺 Détection des écrans")
    print("=" * 50)
    
    displays = detect_displays()
    for d in displays:
        print(f"  {d}")
    
    secondary = get_secondary_display()
    if secondary:
        print(f"\n✓ Écran secondaire: {secondary}")
    else:
        print("\n✗ Pas d'écran secondaire détecté")
