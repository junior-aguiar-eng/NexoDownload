#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nexo Download - Gerador Oficial de Licenças Criptográficas (Administrador)
Use este utilitário para gerar Chaves de Ativação atreladas ao Hardware ID (HWID) do cliente.
"""

import sys
import os
from pathlib import Path

# Adiciona web_app ao path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from web_app.security_engine import generate_license_key, verify_license_key, get_hardware_id

def main():
    print("=" * 65)
    print(" NEXO DOWNLOAD PRO - GERADOR DE LICENÇAS CRIPTOGRÁFICAS")
    print("=" * 65)
    
    current_hwid = get_hardware_id()
    print(f"[*] ID da Máquina deste Computador (Admin): {current_hwid}\n")
    
    target_hwid = input("Digite o ID da Máquina do Cliente (ex: NEXO-XXXX-XXXX-XXXX): ").strip()
    if not target_hwid:
        print("[!] Nenhum ID informado. Usando o ID desta máquina para testes.")
        target_hwid = current_hwid

    print("\nEscolha a validade da licença:")
    print(" [1] Vitalícia / Permanente (Recomendado)")
    print(" [2] 30 Dias")
    print(" [3] 6 Meses (180 dias)")
    print(" [4] 1 Ano (365 dias)")
    print(" [5] Data personalizada (formato YYYYMMDD, ex: 20261231)")
    
    choice = input("\nOpção [1-5] (Padrão: 1): ").strip() or "1"
    
    exp_type = "LIFETIME"
    custom_date = None
    
    if choice == "2":
        exp_type = "30D"
    elif choice == "3":
        exp_type = "6M"
    elif choice == "4":
        exp_type = "1Y"
    elif choice == "5":
        exp_type = "CUSTOM"
        custom_date = input("Digite a data de expiração (YYYYMMDD): ").strip()

    key = generate_license_key(target_hwid, exp_type=exp_type, custom_date=custom_date)
    validation = verify_license_key(key, target_hwid)
    
    print("\n" + "=" * 65)
    print(" [OK] CHAVE DE ATIVAÇÃO GERADA COM SUCESSO!")
    print("=" * 65)
    print(f" ID do Cliente:   {target_hwid}")
    print(f" Tipo de Plano:   {validation.get('plan')}")
    print(f" Expiração:       {validation.get('expires')}")
    print("-" * 65)
    print(f" CHAVE:           {key}")
    print("=" * 65)
    print("\nCopie e envie a chave acima para o cliente ativar o Nexo Download.")

if __name__ == "__main__":
    main()
