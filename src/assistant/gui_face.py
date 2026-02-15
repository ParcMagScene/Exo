from enum import Enum
import asyncio


class FaceState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"   # was THINKING
    RESPONDING = "responding"   # was SPEAKING
    ERROR = "error"


class FaceController:
    """Lightweight state manager for a 2D face UI.

    The actual rendering should run in the GUI thread; this controller exposes
    an async-safe update method that schedules UI updates via a callback.
    """

    def __init__(self, on_state_change=None):
        self.state = FaceState.IDLE
        self.on_state_change = on_state_change

    async def set_state(self, new_state: FaceState):
        self.state = new_state
        if self.on_state_change:
            if asyncio.iscoroutinefunction(self.on_state_change):
                await self.on_state_change(new_state)
            else:
                # run in executor to avoid blocking event loop
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.on_state_change, new_state)
