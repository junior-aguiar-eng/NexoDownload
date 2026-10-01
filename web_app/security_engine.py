# -*- coding: utf-8 -*-
"""
Nexo Download - Motor de Segurança e Licenciamento Criptográfico (HWID-Lock)
Compatível com Windows 10/11 x64.
"""

import os
import sys
import hmac
import hashlib
import json
import base64
import subprocess
try:
    import winreg
except ImportError:
    winreg = None
from pathlib import Path
from datetime import datetime, timezone

# Segredo mestre para assinatura criptográfica de licenças
_MASTER_SECRET = b"NEXO_SECURE_KERNEL_SIGNING_KEY_2026_@AGY_PROTECT#!"

def get_app_data_dir() -> Path:
    """Retorna o diretório seguro de dados do aplicativo."""
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "NexoDownload"
    base.mkdir(parents=True, exist_ok=True)
    return base

def get_license_file_path() -> Path:
    return get_app_data_dir() / "license.lic"

def _get_registry_machine_guid() -> str:
    """Lê o MachineGuid do registro do Windows."""
    if winreg is None:
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(guid).strip()
    except Exception:
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, winreg.KEY_READ) as key:
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(guid).strip()
    except Exception:
        return ""

def _get_wmi_value(command: str) -> str:
    """Executa comando rápido PowerShell para extrair propriedades de hardware."""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return ""

_CACHED_HWID = None
_CACHED_FINGERPRINTS = None

def get_hwid_file_path() -> Path:
    """Retorna o caminho do arquivo de persistência de identidade da máquina."""
    return get_app_data_dir() / "machine.id"

def _compute_hwid_from_raw(raw: str) -> str:
    """Calcula a assinatura formal de HWID a partir de uma string de hardware."""
    digest = hashlib.sha256((raw + "_NEXO_HWID_SALT_V2").encode("utf-8")).hexdigest().upper()
    return f"NEXO-{digest[0:4]}-{digest[4:8]}-{digest[8:12]}"

def _get_machine_fingerprints() -> list:
    """
    Extrai as variações legítimas de identificadores de hardware desta máquina.
    Usa cache em memória para evitar chamadas de processo repetitivas no WMI/PowerShell.
    """
    global _CACHED_FINGERPRINTS
    if _CACHED_FINGERPRINTS is not None:
        return _CACHED_FINGERPRINTS

    guid = _get_registry_machine_guid()
    mb = _get_wmi_value("(Get-CimInstance Win32_ComputerSystemProduct).UUID")
    cpu = _get_wmi_value("(Get-CimInstance Win32_Processor).ProcessorId")

    fps = []
    # 1. Combinação completa (GUID + Placa-mãe + Processador)
    raw_full = f"{guid}|{mb}|{cpu}".strip("|")
    if raw_full:
        fps.append(_compute_hwid_from_raw(raw_full))
        
    # 2. Combinação GUID + Placa-mãe (caso leitura de CPU tenha sofrido timeout)
    raw_guid_mb = f"{guid}|{mb}".strip("|")
    if raw_guid_mb and raw_guid_mb != raw_full:
        fps.append(_compute_hwid_from_raw(raw_guid_mb))
        
    # 3. Identificador nativo do registro do Windows (MachineGuid - sempre disponível)
    if guid:
        fps.append(_compute_hwid_from_raw(guid))

    if not fps:
        fallback = os.environ.get("COMPUTERNAME", "NEXO_GENERIC_HOST")
        fps.append(_compute_hwid_from_raw(fallback))

    _CACHED_FINGERPRINTS = fps
    return _CACHED_FINGERPRINTS

def get_hardware_id() -> str:
    """
    Gera ou recupera o Hardware ID (HWID) único e imutável desta máquina.
    Usa persistência local em machine.id para garantir consistência permanente.
    """
    global _CACHED_HWID
    if _CACHED_HWID:
        return _CACHED_HWID

    hwid_file = get_hwid_file_path()
    if hwid_file.exists():
        try:
            saved = hwid_file.read_text(encoding="utf-8").strip()
            if saved.startswith("NEXO-") and len(saved) == 19:
                _CACHED_HWID = saved
                return _CACHED_HWID
        except Exception:
            pass

    # Se ainda não existe, calcula com as propriedades da máquina e persiste
    fps = _get_machine_fingerprints()
    chosen_hwid = fps[0]
    
    try:
        hwid_file.write_text(chosen_hwid, encoding="utf-8")
    except Exception:
        pass

    _CACHED_HWID = chosen_hwid
    return _CACHED_HWID

