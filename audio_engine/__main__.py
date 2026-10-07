"""
Ponto de entrada do pacote audio_engine quando executado com 'python -m audio_engine'.
"""

import sys
from pathlib import Path

# Garante resolução do diretório pai no sys.path
package_dir = Path(__file__).resolve().parent
project_root = package_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from audio_engine.voice_modifier import main

if __name__ == "__main__":
    main()
