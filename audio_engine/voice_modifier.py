"""
audio_engine/voice_modifier.py
==============================
Módulo Profissional de Pós-Produção de Áudio e Modificação Vocal.

Implementa dois motores 100% gratuitos e de alta fidelidade:
1. Motor DSP Tradicional (STFT Phase Vocoder com preservação/deslocamento de formantes via cepstrum + Redução Estática de Ruído).
2. Motor IA RVC (Retrieval-based Voice Conversion com algoritmo RMVPE e aceleração por hardware CUDA).

Arquitetura modular, fortemente tipada, otimizada para execução local e compatível com UV / PyTorch.
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

# Garante que a raiz do projeto esteja acessível independentemente do diretório de chamada
_current_dir = Path(__file__).resolve().parent
_project_root = _current_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Configuração de Logging do Módulo de Áudio
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("AudioEngine")


# ============================================================================
# EXCEÇÕES PERSONALIZADAS
# ============================================================================

class AudioProcessingError(Exception):
    """Exceção base para falhas de processamento e análise de áudio."""
    pass


class AudioFileNotFoundError(AudioProcessingError, FileNotFoundError):
    """Lançada quando o arquivo de áudio de entrada não é encontrado."""
    pass


class ModelFileNotFoundError(AudioProcessingError, FileNotFoundError):
    """Lançada quando os pesos do modelo RVC (.pth) ou índice (.index) não existem."""
    pass


class DependencyMissingError(AudioProcessingError, ImportError):
    """Lançada quando bibliotecas obrigatórias não estão instaladas no ambiente."""
    pass


class HardwareAccelerationError(AudioProcessingError):
    """Lançada em falhas ou restrições de aceleração por GPU/CUDA."""
    pass


# ============================================================================
# CONFIGURAÇÕES E PRESETS (DATA CLASSES FORTEMENTE TIPADAS)
# ============================================================================

@dataclass(frozen=True)
class DSPConfig:
    """
    Parâmetros de configuração para o Motor 1 (Processamento Digital de Sinais).

    Atributos:
        semitones: Alteração de tom em semitons (+12 = 1 oitava acima, -12 = 1 oitava abaixo).
        formant_shift_semitones: Deslocamento timbral dos formantes em semitons.
        preserve_formants: Quando True, preserva a envoltória espectral original evitando o efeito esquilo.
        quefrency_ms: Frequência de corte do lifter cepstral em milissegundos (padrão: 1.0 ms).
        fft_size: Resolução FFT para análise STFT (padrão 2048 para ótima resolução harmônica).
        hop_size: Passo de sobreposição de janelas (padrão 512).
        reduce_noise: Se True, aplica remoção prévia de ruído estático de fundo.
        noise_prop_decrease: Força da redução de ruído (0.0 a 1.0).
        normalize_peak: Aplica normalização de pico de segurança para evitar saturação/clipping.
        target_peak_db: Nível de pico alvo em dBFS caso normalize_peak seja True (padrão -1.0 dBFS).
    """
    semitones: float = 0.0
    formant_shift_semitones: float = 0.0
    preserve_formants: bool = True
    quefrency_ms: float = 1.0
    fft_size: int = 2048
    hop_size: int = 512
    reduce_noise: bool = False
    noise_prop_decrease: float = 0.85
    normalize_peak: bool = True
    target_peak_db: float = -1.0


@dataclass(frozen=True)
class RVCConfig:
    """
    Parâmetros de inferência para o Motor 2 (IA - Retrieval-based Voice Conversion).

    Atributos:
        pitch_semitones: Transposição de tom (semitons: +12 para voz feminina, -12 para masculina).
        f0_method: Algoritmo de extração de pitch fundamental ('rmvpe' recomendado por precisão e eficiência).
        index_rate: Peso de recuperação de características do arquivo .index (0.0 a 1.0).
        filter_radius: Raio do filtro mediano na curva de tom (suaviza falhas e saltos de oitava).
        rms_mix_rate: Taxa de interpolação entre o volume da fonte e o modelo (0.0 a 1.0).
        protect: Protege fonemas desvozeados e respiração contra artefatos metálicos (0.0 a 0.5).
        resample_sr: Taxa de amostragem de saída (0 para preservar o padrão do modelo de treino).
        version: Versão da arquitetura do modelo RVC ('v1' ou 'v2').
    """
    pitch_semitones: int = 0
    f0_method: Literal["rmvpe", "pm", "harvest", "crepe"] = "rmvpe"
    index_rate: float = 0.75
    filter_radius: int = 3
    rms_mix_rate: float = 0.25
    protect: float = 0.33
    resample_sr: int = 0
    version: Literal["v1", "v2"] = "v2"


# Catálogo de Presets Profissionais de Engenharia de Áudio
DSP_PRESETS: Dict[str, DSPConfig] = {
    "clean_denoised": DSPConfig(
        semitones=0.0,
        formant_shift_semitones=0.0,
        preserve_formants=True,
        reduce_noise=True,
        noise_prop_decrease=0.90,
    ),
    "deep_voice": DSPConfig(
        semitones=-3.5,
        formant_shift_semitones=-2.0,
        preserve_formants=True,
        reduce_noise=True,
        noise_prop_decrease=0.85,
    ),
    "female_bright": DSPConfig(
        semitones=3.5,
        formant_shift_semitones=2.0,
        preserve_formants=True,
        reduce_noise=True,
        noise_prop_decrease=0.85,
    ),
    "chipmunk_free_high": DSPConfig(
        semitones=5.0,
        formant_shift_semitones=0.0,
        preserve_formants=True,
        reduce_noise=True,
        noise_prop_decrease=0.80,
    ),
    "radio_announcer": DSPConfig(
        semitones=-2.0,
        formant_shift_semitones=-1.0,
        preserve_formants=True,
        reduce_noise=True,
        noise_prop_decrease=0.85,
    ),
}

RVC_PRESETS: Dict[str, RVCConfig] = {
    "neutral": RVCConfig(
        pitch_semitones=0,
        f0_method="rmvpe",
        index_rate=0.75,
        rms_mix_rate=0.25,
        protect=0.33,
    ),
    "male_to_female": RVCConfig(
        pitch_semitones=12,
        f0_method="rmvpe",
        index_rate=0.80,
        rms_mix_rate=0.20,
        protect=0.33,
    ),
    "female_to_male": RVCConfig(
        pitch_semitones=-12,
        f0_method="rmvpe",
        index_rate=0.80,
        rms_mix_rate=0.20,
        protect=0.33,
    ),
    "clarity_rmvpe": RVCConfig(
        pitch_semitones=0,
        f0_method="rmvpe",
        index_rate=0.85,
        filter_radius=3,
        rms_mix_rate=0.15,
        protect=0.40,
    ),
}


# ============================================================================
# UTILITÁRIOS DE AMBIENTE, HARDWARE E ÁUDIO
# ============================================================================

def get_optimal_torch_device() -> Tuple[str, str]:
    """
    Detecta automaticamente a disponibilidade de hardware acelerado (CUDA / PyTorch).
    
    Retorna:
        Tuple contendo (identificador_dispositivo, descricao_hardware).
        Ex: ("cuda:0", "NVIDIA GeForce RTX 3060 (VRAM: 12.00 GB)") ou ("cpu", "CPU Host")
    """
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            dev_idx = torch.cuda.current_device()
            dev_name = torch.cuda.get_device_name(dev_idx)
            total_vram_gb = torch.cuda.get_device_properties(dev_idx).total_memory / (1024 ** 3)
            desc = f"{dev_name} (VRAM: {total_vram_gb:.2f} GB)"
            return f"cuda:{dev_idx}", desc
        return "cpu", "CPU Host (Sem aceleração CUDA ativa)"
    except ImportError:
        return "cpu", "PyTorch não instalado no ambiente (CPU padrão)"


def _ensure_valid_input_path(path: Union[str, Path]) -> Path:
    """Verifica e retorna o caminho absoluto verificado do arquivo de áudio."""
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise AudioFileNotFoundError(f"Arquivo de áudio não encontrado no caminho: '{resolved}'")
    if not resolved.is_file():
        raise AudioProcessingError(f"O caminho informado não é um arquivo: '{resolved}'")
    return resolved


def _resolve_output_path(
    input_path: Path,
    output_path: Optional[Union[str, Path]],
    suffix_tag: str,
) -> Path:
    """Resolve e prepara o diretório de destino absoluto para áudio WAV 24-bit."""
    if output_path is not None:
        target = Path(output_path).expanduser().resolve()
        if target.is_dir():
            target = target / f"{input_path.stem}_{suffix_tag}.wav"
    else:
        target_dir = input_path.parent / "outputs"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = (target_dir / f"{input_path.stem}_{suffix_tag}.wav").resolve()

    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _apply_peak_normalization(
    audio_data: Any,
    target_db: float = -1.0,
) -> Any:
    """Normaliza o áudio para um teto máximo em dBFS garantindo zero clipping."""
    import numpy as np  # type: ignore

    peak = float(np.max(np.abs(audio_data)))
    if peak <= 1e-9:
        return audio_data

    target_linear = 10.0 ** (target_db / 20.0)
    if peak > target_linear:
        gain = target_linear / peak
        logger.debug("Normalizando áudio (Pico de %.3f atenuado para %.3f)", peak, target_linear)
        return audio_data * gain
    return audio_data


# ============================================================================
# MOTOR 1: PROCESSAMENTO DIGITAL DE SINAIS (DSP TRADICIONAL)
# ============================================================================

def process_audio_dsp(
    input_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    config: Optional[DSPConfig] = None,
    preset: Optional[str] = None,
) -> str:
    """
    Executa modificação vocal analítica usando processamento digital de sinais (DSP).

    Implementa:
    - Remediação de ruído de fundo estacionário com 'noisereduce' (opcional).
    - Deslocamento de tom (Pitch Shifting) e Formantes independentes via 'stftpitchshift' (cepstral liftering).
    - Preservação da ressonância anatômica do trato vocal, eliminando o "efeito esquilo".
    - Exportação em alta fidelidade WAV PCM 24-bit com proteção contra clipping.

    Parâmetros:
        input_path: Caminho para o arquivo de áudio de origem (WAV, MP3, FLAC, OGG, etc.).
        output_path: Caminho ou diretório para salvar o áudio processado.
        config: Objeto DSPConfig com parâmetros finos.
        preset: Nome de um preset pré-configurado ('deep_voice', 'female_bright', etc.).

    Retorna:
        str: Caminho absoluto do novo arquivo WAV gerado.
    """
    src_file = _ensure_valid_input_path(input_path)

    # Resolução da configuração (Preset vs Config granular)
    if preset is not None:
        if preset not in DSP_PRESETS:
            valid_keys = ", ".join(DSP_PRESETS.keys())
            raise ValueError(f"Preset DSP desconhecido: '{preset}'. Opções disponíveis: {valid_keys}")
        active_config = DSP_PRESETS[preset]
        if config is not None:
            # Overrides do usuário sobre o preset
            active_config = DSPConfig(
                semitones=config.semitones if config.semitones != 0.0 else active_config.semitones,
                formant_shift_semitones=config.formant_shift_semitones if config.formant_shift_semitones != 0.0 else active_config.formant_shift_semitones,
                preserve_formants=config.preserve_formants,
                quefrency_ms=config.quefrency_ms,
                fft_size=config.fft_size,
                hop_size=config.hop_size,
                reduce_noise=config.reduce_noise or active_config.reduce_noise,
                noise_prop_decrease=config.noise_prop_decrease,
                normalize_peak=config.normalize_peak,
                target_peak_db=config.target_peak_db,
            )
    else:
        active_config = config or DSPConfig()

    # Importação e verificação das bibliotecas DSP
    try:
        import numpy as np  # type: ignore
        import soundfile as sf  # type: ignore
    except ImportError as exc:
        raise DependencyMissingError(
            "Bibliotecas fundamentais 'soundfile' ou 'numpy' não encontradas. "
            "Instale com: uv pip install soundfile numpy"
        ) from exc

    try:
        from stftpitchshift import StftPitchShift  # type: ignore
    except ImportError as exc:
        raise DependencyMissingError(
            "Biblioteca 'stftpitchshift' não encontrada. "
            "Instale com: uv pip install stftpitchshift"
        ) from exc

    dest_file = _resolve_output_path(
        src_file,
        output_path,
        suffix_tag=f"dsp_p{active_config.semitones:+.1f}_f{active_config.formant_shift_semitones:+.1f}",
    )

    logger.info("Iniciando Motor DSP em: %s", src_file.name)
    logger.info(
        "Configuração DSP -> Pitch: %+.2f st | Formantes: %+.2f st | Preservar: %s | Ruído: %s",
        active_config.semitones,
        active_config.formant_shift_semitones,
        active_config.preserve_formants,
        active_config.reduce_noise,
    )

    try:
        # Carregamento do áudio em ponto flutuante 32-bit
        audio, sample_rate = sf.read(str(src_file), dtype="float32")
    except Exception as exc:
        raise AudioProcessingError(f"Falha ao ler áudio com soundfile: {exc}") from exc

    # Etapa 1: Redução de Ruído Estático (Opcional)
    if active_config.reduce_noise:
        try:
            import noisereduce as nr  # type: ignore
            logger.info("Aplicando redução de ruído estático (fator: %.2f)...", active_config.noise_prop_decrease)

            if audio.ndim == 1:
                audio = nr.reduce_noise(
                    y=audio,
                    sr=sample_rate,
                    stationary=True,
                    prop_decrease=active_config.noise_prop_decrease,
                )
            else:
                # Processamento canal por canal para preservar estéreo
                cleaned_channels = []
                for ch in range(audio.shape[1]):
                    cleaned_ch = nr.reduce_noise(
                        y=audio[:, ch],
                        sr=sample_rate,
                        stationary=True,
                        prop_decrease=active_config.noise_prop_decrease,
                    )
                    cleaned_channels.append(cleaned_ch)
                audio = np.column_stack(cleaned_channels)
        except ImportError:
            logger.warning("noisereduce não está instalado. Pulando etapa de redução de ruído.")
        except Exception as exc:
            logger.error("Erro na redução de ruído: %s. Continuando com áudio original.", exc)

    # Etapa 2: Transformada STFT com Deslocamento de Pitch & Formantes
    pitch_factor = 2.0 ** (active_config.semitones / 12.0)
    formant_distortion = 2.0 ** (active_config.formant_shift_semitones / 12.0)

    # Se a preservação ou deslocamento de formantes estiver habilitada, ativa lifter cepstral
    if active_config.preserve_formants or abs(active_config.formant_shift_semitones) > 1e-4:
        quefrency_sec = active_config.quefrency_ms * 1e-3
    else:
        quefrency_sec = 0.0

    shifter = StftPitchShift(
        framesize=active_config.fft_size,
        hopsize=active_config.hop_size,
        samplerate=sample_rate,
    )

    try:
        if audio.ndim == 1:
            processed_audio = shifter.shiftpitch(
                audio,
                factors=pitch_factor,
                quefrency=quefrency_sec,
                distortion=formant_distortion,
            )
        else:
            # Processa cada canal independente
            shifted_channels = []
            for ch in range(audio.shape[1]):
                ch_out = shifter.shiftpitch(
                    audio[:, ch],
                    factors=pitch_factor,
                    quefrency=quefrency_sec,
                    distortion=formant_distortion,
                )
                shifted_channels.append(ch_out)
            processed_audio = np.column_stack(shifted_channels)
    except Exception as exc:
        raise AudioProcessingError(f"Falha durante cálculo do STFT Pitch Shift: {exc}") from exc

    # Etapa 3: Normalização de Pico e Salvamento em WAV 24-bit PCM
    if active_config.normalize_peak:
        processed_audio = _apply_peak_normalization(
            processed_audio,
            target_db=active_config.target_peak_db,
        )

    try:
        sf.write(str(dest_file), processed_audio, sample_rate, subtype="PCM_24")
    except Exception as exc:
        raise AudioProcessingError(f"Falha ao salvar áudio resultante em '{dest_file}': {exc}") from exc

    abs_output = str(dest_file.resolve())
    logger.info("Processamento DSP concluído com sucesso: %s", abs_output)
    return abs_output


# ============================================================================
# MOTOR 2: CONVERSÃO DE VOZ POR IA (RVC - RETRIEVAL-BASED VOICE CONVERSION)
# ============================================================================

class RVCVoiceConverter:
    """
    Pipeline de Inferência para Conversão de Identidade Vocal via RVC v2.
    
    Aproveita aceleração por GPU (CUDA) com fallback automático e carrega
    modelos locais (.pth) com suporte opcional a índices de indexação FAISS (.index).
    Utiliza o extrator de frequência fundamental RMVPE para precisão sem falhas de voz.
    """

    def __init__(self, device: Optional[str] = None) -> None:
        """
        Inicializa o motor RVC com verificação de hardware.

        Parâmetros:
            device: Dispositivo de execução (ex: 'cuda:0', 'cuda', 'cpu').
                    Se None, detecta automaticamente o melhor acelerador disponível.
        """
        self.device, self.device_desc = self._resolve_device(device)
        self.model_path: Optional[Path] = None
        self.index_path: Optional[Path] = None
        self._rvc_inference_instance: Optional[Any] = None
        logger.info("Motor RVC inicializado. Dispositivo de processamento: %s [%s]", self.device, self.device_desc)

    @staticmethod
    def _resolve_device(requested_device: Optional[str]) -> Tuple[str, str]:
        """Verifica compatibilidade e aloca o dispositivo ótimo."""
        optimal_id, desc = get_optimal_torch_device()
        if requested_device is None:
            return optimal_id, desc

        req = requested_device.lower().strip()
        if req.startswith("cuda") and not optimal_id.startswith("cuda"):
            logger.warning("CUDA solicitada ('%s'), mas indisponível. Alternando para CPU.", req)
            return "cpu", desc
        return req, desc

    def load_model(
        self,
        model_path: Union[str, Path],
        index_path: Optional[Union[str, Path]] = None,
    ) -> None:
        """
        Carrega o modelo de voz RVC (.pth) e localiza o índice de recuperação de timbre (.index).

        Parâmetros:
            model_path: Caminho absoluto ou relativo para os pesos do modelo RVC (.pth).
            index_path: Caminho opcional para o arquivo FAISS .index. Se None, tenta
                        localizar automaticamente um .index com mesmo nome na mesma pasta.
        """
        resolved_pth = Path(model_path).expanduser().resolve()
        if not resolved_pth.exists():
            raise ModelFileNotFoundError(f"Arquivo de pesos do modelo RVC não encontrado: '{resolved_pth}'")
        if resolved_pth.suffix.lower() != ".pth":
            raise ModelFileNotFoundError(f"O modelo RVC deve ser um arquivo com extensão .pth: '{resolved_pth}'")

        self.model_path = resolved_pth

        # Auto-detecção ou validação do arquivo de índice (.index)
        if index_path is not None:
            resolved_index = Path(index_path).expanduser().resolve()
            if not resolved_index.exists():
                raise ModelFileNotFoundError(f"Arquivo de índice (.index) não encontrado: '{resolved_index}'")
            self.index_path = resolved_index
        else:
            # Busca automática na mesma pasta
            potential_indexes = list(self.model_path.parent.glob("*.index"))
            if potential_indexes:
                # Prioriza índice com mesmo radical
                matching = [idx for idx in potential_indexes if idx.stem == self.model_path.stem]
                self.index_path = matching[0] if matching else potential_indexes[0]
                logger.info("Arquivo .index auto-detectado: %s", self.index_path.name)
            else:
                self.index_path = None
                logger.warning("Nenhum arquivo .index encontrado. Inferência executará sem recuperação FAISS.")

        logger.info("Modelo RVC configurado: %s (Índice: %s)", self.model_path.name, self.index_path.name if self.index_path else "Nenhum")

    def convert_voice(
        self,
        input_audio_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        config: Optional[RVCConfig] = None,
        preset: Optional[str] = None,
    ) -> str:
        """
        Executa a conversão de voz utilizando a rede neural RVC e extração RMVPE.

        Parâmetros:
            input_audio_path: Caminho para o áudio de entrada gravado/falado.
            output_path: Caminho de saída desejado (se None, salva em pasta 'outputs/').
            config: Objeto RVCConfig com os hiperparâmetros de inferência.
            preset: Nome do preset RVC ('neutral', 'male_to_female', 'female_to_male', etc.).

        Retorna:
            str: Caminho absoluto do arquivo WAV de 24-bit gerado.
        """
        if self.model_path is None:
            raise AudioProcessingError("Nenhum modelo RVC carregado. Chame 'load_model()' antes de converter.")

        src_audio = _ensure_valid_input_path(input_audio_path)

        # Resolução de configuração
        if preset is not None:
            if preset not in RVC_PRESETS:
                valid_rvc = ", ".join(RVC_PRESETS.keys())
                raise ValueError(f"Preset RVC desconhecido: '{preset}'. Opções disponíveis: {valid_rvc}")
            active_config = RVC_PRESETS[preset]
            if config is not None:
                active_config = RVCConfig(
                    pitch_semitones=config.pitch_semitones if config.pitch_semitones != 0 else active_config.pitch_semitones,
                    f0_method=config.f0_method,
                    index_rate=config.index_rate,
                    filter_radius=config.filter_radius,
                    rms_mix_rate=config.rms_mix_rate,
                    protect=config.protect,
                    resample_sr=config.resample_sr,
                    version=config.version,
                )
        else:
            active_config = config or RVCConfig()

        dest_audio = _resolve_output_path(
            src_audio,
            output_path,
            suffix_tag=f"rvc_{self.model_path.stem}_p{active_config.pitch_semitones:+d}",
        )

        logger.info(
            "Iniciando conversão RVC IA -> Modelo: %s | F0: %s | Pitch: %+d st | Dispositivo: %s",
            self.model_path.stem,
            active_config.f0_method,
            active_config.pitch_semitones,
            self.device,
        )

        # Compatibilidade com PyTorch 2.6+ (desativação temporária da restrição weights_only)
        try:
            import torch  # type: ignore
            _original_torch_load = torch.load

            def _safe_load(*args: Any, **kwargs: Any) -> Any:
                kwargs["weights_only"] = False
                return _original_torch_load(*args, **kwargs)

            torch.load = _safe_load
        except Exception:
            pass

        # Execução via rvc_python.infer (módulo padrão headless oficial)
        try:
            from rvc_python.infer import infer_file  # type: ignore
        except ImportError as exc:
            raise DependencyMissingError(
                "A biblioteca 'rvc-python' ou suas dependências não estão instaladas. "
                "Para suporte completo com CUDA, execute:\n"
                "  uv pip install rvc-python\n"
                "  uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124"
            ) from exc

        try:
            # Chamada de inferência RVC
            infer_file(
                input_path=str(src_audio),
                model_path=str(self.model_path),
                index_path=str(self.index_path) if self.index_path else "",
                device=self.device,
                f0method=active_config.f0_method,
                pitch=active_config.pitch_semitones,
                output=str(dest_audio),
                index_rate=active_config.index_rate,
                filter_radius=active_config.filter_radius,
                resample_sr=active_config.resample_sr,
                rms_mix_rate=active_config.rms_mix_rate,
                protect=active_config.protect,
                version=active_config.version,
            )
        except Exception as exc:
            raise AudioProcessingError(f"Falha durante inferência neural RVC: {exc}") from exc

        if not dest_audio.exists():
            raise AudioProcessingError(f"A inferência do RVC finalizou mas o arquivo '{dest_audio}' não foi gerado.")

        # Pós-processamento de fidelidade: recodifica em WAV PCM_24 de estúdio e normaliza pico
        try:
            import soundfile as sf  # type: ignore
            audio_out, out_sr = sf.read(str(dest_audio), dtype="float32")
            audio_out = _apply_peak_normalization(audio_out, target_db=-1.0)
            sf.write(str(dest_audio), audio_out, out_sr, subtype="PCM_24")
        except Exception as exc:
            logger.warning("Falha na normalização de fidelidade pós-RVC (%s). Mantendo arquivo original.", exc)

        abs_output = str(dest_audio.resolve())
        logger.info("Conversão RVC finalizada com sucesso: %s", abs_output)
        return abs_output


# ============================================================================
# CLASSE ORQUESTRADORA UNIFICADA (FACHADA DE PÓS-PRODUÇÃO)
# ============================================================================

class AudioVoiceProcessor:
    """
    Controlador unificado de pós-produção vocal.
    Permite acionar DSP, RVC ou encadear ambos (ex: Limpeza/Pré-formatação DSP -> Conversão RVC).
    """

    def __init__(self, rvc_device: Optional[str] = None) -> None:
        self.rvc_engine = RVCVoiceConverter(device=rvc_device)

    def process_dsp(
        self,
        audio_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        config: Optional[DSPConfig] = None,
        preset: Optional[str] = None,
    ) -> str:
        """Executa modificação vocal via Motor 1 (DSP Tradicional)."""
        return process_audio_dsp(
            input_path=audio_path,
            output_path=output_path,
            config=config,
            preset=preset,
        )

    def load_rvc_model(
        self,
        model_path: Union[str, Path],
        index_path: Optional[Union[str, Path]] = None,
    ) -> None:
        """Carrega modelo para o Motor 2 (RVC IA)."""
        self.rvc_engine.load_model(model_path=model_path, index_path=index_path)

    def process_rvc(
        self,
        audio_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        config: Optional[RVCConfig] = None,
        preset: Optional[str] = None,
    ) -> str:
        """Executa clonagem e modificação vocal via Motor 2 (RVC IA)."""
        return self.rvc_engine.convert_voice(
            input_audio_path=audio_path,
            output_path=output_path,
            config=config,
            preset=preset,
        )

    def process_chain(
        self,
        audio_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        dsp_config: Optional[DSPConfig] = None,
        rvc_config: Optional[RVCConfig] = None,
        dsp_preset: Optional[str] = None,
        rvc_preset: Optional[str] = None,
    ) -> str:
        """
        Executa pipeline encadeado completo:
        1. Pré-condicionamento DSP (ex: remoção de ruído, equalização de tom inicial).
        2. Inferência de timbre RVC IA com RMVPE.
        """
        logger.info("Iniciando pipeline encadeado (DSP -> RVC)...")
        # Passo 1: DSP
        dsp_out = self.process_dsp(
            audio_path=audio_path,
            config=dsp_config,
            preset=dsp_preset,
        )

        # Passo 2: RVC a partir da saída DSP
        final_out = self.process_rvc(
            audio_path=dsp_out,
            output_path=output_path,
            config=rvc_config,
            preset=rvc_preset,
        )
        logger.info("Pipeline encadeado concluído: %s", final_out)
        return final_out


# ============================================================================
# INTERFACE DE LINHA DE COMANDO (CLI INDEPENDENTE)
# ============================================================================

def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Processador Vocal Profissional (DSP STFT Formants & IA RVC com RMVPE)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("-i", "--input", required=True, help="Caminho do arquivo de áudio de entrada.")
    parser.add_argument("-o", "--output", default=None, help="Caminho ou diretório para salvar o áudio de saída.")

    # Modo de Execução
    mode_group = parser.add_argument_group("Motores de Processamento")
    mode_group.add_argument(
        "--engine",
        choices=["dsp", "rvc", "chain"],
        default="dsp",
        help="Motor a ser executado: 'dsp' (STFT), 'rvc' (IA) ou 'chain' (DSP + RVC).",
    )

    # Parâmetros DSP
    dsp_group = parser.add_argument_group("Opções Motor 1 - DSP")
    dsp_group.add_argument("--dsp-preset", choices=list(DSP_PRESETS.keys()), default=None, help="Preset DSP pré-definido.")
    dsp_group.add_argument("--semitones", type=float, default=0.0, help="Mudança de tom em semitons (+/-).")
    dsp_group.add_argument("--formant-shift", type=float, default=0.0, help="Mudança de formantes em semitons (+/-).")
    dsp_group.add_argument("--no-formant-preserve", action="store_true", help="Desativa preservação de formantes (efeito esquilo).")
    dsp_group.add_argument("--denoise", action="store_true", help="Ativa remoção de ruído estático antes do pitch.")
    dsp_group.add_argument("--denoise-strength", type=float, default=0.85, help="Intensidade da remoção de ruído (0.0 a 1.0).")

    # Parâmetros RVC
    rvc_group = parser.add_argument_group("Opções Motor 2 - RVC IA")
    rvc_group.add_argument("--model", default=None, help="Caminho do arquivo .pth do modelo RVC.")
    rvc_group.add_argument("--index", default=None, help="Caminho do arquivo .index FAISS do modelo RVC.")
    rvc_group.add_argument("--rvc-preset", choices=list(RVC_PRESETS.keys()), default=None, help="Preset RVC.")
    rvc_group.add_argument("--rvc-pitch", type=int, default=0, help="Transposição RVC em semitons (+12, -12, etc.).")
    rvc_group.add_argument("--f0-method", choices=["rmvpe", "harvest", "crepe", "pm"], default="rmvpe", help="Algoritmo de F0.")
    rvc_group.add_argument("--index-rate", type=float, default=0.75, help="Fator de recuperação do índice FAISS (0.0 a 1.0).")
    rvc_group.add_argument("--device", default=None, help="Dispositivo PyTorch ('cuda:0' ou 'cpu').")

    return parser.parse_args()


def main() -> None:
    args = _parse_arguments()
    processor = AudioVoiceProcessor(rvc_device=args.device)

    try:
        if args.engine == "dsp":
            dsp_cfg = DSPConfig(
                semitones=args.semitones,
                formant_shift_semitones=args.formant_shift,
                preserve_formants=not args.no_formant_preserve,
                reduce_noise=args.denoise,
                noise_prop_decrease=args.denoise_strength,
            )
            out = processor.process_dsp(
                audio_path=args.input,
                output_path=args.output,
                config=dsp_cfg,
                preset=args.dsp_preset,
            )
            print(f"[SUCESSO] Áudio processado via DSP: {out}")

        elif args.engine == "rvc":
            if not args.model:
                print("[ERRO] Para utilizar o motor RVC, especifique o modelo com --model caminho/modelo.pth", file=sys.stderr)
                sys.exit(1)

            processor.load_rvc_model(model_path=args.model, index_path=args.index)
            rvc_cfg = RVCConfig(
                pitch_semitones=args.rvc_pitch,
                f0_method=args.f0_method,
                index_rate=args.index_rate,
            )
            out = processor.process_rvc(
                audio_path=args.input,
                output_path=args.output,
                config=rvc_cfg,
                preset=args.rvc_preset,
            )
            print(f"[SUCESSO] Áudio convertido via RVC IA: {out}")

        elif args.engine == "chain":
            if not args.model:
                print("[ERRO] Para utilizar o modo chain, especifique o modelo RVC com --model caminho/modelo.pth", file=sys.stderr)
                sys.exit(1)

            processor.load_rvc_model(model_path=args.model, index_path=args.index)
            dsp_cfg = DSPConfig(
                semitones=args.semitones,
                formant_shift_semitones=args.formant_shift,
                preserve_formants=not args.no_formant_preserve,
                reduce_noise=args.denoise,
            )
            rvc_cfg = RVCConfig(
                pitch_semitones=args.rvc_pitch,
                f0_method=args.f0_method,
                index_rate=args.index_rate,
            )
            out = processor.process_chain(
                audio_path=args.input,
                output_path=args.output,
                dsp_config=dsp_cfg,
                rvc_config=rvc_cfg,
                dsp_preset=args.dsp_preset,
                rvc_preset=args.rvc_preset,
            )
            print(f"[SUCESSO] Pipeline encadeado (DSP -> RVC) concluído: {out}")

    except AudioProcessingError as err:
        print(f"[ERRO DE PROCESSAMENTO]: {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        print(f"[ERRO INESPERADO]: {err}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
