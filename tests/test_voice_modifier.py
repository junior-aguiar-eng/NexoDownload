"""
Testes Unitários para o Módulo de Áudio (DSP & RVC)
===================================================
Valida contratos de tipos, configurações, presets, tratamento de exceções
e integridade de caminhos de arquivo sem dependência de permissão externa do SO.
"""

from pathlib import Path
import tempfile
import pytest

from audio_engine.voice_modifier import (
    AudioFileNotFoundError,
    AudioProcessingError,
    AudioVoiceProcessor,
    DSPConfig,
    DSP_PRESETS,
    ModelFileNotFoundError,
    RVCConfig,
    RVC_PRESETS,
    RVCVoiceConverter,
    _ensure_valid_input_path,
    _resolve_output_path,
    get_optimal_torch_device,
    process_audio_dsp,
)


def test_dsp_config_defaults():
    """Garante valores padrão seguros e audiologicamente coerentes para DSP."""
    cfg = DSPConfig()
    assert cfg.semitones == 0.0
    assert cfg.formant_shift_semitones == 0.0
    assert cfg.preserve_formants is True
    assert cfg.fft_size == 2048
    assert cfg.hop_size == 512
    assert cfg.reduce_noise is False
    assert cfg.normalize_peak is True
    assert cfg.target_peak_db == -1.0


def test_rvc_config_defaults():
    """Garante que a configuração padrão do RVC utilize RMVPE e valores equilibrados."""
    cfg = RVCConfig()
    assert cfg.pitch_semitones == 0
    assert cfg.f0_method == "rmvpe"
    assert cfg.index_rate == 0.75
    assert cfg.filter_radius == 3
    assert cfg.protect == 0.33
    assert cfg.version == "v2"


def test_presets_catalog_integrity():
    """Valida se todos os presets obrigatórios estão presentes e tipados."""
    expected_dsp = {"clean_denoised", "deep_voice", "female_bright", "chipmunk_free_high", "radio_announcer"}
    for name in expected_dsp:
        assert name in DSP_PRESETS
        assert isinstance(DSP_PRESETS[name], DSPConfig)

    expected_rvc = {"neutral", "male_to_female", "female_to_male", "clarity_rmvpe"}
    for name in expected_rvc:
        assert name in RVC_PRESETS
        assert isinstance(RVC_PRESETS[name], RVCConfig)
        assert RVC_PRESETS[name].f0_method == "rmvpe"


def test_missing_audio_file_raises_custom_exception():
    """Garante que caminhos inexistentes lancem AudioFileNotFoundError."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        fake_path = Path(tmp_dir) / "arquivo_inexistente.wav"
        with pytest.raises(AudioFileNotFoundError):
            _ensure_valid_input_path(fake_path)

        with pytest.raises(AudioFileNotFoundError):
            process_audio_dsp(fake_path)


def test_missing_rvc_model_raises_custom_exception():
    """Garante que modelo RVC inexistente lance ModelFileNotFoundError."""
    converter = RVCVoiceConverter()
    with tempfile.TemporaryDirectory() as tmp_dir:
        fake_model = Path(tmp_dir) / "inexistente.pth"
        with pytest.raises(ModelFileNotFoundError):
            converter.load_model(fake_model)


def test_rvc_without_loaded_model_raises():
    """Garante que tentar converter sem carregar modelo lance AudioProcessingError."""
    converter = RVCVoiceConverter()
    with pytest.raises(AudioProcessingError) as exc_info:
        converter.convert_voice("qualquer_audio.wav")
    assert "Nenhum modelo RVC carregado" in str(exc_info.value)


def test_resolve_output_path():
    """Verifica resolução de caminhos de saída absolutos e subpasta padrão outputs/."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        dummy_input = Path(tmp_dir) / "voz_original.wav"
        dummy_input.touch()

        # 1. Sem output_path explícito -> deve criar pasta outputs/
        res = _resolve_output_path(dummy_input, output_path=None, suffix_tag="test_tag")
        assert res.is_absolute()
        assert res.parent.name == "outputs"
        assert res.name == "voz_original_test_tag.wav"

        # 2. Com output_path explícito apontando para arquivo
        explicit = Path(tmp_dir) / "custom_dir" / "final.wav"
        res_explicit = _resolve_output_path(dummy_input, output_path=explicit, suffix_tag="ignore")
        assert res_explicit == explicit.resolve()
        assert res_explicit.parent.exists()


def test_device_detection_returns_valid_tuple():
    """Garante retorno limpo de dispositivo (cuda ou cpu)."""
    device_id, desc = get_optimal_torch_device()
    assert isinstance(device_id, str)
    assert isinstance(desc, str)
    assert device_id.startswith("cuda") or device_id == "cpu"
