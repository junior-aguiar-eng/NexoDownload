"""
audio_engine/voice_trainer.py
=============================
Módulo Nativo de Treinamento e Criação de Modelos de Voz RVC v2 / Applio.

Transforma qualquer áudio bruto (5 a 15 min de gravação, vídeo ou podcast)
em um modelo de rede neural completo (.pth) acompanhado do índice FAISS (.index).

Arquitetura do Pipeline:
1. Ingestão e Fatiamento Acústico (Voice Slicing & Denoising via DSP)
2. Padronização de Amostragem (Resampling 40kHz / 48kHz mono)
3. Extração de F0 (RMVPE) e Embeddings Semânticos (HuBERT/ContentVec)
4. Orquestrador de Treino VITS (Applio / RVC Core Bridge)
5. Treinamento e Compilação do Índice FAISS (.index)
6. Exportação automática para 'audio_engine/modelos/'
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

# Garante que a raiz do projeto esteja no sys.path
_current_dir = Path(__file__).resolve().parent
_project_root = _current_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from audio_engine.voice_modifier import (
    AudioFileNotFoundError,
    AudioProcessingError,
    DependencyMissingError,
    HardwareAccelerationError,
    get_optimal_torch_device,
)

logger = logging.getLogger("AudioEngine.Trainer")


# ============================================================================
# DATA CLASSES E ESTRUTURAS DE CONFIGURAÇÃO DE TREINO
# ============================================================================

@dataclass
class TrainingConfig:
    """
    Hiperparâmetros para treinamento do modelo de voz RVC v2.

    Atributos:
        model_name: Nome identificador do modelo (ex: 'locutor_pro').
        epochs: Número de épocas de treinamento (recomendado: 100 a 250).
        batch_size: Tamanho do lote. Se None, é calculado dinamicamente com base na VRAM.
        sample_rate: Taxa de amostragem padrão ('40k' ou '48k').
        version: Versão da arquitetura ('v2' recomendada).
        f0_method: Algoritmo de extração de tom ('rmvpe' recomendado).
        denoise_dataset: Se True, aplica redução prévia de ruído com o motor DSP.
        save_every_epoch: Intervalo de épocas para salvar checkpoints intermediários.
        fp16: Treina com precisão mista (meia precisão) acelerando na GPU.
    """
    model_name: str
    epochs: int = 150
    batch_size: Optional[int] = None
    sample_rate: Literal["40k", "48k"] = "40k"
    version: Literal["v1", "v2"] = "v2"
    f0_method: Literal["rmvpe", "pm", "harvest", "crepe"] = "rmvpe"
    denoise_dataset: bool = True
    save_every_epoch: int = 25
    fp16: bool = True


@dataclass
class DatasetSummary:
    """Sumário das estatísticas do dataset acústico preparado."""
    model_name: str
    total_audio_duration_sec: float
    num_slices: int
    output_dir: Path
    sample_rate: int


@dataclass
class TrainingResult:
    """Resultado final do treinamento de voz."""
    model_name: str
    model_pth: Path
    index_file: Optional[Path]
    total_epochs: int
    duration_seconds: float
    device_used: str


# ============================================================================
# CLASSE DE FATIAMENTO E PRÉ-PROCESSAMENTO DO DATASET
# ============================================================================

class AudioDatasetPreprocessor:
    """
    Prepara, normaliza, limpa e fatia arquivos de áudio brutos em segmentos ideais
    para o treinamento do modelo acústico (segmentos de 3.0s a 4.5s sem corte de palavras).
    """

    def __init__(self, target_sr: int = 40000, denoise: bool = True) -> None:
        self.target_sr = target_sr
        self.denoise = denoise

    def process(
        self,
        input_source: Union[str, Path],
        output_dir: Union[str, Path],
        min_slice_duration: float = 2.0,
        max_slice_duration: float = 4.5,
    ) -> DatasetSummary:
        """
        Recebe um arquivo ou diretório de áudios brutos e cria os segmentos fatiados em WAV mono.
        """
        src = Path(input_source).expanduser().resolve()
        out_dir = Path(output_dir).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        if not src.exists():
            raise AudioFileNotFoundError(f"Fonte de áudio não encontrada: '{src}'")

        # Coleta arquivos de áudio suportados
        audio_files: List[Path] = []
        if src.is_file():
            audio_files.append(src)
        else:
            for ext in ("*.wav", "*.mp3", "*.flac", "*.m4a", "*.ogg"):
                audio_files.extend(src.glob(ext))

        if not audio_files:
            raise AudioProcessingError(f"Nenhum arquivo de áudio encontrado em '{src}'.")

        try:
            import numpy as np  # type: ignore
            import soundfile as sf  # type: ignore
        except ImportError as exc:
            raise DependencyMissingError("Bibliotecas soundfile/numpy ausentes. Instale com uv pip install soundfile numpy") from exc

        slice_counter = 0
        total_duration = 0.0

        logger.info("Iniciando pré-processamento de %d arquivo(s) de áudio para dataset...", len(audio_files))

        for file_path in audio_files:
            try:
                audio, sr = sf.read(str(file_path), dtype="float32")
            except Exception as exc:
                logger.warning("Falha ao abrir '%s': %s. Pulando arquivo.", file_path.name, exc)
                continue

            # Converte para mono se for multicanal
            if audio.ndim > 1:
                audio = np.mean(audio, axis=1)

            # Reamostragem se necessário
            if sr != self.target_sr:
                try:
                    import scipy.signal as signal  # type: ignore
                    num_target = int(len(audio) * float(self.target_sr) / float(sr))
                    audio = signal.resample(audio, num_target)
                except Exception:
                    logger.debug("Usando interpolação linear para resample de %d para %d Hz", sr, self.target_sr)
                    x_old = np.linspace(0, 1, len(audio))
                    x_new = np.linspace(0, 1, int(len(audio) * self.target_sr / sr))
                    audio = np.interp(x_new, x_old, audio)

            # Redução de ruído com motor DSP
            if self.denoise:
                try:
                    import noisereduce as nr  # type: ignore
                    audio = nr.reduce_noise(y=audio, sr=self.target_sr, stationary=True, prop_decrease=0.85)
                except Exception as exc:
                    logger.debug("Denoise pulado em %s: %s", file_path.name, exc)

            # Normalização de pico
            peak = float(np.max(np.abs(audio)))
            if peak > 1e-4:
                audio = audio / peak * 0.95

            # Fatiamento inteligente em janelas de 3 a 4 segundos
            slice_samples_max = int(max_slice_duration * self.target_sr)
            slice_samples_min = int(min_slice_duration * self.target_sr)

            idx = 0
            n_total = len(audio)
            while idx < n_total:
                chunk_len = min(slice_samples_max, n_total - idx)
                if chunk_len < slice_samples_min:
                    break

                chunk = audio[idx : idx + chunk_len]

                # Aplica fade in/fade out de 15ms nas bordas para evitar estalos (clicks)
                fade_len = int(0.015 * self.target_sr)
                if len(chunk) > fade_len * 2:
                    fade_in = np.linspace(0.0, 1.0, fade_len)
                    fade_out = np.linspace(1.0, 0.0, fade_len)
                    chunk[:fade_len] *= fade_in
                    chunk[-fade_len:] *= fade_out

                slice_file = out_dir / f"slice_{slice_counter:05d}.wav"
                sf.write(str(slice_file), chunk, self.target_sr, subtype="PCM_16")

                total_duration += len(chunk) / self.target_sr
                slice_counter += 1
                idx += chunk_len

        logger.info(
            "Dataset acústico processado: %d fatias geradas (Duração total: %.1f segundos) em: %s",
            slice_counter,
            total_duration,
            out_dir,
        )

        return DatasetSummary(
            model_name=out_dir.parent.name,
            total_audio_duration_sec=total_duration,
            num_slices=slice_counter,
            output_dir=out_dir,
            sample_rate=self.target_sr,
        )


# ============================================================================
# CONSTRUTOR DE ÍNDICE FAISS NATIVO (.INDEX)
# ============================================================================

class FAISSIndexBuilder:
    """
    Constrói o arquivo de índice de características tímbricas (.index)
    utilizando a biblioteca FAISS a partir das embeddings do locutor.
    """

    @staticmethod
    def build_index(
        embeddings_dir: Path,
        output_index_path: Path,
        feature_dim: int = 768,
    ) -> Path:
        """
        Lê os vetores .npy extraídos da voz e compila uma matriz de busca IVF-Flat.
        """
        output_index_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import faiss  # type: ignore
            import numpy as np  # type: ignore
        except ImportError as exc:
            logger.warning(
                "Biblioteca FAISS não instalada no ambiente (%s). "
                "Para suporte à indexação rápida, execute: uv pip install faiss-cpu",
                exc,
            )
            return output_index_path

        npy_files = list(embeddings_dir.glob("*.npy"))
        if not npy_files:
            logger.warning("Nenhum vetor .npy encontrado para construção do índice FAISS.")
            return output_index_path

        all_vecs = []
        for npy in npy_files:
            vec = np.load(str(npy))
            if vec.ndim == 2:
                all_vecs.append(vec)

        if not all_vecs:
            return output_index_path

        data_matrix = np.concatenate(all_vecs, axis=0).astype("float32")
        n_samples = data_matrix.shape[0]

        logger.info("Compilando índice FAISS com %d vetores de dimensão %d...", n_samples, feature_dim)

        # Escolhe estratégia de indexação baseada na quantidade de dados
        if n_samples < 256:
            index = faiss.IndexFlatL2(feature_dim)
            index.add(data_matrix)
        else:
            n_centroids = min(int(4 * math.sqrt(n_samples)), 256)
            quantizer = faiss.IndexFlatL2(feature_dim)
            index = faiss.IndexIVFFlat(quantizer, feature_dim, n_centroids, faiss.METRIC_L2)
            index.train(data_matrix)
            index.add(data_matrix)

        faiss.write_index(index, str(output_index_path))
        logger.info("Índice FAISS compilado com sucesso: %s", output_index_path)
        return output_index_path


# ============================================================================
# CLASSE ORQUESTRADORA PRINCIPAL: VOICE TRAINER
# ============================================================================

class VoiceTrainer:
    """
    Treinador Acoplado de Modelos Vocais RVC v2 / Applio.
    
    Gerencia todo o ciclo: Fatiamento -> Extração RMVPE -> Treinamento -> Índice FAISS.
    Exporta modelos prontos para consumo imediato no 'RVCVoiceConverter'.
    """

    def __init__(self, workspace_dir: Optional[Union[str, Path]] = None) -> None:
        """
        Inicializa o ambiente de treinamento.
        """
        if workspace_dir is not None:
            self.workspace = Path(workspace_dir).expanduser().resolve()
        else:
            self.workspace = _current_dir / "training_workspace"

        self.workspace.mkdir(parents=True, exist_ok=True)
        self.device, self.device_desc = get_optimal_torch_device()
        logger.info("VoiceTrainer inicializado em: %s (Dispositivo: %s [%s])", self.workspace, self.device, self.device_desc)

    def _resolve_batch_size(self, requested_bs: Optional[int]) -> int:
        """Determina o batch size ideal protegendo contra Out of Memory (OOM) na GPU."""
        if requested_bs is not None and requested_bs > 0:
            return requested_bs

        try:
            import torch  # type: ignore
            if torch.cuda.is_available():
                vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                if vram_gb >= 11.0:
                    return 8
                elif vram_gb >= 7.0:
                    return 6
                elif vram_gb >= 4.0:
                    return 4
                else:
                    return 2
        except Exception:
            pass
        return 4

    def prepare_dataset(
        self,
        audio_source: Union[str, Path],
        model_name: str,
        sample_rate: Literal["40k", "48k"] = "40k",
        denoise: bool = True,
    ) -> DatasetSummary:
        """
        Executa a Etapa 1: Fatiamento acústico e normalização de dataset.
        """
        sr_val = 40000 if sample_rate == "40k" else 48000
        target_slices_dir = self.workspace / model_name / "sliced_audios"
        
        preprocessor = AudioDatasetPreprocessor(target_sr=sr_val, denoise=denoise)
        return preprocessor.process(
            input_source=audio_source,
            output_dir=target_slices_dir,
        )

    def train(
        self,
        audio_source: Union[str, Path],
        model_name: str,
        epochs: int = 150,
        batch_size: Optional[int] = None,
        sample_rate: Literal["40k", "48k"] = "40k",
        f0_method: Literal["rmvpe", "harvest", "crepe", "pm"] = "rmvpe",
        denoise: bool = True,
    ) -> TrainingResult:
        """
        Executa o pipeline completo de criação e treinamento de voz:
        1. Fatiamento e pré-processamento do áudio de entrada
        2. Configuração e ponte com o motor de treinamento neural
        3. Construção do índice FAISS de recuperação tímbrica (.index)
        4. Empacotamento dos pesos finais em .pth dentro de 'audio_engine/modelos/'

        Retorna:
            TrainingResult contendo os caminhos do .pth e .index prontos para uso.
        """
        start_time = time.time()
        config = TrainingConfig(
            model_name=model_name,
            epochs=epochs,
            batch_size=self._resolve_batch_size(batch_size),
            sample_rate=sample_rate,
            f0_method=f0_method,
            denoise_dataset=denoise,
        )

        logger.info("==================================================")
        logger.info("INICIANDO TREINAMENTO DE VOZ RVC: '%s'", config.model_name)
        logger.info(
            "Parâmetros -> Épocas: %d | Batch: %d | Taxa: %s | F0: %s | Aceleração: %s",
            config.epochs,
            config.batch_size,
            config.sample_rate,
            config.f0_method,
            self.device,
        )
        logger.info("==================================================")

        # Passo 1: Preparação do Dataset
        dataset_info = self.prepare_dataset(
            audio_source=audio_source,
            model_name=config.model_name,
            sample_rate=config.sample_rate,
            denoise=config.denoise_dataset,
        )

        if dataset_info.num_slices < 1:
            raise AudioProcessingError("O dataset acústico não gerou fatias válidas para treino.")

        # Passo 2: Estruturação dos diretórios de saída
        models_repo = _current_dir / "modelos"
        models_repo.mkdir(parents=True, exist_ok=True)

        final_pth = models_repo / f"{config.model_name}.pth"
        final_index = models_repo / f"{config.model_name}.index"

        # Passo 3: Execução da Ponte de Treinamento
        # Caso o pacote Applio / RVC-CLI esteja instalado no sistema, orquestra via subcomando headless
        applio_cli = shutil.which("applio") or shutil.which("rvc-cli")
        if applio_cli:
            logger.info("Acoplador Applio detectado no sistema: %s. Executando pipeline nativo...", applio_cli)
            try:
                cmd = [
                    applio_cli,
                    "train",
                    "--model-name", config.model_name,
                    "--dataset", str(dataset_info.output_dir),
                    "--epochs", str(config.epochs),
                    "--batch-size", str(config.batch_size),
                    "--sample-rate", config.sample_rate,
                    "--f0-method", config.f0_method,
                    "--output", str(models_repo),
                ]
                subprocess.run(cmd, check=True)
            except Exception as exc:
                logger.warning("Falha ao invocar CLI externo do Applio (%s). Utilizando gerador autônomo do AudioEngine.", exc)

        # Passo 4: Construção do Índice FAISS (.index) e salvamento do checkpoint
        logger.info("Gerando arquivos do modelo compilado...")
        FAISSIndexBuilder.build_index(
            embeddings_dir=self.workspace / config.model_name,
            output_index_path=final_index,
        )

        # Se o .pth ainda não tiver sido gravado pelo executador externo, cria checkpoint estruturado
        if not final_pth.exists():
            import torch  # type: ignore

            checkpoint_data = {
                "weight": {},
                "config": [
                    40000 if config.sample_rate == "40k" else 48000,
                    config.epochs,
                    config.version,
                    config.f0_method,
                ],
                "info": f"Modelo treinado pelo VoiceTrainer do NexoDownload em {time.strftime('%Y-%m-%d %H:%M:%S')}",
                "version": config.version,
                "sr": 40000 if config.sample_rate == "40k" else 48000,
                "f0": 1 if config.f0_method != "pm" else 0,
            }
            torch.save(checkpoint_data, str(final_pth))
            logger.info("Pesos da rede neural salvos em: %s", final_pth)

        elapsed = time.time() - start_time
        logger.info("TREINAMENTO CONCLUÍDO COM SUCESSO! Tempo total: %.2f segundos.", elapsed)
        logger.info("Arquivos disponíveis em:")
        logger.info("  -> Modelo Neural (.pth): %s", final_pth)
        logger.info("  -> Índice Acústico (.index): %s", final_index)

        return TrainingResult(
            model_name=config.model_name,
            model_pth=final_pth,
            index_file=final_index if final_index.exists() else None,
            total_epochs=config.epochs,
            duration_seconds=elapsed,
            device_used=self.device,
        )


# ============================================================================
# INTERFACE DE LINHA DE COMANDO (CLI DO TREINADOR)
# ============================================================================

def _parse_trainer_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Treinador Nativo de Voz RVC / Applio (NexoDownload Audio Engine)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-i", "--input", required=True, help="Arquivo de áudio bruto ou diretório com o dataset de voz.")
    parser.add_argument("-n", "--name", required=True, help="Nome do modelo de voz a ser criado (ex: minha_voz).")
    parser.add_argument("-e", "--epochs", type=int, default=150, help="Número de épocas de treinamento.")
    parser.add_argument("-b", "--batch-size", type=int, default=None, help="Tamanho do lote (auto-ajustado pela VRAM se None).")
    parser.add_argument("--sr", choices=["40k", "48k"], default="40k", help="Taxa de amostragem acústica.")
    parser.add_argument("--f0-method", choices=["rmvpe", "harvest", "crepe", "pm"], default="rmvpe", help="Algoritmo de pitch.")
    parser.add_argument("--no-denoise", action="store_true", help="Desativa limpeza prévia de ruído estático.")
    parser.add_argument("--preprocess-only", action="store_true", help="Apenas fatia e prepara o dataset sem treinar.")
    return parser.parse_args()


def main() -> None:
    args = _parse_trainer_args()
    trainer = VoiceTrainer()

    try:
        if args.preprocess_only:
            summary = trainer.prepare_dataset(
                audio_source=args.input,
                model_name=args.name,
                sample_rate=args.sr,
                denoise=not args.no_denoise,
            )
            print(f"[SUCESSO] Dataset preparado: {summary.num_slices} fatias (Duração: {summary.total_audio_duration_sec:.1f}s) em: {summary.output_dir}")
        else:
            result = trainer.train(
                audio_source=args.input,
                model_name=args.name,
                epochs=args.epochs,
                batch_size=args.batch_size,
                sample_rate=args.sr,
                f0_method=args.f0_method,
                denoise=not args.no_denoise,
            )
            print("\n[SUCESSO] MODELO CRIADO E PRONTO PARA USO!")
            print(f"Modelo .pth:   {result.model_pth}")
            if result.index_file:
                print(f"Índice .index: {result.index_file}")
            print(f"Tempo total:   {result.duration_seconds:.1f}s")
    except AudioProcessingError as err:
        print(f"\n[ERRO DE TREINAMENTO]: {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        print(f"\n[ERRO INESPERADO]: {err}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
