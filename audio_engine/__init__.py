"""
audio_engine package
====================
Módulo profissional de pós-produção, modificação e treinamento vocal para Python.
Oferece três motores integrados:
1. DSP Tradicional (STFT Phase Vocoder com Formant Preservation via stftpitchshift & Noisereduce)
2. IA RVC v2 (Retrieval-based Voice Conversion via rvc-python com algoritmo RMVPE e CUDA)
3. Treinador de Voz Nativo (VoiceTrainer acoplado com arquitetura Applio/RVC para criação de novos modelos)
"""

from .voice_modifier import (
    AudioProcessingError,
    AudioFileNotFoundError,
    ModelFileNotFoundError,
    DependencyMissingError,
    HardwareAccelerationError,
    DSPConfig,
    RVCConfig,
    DSP_PRESETS,
    RVC_PRESETS,
    get_optimal_torch_device,
    process_audio_dsp,
    RVCVoiceConverter,
    AudioVoiceProcessor,
)

from .voice_trainer import (
    VoiceTrainer,
    TrainingConfig,
    DatasetSummary,
    TrainingResult,
    AudioDatasetPreprocessor,
    FAISSIndexBuilder,
)

__all__ = [
    # Exceções
    "AudioProcessingError",
    "AudioFileNotFoundError",
    "ModelFileNotFoundError",
    "DependencyMissingError",
    "HardwareAccelerationError",
    # Configurações e Presets
    "DSPConfig",
    "RVCConfig",
    "DSP_PRESETS",
    "RVC_PRESETS",
    # Utilidades
    "get_optimal_torch_device",
    # Motores de Modificação e Conversão
    "process_audio_dsp",
    "RVCVoiceConverter",
    "AudioVoiceProcessor",
    # Motor de Treinamento Acoplado
    "VoiceTrainer",
    "TrainingConfig",
    "DatasetSummary",
    "TrainingResult",
    "AudioDatasetPreprocessor",
    "FAISSIndexBuilder",
]
