"""
DIEF JARVIS — configuração inicial.

Installs the Python dependencies for THIS operating system only: the OS-specific
packages in requirements.txt carry `sys_platform` markers, so a macOS or Linux
user never pulls Windows-only libraries (and vice-versa). Then it fetches the
Playwright browsers needed for web automation (current-OS builds only).

Two things it deliberately does NOT install:
  * the optional local wake word ("Hey Jarvis") — one-click, opt-in, from
    ⚙ → WAKE WORD inside the app;
  * anything for the avatar — the holographic head renders in software on the
    PyQt6 and numpy already listed here. No GPU, no OpenGL, no extra packages.
"""
import platform
import subprocess
import sys
from pathlib import Path

OS = platform.system()  # "Windows" | "Darwin" | "Linux"
HERE = Path(__file__).resolve().parent

MIN_PY = (3, 11)        # hard floor: below this the syntax used here won't parse
MAX_PY = (3, 13)        # highest version this is actually tested on


def _run(label: str, args: list[str]) -> None:
    print(f"\n▶ {label}")
    subprocess.run(args, check=True)


def _check_python() -> None:
    """Fail immediately and clearly rather than deep inside a pip resolver.

    A wrong interpreter is the single most common way this install goes sideways,
    and the error it produces on its own names a wheel, not the real problem.
    """
    v = sys.version_info[:2]
    if v > MAX_PY:
        # Newer is a warning, not a wall. Turning away someone who installed
        # today's Python is a worse first impression than a version that
        # turns out to work fine, and if a wheel really is missing pip says
        # so plainly.
        print(f"\n⚠️  Python {v[0]}.{v[1]} é mais recente que a versão "
              f"{MAX_PY[0]}.{MAX_PY[1]} indicada pelo instalador original. Continuando. "
              f"Se algum pacote não tiver uma distribuição compatível, instale Python "
              f"{MAX_PY[0]}.{MAX_PY[1]} e execute a configuração com essa versão.")
        return
    if v < MIN_PY:
        print(f"\n❌ Python {v[0]}.{v[1]} detectado. DIEF JARVIS precisa de pelo "
              f"menos Python {MIN_PY[0]}.{MIN_PY[1]}.")
        print("   Instale uma versão compatível e execute a configuração. Exemplos:")
        print(f"     py -{MIN_PY[0]}.{MIN_PY[1]} setup.py        (Windows)")
        print(f"     python{MIN_PY[0]}.{MIN_PY[1]} setup.py      (macOS / Linux)")
        sys.exit(1)


def _check_assets() -> None:
    """The avatar's face is a shipped file; a truncated clone should say so."""
    face = HERE / "core" / "face_model.obj"
    if not face.exists() or face.stat().st_size < 4096:
        print(
            "\n⚠️  core/face_model.obj está ausente ou incompleto. O visual usará "
            "o núcleo alternativo.\n"
            "    Restaure esse arquivo a partir do projeto original."
        )


def main() -> None:
    print(f"⚙  DIEF JARVIS · configuração · sistema detectado: {OS or 'desconhecido'}, "
          f"Python {sys.version_info[0]}.{sys.version_info[1]}")
    _check_python()

    # requirements.txt filters OS-specific extras by itself via pip markers.
    _run("Instalando dependências compatíveis com este sistema…",
         [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    # Chromium covers Chrome/Edge/Opera/Brave/Vivaldi; Firefox for Firefox.
    # (Safari automation additionally needs: python -m playwright install webkit)
    # Not fatal: these are a few hundred megabytes from a CDN that a corporate
    # network or a flaky connection can refuse, and everything except browser
    # automation works without them. Failing the whole install there would send
    # a user away from a working app.
    try:
        _run("Instalando navegadores de automação (chromium + firefox)…",
             [sys.executable, "-m", "playwright", "install", "chromium", "firefox"])
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"\n⚠️  Os navegadores de automação não foram instalados ({e}).")
        print("    A automação de navegador ficará indisponível. Tente novamente com:")
        print(f'    {sys.executable} -m playwright install chromium firefox')

    _check_assets()

    # ── OS-specific post-install notes ────────────────────────────────────────
    if OS == "Windows":
        try:
            import win32com.client  # noqa: F401
        except ImportError:
            postinstall = Path(sys.executable).parent / "Scripts" / "pywin32_postinstall.py"
            print(
                "\n⚠️  pywin32 não foi registrado corretamente. A criação de "
                "atalhos usará um método alternativo. Para corrigir, execute:\n"
                f'    "{sys.executable}" -m pip install --force-reinstall pywin32\n'
                f'    "{sys.executable}" "{postinstall}" -install'
            )
    elif OS == "Linux":
        print(
            "\nℹ️  Linux: algumas ações usam ferramentas nativas do sistema. "
            "Instale as necessárias pelo gerenciador de pacotes:\n"
            "    • volume      → pulseaudio-utils   (pactl)\n"
            "    • brilho      → brightnessctl\n"
            "    • lembretes   → systemd (systemd-run) ou 'at'\n"
            "    • abrir links → xdg-utils          (xdg-open)"
        )
    elif OS == "Darwin":
        print(
            "\nℹ️  macOS: volume, brilho e lembretes usam as ferramentas nativas "
            "'osascript' / LaunchAgents.\n"
            "    Para automação do Safari: python -m playwright install webkit"
        )

    print("\n✅ Configuração concluída!")
    print("   1. Inicie com: python main.py")
    print("   2. Informe sua chave Gemini na tela de configuração.")
    print("   3. Configure a ativação por voz nos controles do assistente.")


if __name__ == "__main__":
    main()
