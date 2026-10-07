"""
Gera um arquivo de áudio WAV de demonstração (3 segundos, 44.1kHz)
usando apenas a biblioteca padrão 'wave' do Python (sem dependências externas).
"""

import math
import struct
import wave
from pathlib import Path

output_path = Path(__file__).resolve().parent / "demo.wav"

sample_rate = 44100
duration_sec = 3.0
num_samples = int(sample_rate * duration_sec)

# Frequência fundamental de voz masculina (130 Hz - Nota C3) com harmônicos vocais
f0 = 130.0

with wave.open(str(output_path), "wb") as wav_file:
    wav_file.setnchannels(1)        # Mono
    wav_file.setsampwidth(2)        # 16-bit PCM
    wav_file.setframerate(sample_rate)

    frames = bytearray()
    for i in range(num_samples):
        t = float(i) / sample_rate
        # Envelope suave de fade in/out
        envelope = min(1.0, t * 4.0) * min(1.0, (duration_sec - t) * 4.0)
        
        # Fundamental + formantes simulados (2º e 3º harmônico vocal)
        signal = (
            0.6 * math.sin(2.0 * math.pi * f0 * t) +
            0.3 * math.sin(2.0 * math.pi * (2.0 * f0) * t) +
            0.15 * math.sin(2.0 * math.pi * (3.0 * f0) * t)
        ) * envelope
        
        # Converte para int16
        val = int(signal * 32767.0 * 0.7)
        val = max(-32768, min(32767, val))
        frames.extend(struct.pack("<h", val))

    wav_file.writeframes(frames)

print(f"[OK] Áudio de teste gerado com sucesso em: {output_path}")
