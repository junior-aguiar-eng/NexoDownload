"""
Testes Unitários para o Módulo de Treinamento Vocal (VoiceTrainer)
==================================================================
Valida fatiamento de dataset, resolução de hiperparâmetros e contratos de dados.
"""

from pathlib import Path
import tempfile
import pytest

from audio_engine.voice_trainer import (
    AudioDatasetPreprocessor,
    DatasetSummary,
    FAISSIndexBuilder,
    TrainingConfig,
    VoiceTrainer,
)
from audio_engine.voice_modifier import AudioFileNotFoundError


def test_training_config_defaults():
    """Valida valores padrão da configuração de treino."""
    cfg = TrainingConfig(model_name="modelo_teste")
    assert cfg.model_name == "modelo_teste"
    assert cfg.epochs == 150
    assert cfg.sample_rate == "40k"
    assert cfg.version == "v2"
    assert cfg.f0_method == "rmvpe"
    assert cfg.denoise_dataset is True
    assert cfg.fp16 is True


def test_voice_trainer_initialization():
    """Valida que o VoiceTrainer cria o workspace corretamente."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        trainer = VoiceTrainer(workspace_dir=tmp_dir)
        assert trainer.workspace == Path(tmp_dir).resolve()
        assert trainer.workspace.exists()


def test_preprocessor_missing_input_raises():
    """Garante que fonte inexistente lance AudioFileNotFoundError."""
    preprocessor = AudioDatasetPreprocessor()
    with tempfile.TemporaryDirectory() as tmp_dir:
        fake_src = Path(tmp_dir) / "audio_nao_existe.wav"
        out_dir = Path(tmp_dir) / "output"
        with pytest.raises(AudioFileNotFoundError):
            preprocessor.process(fake_src, out_dir)


def test_prepare_dataset_with_demo_audio():
    """Valida fatiamento real de áudio pelo VoiceTrainer."""
    demo_audio = Path("audio_engine/demo.wav").resolve()
    if not demo_audio.exists():
        pytest.skip("demo.wav não disponível")

    with tempfile.TemporaryDirectory() as tmp_dir:
        trainer = VoiceTrainer(workspace_dir=tmp_dir)
        summary = trainer.prepare_dataset(
            audio_source=demo_audio,
            model_name="test_model",
            sample_rate="40k",
            denoise=False,
        )
        assert isinstance(summary, DatasetSummary)
        assert summary.num_slices >= 1
        assert summary.total_audio_duration_sec > 0
        assert summary.output_dir.exists()
