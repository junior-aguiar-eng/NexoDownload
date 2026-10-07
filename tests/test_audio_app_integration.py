"""
Testes de Integração da API do Estúdio de Áudio & IA (DSP, RVC e Applio)
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from web_app.app import app, BASE_DIR

client = TestClient(app)


def test_audio_status_endpoint():
    """Testa se o status do motor de áudio retorna informações completas de hardware e presets."""
    response = client.get("/api/audio/status")
    assert response.status_code == 200
    data = response.json()
    assert "available" in data
    assert "device" in data
    assert "dsp_presets" in data
    assert "demo_available" in data
    assert isinstance(data["dsp_presets"], dict)
    assert "deep_voice" in data["dsp_presets"]


def test_audio_models_endpoint():
    """Testa a listagem de modelos RVC."""
    response = client.get("/api/audio/models")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert isinstance(data["models"], list)


def test_process_dsp_with_demo_audio():
    """Testa a transformação vocal via DSP utilizando o áudio demo."""
    demo_audio = BASE_DIR / "audio_engine" / "demo.wav"
    assert demo_audio.exists(), "demo.wav deve existir para teste"

    payload = {
        "input_path": str(demo_audio),
        "preset": "deep_voice",
        "semitones": -3.0,
        "formant_shift_semitones": -1.5,
        "preserve_formants": True,
        "reduce_noise": True,
        "noise_prop_decrease": 0.80,
    }

    response = client.post("/api/audio/process-dsp", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "output_path" in data
    assert "stream_url" in data
    assert Path(data["output_path"]).exists()

    # Testa o streaming do áudio gerado
    stream_resp = client.get(data["stream_url"])
    assert stream_resp.status_code == 200
    assert "audio" in stream_resp.headers.get("content-type", "")
    assert len(stream_resp.content) > 1000


def test_process_dsp_missing_file_raises_404():
    """Testa se tentar processar um arquivo inexistente retorna 404."""
    payload = {
        "input_path": "c:/arquivo_fantasma_inexistente_123.wav",
        "preset": "deep_voice",
    }
    response = client.post("/api/audio/process-dsp", json=payload)
    assert response.status_code == 404


def test_process_rvc_missing_model_raises_404():
    """Testa se tentar inferência RVC sem modelo retorna 404."""
    demo_audio = BASE_DIR / "audio_engine" / "demo.wav"
    payload = {
        "input_path": str(demo_audio),
        "model_name": "modelo_completamente_inexistente",
        "pitch_semitones": 0,
    }
    response = client.post("/api/audio/process-rvc", json=payload)
    assert response.status_code == 404


def test_train_voice_lifecycle():
    """Testa o acionamento e monitoramento de tarefa de treinamento em segundo plano."""
    demo_audio = BASE_DIR / "audio_engine" / "demo.wav"
    payload = {
        "audio_source": str(demo_audio),
        "model_name": "teste_api_voice",
        "epochs": 20,
        "sample_rate": "40k",
        "denoise": True,
    }
    response = client.post("/api/audio/train-voice", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "task_id" in data

    task_id = data["task_id"]
    status_resp = client.get(f"/api/audio/train-status/{task_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["task_id"] == task_id
    assert status_data["status"] in ("running", "finished")
