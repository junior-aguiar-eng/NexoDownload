# Guia de Instalação e Uso do Audio Engine (DSP, RVC & VoiceTrainer)

Módulo em Python completo, fortemente tipado e modular para pós-produção, modificação vocal e treinamento de novos modelos de voz, operando com aceleração por hardware (CUDA) e motores 100% gratuitos e de código aberto.

---

## 1. Instalação e Gerenciamento de Dependências (UV)

Recomendamos o gerenciador ultra-rápido **UV** (`uv pip install`).

### Ambiente com Aceleração por GPU (NVIDIA CUDA - Recomendado para RVC e Treinamento)

```bash
# 1. Instalação do PyTorch com suporte a CUDA 12.4
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# 2. Instalação das bibliotecas de áudio, DSP, FAISS e IA
uv pip install librosa soundfile stftpitchshift noisereduce numpy rvc-python faiss-cpu
```

### Ambiente Apenas CPU (Fallback)

```bash
uv pip install torch torchvision torchaudio
uv pip install librosa soundfile stftpitchshift noisereduce numpy rvc-python faiss-cpu
```

---

## 2. Arquitetura do Módulo

O pacote expõe três motores principais:
1. **`process_audio_dsp`**: Motor 1 (Processamento Digital de Sinais STFT com Formant Preservation & Denoise).
2. **`RVCVoiceConverter`**: Motor 2 (Inferência Neural RVC v2 com RMVPE).
3. **`VoiceTrainer`**: Motor 3 (Treinador Nativo de Vozes com arquitetura RVC v2 / Applio).
4. **`AudioVoiceProcessor`**: Fachada unificada para encadear limpeza DSP e conversão RVC.

---

## 3. Exemplos de Uso em Código (Python)

### Motor 1: Processamento Digital de Sinais (STFT Formants + Denoise)

```python
from audio_engine import process_audio_dsp, DSPConfig

# Exemplo 1: Usando Preset de Engenharia
wav_deep = process_audio_dsp(
    input_path="gravacao.wav",
    preset="deep_voice", # Voz encorpada com formantes preservados e remoção de ruído
)
print("Áudio DSP gerado:", wav_deep)

# Exemplo 2: Ajuste Paramétrico Fino (Sem efeito esquilo)
custom_dsp = DSPConfig(
    semitones=4.0,                 # Sobe 4 semitons no tom
    formant_shift_semitones=0.0,   # Mantém os formantes travados na anatomia original
    preserve_formants=True,        # Ativa lifter cepstral (1ms)
    reduce_noise=True,             # Remove ruído estático de fundo antes do shift
    noise_prop_decrease=0.85,      # 85% de atenuação do ruído estático
)
wav_custom = process_audio_dsp(
    input_path="gravacao.wav",
    output_path="saida_stft_formant.wav",
    config=custom_dsp,
)
```

### Motor 2: Conversão de Voz por IA (RVC v2 + RMVPE)

```python
from audio_engine import RVCVoiceConverter, RVCConfig

# 1. Instancia o conversor (detecta GPU automaticamente)
rvc = RVCVoiceConverter()

# 2. Carrega o modelo de voz local (.pth)
# O arquivo .index na mesma pasta é detectado automaticamente
rvc.load_model(
    model_path="modelos/narrador_pro.pth",
    index_path="modelos/narrador_pro.index", # opcional se estiver na mesma pasta
)

# 3. Executa a inferência vocal com RMVPE
wav_ai = rvc.convert_voice(
    input_audio_path="voz_original.wav",
    config=RVCConfig(
        pitch_semitones=0,     # 0 = tom natural do locutor; +12 = oitava feminina
        f0_method="rmvpe",     # Algoritmo neural de F0 RMVPE de alta precisão
        index_rate=0.75,       # Força da semelhança tímbrica via FAISS
        protect=0.33,          # Proteção contra artefatos em consoantes e respiração
    )
)
print("Áudio RVC gerado:", wav_ai)
```

### Motor 3: Treinamento e Criação de Vozes Novas (VoiceTrainer)

```python
from audio_engine import VoiceTrainer

trainer = VoiceTrainer()

# Treina um modelo completo a partir de 5-15 min de áudio bruto
resultado = trainer.train(
    audio_source="gravações/voz_amigo.wav", # ou pasta com vários áudios
    model_name="voz_amigo",
    epochs=150,                             # 150 épocas recomendado
    sample_rate="40k",                      # 40kHz padrão RVC v2
    f0_method="rmvpe",
    denoise=True,                           # Limpa ruído de fundo automaticamente
)

print(f"Modelo .pth pronto:   {resultado.model_pth}")
print(f"Índice .index pronto: {resultado.index_file}")
```

### Pipeline Encadeado Unificado (DSP Pré-Condicionamento -> IA RVC)

```python
from audio_engine import AudioVoiceProcessor, DSPConfig, RVCConfig

processor = AudioVoiceProcessor()
processor.load_rvc_model("modelos/minha_voz_ai.pth")

# Limpa o ruído e alinha o tom antes de injetar no modelo RVC
resultado_final = processor.process_chain(
    audio_path="podcast_bruto.wav",
    dsp_config=DSPConfig(reduce_noise=True, noise_prop_decrease=0.9),
    rvc_config=RVCConfig(pitch_semitones=0, f0_method="rmvpe", index_rate=0.8),
)
print("Áudio Final WAV 24-bit:", resultado_final)
```

---

## 4. Uso via Linha de Comando (CLI)

### Modificação Vocal:
```powershell
# Motor 1 (DSP com preset e denoise):
python voice_modifier.py -i demo.wav --engine dsp --dsp-preset deep_voice

# Motor 2 (RVC com modelo e RMVPE):
python voice_modifier.py -i demo.wav --engine rvc --model modelos/locutor.pth --rvc-pitch 0
```

### Treinamento de Nova Voz:
```powershell
# Treina uma nova voz e gera .pth e .index automaticamente em modelos/:
python voice_trainer.py -i audio_bruto.wav -n meu_locutor -e 150

# Apenas fatia e prepara o dataset sem treinar:
python voice_trainer.py -i audio_bruto.wav -n meu_locutor --preprocess-only
```
