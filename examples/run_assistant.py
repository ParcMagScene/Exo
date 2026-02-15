import asyncio
import os
from assistant import Brain
from assistant.gui_face import FaceController, FaceState


async def simple_face_update(state):
    print("Face state ->", state.value)


async def main():
    # Ensure env vars exist (for demo only)
    for k in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_KEY", "HA_URL", "HA_TOKEN", "FISH_SPEECH_URL"):
        if not os.environ.get(k):
            print(f"Warning: environment variable {k} not set; some features will fail.")

    face = FaceController(on_state_change=simple_face_update)
    brain = Brain(face=face)

    # Example input (simulating Whisper transcription)
    text = "Allume la lumière du salon à 50%"
    await brain.handle_text(text)


if __name__ == "__main__":
    asyncio.run(main())
