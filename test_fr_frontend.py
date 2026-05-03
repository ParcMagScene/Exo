import sys, torch, numpy as np
sys.path.insert(0, r"D:\EXO\project\python")
from cosyvoice.cli.cosyvoice import CosyVoice2
import scipy.io.wavfile as wf

print("Loading model...")
m = CosyVoice2(r"D:\EXO\models\cosyvoice", load_jit=False, fp16=False)
print("Model loaded")

prompt_wav  = r"D:\EXO\models\cosyvoice\voices\fr_denise.wav"
prompt_text = "Bienvenue dans notre espace d assistance. Je suis disponible pour vous accompagner dans toutes vos demarches."
tts_text    = "Bonjour, je suis votre assistante. Aujourd hui il fait beau et je suis ravie de vous parler."

print("Testing zero_shot text_frontend=False ...")
chunks = []
for r in m.inference_zero_shot(tts_text, prompt_text, prompt_wav, stream=False, speed=1.0, text_frontend=False):
    chunks.append(r["tts_speech"].squeeze().cpu().numpy())
audio = np.concatenate(chunks)
wf.write(r"D:\EXO\project\test_fr_nofrontend.wav", 24000, (audio * 32767).astype("int16"))
print("Done: %.2fs -> test_fr_nofrontend.wav" % (len(audio)/24000))