def generate_license_key(target_hwid: str, exp_type: str = "LIFETIME", custom_date: str = None) -> str:
    """
    Gera uma chave criptográfica válida para um HWID específico.
    exp_type: 'LIFETIME', '30D', '6M', '1Y', 'CUSTOM'
    custom_date: 'YYYYMMDD' se exp_type == 'CUSTOM'
    """
    clean_hwid = target_hwid.strip().upper()
    
    now = datetime.now(timezone.utc)
    if exp_type == "LIFETIME":
        exp_code = "99991231"
    elif exp_type == "30D":
        target = now.timestamp() + (30 * 86400)
        exp_code = datetime.fromtimestamp(target, timezone.utc).strftime("%Y%m%d")
    elif exp_type == "6M":
        target = now.timestamp() + (180 * 86400)
        exp_code = datetime.fromtimestamp(target, timezone.utc).strftime("%Y%m%d")
    elif exp_type == "1Y":
        target = now.timestamp() + (365 * 86400)
        exp_code = datetime.fromtimestamp(target, timezone.utc).strftime("%Y%m%d")
    elif exp_type == "CUSTOM" and custom_date:
        exp_code = custom_date.replace("-", "").strip()
    else:
        exp_code = "99991231"

    payload = f"{clean_hwid}:{exp_code}"
    sig = hmac.new(_MASTER_SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest().upper()
    key = f"NEXO-{exp_code[:4]}-{exp_code[4:]}-{sig[:6]}-{sig[6:12]}"
    return key

def verify_license_key(key: str, current_hwid: str = None) -> dict:
    """
    Valida a chave contra o Hardware ID atual ou qualquer variante legítima desta máquina.
    Se bater com uma variante legítima, unifica e fixa o HWID em machine.id.
    """
    global _CACHED_HWID
    clean_key = key.strip().upper()
    parts = clean_key.split("-")
    if len(parts) != 5 or parts[0] != "NEXO":
        return {"valid": False, "reason": "Formato de chave inválido. Ex: NEXO-XXXX-XXXX-XXXXXX-XXXXXX"}
    
    exp_code = parts[1] + parts[2]
    key_sig_part = parts[3] + parts[4]
    
    # Construir lista de HWIDs candidatos desta máquina física
    candidates = []
    if current_hwid:
        c = current_hwid.strip().upper()
        if c not in candidates:
            candidates.append(c)
    
    active_hwid = get_hardware_id()
    if active_hwid not in candidates:
        candidates.append(active_hwid)
        
    for fp in _get_machine_fingerprints():
        if fp not in candidates:
            candidates.append(fp)

    matched_hwid = None
    for cand in candidates:
        payload = f"{cand}:{exp_code}"
        expected_sig = hmac.new(_MASTER_SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest().upper()
        if hmac.compare_digest(key_sig_part, expected_sig[:12]):
            matched_hwid = cand
            break

    if not matched_hwid:
        return {"valid": False, "reason": "Chave não autorizada para este computador (HWID incompatível)."}

    # Fixar o HWID que deu match permanente no arquivo machine.id para consistência absoluta
    try:
        hwid_file = get_hwid_file_path()
        hwid_file.write_text(matched_hwid, encoding="utf-8")
        _CACHED_HWID = matched_hwid
    except Exception:
        pass

    if exp_code == "99991231":
        plan_desc = "Licença Vitalícia (Permanente)"
        exp_formatted = "Sem expiração"
    else:
        try:
            exp_date = datetime.strptime(exp_code, "%Y%m%d").replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if now > exp_date:
                return {"valid": False, "reason": f"Esta licença expirou em {exp_date.strftime('%d/%m/%Y')}."}
            plan_desc = "Licença Periódica"
            exp_formatted = exp_date.strftime("%d/%m/%Y")
        except Exception:
            return {"valid": False, "reason": "Código de data de expiração corrompido."}
            
    return {
        "valid": True,
        "machine_id": matched_hwid,
        "plan": plan_desc,
        "expires": exp_formatted,
        "key": clean_key
    }

def save_license(key: str, validation_data: dict) -> bool:
    """Salva a licença criptografada no diretório do usuário."""
    try:
        lic_file = get_license_file_path()
        record = {
            "machine_id": validation_data.get("machine_id"),
            "key": key,
            "plan": validation_data.get("plan"),
            "expires": validation_data.get("expires"),
            "saved_at": datetime.now(timezone.utc).isoformat()
        }
        raw_json = json.dumps(record)
        xor_key = _MASTER_SECRET[0:16]
        obfuscated = bytes([b ^ xor_key[i % len(xor_key)] for i, b in enumerate(raw_json.encode("utf-8"))])
        b64 = base64.b64encode(obfuscated).decode("ascii")
        lic_file.write_text(b64, encoding="utf-8")
        return True
    except Exception:
        return False

def load_saved_license() -> dict:
    """Lê a licença salva e valida contra o hardware atual."""
    lic_file = get_license_file_path()
    hwid = get_hardware_id()
    
    if not lic_file.exists():
        return {"activated": False, "machine_id": hwid, "reason": "Nenhuma licença instalada."}
    
    try:
        b64 = lic_file.read_text(encoding="utf-8").strip()
        obfuscated = base64.b64decode(b64)
        xor_key = _MASTER_SECRET[0:16]
        raw_json = bytes([b ^ xor_key[i % len(xor_key)] for i, b in enumerate(obfuscated)]).decode("utf-8")
        record = json.loads(raw_json)
        
        key = record.get("key", "")
        validation = verify_license_key(key, hwid)
        if validation.get("valid"):
            return {
                "activated": True,
                "machine_id": validation.get("machine_id", hwid),
                "plan": validation.get("plan"),
                "expires": validation.get("expires"),
                "key": key
            }
        else:
            return {
                "activated": False,
                "machine_id": hwid,
                "reason": validation.get("reason", "Licença inválida ou corrompida.")
            }
    except Exception as e:
        return {"activated": False, "machine_id": hwid, "reason": f"Falha ao validar licença: {e}"}
