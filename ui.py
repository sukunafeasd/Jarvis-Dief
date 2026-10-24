from __future__ import annotations

import json
import copy
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import psutil

if platform.system() == "Windows":
    _WIN_HIDE: dict = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    _WIN_HIDE: dict = {}

# Qt's video backend prints the ffmpeg stream banner — codec, bitrate, the
# whole signed googlevideo URL — to the console for every stream it opens. That
# is two screenfuls per video, it looks like an error to anyone reading the log,
# and it puts a URL carrying the viewer's IP address into a terminal people
# paste into bug reports. Silenced here, before Qt initialises its logging.
# An explicit setting from the user is left alone.
os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.*=false")

from PyQt6.QtCore import (
    QEasingCurve, QLineF, QMimeData, QObject, QParallelAnimationGroup, QPointF,
    QPoint, QPropertyAnimation, QRect, QRectF, QSize, QSizeF, Qt, QTimer,
    QUrl, QDate, QLocale, QLibraryInfo, QTranslator, QCoreApplication, QThread, QEvent, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QConicalGradient, QDragEnterEvent, QDropEvent, QFont,
    QFontDatabase, QKeySequence, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QRadialGradient, QShortcut,
)
# Video playback for the HUD. Part of PyQt6, so it costs no new dependency —
# but the multimedia plugins are a separate piece of the Qt install and can be
# absent on a stripped-down system, so a failure here disables one feature
# rather than stopping JARVIS from starting.
try:
    from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
    HAVE_VIDEO = True
except Exception as _e:            # noqa: BLE001 - reported, never fatal
    QAudioOutput = QMediaPlayer = QGraphicsVideoItem = None
    HAVE_VIDEO = False
    print(f"[Video] playback unavailable ({_e}) — the HUD will not show video.")

from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QAbstractButton, QTabBar, QListWidget, QScrollArea, QSizePolicy, QSplitter,
    QGraphicsScene, QGraphicsView,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget, QProgressBar,QStyle,
)
from core.hud_glass import HudGlassFrame
from core.environment_director import EnvironmentDirector

QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
try:
    from core.spatial_view import SpatialCoreView
except ImportError:
    SpatialCoreView = None

try:
    from core.avatar import HoloAvatar
except Exception:      # pragma: no cover — HUD must never die over cosmetics
    HoloAvatar = None


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
from memory.config_manager import CONFIG_FILE as API_FILE


def _read_full_config() -> dict:
    """Read api_keys.json config dict. Returns {} on any error."""
    from memory.config_manager import CONFIG_FILE,load_api_keys
    if API_FILE==CONFIG_FILE:return load_api_keys()
    try:
        return json.loads(API_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


# Single source of truth for the release name — the window title, the header
# badge and the readme must never disagree again.
APP_VERSION  = "DIEF JARVIS"
APP_PROTOCOL = APP_VERSION.split()[-1]

PT_BR = QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil)
STATE_LABELS = {
    "INITIALISING": "INICIANDO", "LISTENING": "ESCUTANDO",
    "THINKING": "ANALISANDO", "PROCESSING": "PROCESSANDO",
    "SPEAKING": "FALANDO", "SLEEPING": "EM REPOUSO", "MUTED": "SEM MICROFONE",
}

_DEFAULT_W, _DEFAULT_H = 980, 700
_MIN_W,     _MIN_H     = 820, 580
_LEFT_W  = 148
_RIGHT_W = 340

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"


class C:
    BG        = "#00060a"
    PANEL     = "#010d14"
    PANEL2    = "#010f18"
    BORDER    = "#0d3347"
    BORDER_B  = "#1a5c7a"
    BORDER_A  = "#0f4060"
    PRI       = "#00d4ff"
    PRI_DIM   = "#007a99"
    PRI_GHO   = "#001f2e"
    ACC       = "#ff6b00"
    ACC2      = "#ffcc00"
    GREEN     = "#00ff88"
    GREEN_D   = "#00aa55"
    RED       = "#ff3355"
    MUTED_C   = "#ff3366"
    TEXT      = "#8ffcff"
    TEXT_DIM  = "#3a8a9a"
    TEXT_MED  = "#5ab8cc"
    WHITE     = "#d8f8ff"
    DARK      = "#000d14"
    BAR_BG    = "#011520"


# Keys tied to the accent colour — status colours (ACC, GREEN, RED…) stay fixed
_HUE_LINKED = (
    "PRI", "PRI_DIM", "PRI_GHO",
)
_PALETTE_DEFAULTS: dict[str, str] = {k: getattr(C, k) for k in _HUE_LINKED}

DEFAULT_UI_COLOR = _PALETTE_DEFAULTS["PRI"]


def apply_ui_accent(accent_hex: str) -> bool:
    """
    Re-derives the whole teal-family palette from the chosen accent colour
    (hue shift — brightness/saturation ratios are preserved, design stays intact).
    Painted elements (HUD, waveform, metrics) pick up the new colour on the next
    frame; stylesheet-based panels pick it up when they are rebuilt.
    """
    import colorsys

    accent_hex = (accent_hex or "").strip().lower()
    if not (accent_hex.startswith("#") and len(accent_hex) == 7):
        return False
    try:
        int(accent_hex[1:], 16)
    except ValueError:
        return False

    def _hsv(h: str) -> tuple[float, float, float]:
        r = int(h[1:3], 16) / 255
        g = int(h[3:5], 16) / 255
        b = int(h[5:7], 16) / 255
        return colorsys.rgb_to_hsv(r, g, b)

    base_h            = _hsv(_PALETTE_DEFAULTS["PRI"])[0]
    acc_h, acc_s, _av = _hsv(accent_hex)
    dh   = acc_h - base_h
    grey = acc_s < 0.08   # near-grey accent → the whole theme is desaturated

    for key, hex0 in _PALETTE_DEFAULTS.items():
        h, s, v = _hsv(hex0)
        if grey:
            s *= 0.15
        r, g, b = colorsys.hsv_to_rgb((h + dh) % 1.0, s, v)
        setattr(C, key, "#{:02x}{:02x}{:02x}".format(
            int(r * 255 + 0.5), int(g * 255 + 0.5), int(b * 255 + 0.5)))
    return True


def current_palette() -> dict[str, str]:
    """A snapshot of the accent-linked colours currently on class C."""
    return {k: getattr(C, k) for k in _HUE_LINKED}


def retheme_all_widgets(old: dict[str, str], new: dict[str, str]) -> None:
    """
    LIVE full theme change. Replaces the old palette colours with the new ones
    in EVERY widget's stylesheet across the app and repaints them. This way the
    colour change applies INSTANTLY across the whole interface — panels, buttons,
    borders included — not just the painted elements. No restart needed.
    """
    mapping = {old[k].lower(): new[k].lower()
               for k in old if old[k].lower() != new.get(k, old[k]).lower()}
    if not mapping:
        return
    app = QApplication.instance()
    if app is None:
        return
    for w in app.allWidgets():
        try:
            ancestor = w
            independent = False
            while ancestor is not None:
                if ancestor.property('independentTheme'):
                    independent = True
                    break
                ancestor = ancestor.parentWidget()
            if independent:
                continue
            ss = w.styleSheet()
            if ss:
                s2 = ss
                for o, n in mapping.items():
                    if o in s2:
                        s2 = s2.replace(o, n)
                if s2 != ss:
                    w.setStyleSheet(s2)
            w.update()
        except Exception:
            pass


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c


# ── Windows GPU via NVML DLL (no subprocess, no console window) ──────────────
_nvml_lib: object = None   # cached ctypes DLL
_nvml_ok:  object = None   # None=untested, True=works, False=unavailable


def _nvml_gpu_windows() -> float:
    """Return NVIDIA GPU utilisation % using nvml.dll directly — zero subprocess."""
    global _nvml_lib, _nvml_ok
    if _nvml_ok is False:
        return -1.0
    try:
        import ctypes

        class _Util(ctypes.Structure):
            _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

        if _nvml_lib is None:
            for dll_name in ("nvml", r"C:\Windows\System32\nvml.dll"):
                try:
                    lib = ctypes.WinDLL(dll_name)
                    lib.nvmlInit_v2()
                    _nvml_lib = lib
                    break
                except Exception:
                    continue

        if _nvml_lib is None:
            import pynvml  # type: ignore
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            _nvml_ok = True
            return float(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)

        dev = ctypes.c_void_p()
        _nvml_lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev))
        util = _Util()
        _nvml_lib.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(util))
        _nvml_ok = True
        return float(util.gpu)
    except Exception:
        _nvml_ok = False
        return -1.0


class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0
        self.mem  = 0.0
        self.net  = 0.0   
        self.gpu  = -1.0  
        self.tmp  = -1.0  
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        # Probe caches — GPU (NVML) and temperature (WMI) are the expensive
        # queries; initialise their handles once and reuse them instead of
        # rebuilding a connection on every poll.
        self._slow_tick = 0            # gpu/temp refreshed every 3rd cycle
        self._pynvml    = None         # cached pynvml module + device handle
        self._pynvml_h  = None
        self._pynvml_ok = None         # None=untested, False=unavailable here
        self._nv_unix   = None         # cached (lib, dev) for Linux/macOS NVML
        self._wmi_conn  = None         # cached WMI connection (creating one is slow)
        self._wmi_ok    = None         # None=untested, False=unavailable here
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(2.0)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent

        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net  = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net   = nc
        self._last_net_t = now

        # GPU and temperature change slowly and are the most expensive probes
        # (NVML / WMI) — refresh them every 3rd cycle (~6 s) instead of every
        # cycle, reusing the previous reading in between.
        self._slow_tick = (self._slow_tick + 1) % 3
        if self._slow_tick == 1:
            gpu = self._get_gpu()
            tmp = self._get_temp()
        else:
            gpu = self.gpu
            tmp = self.tmp

        with self._lock:
            self.cpu = cpu
            self.mem = mem
            self.net = net
            self.gpu = gpu
            self.tmp = tmp

    def _get_gpu(self) -> float:
        # pynvml — subprocess-free; initialise once and reuse the handle.
        # Re-initialising NVML on every poll is slow, so cache it and stop
        # retrying pynvml entirely once it proves unavailable here.
        if self._pynvml_ok is not False:
            try:
                if self._pynvml_h is None:
                    import pynvml  # type: ignore
                    pynvml.nvmlInit()
                    self._pynvml    = pynvml
                    self._pynvml_h  = pynvml.nvmlDeviceGetHandleByIndex(0)
                    self._pynvml_ok = True
                return float(self._pynvml.nvmlDeviceGetUtilizationRates(self._pynvml_h).gpu)
            except Exception:
                self._pynvml_ok = False

        # Windows: nvml.dll via ctypes (already cached in _nvml_gpu_windows)
        if _OS == "Windows":
            return _nvml_gpu_windows()

        # Linux / macOS: libnvidia-ml shared lib via ctypes — init once, reuse
        try:
            import ctypes

            class _Util(ctypes.Structure):
                _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

            if self._nv_unix is None:
                _lib = "libnvidia-ml.so.1" if _OS == "Linux" else "libnvidia-ml.dylib"
                nv = ctypes.CDLL(_lib)
                nv.nvmlInit_v2()
                dev = ctypes.c_void_p()
                nv.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev))
                self._nv_unix = (nv, dev)

            nv, dev = self._nv_unix
            u = _Util()
            nv.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(u))
            return float(u.gpu)
        except Exception:
            pass

        return -1.0   # N/A — zero subprocess on all platforms

    def _get_temp(self) -> float:
        # psutil — works on Linux; occasionally Windows with driver support
        try:
            temps = psutil.sensors_temperatures()
            for name in ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                         "cpu-thermal", "zenpower", "it8688"]:
                if name in temps and temps[name]:
                    return temps[name][0].current
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass

        # Windows: wmi module (pure Python COM, zero subprocess). Reuse a single
        # connection — building a fresh wmi.WMI() on every poll spins up a COM
        # connection each time and is very slow. Give up after one failure.
        if _OS == "Windows" and self._wmi_ok is not False:
            try:
                if self._wmi_conn is None:
                    import wmi  # type: ignore
                    self._wmi_conn = wmi.WMI(namespace="root/wmi")
                tz = self._wmi_conn.MSAcpi_ThermalZoneTemperature()
                if tz:
                    return (tz[0].CurrentTemperature / 10.0) - 273.15
            except Exception:
                self._wmi_ok   = False
                self._wmi_conn = None

        return -1.0   # N/A — zero subprocess on all platforms

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cpu": self.cpu,
                "mem": self.mem,
                "net": self.net,
                "gpu": self.gpu,
                "tmp": self.tmp,
            }


_metrics = _SysMetrics()

class HudCanvas(QWidget):
    interaction = pyqtSignal(str, float, float)
    def __init__(self, face_path: str, assistant_name: str = "DIEF JARVIS", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(300, 300)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip('')
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted    = False
        self.resting = False
        self.news_projection = False
        self.news_content = None
        self._rest_visibility = 1.0
        self.speaking = False
        self.state    = "INITIALISING"
        self._assistant_name = assistant_name

        # The holographic head that fills the HUD. If it could not be imported
        # we fall back to the old glowing core so the panel is never empty.
        self._avatar = None
        if HoloAvatar is not None:
            try:
                self._avatar = HoloAvatar()
            except Exception:
                self._avatar = None

        # Which centrepiece to draw. Read once here and changed live by the
        # settings toggle; the avatar object is kept either way so switching
        # back is instant and costs no reload.
        try:
            from memory.config_manager import get_hud_style
            self.hud_style = get_hud_style()
        except Exception:
            self.hud_style = "face"
        self._core_phase = 0.0
        self._spatial_core = None
        self._core_attempted = False
        self._core_sync_at = 0.0
        self._motion_config_at=0.0
        self.motion_reduced=False
        self._cue_serial=0
        self._cue_kind=''
        self._cue_until=0.0
        self._face_accent=QColor(C.PRI)

        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._halo       = 55.0
        self._tgt_halo   = 55.0
        self._last_t     = time.time()
        self._step_t     = time.time()
        self._blink      = True
        self._blink_tick = 0

        # Rescaled-face cache: the smooth rescale is expensive, so we keep the
        # last result and only rebuild it when the (quantised) size changes.

        # Static grid-dot layer, pre-rendered once per size/theme into a pixmap
        # so paintEvent blits it in one call instead of thousands of drawPoint()s.
        self._grid_cache: QPixmap | None = None
        self._grid_key = None
        # Repaint throttle counter (idle frames drop to ~20 Hz — see _step()).
        self._paint_tick = 0

        # Live audio reactivity: _live_amp is written from the audio threads
        # (0.0–1.0), _amp_disp is the smoothed value the paint code reads.
        self._live_amp  = 0.0
        self._amp_disp  = 0.0
        # (frames, start_time, hop) posted by the playback thread — see
        # push_visemes(). None means "no schedule; use the plain level".
        self._visemes = None
        self._vis_i = None        # first schedule frame not yet handed to the mouth
        self._base_scale = 1.0    # slow "breathing" target; amp is added per-frame
        self._base_halo  = 55.0

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def cancel_audio_animation(self):
        self._visemes=None
        self._vis_i=None
        self._live_amp=0.
        self._amp_disp=0.

    def glance(self, dx: float, dy: float, hold: float = 1.1) -> None:
        """Ask the avatar to look somewhere for a moment (see HoloAvatar.glance)."""
        try:
            if self._avatar is not None:
                self._avatar.glance(dx, dy, hold)
        except Exception:
            pass

    def push_visemes(self, frames, hop: float, at: float) -> None:
        """Thread-safe: hand over a schedule of (level, openness, width) frames.

        The playback thread writes up to 200 ms of audio in one go, so a single
        averaged level would only move the mouth five times a second — enough to
        flap, nowhere near enough to articulate. It instead posts the whole
        slice's worth of 20 ms frames here and `_step()` plays them out against
        the wall clock, in step with the audio going to the speakers.

        `at` is the wall-clock time this batch will *begin to sound*, which the
        caller tracks as a playback cursor. It is not the time of the call, and
        the difference is the whole point: `stream.write` returns once the buffer
        accepts the samples, so consecutive batches are handed over far faster
        than they play. Anchoring each one to "now" made every batch start while
        its predecessor was still sounding, so each schedule replaced the last
        after a couple of frames and the mouth only ever played the opening
        instant of every 200 ms — the reason it did not match the words.

        Successive batches are therefore *appended* into one continuous
        timeline, not swapped in. A paragraph is one schedule; the mouth stops
        falling into a gap at every chunk boundary and having to climb back out.
        """
        try:
            if not frames:
                return
            hop = max(1e-3, float(hop))
            at = float(at)
            new = list(frames)
            cur = self._visemes
            if cur is not None:
                old, t0, ohop = cur
                if abs(ohop - hop) < 1e-6:
                    # Where in the existing timeline does this batch land?
                    i = int(round((at - t0) / hop))
                    if 0 <= i <= len(old) + 1:
                        # Continues (or slightly overlaps) what is already
                        # queued: extend rather than restart. Drop whatever has
                        # already been played so the list cannot grow without
                        # bound over a long reply.
                        merged = old[:i] + new
                        played = int((time.time() - t0) / hop) - 2
                        if played > 60:
                            merged = merged[played:]
                            t0 += played * hop
                            if self._vis_i is not None:
                                self._vis_i = max(0, self._vis_i - played)
                        self._visemes = (merged, t0, hop)
                        return
            self._visemes = (new, at, hop)
            self._vis_i = None
        except Exception:
            pass

    def set_audio_level(self, level: float) -> None:
        """Thread-safe entry point for the audio threads. Stores the louder of
        the incoming level and the current value so brief gaps between chunks
        don't make the waveform stutter; _step() decays it back down."""
        try:
            lv = float(level)
        except (TypeError, ValueError):
            return
        if lv < 0.0:
            lv = 0.0
        elif lv > 1.0:
            lv = 1.0
        if lv > self._live_amp:
            self._live_amp = lv

    def _make_grid(self, W: int, H: int) -> QPixmap:
        """Pre-render the static grid-dot background into a transparent pixmap so
        paintEvent can blit it once per frame instead of running a nested
        drawPoint() loop across the whole widget every 16 ms."""
        pm = QPixmap(max(1, W), max(1, H))
        pm.fill(Qt.GlobalColor.transparent)
        gp = QPainter(pm)
        gp.setPen(QPen(qcol(C.PRI_GHO), 1))
        for x in range(0, W, 48):
            for y in range(0, H, 48):
                gp.drawPoint(x, y)
        gp.end()
        return pm

    def _step(self):
        self._tick += 1
        now = time.time()
        self._rest_visibility += ((0.14 if self.resting else 1.0)-self._rest_visibility)*0.065

        # ── Live audio reactivity ────────────────────────────────────────────
        # A viseme schedule, if one is playing, gives both the level and the
        # mouth shape for this exact instant; otherwise fall back to the peak
        # level the audio threads pushed in.
        v_open = v_wide = v_level = None
        v_seq = None
        sched = self._visemes
        if sched is not None:
            frames, t0, hop = sched
            i = int((now - t0) / hop)
            if 0 <= i < len(frames):
                # Hand over *every* frame since the last tick, not just the one
                # under the cursor. This timer runs at 60 Hz but the paint is
                # throttled and the machine may be busy, so a tick can span two
                # or three 20 ms frames — and a consonant closure is only two
                # frames long. Sampling one and discarding the rest is how the
                # closures between words went missing.
                j = self._vis_i if self._vis_i is not None else i
                v_seq = frames[max(0, j):i + 1]
                self._vis_i = max(j, i + 1)
                v_level, v_open, v_wide = frames[i]
                if v_seq:
                    peak = max(f[0] for f in v_seq)
                    if peak > self._live_amp:
                        self._live_amp = peak
            elif i >= len(frames):
                self._visemes = None        # schedule spent
                self._vis_i = None

        # Audio threads push peaks into _live_amp; decay it toward silence so
        # gaps between chunks fade out instead of freezing, then smooth it.
        self._live_amp *= 0.86
        self._amp_disp += (self._live_amp - self._amp_disp) * 0.45
        amp = self._amp_disp

        # The avatar animates off the very same smoothed level the waveform
        # uses — one audio source, so the mouth can never drift out of sync.
        dt = now - self._step_t
        self._step_t = now
        # Integrated, not derived from absolute time: multiplying wall-clock by
        # a rate that changes with state jumps the rings the instant JARVIS
        # starts talking. Same lesson the head's sway taught.
        self._core_phase += min(0.10, max(0.0, dt))
        if now-self._motion_config_at>=1:
            self.motion_reduced=bool(_read_full_config().get('reduce_motion',False))
            self._motion_config_at=now
        target=qcol(C.ACC if self.speaking else C.ACC2 if self.state in ('THINKING','PROCESSING') else C.PRI)
        if self._cue_kind=='warning' and time.monotonic()<self._cue_until:
            target=QColor('#e7b882')
        blend=1-math.exp(-min(.1,max(0,dt))*5)
        self._face_accent=QColor(*[int(a+(b-a)*blend) for a,b in zip(self._face_accent.getRgb()[:3],target.getRgb()[:3])])
        self._sync_spatial_core(now)

        if self._avatar is not None and self.hud_style == "face":
            self._avatar.reduced_motion=self.motion_reduced
            self._avatar.step(dt, amp, speaking=self.speaking,
                              muted=self.muted, state=self.state,
                              v_open=v_open, v_wide=v_wide or 0.0,
                              v_level=v_level, v_seq=v_seq,
                              v_hop=(sched[2] if sched is not None else 0.02))
        else:
            # Fallback core: slow "breathing" base target, lifted by the level.
            if now - self._last_t > (0.12 if self.speaking else 0.5):
                if self.speaking:
                    self._base_scale = 1.03
                    self._base_halo  = 122.0
                elif self.muted:
                    self._base_scale = random.uniform(0.998, 1.002)
                    self._base_halo  = random.uniform(15, 28)
                else:
                    self._base_scale = random.uniform(1.001, 1.008)
                    self._base_halo  = random.uniform(48, 68)
                self._last_t = now

            if self.muted or self.resting:
                self._tgt_scale, self._tgt_halo = self._base_scale, self._base_halo
            elif self.speaking:
                self._tgt_scale = self._base_scale + amp * 0.13
                self._tgt_halo  = self._base_halo  + amp * 95.0
            else:
                self._tgt_scale = self._base_scale + amp * 0.06
                self._tgt_halo  = self._base_halo  + amp * 75.0

            sp = 0.38 if self.speaking else (0.30 if amp > 0.02 else 0.15)
            self._scale += (self._tgt_scale - self._scale) * sp
            self._halo  += (self._tgt_halo  - self._halo)  * sp

        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0
            _blinked = True
        else:
            _blinked = False

        # Repaint throttling — advancing the animation state above is cheap at
        # 60 Hz, but the paint is heavy. Active (speaking, audio, thinking) runs
        # at ~30 Hz, which is the frame rate animation has used for talking
        # characters forever and is indistinguishable here; idle drops to ~20 Hz
        # so a sleeping HUD stops pinning a CPU core. The visuals stay smooth
        # either way because the animation state keeps stepping at 60 Hz.
        self._paint_tick = (self._paint_tick + 1) % 6
        active = (self.speaking or amp > 0.02
                  or self.state in ("THINKING", "PROCESSING"))
        if _blinked or (self._paint_tick % 2 == 0 if active
                        else self._paint_tick % 3 == 0):
            # Nothing is on screen when the window is hidden or minimised, so
            # rendering the avatar into it is pure waste — and this app is meant
            # to sit running all day. The animation state above keeps stepping,
            # so it picks up mid-motion instead of snapping when you come back.
            if self._on_screen():
                self.update()

    def _on_screen(self) -> bool:
        """True only when this canvas can actually be seen by the user."""
        try:
            if not self.isVisible():
                return False
            win = self.window()
            return not (win.isMinimized() or win.isHidden())
        except Exception:
            return True      # never let a visibility check stop the HUD drawing

    # ── reactor core ─────────────────────────────────────────────────────────
    # The centrepiece for anyone who did not want a face looking back at them.
    # Built from the same budget as the head — software QPainter, no GPU — and
    # from the same principle: everything on it means something. The rings turn
    # at a rate the state sets, the spectrum ring is the real audio level, and
    # the core brightens with the voice. Nothing here is decoration that moves
    # for its own sake, which is what made the old glowing orb feel dead.

    def _sync_spatial_core(self, now):
        if now - self._core_sync_at < 0.1:
            return
        self._core_sync_at = now
        phase = {"INITIALISING": "booting", "THINKING": "thinking", "PROCESSING": "executing", "SLEEPING": "sleeping",
                 "AWAITING_RESPONSE": "awaiting_response", "WARNING": "warning", "ERROR": "error", "OFFLINE": "offline"}.get(
                     self.state, "listening" if self._amp_disp > 0.02 else "idle")
        if self.speaking:
            phase = 'speaking'
        if self.muted:
            phase = 'sleeping'
        if hasattr(self.window(), '_sync_environment'):
            self.window()._sync_environment(phase, self._amp_disp)
        wanted = self.hud_style == "core"
        if wanted and not self._core_attempted and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            self._core_attempted = True
            try:
                if SpatialCoreView is not None:
                    self._spatial_core = SpatialCoreView(self)
                    self._spatial_core.ready.connect(self.window()._start_environment)
                    self._spatial_core.neural_finished.connect(self.window()._finish_neural_memory)
                    self._spatial_core.unavailable.connect(self.window()._start_environment)
                    self._spatial_core.page().urlChanged.connect(self._core_gesture)
                    if hasattr(self.window(),'_render_presentation'):
                        self._spatial_core.unavailable.connect(self.window()._render_presentation)
                        self._spatial_core.loadFinished.connect(lambda ok: self.window()._render_presentation() if ok else None)
            except Exception as error:
                print(f"[Core] Local renderer unavailable: {error}")
                if hasattr(self.window(),'_start_environment'):QTimer.singleShot(0,self.window()._start_environment)
        if self._spatial_core:
            visible = wanted and self._on_screen() and not self._spatial_core.failed
            self._spatial_core.setVisible(visible)
            fw = min(self.width(), self.height())
            height = max(1, int(self.height() / 2 + fw * 0.4 - 28))
            self._spatial_core.setGeometry(0, 0, self.width(), height)
            phase = {"INITIALISING": "booting", "THINKING": "thinking", "PROCESSING": "executing", "SLEEPING": "sleeping",
                "AWAITING_RESPONSE":"awaiting_response","WARNING":"warning","ERROR":"error","OFFLINE":"offline"}.get(self.state, "listening" if self._amp_disp > 0.02 else "idle")
            if self.speaking:
                phase = "speaking"
            if self.muted:
                phase = "sleeping"
            self._spatial_core.sync({"phase": phase, "level": self._amp_disp,
                                     "color": C.PRI, "visible": visible, "resting":self.resting,"projection":self.news_projection,
                                     "motion":"reduced" if self.motion_reduced else "full",
                                     "cue":{'kind':self._cue_kind,'serial':self._cue_serial}})
            self._spatial_core.sync_news(self.news_content)

    def semantic_cue(self,kind):
        if time.monotonic()<self._cue_until and kind=='projection':return
        self._cue_serial+=1;self._cue_kind=kind;self._cue_until=time.monotonic()+.85

    def _core_gesture(self,url):
        parts=url.fragment().split("-")
        if len(parts)>=4 and parts[0]=="gesture":
            try:
                self.interaction.emit(parts[1],float(parts[2]),float(parts[3]))
            except ValueError:
                pass

    def _face_geometry(self):
        fw=min(self.width(),self.height())
        band=max(60.0,self.height()/2+fw*.4-24.0)
        r=min(fw*.355,band/(self._avatar.SPAN+.08))
        cy=12.0+(band-self._avatar.SPAN*r)/2+r
        scale=.72+.28*(self._rest_visibility-.14)/.86
        return self.width()/2,cy,r*scale

    def _hits_hologram(self,position):
        if self.hud_style=="face" and self._avatar is not None:
            return self._avatar.contains_point(position.x(),position.y(),*self._face_geometry())
        if self._spatial_core is not None and self._spatial_core.isVisible():
            return False  # The WebGL child owns its projected hit target.
        band=max(60.0,self.height()/2+min(self.width(),self.height())*.4-24.0)
        r=min(self.width()*.46,band/2)
        return (position.x()-self.width()/2)**2+(position.y()-(12+band/2))**2<=r*r

    def mousePressEvent(self,event):
        self._gesture_origin=None
        if event.button()==Qt.MouseButton.LeftButton and self._hits_hologram(event.position()):
            self._gesture_origin=event.position()

    def mouseReleaseEvent(self,event):
        origin=getattr(self,"_gesture_origin",None)
        if origin is not None and event.button()==Qt.MouseButton.LeftButton:
            delta=event.position()-origin
            moved=abs(delta.x())+abs(delta.y())>12
            if moved or self._hits_hologram(event.position()):
                self.interaction.emit("move" if moved else "touch",event.position().x()/max(1,self.width()),event.position().y()/max(1,self.height()))
            self._gesture_origin=None

    def _core_colours(self):
        if self.muted:
            return qcol(C.MUTED_C), qcol(C.MUTED_C)
        if self.speaking:
            return qcol(C.PRI), qcol(C.ACC)
        if self.state in ("THINKING", "PROCESSING"):
            return qcol(C.PRI), qcol(C.ACC2)
        if self.state == "LISTENING":
            return qcol(C.PRI), qcol(C.GREEN)
        return qcol(C.PRI), qcol(C.PRI_DIM)

    def _paint_core(self, p: QPainter, cx: float, cy: float, r: float,
                    W: float = 0.0, H: float = 0.0):
        """Draw the reactor at (cx, cy) with outer radius r, using the whole
        canvas (W x H) for the marks that frame it."""
        main, acc = self._core_colours()
        bg = qcol(C.BG)
        amp = self._amp_disp
        t = self._core_phase
        live = (self.speaking or amp > 0.04) and not self.muted

        def blend(col: QColor, a: float) -> QColor:
            """Pre-mix onto the background instead of asking Qt to composite.
            The raster engine's opaque path is several times faster than its
            translucent one, and everything here is a line or an arc."""
            k = max(0.0, min(1.0, a))
            return QColor(int(bg.red()   + (col.red()   - bg.red())   * k),
                          int(bg.green() + (col.green() - bg.green()) * k),
                          int(bg.blue()  + (col.blue()  - bg.blue())  * k))

        p.setBrush(Qt.BrushStyle.NoBrush)

        # 1. The atmosphere. One radial gradient doing what a stack of discs did
        #    badly: a wide, soft body of light that gives the thing presence
        #    before any detail is read. This single element decides whether the
        #    HUD looks vast or looks small, so it is drawn first and drawn big.
        # Concentrated rather than spread: a gradient reaching the outer rim
        # washes the whole disc a flat dim blue and reads as fog. Ending it at
        # two thirds leaves it a body of light with somewhere to fall off to,
        # which is what makes it look lit rather than tinted.
        lift = 1.0 + 0.55 * amp + (0.18 if self.speaking else 0.0)
        p.setPen(Qt.PenStyle.NoPen)
        for gr, a0, a1 in ((r * 0.70, 0.30, 0.0), (r * 0.34, 0.34, 0.0)):
            g = QRadialGradient(cx, cy, gr)
            g.setColorAt(0.00, blend(main, min(0.95, a0 * lift)))
            g.setColorAt(0.45, blend(main, min(0.95, a0 * lift * 0.52)))
            g.setColorAt(0.78, blend(main, min(0.95, a0 * lift * 0.18)))
            g.setColorAt(1.00, blend(main, a1))
            p.setBrush(QBrush(g))
            p.drawEllipse(QRectF(cx - gr, cy - gr, gr * 2, gr * 2))
        p.setBrush(Qt.BrushStyle.NoBrush)

        # 2. Frame marks at the corners of the whole canvas, not of the circle.
        #    They are what set the scale: the eye reads the reactor as filling
        #    the room rather than sitting in the middle of it.
        if W > 40 and H > 40:
            m, arm = min(W, H) * 0.035, min(W, H) * 0.055
            p.setPen(QPen(blend(main, 0.45), 1.4))
            for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                x = cx + sx * (W / 2 - m)
                y = cy + sy * (H / 2 - m)
                p.drawLine(QLineF(x, y, x - sx * arm, y))
                p.drawLine(QLineF(x, y, x, y - sy * arm))

        # 3. Crosshair across the full canvas, broken around the core so it
        #    frames the reactor rather than crossing it.
        p.setPen(QPen(blend(main, 0.16), 1))
        gap = r * 0.62
        if W > 40:
            p.drawLine(QLineF(cx - W / 2, cy, cx - gap, cy))
            p.drawLine(QLineF(cx + gap, cy, cx + W / 2, cy))
        if H > 40:
            p.drawLine(QLineF(cx, cy - H / 2, cx, cy - gap))
            p.drawLine(QLineF(cx, cy + gap, cx, cy + H / 2))

        # 4. Two thin outer circles. Sparse on purpose — a dense ring reads as a
        #    grey band at this size, and restraint is what made the original
        #    look expensive.
        for rr, a in ((1.00, 0.34), (0.93, 0.16)):
            rad = r * rr
            p.setPen(QPen(blend(main, a), 1))
            p.drawEllipse(QRectF(cx - rad, cy - rad, rad * 2, rad * 2))

        # 5. Long, sparse graduations: 24 majors reaching well in from the rim,
        #    with shorter minors between them.
        major, minor = [], []
        for i in range(72):
            a = math.radians(i * 5.0)
            ca, sa = math.cos(a), math.sin(a)
            if i % 3 == 0:
                major.append(QLineF(cx + ca * r * 0.885, cy + sa * r * 0.885,
                                    cx + ca * r * 0.985, cy + sa * r * 0.985))
            else:
                minor.append(QLineF(cx + ca * r * 0.945, cy + sa * r * 0.945,
                                    cx + ca * r * 0.985, cy + sa * r * 0.985))
        p.setPen(QPen(blend(main, 0.42), 1.3))
        p.drawLines(major)
        p.setPen(QPen(blend(main, 0.18), 1))
        p.drawLines(minor)

        # 6. Sweeping arcs. Long spans, not dashes — the original's grandeur
        #    came from a few big strokes. Speed is the state: idle drifts,
        #    thinking hurries, speaking runs.
        rate = 1.0 + (1.9 if self.state in ("THINKING", "PROCESSING") else 0.0) \
                   + (1.2 if self.speaking else 0.0)
        for k, (rr, span, count, dirn, col, a, wid) in enumerate((
                (0.955, 118, 2, +1, acc,  0.75, 2.0),
                (0.845, 82,  3, -1, main, 0.38, 1.3),
                (0.760, 150, 1, +1, acc,  0.45, 1.6),
                (0.660, 64,  4, -1, main, 0.26, 1.1),
                (0.545, 128, 2, +1, main, 0.30, 1.2))):
            rad = r * rr
            p.setPen(QPen(blend(col, a), wid))
            box = QRectF(cx - rad, cy - rad, rad * 2, rad * 2)
            base = (t * rate * (9 + k * 6) * dirn) % 360.0
            for sgm in range(count):
                p.drawArc(box, int((base + sgm * (360.0 / count)) * 16),
                          int(span * 16))

        # 7. The voice, as a ring of graduations that grow with it. Kept out at
        #    a wide radius so it never crowds the middle.
        n = 60
        ring = r * 0.415
        spikes = []
        for i in range(n):
            a = math.radians(i * (360.0 / n))
            ca, sa = math.cos(a), math.sin(a)
            wob = 0.5 + 0.5 * math.sin(t * 2.3 + i * 0.42)
            idle = 0.018 + 0.012 * math.sin(t * 1.2 + i * 0.7)
            h = r * (idle + (amp * 0.20 * wob if live else 0.0))
            spikes.append(QLineF(cx + ca * ring, cy + sa * ring,
                                 cx + ca * (ring + h), cy + sa * (ring + h)))
        p.setPen(QPen(blend(acc if live else main, 0.25 + 0.5 * amp), 1.6))
        p.drawLines(spikes)

        # 8. The inner ring the name sits in.
        inner = r * 0.355
        p.setPen(QPen(blend(acc, 0.30 + 0.45 * amp), 1.5))
        p.drawEllipse(QRectF(cx - inner, cy - inner, inner * 2, inner * 2))

        # 9. The name, sized from the string rather than from the radius alone:
        #    "J.A.R.V.I.S" and a name someone renamed to "MAX" are very
        #    different widths, and a fixed fraction of r spills one of them past
        #    the ring it is supposed to sit inside.
        name = self._assistant_name or ""
        if name:
            space = max(1.0, r * 0.018)
            fsz = max(8, int(min(r * 0.105,
                                 (inner * 1.75) / max(1, len(name)) * 1.6 - space)))
            f = QFont("Courier New", fsz, QFont.Weight.Bold)
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, space)
            p.setFont(f)
            p.setPen(QPen(blend(qcol(C.WHITE), 0.6 + 0.4 * min(1.0, amp * 2)), 1))
            p.drawText(QRectF(cx - r, cy - fsz, r * 2, fsz * 2),
                       Qt.AlignmentFlag.AlignCenter, name)

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():      # device not ready (e.g. 0-size during layout) — skip cleanly
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent):
            p.fillRect(self.rect(), qcol(C.BG))

        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        fw = min(W, H)

        # grid dots — blitted from a cached layer; rebuilt only when the size
        # or the theme's ghost colour changes (so live re-theming still works).
        _gkey = (W, H, C.PRI_GHO)
        if self._grid_cache is None or self._grid_key != _gkey:
            self._grid_cache = self._make_grid(W, H)
            self._grid_key   = _gkey
        if self.testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent):
            p.drawPixmap(0, 0, self._grid_cache)
        p.setOpacity(self._rest_visibility)

        # ── holographic head ────────────────────────────────────────────────
        # Sized to the band between the top of the canvas and the status line,
        # capped by width, so it fills the HUD at any window size — including
        # fullscreen — without ever colliding with the status text below.
        _sy_status = cy + fw * 0.40
        if self._avatar is not None and self.hud_style == "face":
            _band_t = 12.0
            _band_h = max(60.0, _sy_status - 12.0 - _band_t)
            _, _head_cy, _r_head = self._face_geometry()

            if self.muted:
                _main = _acc = qcol(C.MUTED_C)
            else:
                _main = qcol(C.PRI)
                if self.speaking:
                    _acc = qcol(C.ACC)
                elif self.state in ("THINKING", "PROCESSING"):
                    _acc = qcol(C.ACC2)
                elif self.state == "LISTENING":
                    _acc = qcol(C.GREEN)
                else:
                    _acc = qcol(C.PRI)
            p.setOpacity(self._rest_visibility*(.22 if self.news_projection else 1.0))
            _acc=self._face_accent
            self._avatar.paint(p, cx, _head_cy, _r_head, _main, _acc, qcol(C.BG))

        # reactor core — the other centrepiece, and the fallback if the head
        # could not be built. There is no third path: the old face.png branch
        # was unreachable (no such file ships) and the bare orb it fell through
        # to is what this replaces.
        elif self._spatial_core is None or not self._spatial_core.isVisible():
            _band_t = 12.0
            _band_h = max(60.0, _sy_status - 12.0 - _band_t)
            _r = min(W * 0.46, _band_h / 2.0)
            self._paint_core(p, cx, _band_t + _band_h / 2.0, _r, W, _band_h)

        p.setOpacity(1)
        # status text
        sy = _sy_status
        if self.muted:
            txt, col = '⊘  MICROFONE DESLIGADO',     qcol(C.MUTED_C)
        elif self.speaking:
            txt, col = '●  FALANDO',  qcol(C.ACC)
        elif self.state == "THINKING":
            sym = "◈" if self._blink else "◇"
            txt, col = f"{sym}  ANALISANDO",   qcol(C.ACC2)
        elif self.state == "PROCESSING":
            sym = "▷" if self._blink else "▶"
            txt, col = f"{sym}  PROCESSANDO", qcol(C.ACC2)
        elif self.state == "LISTENING":
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  ESCUTANDO",  qcol(C.GREEN)
        else:
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  {STATE_LABELS.get(self.state, self.state)}", qcol(C.PRI)

        p.setPen(QPen(col, 1))
        p.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        p.drawText(QRectF(0, sy, W, 26), Qt.AlignmentFlag.AlignCenter, txt)

        # waveform — reacts to the real audio level (mic while listening,
        # JARVIS's own voice while speaking). Falls back to a gentle idle
        # ripple when there's no sound. _amp_disp is the smoothed 0–1 level.
        wy = sy + 30
        N, bw = 36, 8
        wx0 = (W - N * bw) / 2
        amp = self._amp_disp
        mid = (N - 1) / 2.0
        for i in range(N):
            if self.muted:
                hgt, cl = 2, qcol(C.MUTED_C)
            else:
                env     = (1.0 - abs(i - mid) / mid) ** 0.7      # center-weighted hump
                shimmer = 0.55 + 0.45 * math.sin(self._tick * 0.18 + i * 0.7)
                idle    = 3.0 + 2.0 * math.sin(self._tick * 0.09 + i * 0.6)
                hgt     = int(max(2, min(24, idle + amp * 22.0 * env * shimmer)))
                if amp > 0.05:
                    cl = qcol(C.PRI) if hgt > 12 else qcol(C.PRI_DIM)
                else:
                    cl = qcol(C.BORDER_B)
            p.fillRect(QRectF(wx0 + i * bw, wy + 20 - hgt, bw - 1, hgt), cl)

        p.end()   # end deterministically so the backing store never flushes an active painter

class MetricBar(QWidget):

    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0       # 0–100
        self._text  = "--"
        self.setFixedHeight(38)
        self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        v = max(0.0, min(100.0, pct))
        if v == self._value and text == self._text:
            return          # unchanged — skip the repaint
        self._value = v
        self._text  = text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 4, 4)

        bar_h   = 4
        bar_y   = H - bar_h - 5
        bar_w   = W - 12
        bar_x   = 6
        fill_w  = int(bar_w * self._value / 100)

        p.setBrush(QBrush(qcol(C.BAR_BG)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

        if self._value > 85:
            bar_col = qcol(C.RED)
        elif self._value > 65:
            bar_col = qcol(C.ACC)
        else:
            bar_col = qcol(self._color)

        if fill_w > 0:
            p.setBrush(QBrush(bar_col))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 2, 2)

        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(8, 5, 50, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(bar_col if self._text != "--" else qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, 4, W - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)

        p.end()

class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty('independentTheme',True)
        self.setReadOnly(True)
        # Cap scrollback so an hours-long session can't grow the document
        # without bound — keeps memory flat and every insert cheap. Oldest
        # lines drop off the top automatically.
        self.document().setMaximumBlockCount(600)
        self.setFont(QFont("Consolas", 10))
        from core.auxiliary_theme import SURFACE_STYLE
        self.setStyleSheet(SURFACE_STYLE)
        self._queue: list[str] = []
        self._typing  = False
        self._text    = ""
        self._pos     = 0
        self._tag     = "sys"
        self._ai_name_lc = "jarvis"   # updated when assistant name changes
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        self._queue.append(text)
        if not self._typing:
            self._next()

    def _next(self):
        if not self._queue:
            self._typing = False
            return
        self._typing = True
        self._text   = self._queue.pop(0)
        self._pos    = 0
        tl = self._text.lower()
        _ai_pfx = f"{self._ai_name_lc}:"
        if   tl.startswith(("you:", "você:")):                    self._tag = "you"
        elif tl.startswith(_ai_pfx) or tl.startswith("jarvis:"): self._tag = "ai"
        elif tl.startswith("file:"):                             self._tag = "file"
        elif "err" in tl:                                        self._tag = "err"
        else:                                                    self._tag = "sys"
        self._tmr.start(16)

    def _step(self):
        if self._pos < len(self._text):
            # Hidden history needs no animation; visible bursts must not fall behind speech.
            remaining=len(self._text)-self._pos
            count=remaining if not self.isVisible() else max(4,min(128,remaining//12+len(self._queue)*8))
            ch=self._text[self._pos:self._pos+count]
            cur = self.textCursor()
            fmt = cur.charFormat()
            col = {
                "you":  qcol(C.WHITE),
                "ai":   qcol('#9bdfff'),
                "err":  qcol(C.RED),
                "file": qcol(C.GREEN),
                # SYS lines are the bulk of the log. Amber fought the cyan HUD
                # and, being a fixed status colour rather than a hue-linked one,
                # stayed amber even after the accent picker retinted everything
                # else. TEXT_MED follows the theme and drops the contrast to a
                # level you can read past.
                "sys":  qcol(C.TEXT_MED),
            }.get(self._tag, qcol(C.TEXT))
            fmt.setForeground(QBrush(col))
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText(ch, fmt)
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            self._pos += len(ch)
        if self._pos >= len(self._text):
            self._tmr.stop()
            cur = self.textCursor()
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText("\n")
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            QTimer.singleShot(0, self._next)

_FILE_ICONS = {
    "image":   ("🖼", "#00d4ff"), "video":   ("🎬", "#ff6b00"),
    "audio":   ("🎵", "#cc44ff"), "pdf":     ("📄", "#ff4444"),
    "word":    ("📝", "#4488ff"), "excel":   ("📊", "#44bb44"),
    "code":    ("💻", "#ffcc00"), "archive": ("📦", "#ff8844"),
    "pptx":    ("📊", "#ff6622"), "text":    ("📃", "#aaaaaa"),
    "data":    ("🔧", "#88ddff"), "unknown": ("📎", "#888888"),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],         "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],        "audio"),
    **dict.fromkeys(["pdf"],                                                     "pdf"),
    **dict.fromkeys(["doc","docx"],                                              "word"),
    **dict.fromkeys(["xls","xlsx","ods"],                                        "excel"),
    **dict.fromkeys(["ppt","pptx"],                                              "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp",
                     "cs","go","rs","rb","php","swift","kt","sh","sql","lua"],   "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],                   "archive"),
    **dict.fromkeys(["txt","md","rst","log"],                                    "text"),
    **dict.fromkeys(["csv","tsv","json","xml"],                                  "data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"


class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(100)
        self._current_file: str | None = None
        self._hovering  = False
        self._drag_over = False
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._canvas = _DropCanvas(self)
        layout.addWidget(self._canvas)

    def _animate(self):
        # The marching-ants dashed border is only meaningful while the user is
        # hovering or dragging a file over the zone. When idle, skip the repaint
        # entirely instead of redrawing the whole zone 25×/s forever — that idle
        # repaint held the GIL and stole time from the audio/response threads.
        if not (self._hovering or self._drag_over):
            return
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self._canvas.update()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_over = True; self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()

    def dropEvent(self, e: QDropEvent):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._browse()

    def enterEvent(self, e):
        self._hovering = True; self._canvas.update()

    def leaveEvent(self, e):
        self._hovering = False; self._canvas.update()

    def current_file(self) -> str | None:
        return self._current_file

    def clear_file(self):
        self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Selecionar arquivo para JARVIS', str(Path.home()),
            "Todos os arquivos (*.*);;"
            "Imagens (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documentos (*.pdf *.docx *.txt *.md *.pptx);;"
            "Dados (*.csv *.xlsx *.json *.xml);;"
            "Código (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Áudio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Vídeo (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Arquivos compactados (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        self._canvas.update()
        self.file_selected.emit(path)


class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone)
        self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z    = self._z
        W, H = self.width(), self.height()
        pad  = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        bg_col = qcol("#001a24" if z._drag_over else ("#001218" if z._hovering else C.PANEL))
        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   border_col = qcol(C.GREEN, 200)
        elif z._drag_over:    border_col = qcol(C.PRI, 230)
        elif z._hovering:     border_col = qcol(C.BORDER_B, 200)
        else:                 border_col = qcol(C.BORDER, 160)

        pen = QPen(border_col, 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   self._paint_file(p, W, H)
        elif z._drag_over:    self._paint_drag_over(p, W, H)
        else:                 self._paint_idle(p, W, H, z._hovering)

        p.end()

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = qcol(C.PRI_DIM if not hover else C.PRI)
        p.setPen(QPen(col, 2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 14), QPointF(cx, cy + 4))
        p.drawLine(QPointF(cx - 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx + 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx - 14, cy + 4), QPointF(cx + 14, cy + 4))
        p.setFont(QFont("Courier New", 8))
        p.setPen(QPen(qcol(C.PRI_DIM if not hover else C.TEXT), 1))
        p.drawText(QRectF(0, cy + 8, W, 16), Qt.AlignmentFlag.AlignCenter,
                   'Solte um arquivo ou clique aqui')
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol("#1a4a5a"), 1))
        p.drawText(QRectF(0, cy + 24, W, 14), Qt.AlignmentFlag.AlignCenter,
                   'Imagens · Vídeo · Áudio · PDF · Documentos · Código · Dados')

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(QFont("Courier New", 20))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy - 24, W, 32), Qt.AlignmentFlag.AlignCenter, "⬇")
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter, 'Solte para carregar')

    def _paint_file(self, p, W, H):
        path = Path(self._z._current_file)
        cat  = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size)
        ext_str  = path.suffix.upper().lstrip(".") or "FILE"

        block_x, block_w = 10, 60
        p.setFont(QFont("Segoe UI Emoji", 22) if _OS == "Windows" else QFont("Arial", 22))
        p.setPen(QPen(qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)

        tx = block_x + block_w + 6
        tw = W - tx - 38

        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE), 1))
        name = path.name if len(path.name) <= 34 else path.name[:31] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{ext_str}  ·  {size_str}")

        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(qcol("#1e5c6a"), 1))
        par = str(path.parent)
        if len(par) > 42: par = "…" + par[-41:]
        p.drawText(QRectF(tx, H * 0.18 + 34, tw, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, par)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED, 180), 1))
        p.drawText(QRectF(W - 34, 0, 28, H), Qt.AlignmentFlag.AlignCenter, "✕")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width() - 34:
            z.clear_file()
        else:
            z.mousePressEvent(e)


class _FuiOverlay(HudGlassFrame):
    def showEvent(self,event):
        from core.auxiliary_theme import apply_auxiliary_theme
        apply_auxiliary_theme(self)
        self.set_motion_reduced(_read_full_config().get('reduce_motion',False))
        super().showEvent(event)


class _CameraPreview(_FuiOverlay):
    """Floating overlay that briefly shows what the camera captured."""

    _W, _H = 244, 188

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            _CameraPreview {{
                background: rgba(0, 6, 10, 242);
                border: 1px solid {C.PRI};
                border-radius: 6px;
            }}
        """)
        self.setFixedWidth(self._W)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 5, 6, 6)
        lay.setSpacing(4)

        hdr = QHBoxLayout()
        title = QLabel('◈  ENTRADA VISUAL')
        title.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(16, 16)
        close_btn.setFont(QFont("Courier New", 8))
        close_btn.setStyleSheet(
            f"color: {C.TEXT_DIM}; background: transparent; border: none;"
        )
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.hide)
        hdr.addWidget(close_btn)
        lay.addLayout(hdr)

        self._img_lbl = QLabel()
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setStyleSheet("background: transparent;")
        lay.addWidget(self._img_lbl)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        self.hide()

    def show_frame(self, img_bytes: bytes) -> None:
        px = QPixmap()
        px.loadFromData(img_bytes)
        if not px.isNull():
            max_w = self._W - 12
            scaled = px.scaled(
                max_w, 160,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._img_lbl.setPixmap(scaled)
            self._img_lbl.setFixedSize(scaled.width(), scaled.height())
            self.adjustSize()
        self.show()
        self.raise_()
        self._timer.start(6_000)   # auto-dismiss after 6 s


class SetupOverlay(_FuiOverlay):
    done = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: transparent;
                border: 0;
            }}
        """)

        detected = {"darwin": "mac", "windows": "windows"}.get(
            _OS.lower(), "linux"
        )
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 22, 30, 22)
        layout.setSpacing(8)

        def _lbl(txt, font_size=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Segoe UI", font_size,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl('DIEF JARVIS', 18, True, color='#edfaff'))
        layout.addWidget(_lbl('Configure o DIEF JARVIS para começar.', 9, color='#a4c2cd'))
        layout.addSpacing(6)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl('CHAVE DE API DO GEMINI', 8, color='#84e5f0',
                               align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(QFont("Segoe UI", 10))
        self._key_input.setFixedHeight(38)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: #0b1a22; color: #edfaff;
                border: 1px solid #315765; border-radius: 5px; padding: 6px 10px;
            }}
            QLineEdit:focus {{ border: 1px solid #53e1ef; background: #10242c; }}
        """)
        layout.addWidget(self._key_input)
        layout.addSpacing(12)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl('SISTEMA OPERACIONAL', 8, color='#84e5f0',
                               align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Detectado: {det_name}", 8, color='#83d7cf',
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows","Windows"),("mac","macOS"),("linux","Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(detected)
        layout.addSpacing(12)

        init_btn = QPushButton('Iniciar DIEF JARVIS')
        init_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        init_btn.setFixedHeight(36)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: #54242e; color: #ffffff;
                border: 1px solid #ff5964; border-radius: 5px;
            }}
            QPushButton:hover {{
                background: #70303a; border: 1px solid #ff9b9f;
            }}
            QPushButton:focus {{ border: 2px solid #83d7cf; }}
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)
        self.save_status=QLabel();self.save_status.setWordWrap(True)
        self.save_status.setTextFormat(Qt.TextFormat.PlainText)
        self.save_status.setStyleSheet('color:#ffaaaa;background:transparent;')
        self.save_status.hide();layout.addWidget(self.save_status)

    def _sel(self, key: str):
        self._sel_os = key
        for name,button in self._os_btns.items():
            button.setCheckable(True);button.setChecked(name==key);button.setStyleSheet('')

    def paintEvent(self, event):
        super().paintEvent(event)

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._key_input.styleSheet() +
                f" QLineEdit {{ border: 1px solid {C.RED}; }}"
            )
            return
        self.done.emit(key, self._sel_os)


class HueWheel(QWidget):
    """
    Circular colour picker. The user drags the handle (small white circle)
    around the wheel to choose from ALL hues. The filled circle in the centre
    is a live preview of the selected colour.
    """

    hue_picked    = pyqtSignal(str)   # while dragging (live)
    hue_committed = pyqtSignal(str)   # when the handle is released

    _RING = 16   # ring thickness (px)

    def __init__(self, initial_hex: str = DEFAULT_UI_COLOR, parent=None):
        super().__init__(parent)
        self.setFixedSize(148, 148)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hue  = 0.53
        self._drag = False
        self.set_color(initial_hex)

    # ── API ──────────────────────────────────────────────────────────────────
    def color(self) -> str:
        return QColor.fromHsvF(self._hue, 1.0, 1.0).name()

    def set_color(self, hex_str: str):
        c = QColor((hex_str or "").strip())
        if c.isValid() and c.hsvHueF() >= 0:
            self._hue = c.hsvHueF()
            self.update()

    # ── geometry helpers ─────────────────────────────────────────────────────
    def _ring_rect(self) -> QRectF:
        m = self._RING / 2 + 3
        return QRectF(self.rect()).adjusted(m, m, -m, -m)

    def _hue_from_pos(self, pos: QPointF) -> float:
        c  = QRectF(self.rect()).center()
        dx = pos.x() - c.x()
        dy = c.y() - pos.y()          # screen y goes down — flip to math axis
        ang = math.atan2(dy, dx)      # [-π, π], counter-clockwise
        return (ang / (2 * math.pi)) % 1.0

    # ── drawing ──────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect   = self._ring_rect()
        center = rect.center()

        grad = QConicalGradient(center, 0)
        for i in range(0, 361, 20):
            grad.setColorAt(i / 360.0, QColor.fromHsvF((i % 360) / 360.0, 1.0, 1.0))
        p.setPen(QPen(QBrush(grad), self._RING))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)

        # centre preview circle
        preview = QColor.fromHsvF(self._hue, 1.0, 1.0)
        inner   = rect.adjusted(30, 30, -30, -30)
        p.setPen(QPen(qcol(C.BORDER_B), 1))
        p.setBrush(QBrush(preview))
        p.drawEllipse(inner)

        # draggable handle
        r   = rect.width() / 2
        ang = self._hue * 2 * math.pi
        hx  = center.x() + r * math.cos(ang)
        hy  = center.y() - r * math.sin(ang)
        p.setPen(QPen(QColor("#00060a"), 2))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(QPointF(hx, hy), 7.5, 7.5)
        p.end()

    # ── fare ─────────────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        self._drag = True
        self._hue  = self._hue_from_pos(e.position())
        self.update()
        self.hue_picked.emit(self.color())

    def mouseMoveEvent(self, e):
        if self._drag:
            self._hue = self._hue_from_pos(e.position())
            self.update()
            self.hue_picked.emit(self.color())

    def mouseReleaseEvent(self, e):
        if self._drag:
            self._drag = False
            self.hue_committed.emit(self.color())


class CustomizeOverlay(_FuiOverlay):
    """Floating overlay — change assistant name, user name, UI colour and voice."""

    saved = pyqtSignal(str, str, str, str)   # assistant_name, user_name, ui_color, voice
    _OW, _OH = 400, 588

    def __init__(self, assistant_name="DIEF JARVIS", user_name="",
                 ui_color=DEFAULT_UI_COLOR, voice="", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            CustomizeOverlay {{
                background: transparent;
                border: 0;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(8)

        def _lbl(txt, fs=9, bold=False, color=C.PRI, align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt); w.setAlignment(align)
            w.setFont(QFont("Courier New", fs,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        _fs = (f"QLineEdit {{ background: #000d12; color: {C.TEXT}; "
               f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px; }}"
               f"QLineEdit:focus {{ border: 1px solid {C.PRI}; }}")

        lay.addWidget(_lbl('⚙  PERSONALIZAR', 12, True))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        lay.addWidget(_lbl('NOME DO ASSISTENTE', 8, color=C.TEXT_DIM,
                            align=Qt.AlignmentFlag.AlignLeft))
        self._name_input = QLineEdit(assistant_name)
        self._name_input.setFont(QFont("Courier New", 10))
        self._name_input.setFixedHeight(32)
        self._name_input.setStyleSheet(_fs)
        lay.addWidget(self._name_input)

        lay.addSpacing(4)
        lay.addWidget(_lbl('SEU NOME (opcional)', 8,
                            color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._user_input = QLineEdit(user_name)
        self._user_input.setPlaceholderText('Ex.: Tony (opcional)')
        self._user_input.setFont(QFont("Courier New", 10))
        self._user_input.setFixedHeight(32)
        self._user_input.setStyleSheet(_fs)
        lay.addWidget(self._user_input)

        # ── Assistant voice — Gemini prebuilt voices ─────────────────────────
        # Names are language-neutral proper nouns, so the row reads the same in
        # every locale. Selecting one and applying rebuilds the Live session.
        from memory.config_manager import AVAILABLE_VOICES, DEFAULT_VOICE
        lay.addSpacing(4)
        lay.addWidget(_lbl('VOZ DO ASSISTENTE', 8, color=C.TEXT_DIM,
                            align=Qt.AlignmentFlag.AlignLeft))
        self._sel_voice   = (voice or DEFAULT_VOICE)
        if self._sel_voice not in AVAILABLE_VOICES:
            self._sel_voice = DEFAULT_VOICE
        self._voice_btns: dict[str, QPushButton] = {}
        voice_row = QHBoxLayout(); voice_row.setSpacing(4)
        for _v in AVAILABLE_VOICES:
            b = QPushButton(_v)
            b.setCheckable(True)
            b.setFixedHeight(28)
            b.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, name=_v: self._on_voice_pick(name))
            self._voice_btns[_v] = b
            voice_row.addWidget(b)
        lay.addLayout(voice_row)
        self._refresh_voice_btns()

        # ── UI colour — colour wheel ─────────────────────────────────────────
        lay.addSpacing(4)
        clr_hdr = QHBoxLayout()
        clr_hdr.addWidget(_lbl('COR DA INTERFACE', 8,
                               color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        clr_hdr.addStretch()
        df_btn = QPushButton('PADRÃO')
        df_btn.setFixedSize(64, 20)
        df_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        df_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        df_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        df_btn.clicked.connect(lambda: self._set_color(DEFAULT_UI_COLOR))
        clr_hdr.addWidget(df_btn)
        lay.addLayout(clr_hdr)

        self._initial_color = (ui_color or DEFAULT_UI_COLOR).strip().lower()
        self._sel_color     = self._initial_color
        self.on_preview     = None   # callable(hex) — live preview; MainWindow wires it

        self._wheel = HueWheel(self._sel_color)
        wheel_row = QHBoxLayout()
        wheel_row.addStretch(); wheel_row.addWidget(self._wheel); wheel_row.addStretch()
        lay.addLayout(wheel_row)
        self._wheel.hue_picked.connect(self._on_wheel_pick)
        self._wheel.hue_committed.connect(self._on_wheel_commit)

        self._hex_input = QLineEdit(self._sel_color)
        self._hex_input.setPlaceholderText('#00d4ff (cor hexadecimal)')
        self._hex_input.setFont(QFont("Courier New", 10))
        self._hex_input.setFixedHeight(28)
        self._hex_input.setStyleSheet(_fs)
        self._hex_input.textEdited.connect(self._on_hex_edited)
        lay.addWidget(self._hex_input)

        lay.addSpacing(6)
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)

        save_btn = QPushButton('▸  APLICAR ALTERAÇÕES')
        save_btn.setFixedHeight(34)
        save_btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton('CANCELAR')
        cancel_btn.setFixedHeight(34)
        cancel_btn.setFont(QFont("Courier New", 9))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(cancel_btn)
        lay.addLayout(btn_row)

    # ── voice selection ──────────────────────────────────────────────────────
    def _on_voice_pick(self, name: str):
        self._sel_voice = name
        self._refresh_voice_btns()

    def _refresh_voice_btns(self):
        for name,button in self._voice_btns.items():
            button.setChecked(name==self._sel_voice);button.setStyleSheet('')

    # ── colour flow ──────────────────────────────────────────────────────────
    def _set_color(self, hx: str, update_wheel: bool = True, preview: bool = True):
        """Updates the selected colour; hex box + wheel stay in sync, theme is live-previewed."""
        self._sel_color = hx.strip().lower()
        self._hex_input.blockSignals(True)
        self._hex_input.setText(self._sel_color)
        self._hex_input.blockSignals(False)
        if update_wheel:
            self._wheel.set_color(self._sel_color)
        if preview and self.on_preview:
            self.on_preview(self._sel_color)

    def _on_wheel_pick(self, hx: str):
        # While dragging: update the hex box, don't apply the theme yet
        self._sel_color = hx
        self._hex_input.blockSignals(True)
        self._hex_input.setText(hx)
        self._hex_input.blockSignals(False)

    def _on_wheel_commit(self, hx: str):
        # Handle released → live-preview the whole interface
        self._set_color(hx, update_wheel=False)

    def _on_hex_edited(self, text: str):
        t = text.strip().lower()
        if t.startswith("#") and len(t) == 7:
            try:
                int(t[1:], 16)
            except ValueError:
                return
            self._set_color(t, update_wheel=True, preview=True)

    def _cancel(self):
        # If a preview was applied, revert to the colour from launch
        if self.on_preview and self._sel_color != self._initial_color:
            self.on_preview(self._initial_color)
        self.hide()

    def _save(self):
        name = self._name_input.text().strip() or "JARVIS"
        user = self._user_input.text().strip()
        self.saved.emit(name, user, self._sel_color or DEFAULT_UI_COLOR, self._sel_voice)
        self.hide()


class PluginManagerOverlay(_FuiOverlay):
    """Floating overlay — lists discovered plugins with per-plugin ON/OFF toggles."""

    _OW = 420

    def __init__(self, plugins: list[dict], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            PluginManagerOverlay {{
                background: transparent;
                border: 0;
            }}
        """)
        self.setFixedWidth(self._OW)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(6)

        hdr = QLabel('GERENCIAR PLUGINS')
        hdr.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        lay.addWidget(hdr)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        if not plugins:
            empty = QLabel('Nenhum plugin em /plugins.')
            empty.setFont(QFont("Courier New", 8))
            empty.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lay.addWidget(empty)

        for p in plugins:
            lay.addLayout(self._build_row(p))

        lay.addSpacing(4)
        close_btn = QPushButton('FECHAR')
        close_btn.setFixedHeight(30)
        close_btn.setFont(QFont("Courier New", 9))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self.hide)
        lay.addWidget(close_btn)
        self.adjustSize()

    def _build_row(self, p: dict) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(6)

        from core.locale_pt_br import tool_label
        label_text = tool_label(p["name"]) if p["valid"] else f"{tool_label(p['name'])}  (⚠ {p['file']})"
        lbl = QLabel(label_text)
        lbl.setFont(QFont("Courier New", 8))
        lbl.setStyleSheet(f"color: {C.TEXT if p['valid'] else C.TEXT_DIM}; background: transparent;")
        lbl.setToolTip(p["description"] if p["valid"] else p["error"])
        lbl.setWordWrap(False)
        row.addWidget(lbl, stretch=1)

        btn = QPushButton()
        btn.setFixedSize(72, 24)
        btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        if not p["valid"]:
            btn.setText('ERRO')
            btn.setEnabled(False)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER}; border-radius: 3px;
                }}
            """)
        else:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._style_toggle(btn, p["enabled"])
            btn.clicked.connect(lambda _, name=p["name"], b=btn: self._toggle(name, b))
        row.addWidget(btn)
        return row

    def _style_toggle(self, btn: QPushButton, enabled: bool):
        btn.setText('SIM' if enabled else 'NÃO')
        btn.setCheckable(True);btn.setChecked(enabled);btn.setStyleSheet('')

    def _toggle(self, name: str, btn: QPushButton):
        from memory.config_manager import get_plugin_enabled, save_plugin_enabled
        new_val = not get_plugin_enabled(name)
        save_plugin_enabled(name, new_val)
        self._style_toggle(btn, new_val)


class _HudOverlay(_FuiOverlay):
    """Base for the floating panels placed by hand over the HUD.

    They are children of the central widget but sit in no layout, so Qt never
    invalidates the region they occupy when they hide or shrink: the HUD keeps
    painting around them and their last frame stays on screen as a ghost. Any
    overlay positioned with _centre_overlay needs this."""

    def hideEvent(self, e):
        p = self.parentWidget()
        if p is not None:
            # Repaint exactly what we were covering, before we stop covering it.
            p.update(self.geometry())
        super().hideEvent(e)

    def closeEvent(self, e):
        p = self.parentWidget()
        if p is not None:
            p.update(self.geometry())
        super().closeEvent(e)


class ConfirmBanner(_HudOverlay):
    """The gate in front of an action that cannot be taken back.

    The old confirmation was a tool parameter the model filled in itself, which
    means it confirmed its own shutdown requests. This is the interface asking,
    and the answer travels from a human finger to core/confirm.py without the
    model in the loop. Nothing blocks while it is up: the assistant keeps
    talking, so this costs no latency — unlike the old gate, which spent two
    tool round trips on every power command."""

    answered = pyqtSignal(bool)
    _OW = 430

    def __init__(self, title: str, detail: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ConfirmBanner {{
                background: transparent;
                border: 0;
            }}
        """)
        self.setFixedWidth(self._OW)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(8)

        hdr = QLabel('CONFIRMAR')
        hdr.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        hdr.setStyleSheet('color: #ff7180; background: transparent;')
        lay.addWidget(hdr)

        ttl = QLabel(title)
        ttl.setWordWrap(True)
        ttl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        ttl.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        lay.addWidget(ttl)

        if detail:
            dtl = QLabel(detail)
            dtl.setWordWrap(True)
            dtl.setFont(QFont("Segoe UI", 9))
            dtl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            lay.addWidget(dtl)

        row = QHBoxLayout(); row.setSpacing(8)

        yes = QPushButton('CONFIRMAR')
        yes.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        yes.setFixedHeight(32)
        yes.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        yes.setCursor(Qt.CursorShape.PointingHandCursor)
        yes.setStyleSheet(f"""
            QPushButton {{ background: #45212b; color: #ffffff;
                border: 1px solid #ff5964; border-radius: 3px; }}
            QPushButton:hover {{ background: #70303a; }}
        """)
        yes.clicked.connect(lambda: self.answered.emit(True))
        row.addWidget(yes)

        no = QPushButton('CANCELAR')
        no.setFixedHeight(32)
        no.setFont(QFont("Courier New", 9))
        no.setCursor(Qt.CursorShape.PointingHandCursor)
        no.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        no.clicked.connect(lambda: self.answered.emit(False))
        row.addWidget(no)
        lay.addLayout(row)

        # Default focus on CANCEL: if someone hits Enter without reading, the
        # safe answer wins.
        no.setDefault(True)
        no.setFocus()


class AudioDeviceOverlay(_HudOverlay):
    """Choose which microphone JARVIS listens to and which speakers it uses.

    Both audio streams used to open with no `device=` at all, so they always
    took the OS default — which on Windows moves by itself the moment a headset
    is plugged in. 'JARVIS can't hear me' is usually 'JARVIS is listening to the
    webcam'."""

    picked = pyqtSignal()      # emitted after Apply, when something changed
    _OW = 460

    def __init__(self, parent=None):
        super().__init__(parent)
        from core.audio_devices import list_devices, DEFAULT_LABEL
        from memory.config_manager import get_input_device, get_output_device

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            AudioDeviceOverlay {{
                background: transparent;
                border: 0;
            }}
        """)
        self.setFixedWidth(self._OW)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(6)

        hdr = QLabel('ÁUDIO')
        hdr.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        lay.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        _combo_css = (
            f"QComboBox {{ background: #000d12; color: {C.TEXT}; "
            f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px; }}"
            f"QComboBox:hover {{ border-color: {C.BORDER_B}; }}"
            f"QComboBox QAbstractItemView {{ background: #000d12; color: {C.TEXT}; "
            f"selection-background-color: {C.PRI_GHO}; border: 1px solid {C.BORDER}; }}"
        )

        def _row(label: str, kind: str, current: str) -> QComboBox:
            cap = QLabel(label)
            cap.setFont(QFont("Courier New", 8))
            cap.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lay.addWidget(cap)

            box = QComboBox()
            box.setFont(QFont("Courier New", 9))
            box.setFixedHeight(30)
            box.setStyleSheet(_combo_css)
            # The list is served from a cache warmed on a background thread at
            # startup, so opening this panel never blocks the Qt thread on the
            # host audio API.
            box.addItem(DEFAULT_LABEL, "")
            for name in list_devices(kind):
                box.addItem(name, name)
            idx = box.findData(current) if current else 0
            box.setCurrentIndex(idx if idx >= 0 else 0)
            if current and idx < 0:
                # Saved device is not plugged in right now. Show it rather than
                # silently resetting the user's choice to default.
                box.addItem(f"{current}  (desconectado)", current)
                box.setCurrentIndex(box.count() - 1)
            lay.addWidget(box)
            return box

        self._in_box  = _row('MICROFONE',
                             "input", get_input_device())
        lay.addSpacing(4)
        self._out_box = _row('SAÍDA DE ÁUDIO',
                             "output", get_output_device())

        note = QLabel('Ao aplicar, a sessão reconecta sem perder a conversa.')
        note.setWordWrap(True)
        note.setFont(QFont("Courier New", 7))
        note.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addSpacing(6)
        lay.addWidget(note)

        row = QHBoxLayout(); row.setSpacing(8)
        ok = QPushButton('▸  APLICAR')
        ok.setFixedHeight(32)
        ok.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px; }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
        """)
        ok.clicked.connect(self._apply)
        row.addWidget(ok)

        cancel = QPushButton('FECHAR')
        cancel.setFixedHeight(32)
        cancel.setFont(QFont("Courier New", 9))
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        cancel.clicked.connect(self.hide)
        row.addWidget(cancel)
        lay.addLayout(row)

    def _apply(self):
        from memory.config_manager import (
            get_input_device, get_output_device,
            save_input_device, save_output_device,
        )
        new_in  = self._in_box.currentData()  or ""
        new_out = self._out_box.currentData() or ""
        changed = (new_in != get_input_device()) or (new_out != get_output_device())
        save_input_device(new_in)
        save_output_device(new_out)
        self.hide()
        # Only rebuild the session if something actually moved — a no-op Apply
        # should not cost a reconnect.
        if changed:
            self.picked.emit()


class MemoryOverlay(_HudOverlay):
    """Everything JARVIS has stored about you, and when it learned it.

    Memory used to be a 2200-character store that deleted its oldest entries
    when full and mentioned it only on stdout. The cap is gone; this panel is
    the other half of that change — a memory you cannot inspect is a memory you
    cannot trust, and 'delete' has to be something the person can do."""

    _OW = 520

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            MemoryOverlay {{
                background: transparent;
                border: 0;
            }}
        """)
        self.setFixedWidth(self._OW)

        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(20, 16, 20, 16)
        self._lay.setSpacing(5)
        self._rebuild()

    def _clear_layout(self):
        """Take every item out of the layout and detach it from the widget tree
        in this call.

        deleteLater() on its own is not enough: it queues destruction for the
        next event-loop pass, and until then the old rows are still children of
        this widget and still paint — which is what drew half of the previous
        panel over the new one. setParent(None) removes them from the tree now;
        deleteLater() then frees them safely."""
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                # hide() stops it painting in this frame; deleteLater() frees it
                # safely afterwards. setParent(None) would also stop the paint,
                # but it turns the widget into a top-level window for the moment
                # between the two calls, which is not something to leave lying
                # around inside a click handler.
                w.hide()
                w.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                while sub.count():
                    si = sub.takeAt(0)
                    sw = si.widget()
                    if sw is not None:
                        sw.hide()
                        sw.deleteLater()
                sub.deleteLater()

    def _settle(self, before):
        """Size the panel to its content, re-centre it, and repaint what the old
        size covered.

        The re-size has to happen here rather than at the end of _rebuild
        because Qt has not polished the freshly-created children at that point,
        so the size hint it would read is the empty-layout one. Measured: a
        first adjustSize() returned 32 px for a panel whose content needed 155,
        and a second call — after the same widgets had been through the event
        loop — returned 155. So this runs twice: once now, once on the next
        turn, from _rebuild.

        The re-centre and the repaint are needed because the overlay is placed
        by hand and is in no layout: shrinking it leaves it off-centre and
        leaves its former pixels on screen, since nothing tells the parent that
        region changed. The repaint has to cover the union of the old and new
        rectangles."""
        self._lay.invalidate()
        self._lay.activate()
        self.updateGeometry()
        self.adjustSize()

        p = self.parentWidget()
        if p is None:
            self.update()
            return
        self.move(max(0, (p.width()  - self.width())  // 2),
                  max(0, (p.height() - self.height()) // 2))
        p.update(before.united(self.geometry()))
        self.update()

    def _rebuild(self):
        before = self.geometry()
        self._clear_layout()

        from memory.memory_manager import all_entries_for_ui

        hdr = QLabel('🧠  MEMÓRIAS DO JARVIS')
        hdr.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._lay.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        self._lay.addWidget(sep)

        rows = all_entries_for_ui()

        cap = QLabel(f"{len(rows)} fatos guardados, dos mais recentes aos antigos. "
                     "Armazenados neste computador, no perfil local. Trechos relevantes "
                     "podem ser enviados à API configurada como contexto da conversa.")
        cap.setWordWrap(True)
        cap.setFont(QFont("Courier New", 7))
        cap.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._lay.addWidget(cap)

        if not rows:
            empty = QLabel('Nenhuma memória ainda.')
            empty.setFont(QFont("Courier New", 9))
            empty.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            self._lay.addWidget(empty)
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFixedHeight(min(420, 34 * len(rows) + 10))
            scroll.setStyleSheet(
                f"QScrollArea {{ border: 1px solid {C.BORDER}; border-radius: 3px; "
                f"background: transparent; }}"
            )
            inner = QWidget()
            ilay  = QVBoxLayout(inner)
            ilay.setContentsMargins(6, 6, 6, 6)
            ilay.setSpacing(3)

            for r in rows:
                line = QHBoxLayout(); line.setSpacing(6)
                txt = QLabel(f"<b>{r['key'].replace('_', ' ')}</b> "
                             f"<span style='color:{C.TEXT_MED}'>— {r['value']}</span>")
                txt.setWordWrap(True)
                txt.setFont(QFont("Courier New", 8))
                txt.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
                line.addWidget(txt, 1)

                meta = QLabel(f"{r['category'][:4]} · {r['updated'] or '—'}")
                meta.setFont(QFont("Courier New", 7))
                meta.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
                line.addWidget(meta)

                rm = QPushButton("✕")
                rm.setFixedSize(20, 20)
                rm.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
                rm.setCursor(Qt.CursorShape.PointingHandCursor)
                rm.setToolTip('Esquecer esta memória')
                rm.setStyleSheet(f"""
                    QPushButton {{ background: transparent; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 3px; }}
                    QPushButton:hover {{ color: {C.RED}; border-color: {C.RED}; }}
                """)
                rm.clicked.connect(
                    lambda _=False, c=r["category"], k=r["key"]: self._forget(c, k))
                line.addWidget(rm)

                holder = QWidget()
                holder.setLayout(line)
                ilay.addWidget(holder)

            ilay.addStretch()
            scroll.setWidget(inner)
            self._lay.addWidget(scroll)

        close = QPushButton('FECHAR')
        close.setFixedHeight(30)
        close.setFont(QFont("Courier New", 9))
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close.clicked.connect(self.hide)
        self._lay.addWidget(close)

        self._settle(before)
        # …and again once Qt has polished the new children, because the size
        # hint is not final until then. Harmless when the first pass already
        # got it right: _settle is idempotent.
        QTimer.singleShot(0, lambda g=before: self._settle(g))

    def _forget(self, category: str, key: str):
        from memory.memory_manager import forget
        forget(key, category)
        # Rebuild on the NEXT event-loop turn, not inside this click handler.
        # The rebuild destroys the very ✕ button that emitted this signal, and
        # Qt is entitled to touch the sender after a slot returns; tearing it
        # down mid-emission is how a widget ends up half-alive on screen.
        QTimer.singleShot(0, self._rebuild)


class ClipboardPanel(_FuiOverlay):
    """Floating panel shown when text is copied — offers quick Jarvis actions."""

    action_requested = pyqtSignal(str)
    _W, _H = 326, 112

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ClipboardPanel {{
                background: transparent;
                border: 0;
            }}
        """)
        self.setFixedWidth(self._W)
        self._clip_text = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 7)
        lay.setSpacing(4)

        hdr = QHBoxLayout(); hdr.setSpacing(4)
        icon_lbl = QLabel('◈  TEXTO COPIADO')
        icon_lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        icon_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent;")
        hdr.addWidget(icon_lbl); hdr.addStretch()
        x_btn = QPushButton("✕")
        x_btn.setFixedSize(16, 16)
        x_btn.setFont(QFont("Courier New", 8))
        x_btn.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.clicked.connect(self.hide)
        hdr.addWidget(x_btn)
        lay.addLayout(hdr)

        self._preview = QLabel()
        self._preview.setFont(QFont("Courier New", 8))
        self._preview.setStyleSheet(f"""
            color: {C.TEXT}; background: {C.PANEL2};
            border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 6px;
        """)
        self._preview.setWordWrap(False)
        self._preview.setFixedHeight(28)
        lay.addWidget(self._preview)

        btn_row = QHBoxLayout(); btn_row.setSpacing(4)
        _bs = (f"QPushButton {{ background: {C.PANEL2}; color: {C.TEXT_MED}; "
               f"border: 1px solid {C.BORDER}; border-radius: 2px; }}"
               f"QPushButton:hover {{ color: {C.PRI}; border-color: {C.BORDER_B}; }}")
        for label, cmd_fmt in [
            ('TRADUZIR', 'Traduza este texto para português do Brasil: {text}'),
            ('RESUMIR', 'Resuma em português do Brasil: {text}'),
            ('EXPLICAR',   'Explique em português do Brasil: {text}'),
            ("CORRIGIR", "Corrija a gramática e a ortografia: {text}"),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(22)
            b.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(_bs)
            b.clicked.connect(lambda _, c=cmd_fmt: self._trigger(c))
            btn_row.addWidget(b)
        lay.addLayout(btn_row)

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.hide)
        self.hide()

    def _trigger(self, cmd_fmt: str):
        if self._clip_text:
            self.action_requested.emit(cmd_fmt.format(text=self._clip_text[:800]))
        self.hide()

    def show_clipboard(self, text: str):
        self._clip_text = text
        preview = text[:58].replace('\n', ' ')
        if len(text) > 58:
            preview += "…"
        self._preview.setText(f'"{preview}"')
        self.show(); self.raise_()
        self._dismiss_timer.start(8000)


class PluginSettingsOverlay(_FuiOverlay):
    """Floating overlay — renders per-plugin settings forms.

    Fully generic: it iterates the settings schemas a plugin declared via its
    PLUGIN_SETTINGS constant (delivered by PluginRegistry.settings_schemas) and
    builds a form for each. It knows NOTHING about any specific plugin, so the
    core stays clean and plugins remain pure drop-in — install a plugin that
    declares fields (e.g. the 3D-printer suite) and its section appears here;
    install none and this panel simply says there's nothing to configure.
    """

    _test_done = pyqtSignal(str, bool, str)   # namespace, ok, message
    _OW = 460

    def __init__(self, sections: list[dict], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            PluginSettingsOverlay {{
                background: transparent;
                border: 0;
            }}
        """)
        self._sections = sections or []
        self._widgets: dict[tuple, object] = {}    # (namespace, key) -> input widget
        self._types:   dict[tuple, str]    = {}     # (namespace, key) -> field type
        self._status_labels: dict[str, QLabel] = {} # namespace -> status QLabel
        self._running_actions=set()
        self._action_buttons={}
        self._test_done.connect(self._on_test_done)

        self._fs = (f"QLineEdit {{ background: #000d12; color: {C.TEXT}; "
                    f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px; }}"
                    f"QLineEdit:focus {{ border: 1px solid {C.PRI}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 16)
        root.setSpacing(8)

        root.addWidget(self._lbl('Configuração da conexão', 12, True))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        root.addWidget(sep)

        if not self._sections:
            root.addWidget(self._lbl(
                'Esta ferramenta não possui campos de configuração.', 9, color=C.TEXT_DIM))
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet("QScrollArea { background: transparent; }")
            inner = QWidget()
            inner.setStyleSheet("background: transparent;")
            form = QVBoxLayout(inner)
            form.setContentsMargins(0, 0, 6, 0)
            form.setSpacing(6)
            for sec in self._sections:
                self._build_section(form, sec)
            form.addStretch(1)
            scroll.setWidget(inner)
            root.addWidget(scroll, 1)

        # ── bottom buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        if self._sections:
            save_btn = QPushButton('Salvar configuração')
            save_btn.setFixedHeight(34)
            save_btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {C.PRI};
                    border: 1px solid {C.PRI_DIM}; border-radius: 3px; }}
                QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
            """)
            save_btn.clicked.connect(self._save_all)
            btn_row.addWidget(save_btn)

        close_btn = QPushButton('Voltar')
        close_btn.setFixedHeight(34)
        close_btn.setFont(QFont("Courier New", 9))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self.hide)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    # ── helpers ───────────────────────────────────────────────────────────────
    def _lbl(self, txt, fs=9, bold=False, color=C.PRI,
             align=Qt.AlignmentFlag.AlignLeft):
        w = QLabel(txt); w.setAlignment(align); w.setWordWrap(True)
        w.setFont(QFont("Courier New", fs,
                        QFont.Weight.Bold if bold else QFont.Weight.Normal))
        w.setStyleSheet(f"color: {color}; background: transparent;")
        return w

    def _build_section(self, form: QVBoxLayout, sec: dict):
        ns     = sec.get("namespace") or sec.get("plugin") or "plugin"
        title  = sec.get("title") or ns
        fields = sec.get("fields") or []
        values = sec.get("values") or {}

        form.addSpacing(4)
        form.addWidget(self._lbl(title, 10, True, C.PRI))

        for field in fields:
            if not isinstance(field, dict) or not field.get("key"):
                continue
            key   = field["key"]
            ftype = (field.get("type") or "text").lower()
            label = field.get("label") or key
            default = field.get("default")
            stored  = values.get(key, default)
            if field.get('readonly'):stored=default

            form.addWidget(self._lbl(label, 9, color=C.TEXT_DIM))

            if ftype == "choice":
                w = QComboBox()
                w.addItems([str(o) for o in field.get("options", [])])
                w.setFont(QFont("Courier New", 9))
                w.setFixedHeight(30)
                w.setStyleSheet(
                    f"QComboBox {{ background: #000d12; color: {C.TEXT}; "
                    f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 2px 8px; }}"
                    f"QComboBox QAbstractItemView {{ background: #000d12; color: {C.TEXT}; "
                    f"selection-background-color: {C.PRI_GHO}; }}")
                if stored is not None:
                    w.setCurrentText(str(stored))
            elif ftype == "toggle":
                w = QPushButton()
                w.setCheckable(True)
                w.setChecked(bool(stored))
                w.setFixedHeight(28)
                w.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
                w.setCursor(Qt.CursorShape.PointingHandCursor)
                self._style_toggle(w)
                w.toggled.connect(lambda _=False, b=w: self._style_toggle(b))
            else:  # text / password / local file
                w = QLineEdit("" if stored is None else str(stored))
                w.setFont(QFont("Courier New", 10))
                w.setFixedHeight(30)
                w.setStyleSheet(self._fs)
                if field.get("placeholder"):
                    w.setPlaceholderText(str(field["placeholder"]))
                if ftype in ("password","secret"):
                    w.setEchoMode(QLineEdit.EchoMode.Password)
                w.setReadOnly(bool(field.get('readonly')))

            self._widgets[(ns, key)] = w
            self._types[(ns, key)]   = ftype
            if ftype == 'file':
                row=QHBoxLayout();row.setSpacing(6);row.addWidget(w,1)
                browse=QPushButton('Selecionar JSON')
                browse.setToolTip('Selecionar um arquivo de credencial OAuth no computador')
                def choose_file(_=False,target=w):
                    path,_=QFileDialog.getOpenFileName(self,'Selecionar credencial OAuth','','Credenciais Google (*.json);;Todos os arquivos (*)')
                    if path:target.setText(path)
                browse.clicked.connect(choose_file);row.addWidget(browse)
                form.addLayout(row)
            else:
                form.addWidget(w)

        # optional test/connect action button + status line
        setup_url=sec.get('setup_url')
        if isinstance(setup_url,str) and setup_url.startswith('https://'):
            setup=QPushButton(str(sec.get('setup_label') or 'Abrir cadastro do provedor'))
            setup.setToolTip(setup_url)
            def open_setup(checked=False,url=setup_url):
                from PyQt6.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl(url))
            setup.clicked.connect(open_setup)
            form.addWidget(setup)
        action = sec.get("action")
        if isinstance(action, dict) and callable(action.get("run")):
            form.addSpacing(2)
            ab = QPushButton(str(action.get("label") or 'TESTAR'))
            ab.setFixedHeight(30)
            ab.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            ab.setCursor(Qt.CursorShape.PointingHandCursor)
            ab.setStyleSheet(f"""
                QPushButton {{ background: #00091a; color: {C.PRI};
                    border: 1px solid {C.PRI_DIM}; border-radius: 3px; }}
                QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
            """)
            ab.clicked.connect(lambda _=False, n=ns: self._run_action(n))
            self._action_buttons[ns]=ab
            form.addWidget(ab)

        status = self._lbl("", 8, color=C.TEXT_DIM)
        self._status_labels[ns] = status
        form.addWidget(status)

        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {C.BORDER}; margin: 4px 0;")
        form.addWidget(line)

    def _style_toggle(self, btn: QPushButton):
        btn.setText('SIM' if btn.isChecked() else 'NÃO');btn.setStyleSheet('')

    # ── data ──────────────────────────────────────────────────────────────────
    def _gather(self, ns: str) -> dict:
        out = {}
        for (n, key), w in self._widgets.items():
            if n != ns:
                continue
            t = self._types.get((n, key), "text")
            if t == "choice":
                out[key] = w.currentText()
            elif t == "toggle":
                out[key] = w.isChecked()
            else:
                out[key] = w.text().strip()
        return out

    def _save_ns(self, ns: str):
        from memory.config_manager import save_plugin_config
        values=self._gather(ns)
        if ns in ('home_automation','notion_service','github_mcp','context7','deep_research','fish_audio') and values.get('access_token'):
            from core import integration_tokens
            from core.local_data import LOCK,atomic_write
            from memory import config_manager
            token=values['access_token']
            values['access_token']=''
            # Keep the previous connection usable if either durable write fails.
            with LOCK,integration_tokens.LOCK:
                config_manager.prepare_storage()
                path=config_manager.CONFIG_FILE
                previous=path.read_bytes() if path.exists() else None
                save_plugin_config(ns,values)
                try:
                    integration_tokens.write('notion_candidate' if ns=='notion_service' else ns,{'token':token})
                except Exception:
                    if previous is None:path.unlink(missing_ok=True)
                    else:atomic_write(path,previous)
                    raise
            self._widgets[(ns,'access_token')].clear()
            if ns in ('github_mcp','context7','deep_research'):
                from core.extension_suite import reset
                reset(ns)
        else:save_plugin_config(ns, values)
        if ns=='fish_audio':
            owner=self.parentWidget()
            while owner is not None and not hasattr(owner,'on_voice_change'):owner=owner.parentWidget()
            if owner is not None and owner.on_voice_change:owner.on_voice_change()

    def _save_all(self):
        for sec in self._sections:
            ns = sec.get("namespace") or sec.get("plugin")
            if ns:
                try:self._save_ns(ns)
                except Exception as error:
                    self._show_settings_error(ns,error)
                    continue
                lbl = self._status_labels.get(ns)
                if lbl:
                    lbl.setText('Salvo ✓')
                    lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")

    def _run_action(self, ns: str):
        if ns in self._running_actions:
            self._status_labels[ns].setText('Esta conexão já está em andamento. Aguarde a autorização ou o resultado.');return
        sec = next((s for s in self._sections
                    if (s.get("namespace") or s.get("plugin")) == ns), None)
        if not sec:
            return
        run_fn = (sec.get("action") or {}).get("run")
        if not callable(run_fn):
            return
        try:self._save_ns(ns)
        except Exception as error:
            self._show_settings_error(ns,error)
            return
        self._running_actions.add(ns)
        if ns in self._action_buttons:self._action_buttons[ns].setEnabled(False)
        values = self._gather(ns)
        lbl = self._status_labels.get(ns)
        if lbl:
            lbl.setText('Testando…')
            lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")

        def worker():
            try:
                res = run_fn(values)
                if isinstance(res, tuple) and len(res) == 2:
                    ok, msg = bool(res[0]), str(res[1])
                else:
                    ok, msg = bool(res), str(res)
            except Exception as e:
                ok=False
                if ns=='spotify_control':
                    from core.spotify_service import error_details
                    msg=error_details(e)['message']
                elif ns in ('google_drive','google_calendar','gmail_compose'):
                    from core.google_services import error_details
                    msg=error_details(e)['message']
                else:
                    from core.connection_errors import describe
                    msg=describe(e)
            try:self._test_done.emit(ns, ok, msg)
            except RuntimeError:pass

        threading.Thread(target=worker, daemon=True).start()

    def _show_settings_error(self,ns,error):
        from core.connection_errors import describe
        label=self._status_labels.get(ns)
        if label:
            label.setText(describe(error));label.setStyleSheet('color:#ffaaaa;background:transparent;')
        if ns in self._action_buttons:self._action_buttons[ns].setEnabled(ns not in self._running_actions)

    def _on_test_done(self, ns: str, ok: bool, msg: str):
        self._running_actions.discard(ns)
        if ns in self._action_buttons:self._action_buttons[ns].setEnabled(True)
        lbl = self._status_labels.get(ns)
        if not lbl:
            return
        lbl.setText(msg)
        color = C.PRI if ok else "#ff6b6b"
        lbl.setStyleSheet(f"color: {color}; background: transparent;")


class RemoteKeyOverlay(_FuiOverlay):
    """Floating overlay — QR code for instant phone pairing + manual key fallback."""

    closed = pyqtSignal()

    _OW, _OH = 400, 465

    def __init__(self, url: str, key: str, auto_login_url: str = "",
                 manual_url: str = "", expiry_secs: int = 600, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            RemoteKeyOverlay {{
                background: transparent;
                border: 0;
            }}
        """)
        self._expiry          = time.time() + expiry_secs
        self._on_new_key      = None
        self._auto_login_url  = auto_login_url
        self._manual_url      = manual_url or url

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(5)

        def _lbl(txt, fs=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Courier New", fs,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            w.setWordWrap(True)
            return w

        lay.addWidget(_lbl('◈  ACESSO REMOTO', 12, True))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 1px 0;")
        lay.addWidget(sep)

        # ── QR code ───────────────────────────────────────────────────────────
        self._qr_label = QLabel()
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setFixedSize(176, 176)
        self._qr_label.setStyleSheet(
            "background: white; border-radius: 10px; padding: 4px;"
        )
        qr_row = QHBoxLayout()
        qr_row.addStretch()
        qr_row.addWidget(self._qr_label)
        qr_row.addStretch()
        lay.addLayout(qr_row)

        self._update_qr(auto_login_url)

        lay.addWidget(_lbl('Escaneie com o celular para conectar', 8, color=C.TEXT_DIM))

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER}; margin: 1px 0;")
        lay.addWidget(sep2)

        lay.addWidget(_lbl('Ou digite manualmente:', 7, color=C.TEXT_DIM,
                           align=Qt.AlignmentFlag.AlignLeft))

        self._url_lbl = QLabel(self._manual_url)
        self._url_lbl.setFont(QFont("Courier New", 8))
        self._url_lbl.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        self._url_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._url_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._url_lbl)

        self._key_lbl = QLabel(key)
        self._key_lbl.setFont(QFont("Courier New", 28, QFont.Weight.Bold))
        self._key_lbl.setStyleSheet(f"""
            color: {C.ACC};
            background: {C.PANEL2};
            border: 1px solid {C.BORDER_B};
            border-radius: 8px;
            padding: 6px 4px;
            letter-spacing: 10px;
        """)
        self._key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._key_lbl)

        self._timer_lbl = QLabel()
        self._timer_lbl.setFont(QFont("Courier New", 8))
        self._timer_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._timer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._timer_lbl)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        new_btn = QPushButton('NOVA CHAVE')
        new_btn.setFixedHeight(32)
        new_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 5px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        new_btn.clicked.connect(self._refresh_key)
        btn_row.addWidget(new_btn)

        close_btn = QPushButton('FECHAR')
        close_btn.setFixedHeight(32)
        close_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 5px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self._do_close)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        self._ctimer = QTimer(self)
        self._ctimer.timeout.connect(self._tick)
        self._ctimer.start(1000)
        self._tick()

    def set_new_key_callback(self, fn) -> None:
        self._on_new_key = fn

    def _update_qr(self, url: str) -> None:
        if not url:
            self._qr_label.setText("—")
            return
        try:
            import qrcode as _qrmod
            from io import BytesIO
            qr = _qrmod.QRCode(
                box_size=5, border=2,
                error_correction=_qrmod.constants.ERROR_CORRECT_M,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap()
            px.loadFromData(buf.getvalue())
            self._qr_label.setPixmap(
                px.scaled(170, 170,
                          Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
            )
        except ImportError:
            self._qr_label.setText("pip install\nqrcode[pil]")
            self._qr_label.setFont(QFont("Courier New", 8))
            self._qr_label.setStyleSheet(
                "color: #888; background: white; border-radius: 10px; padding: 4px;"
            )
        except Exception:
            self._qr_label.setText(url[:28])
            self._qr_label.setFont(QFont("Courier New", 7))
            self._qr_label.setStyleSheet(
                f"color: {C.PRI}; background: white; border-radius: 10px; padding: 4px;"
            )

    def _tick(self):
        remaining = max(0, int(self._expiry - time.time()))
        m, s = divmod(remaining, 60)
        self._timer_lbl.setText(f"Chave expira em  {m:02d}:{s:02d}")
        if remaining == 0:
            self._do_close()

    def mark_connected(self) -> None:
        """Call from any thread when a phone successfully connects."""
        self._ctimer.stop()
        self._key_lbl.setText('CONECTADO')
        self._key_lbl.setStyleSheet(f"""
            color: {C.GREEN};
            background: rgba(34,197,94,0.08);
            border: 2px solid rgba(34,197,94,0.4);
            border-radius: 8px;
            padding: 6px 4px;
            letter-spacing: 4px;
        """)
        self._qr_label.setText("✓")
        self._qr_label.setFont(QFont("Courier New", 54, QFont.Weight.Bold))
        self._qr_label.setStyleSheet(
            "color: #00ff88; background: #001a0d; border-radius: 10px;"
        )
        self._timer_lbl.setText('Celular conectado. JARVIS pronto')
        self._timer_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")

    def _refresh_key(self):
        if self._on_new_key:
            result = self._on_new_key()
            if result:
                url    = result[0]
                key    = result[1]
                auto   = result[2] if len(result) >= 3 else ""
                manual = result[3] if len(result) >= 4 else url
                self._manual_url     = manual or url
                self._url_lbl.setText(self._manual_url)
                self._key_lbl.setText(key)
                self._auto_login_url = auto
                self._update_qr(auto or url)
                self._expiry = time.time() + 600
                self._key_lbl.setStyleSheet(f"""
                    color: {C.ACC};
                    background: {C.PANEL2};
                    border: 1px solid {C.BORDER_B};
                    border-radius: 8px;
                    padding: 6px 4px;
                    letter-spacing: 10px;
                """)
                self._timer_lbl.setStyleSheet(
                    f"color: {C.TEXT_MED}; background: transparent;"
                )
                self._ctimer.start(1000)
                self._tick()

    def _do_close(self):
        self._ctimer.stop()
        self.hide()
        self.closed.emit()


class MainWindow(QMainWindow):
    _neural_sig = pyqtSignal(object)
    _operation_sig = pyqtSignal(str, str)
    _environment_media_sig = pyqtSignal(dict)
    _ultron_sig = pyqtSignal(object)
    _forge_sig = pyqtSignal(object)
    _interface_sig = pyqtSignal(object)
    _log_sig        = pyqtSignal(str)
    _state_sig      = pyqtSignal(str)
    _content_sig    = pyqtSignal(str, str)   # (title, text) — thread-safe content display
    _manifestation_sig = pyqtSignal(object)
    _verified_manifestation_sig = pyqtSignal(object)
    _live_pin_sig = pyqtSignal(object)
    _telemetry_sig = pyqtSignal(object, object)
    _narration_sig = pyqtSignal(object)
    _connection_sig = pyqtSignal(bool, str)
    _presentation_audio_sig = pyqtSignal(float)
    _sound_sig = pyqtSignal(str)
    _presentation_cancel_sig = pyqtSignal()
    _presentation_reset_sig = pyqtSignal()
    _reconfig_sig   = pyqtSignal()           # trigger setup overlay from any thread
    _camera_sig     = pyqtSignal(bytes)      # show camera frame preview (small overlay)
    _cam_stream_sig = pyqtSignal(bool)       # True=start live stream, False=stop
    _cam_frame_sig  = pyqtSignal(bytes)      # live camera frame → HUD area
    _video_open_sig  = pyqtSignal(str, str, bool, str)  # video, title, muted, audio
    _wake_btns_sig   = pyqtSignal()          # wake state resolved off-thread
    _video_close_sig = pyqtSignal()
    _video_mute_sig  = pyqtSignal(bool)
    _clipboard_sig  = pyqtSignal(str)        # clipboard text changed (thread-safe)
    _confirm_sig    = pyqtSignal(str, str)   # (title, detail) — irreversible-action gate
    _confirm_hide_sig = pyqtSignal()
    _wake_dl_sig    = pyqtSignal(bool, str)  # wake-word install finished (ok, message)
    _quiz_sig       = pyqtSignal(str, object, object)  # (topic, questions, grader)
    _quiz_hide_sig  = pyqtSignal()
    _review_sig     = pyqtSignal(str, str, object, object)  # document review payload

    def __init__(self, face_path: str):
        super().__init__()
        self._face_path = face_path
        self._presentation_history = []
        self._presentation = None
        self._pinned = False
        self._pinned_context = None
        self._pin_previews = {}
        from core.pinned_scene_store import PinnedSceneStore
        self._pin_store = PinnedSceneStore(API_FILE.parent)
        self._restoring_pins = False
        self._pending_saved_pins=None
        self._pin_restore_attempts=0
        self._attachments = {}
        self._pending_image_pin = False
        self._space_view = None
        self._forge_controller=None
        self._spectro_controller=None
        self._spectro_color=lambda:C.PRI
        QTimer.singleShot(0,self._start_screen_observation)
        self._forge_runtime=None
        self.on_forge_command=None
        self.on_forge_snapshot=None
        self.on_forge_scene_failure=None
        self._forge_sig.connect(self._apply_forge_request)
        self._environment = EnvironmentDirector()
        self._interface_sig.connect(self._apply_interface_request)

        # Load customization from config
        _cfg = _read_full_config()
        self._assistant_name: str = (_cfg.get("assistant_name") or "DIEF JARVIS").strip()
        _display = self._assistant_name.upper()

        # Apply the saved UI colour BEFORE panels/stylesheets are built
        _ui_color = (_cfg.get("ui_color") or "").strip()
        if _ui_color and _ui_color.lower() != DEFAULT_UI_COLOR:
            apply_ui_accent(_ui_color)

        self.setWindowTitle("DIEF JARVIS")
        from core.branding import app_icon
        self.setWindowIcon(app_icon())
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command   = None
        self.on_remote_clicked = None   # callable: () -> (url, key) | None
        self.on_interrupt      = None   # callable: () -> None — stop JARVIS mid-speech
        self.on_voice_change   = None   # callable: () -> None — rebuild session with new voice
        self.on_connection_test = None
        self.on_audio_device_change = None  # callable: () -> None — reopen audio streams
        self._confirm_overlay  = None   # live ConfirmBanner, if one is on screen
        self.get_plugins       = None   # callable: () -> list[dict], set by JarvisLive
        self.get_plugin_settings = None # callable: () -> list[dict] settings schemas, set by JarvisLive
        self.on_wake_toggle    = None   # callable: (enable: bool) -> str, set by JarvisLive
        self.on_wake_manual    = None   # callable: () -> None — manual sleep/wake
        self.on_push_to_talk   = None   # callable: (enable: bool) -> str scope
        self.ptt_hold          = None   # callable: (held: bool) -> None — windowed chord
        self.wake_get_state    = None   # callable: () -> dict {enabled, awake, ready}
        self._muted            = False
        self._resting = False
        self.on_rest_toggle = None
        self._current_file: str | None = None
        self._remote_overlay: RemoteKeyOverlay | None = None
        self._customize_overlay: CustomizeOverlay | None = None

        central = QWidget()
        central.setObjectName('JarvisScene')
        central.setStyleSheet(f"QWidget#JarvisScene {{ background: {C.BG}; }}")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._floating_controls = self._build_header()
        self._floating_controls.setParent(central)
        self._floating_controls.setGeometry(14, 12, 120, 42)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._left_panel = self._build_left_panel()
        self._left_panel.setParent(self)
        self._left_panel.hide()

        # Center column: HUD + resizable content panel via QSplitter
        self.hud = HudCanvas(face_path, _display)
        self.hud.interaction.connect(self._avatar_interaction)
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._content_panel = self._build_content_panel()
        self._quiz_panel = self._build_quiz_panel()

        # Live camera container — replaces HUD when camera stream is active
        _cam_cont = _FuiOverlay()
        _cam_cont.setStyleSheet("background: #000308;")
        _cam_v = QVBoxLayout(_cam_cont)
        _cam_v.setContentsMargins(12, 12, 12, 12)
        _cam_v.setSpacing(0)
        _cam_hdr = QHBoxLayout()
        _cam_hdr.setContentsMargins(8, 5, 8, 5)
        _cam_title = QLabel('◈  CÂMERA AO VIVO')
        _cam_title.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        _cam_title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        _cam_hdr.addWidget(_cam_title)
        _cam_hdr.addStretch()
        _cam_x = QPushButton('✕  FECHAR')
        _cam_x.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        _cam_x.setCursor(Qt.CursorShape.PointingHandCursor)
        _cam_x.setStyleSheet(f"""
            QPushButton {{
                color: {C.TEXT_DIM}; background: transparent;
                border: none; padding: 2px 6px;
            }}
            QPushButton:hover {{ color: {C.PRI}; }}
        """)
        _cam_x.clicked.connect(self.stop_camera_stream)
        _cam_hdr.addWidget(_cam_x)
        _cam_v.addLayout(_cam_hdr)
        self._cam_live_lbl = QLabel()
        self._cam_live_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cam_live_lbl.setStyleSheet("background: transparent;")
        self._cam_live_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        _cam_v.addWidget(self._cam_live_lbl, stretch=1)

        # ── Video surface ────────────────────────────────────────────────
        # Built exactly like the camera page above and stacked beside it,
        # because it is the same idea: something takes the centre of the HUD
        # for a while and then gives it back. Sharing the stack rather than
        # inventing a second mechanism means the avatar, the camera and a video
        # can never be on screen at once.
        self._video_split = False        # is the sound a separate stream?
        self._video_auto_muted = False   # did JARVIS close the mic, or the user?
        # A plain flag rather than reading the widget. video_is_playing() is
        # called from plugin threads, and reading a widget's state from one is
        # not something to rely on; an attribute is.
        self._video_on = False
        self._video_cont = _FuiOverlay()
        self._video_cont.setStyleSheet(f"background: {C.BG};")
        _vid_v = QVBoxLayout(self._video_cont)
        _vid_v.setContentsMargins(14, 14, 14, 14)
        _vid_v.setSpacing(4)

        _vid_hdr = QHBoxLayout()
        self._video_title = QLabel('▶  VÍDEO')
        self._video_title.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        self._video_title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        _vid_hdr.addWidget(self._video_title)
        _vid_hdr.addStretch()

        def _vid_btn(text: str) -> QPushButton:
            b = QPushButton(text)
            b.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    color: {C.TEXT_DIM}; background: transparent;
                    border: none; padding: 2px 6px;
                }}
                QPushButton:hover {{ color: {C.PRI}; }}
            """)
            return b

        # Muted is the default and the button says so, because a soundtrack
        # talking over JARVIS is the one way this feature could make the
        # assistant worse rather than better.
        self._video_mute_btn = _vid_btn('🔇  SOM DESLIGADO')
        self._video_mute_btn.clicked.connect(self._toggle_video_mute)
        _vid_hdr.addWidget(self._video_mute_btn)

        _vid_x = _vid_btn('✕  FECHAR')
        _vid_x.clicked.connect(self.stop_video)
        _vid_hdr.addWidget(_vid_x)
        _vid_v.addLayout(_vid_hdr)

        if HAVE_VIDEO:
            # A GRAPHICS ITEM, NOT A QVideoWidget.
            #
            # QVideoWidget gets a native window of its own, and a native window
            # is painted by the compositor above every ordinary widget that
            # shares the screen with it — so the settings drawer opened
            # *underneath* the video and raise_() could not help, because the
            # two are not in the same painting order at all. A video item drawn
            # into a QGraphicsView goes through Qt's own painter like any other
            # widget, and anything laid over it stays over it.
            self._video_scene = QGraphicsScene(self)
            self._video_item = QGraphicsVideoItem()
            self._video_scene.addItem(self._video_item)
            self._video_widget = QGraphicsView(self._video_scene)
            self._video_widget.setStyleSheet("background: #000; border: none;")
            self._video_widget.setFrameShape(QGraphicsView.Shape.NoFrame)
            self._video_widget.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._video_widget.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._video_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            _vid_v.addWidget(self._video_widget, stretch=1)

            self._video_audio = QAudioOutput()
            self._video_audio.setMuted(True)
            self._video_player = QMediaPlayer()
            self._video_player.setVideoOutput(self._video_item)
            # Keep the picture filling the view as the window is resized.
            self._video_item.nativeSizeChanged.connect(self._fit_video)
            self._video_player.setAudioOutput(self._video_audio)
            self._video_player.errorOccurred.connect(self._on_video_error)

            # A SECOND player, for sound that arrives separately.
            #
            # YouTube no longer serves a single stream carrying both picture and
            # sound — not for new uploads and not for old ones; checked against
            # three videos including the oldest on the site, and every one of
            # them offered zero combined formats. Picture and sound are two
            # URLs, so they are two players, started together and nudged back
            # into line by the timer below.
            #
            # A local file or a direct video URL still uses the first player
            # alone: one stream, one player, nothing to synchronise.
            self._video_sound = QMediaPlayer()
            self._video_sound_out = QAudioOutput()
            self._video_sound_out.setMuted(True)
            self._video_sound.setAudioOutput(self._video_sound_out)

            self._video_sync = QTimer(self)
            self._video_sync.setInterval(1000)
            self._video_sync.timeout.connect(self._sync_video_sound)
        else:
            self._video_scene = None
            self._video_item = None
            self._video_widget = None
            self._video_player = None
            self._video_audio = None
            self._video_sound = None
            self._video_sound_out = None
            self._video_sync = None
            _miss = QLabel('Reprodução de vídeo indisponível nesta instalação.')
            _miss.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _miss.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            _vid_v.addWidget(_miss, stretch=1)

        # Stack: 0 = animated HUD, 1 = live camera, 2 = video
        self._hud_cam_stack = QStackedWidget()
        self._avatar_scene = QWidget()
        avatar_layout = QVBoxLayout(self._avatar_scene)
        avatar_layout.setContentsMargins(0, 0, 0, 0)
        avatar_layout.setSpacing(4)
        self._scene_header_visible = False
        for label in (self._title_lbl, self._clock_lbl, self._date_lbl):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setParent(self.centralWidget())
            label.raise_()
            # The clock belongs to the observatory, not its loading cover.  It
            # is revealed only after either renderer has prepared a scene.
            label.hide()
            label.installEventFilter(self)
        self._title_lbl.setText("DIEF JARVIS")
        self._title_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        self._title_lbl.setFont(QFont("Segoe UI", 11))
        self._clock_lbl.setFont(QFont("Segoe UI", 15))
        self._clock_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        self._date_lbl.setFont(QFont("Segoe UI", 8))
        avatar_layout.addWidget(self.hud, stretch=1)
        self._hud_cam_stack.addWidget(self._avatar_scene)
        self._hud_cam_stack.addWidget(_cam_cont)
        self._hud_cam_stack.addWidget(self._video_cont)

        self._center_split = QSplitter(Qt.Orientation.Horizontal)
        self._center_split.setStyleSheet(f"""
            QSplitter {{ background: transparent; border: none; }}
            QSplitter::handle {{
                background: {C.BG};
                width: 10px;
            }}
            QSplitter::handle:hover {{
                background: {C.PRI_DIM};
            }}
        """)
        self._center_split.addWidget(self._hud_cam_stack)
        self._center_split.addWidget(self._quiz_panel)
        self._center_split.setStretchFactor(0, 3)
        self._center_split.setStretchFactor(1, 1)
        self._center_split.setCollapsible(0, False)
        self._scene_stage = QWidget()
        self._scene_stage.setStyleSheet('background:transparent;')
        self.hud.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent,False)
        self.hud.setStyleSheet('background:transparent;')
        self._avatar_scene.setStyleSheet('background:transparent;')
        self._hud_cam_stack.setStyleSheet('background:transparent;')
        self._scene_stage.installEventFilter(self)
        from core.projection_trace import ProjectionTrace
        self._projection_trace=ProjectionTrace(self._scene_stage)
        self._center_split.setParent(self._scene_stage)
        self._center_split.show()
        self._center_split.setHandleWidth(0)
        self._content_panel.setParent(self._scene_stage)
        self._content_panel.setStyleSheet("background: transparent; border: none;")
        self._scene_animations = []
        self._scene_position = "auto"
        self._avatar_anchor = None
        body.addWidget(self._scene_stage, stretch=5)

        from core.workspace_panels import WorkspacePanel
        self._terminal = WorkspacePanel(self._scene_stage,'terminal')
        self._execution = WorkspacePanel(self._scene_stage,'execution')
        self._terminal.submitted.connect(self._terminal_send)
        self._terminal.attached.connect(self._terminal_attach)
        self._terminal.pin_requested.connect(self._safe_pin_image)
        self._terminal.closed.connect(self._terminal_closed)
        self._execution.closed.connect(lambda:self._layout_scene(True))
        self._operation_sig.connect(self._operation_event)
        self._environment_media_sig.connect(self._environment.media_update)
        self._execution_settle = QTimer(self)
        self._execution_settle.setSingleShot(True)
        self._execution_settle.timeout.connect(self._execution.close_panel)

        self._right_panel = self._build_right_panel()
        self._right_panel.setParent(self)
        self._right_panel.hide()

        root.addLayout(body, stretch=1)
        self._pin_button = QPushButton(central)
        self._pin_button.setToolTip("Restaurar apresentação fixada")
        self._pin_button.setStyleSheet(f"background:{C.BG};color:{C.PRI};border:1px solid {C.BORDER};padding:5px;border-radius:4px;")
        self._pin_button.clicked.connect(self._restore_pin)
        self._pin_button.hide()
        self._command_bar = QWidget()
        command_layout = QHBoxLayout(self._command_bar)
        command_layout.setContentsMargins(24, 6, 24, 12)
        command_layout.addLayout(self._build_input_row())
        root.addWidget(self._command_bar)
        self._command_bar.hide()
        command_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        command_shortcut.activated.connect(self._open_terminal)

        # Quick-access drawer (floating overlay, built after central widget layout is done)
        self._quick_drawer = self._build_quick_drawer()
        self._update_autostart_btn(self._check_autostart())
        from memory.config_manager import get_brief_enabled as _gbe
        self._update_brief_btn(_gbe())

        self._clock_tmr = QTimer(self)
        self._telemetry_busy = False
        self._telemetry_at = 0
        self._telemetry_sig.connect(self._receive_telemetry)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        # Telemetry is sampled on request, not a permanent dashboard.
        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)

        self._log_sig.connect(self._log.append_log)
        self._log_sig.connect(self._terminal_log)
        self._state_sig.connect(self._apply_state)
        self._content_sig.connect(self._show_content)
        self._manifestation_sig.connect(self._show_manifestation)
        self._verified_manifestation_sig.connect(self._show_verified_manifestation)
        self._neural_sig.connect(self._update_neural_memory)
        self._narration_sig.connect(self._narrate_presentation)
        from core.presentation_clock import PresentationClock
        self._presentation_clock=PresentationClock()
        self._ultron_clock=PresentationClock()
        self._narration_elapsed=0.
        self._ultron_payload=None
        self._ultron_polling=False
        self._ultron_announced=None
        self.on_ultron_ready=None
        self.on_ultron_alert=None
        self._ultron_alerted_at=0
        self._ultron_sig.connect(self._show_ultron)
        self._ultron_timer=QTimer(self)
        self._ultron_timer.setInterval(2000)
        self._ultron_timer.timeout.connect(self._poll_ultron)
        self._presentation_audio_sig.connect(self._advance_presentation)
        self._presentation_cancel_sig.connect(self._cancel_presentation)
        self._presentation_reset_sig.connect(self._presentation_clock.reset)
        self._presentation_reset_sig.connect(self._ultron_clock.reset)
        self._presentation_reset_sig.connect(self._reset_narration_timeline)
        self._connection_sig.connect(self._connection_changed)
        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.timeout.connect(self._settle_presentation)
        from core.live_pins import LivePins
        self._live_pins=LivePins(self._live_pin_sig.emit)
        self._live_pin_sig.connect(self._apply_live_pin)
        self._live_pin_timer=QTimer(self)
        self._live_pin_timer.setInterval(1000)
        self._live_pin_timer.timeout.connect(self._tick_live_pins)
        if os.environ.get('QT_QPA_PLATFORM')!='offscreen':self._live_pin_timer.start()
        self._floating_controls.raise_()
        self._reconfig_sig.connect(self._show_setup)
        self._camera_sig.connect(self._show_camera_frame)
        self._confirm_sig.connect(self._show_confirm_banner)
        self._confirm_hide_sig.connect(self._hide_confirm_banner)
        self._cam_stream_sig.connect(self._on_cam_stream)
        self._cam_frame_sig.connect(self._on_cam_frame)
        self._wake_btns_sig.connect(self._refresh_wake_btns)
        self._video_open_sig.connect(self._on_video_open)
        self._video_close_sig.connect(self._on_video_close)
        self._video_mute_sig.connect(self._on_video_mute)
        self._clipboard_sig.connect(self._show_clipboard_panel)
        self._wake_dl_sig.connect(self._on_wake_install_done)
        self._quiz_sig.connect(self._show_quiz)
        self._quiz_hide_sig.connect(self._hide_quiz)
        self._review_sig.connect(self._show_review)
        self._cam_stop = threading.Event()

        # Camera preview overlay (child of central widget, positioned in resizeEvent)
        self._cam_preview = _CameraPreview(self.centralWidget())

        # Clipboard panel (child of central widget, bottom-center)
        self._clipboard_panel = ClipboardPanel(self.centralWidget())
        self._clipboard_panel.action_requested.connect(self._on_clipboard_action)
        # Clipboard suggestions must not interrupt the intentionally empty scene.

        self._overlay: SetupOverlay | None = None
        self._ready = self._check_config()
        if not self._ready:
            self._show_setup()

        sc_mute = QShortcut(QKeySequence("F4"), self)
        sc_mute.activated.connect(self._toggle_mute)
        self._fullscreen_shortcut=QShortcut(QKeySequence('F11'),self)
        self._fullscreen_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._fullscreen_shortcut.setAutoRepeat(False)
        self._fullscreen_shortcut.activated.connect(self._fullscreen_key)
        from core.ui_sounds import SoundDirector
        self._ui_sounds=SoundDirector(self)
        self._environment_media_sig.connect(self._ui_sounds.media)
        from core.connection_verifier import ConnectionVerifier
        self._connection_verifier=ConnectionVerifier()
        self._connection_checks=self._connection_verifier.checks
        self._connection_timer=QTimer(self)
        self._connection_timer.timeout.connect(self._verify_saved_connections)
        if os.environ.get('QT_QPA_PLATFORM')!='offscreen':
            self._connection_timer.start(300000)
            QTimer.singleShot(1500,self._verify_saved_connections)
        self._sound_sig.connect(self._ui_sounds.play)
        from core.update_notice import UpdateNotice
        self._update_notice=UpdateNotice(self)
        self._refresh_lock=None
        self._pins_restored=False
        self._opening_veil=None
        self._scene_layout_ready=False
        if os.environ.get('QT_QPA_PLATFORM')!='offscreen':
            from core.opening_veil import OpeningVeil
            self._opening_veil=OpeningVeil(self._scene_stage)
            self._opening_veil.hub_visible=self._ready
            self._opening_veil.setGeometry(self._scene_stage.rect());self._opening_veil.show();self._opening_veil.raise_()
        QApplication.instance().installEventFilter(self)
        sc_intr = QShortcut(QKeySequence("Escape"), self)
        sc_intr.activated.connect(self._do_interrupt)
        QTimer.singleShot(200,self._ensure_content_renderer)
        QTimer.singleShot(250,self._ensure_space)
        if os.environ.get('QT_QPA_PLATFORM')=='offscreen':QTimer.singleShot(100,self._restore_saved_pins)

    def _verify_saved_connections(self):
        plugins=self.get_plugins() if self.get_plugins else []
        self._connection_verifier.schedule(plugins)

    def _save_pins(self):
        if self._restoring_pins:return True
        try:
            saved=self._load_pin_snapshots() if not self._pins_restored else []
        except Exception as error:
            self._log.append_log('ERR: Cache antigo preservado; nao consegui ler as previas ('+type(error).__name__+').')
            return False
        pins=[]
        for key,preview in self._pin_previews.items():
            pin={'key':key,'data':copy.deepcopy(preview['data']),'slot':preview.get('slot')}
            if preview.get('placement'):pin['placement']=dict(preview['placement'])
            if 'asset' in preview:pin['asset']=preview['asset']
            pins.append(pin)
        merged={pin['key']:pin for pin in saved}
        merged.update({pin['key']:pin for pin in pins})
        try:
            self._pin_store.save(list(merged.values()))
            self._pending_saved_pins=copy.deepcopy(list(merged.values()))
            return True
        except Exception as error:
            self._log.append_log('ERR: Nao consegui salvar as previas locais ('+type(error).__name__+').')
            return False

    def _load_pin_snapshots(self):
        if self._pending_saved_pins is None:self._pending_saved_pins=self._pin_store.load()
        return copy.deepcopy(self._pending_saved_pins)

    def _pin_capacity(self):
        saved=self._load_pin_snapshots() if not self._pins_restored else []
        return set(self._pin_previews)|{pin['key'] for pin in saved}

    def _restore_saved_pins(self):
        if self._pins_restored:return
        forge=getattr(self,'_forge_controller',None)
        ultron=getattr(self,'_ultron_payload',None)
        if ((forge and forge.active) or isinstance(ultron,dict) and ultron.get('state',{}).get('phase','idle')!='idle'
                or getattr(self,'_closed_for_shutdown',False)):return
        self._restoring_pins=True
        complete=True
        try:
            for pin in self._load_pin_snapshots():
                try:
                    data=pin['data'];key=pin['key']
                    if key in self._pin_previews:continue
                    if data['kind']=='photo':
                        identifier=data['attachment_id']
                        path=self._pin_store.assets/pin['asset']
                        self._attachments[identifier]={'path':str(path),'image':True,'name':data['title']}
                        self._pin_image(identifier)
                    else:
                        data={**data,'restored_snapshot':True,'narrationDriven':False,
                              'live':{**data.get('live',{}),'stale':True,'message':'Previa salva; aguardando consulta atual.'}}
                        data['source']='Previa salva · atualizacao pendente'
                        self._pin_data(data)
                    if pin.get('slot') is not None:self._pin_previews[key]['slot']=pin['slot']
                    if pin.get('placement'):self._pin_previews[key]['placement']=dict(pin['placement'])
                except Exception:
                    complete=False
                    self._log.append_log('SYS: Uma previa salva nao pode ser restaurada; cache preservado.')
            self._position_pin()
            self._pins_restored=complete
        except Exception:
            self._log.append_log('SYS: Cache de previas indisponivel; arquivo original preservado.')
        finally:self._restoring_pins=False
        if not self._pins_restored and self._pin_restore_attempts<3:
            self._pin_restore_attempts+=1
            QTimer.singleShot(2000,self._restore_saved_pins)

    def _ensure_space(self):
        self._layout_scene()
        if self._space_view is not None or hasattr(self,'_space_fallback'):
            return
        self._space_fallback = QLabel(self._scene_stage)
        self._space_fallback.setStyleSheet('background:#03060b;')
        self._space_fallback.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._space_fallback.setScaledContents(True)
        self._space_fallback.setPixmap(QPixmap(str(BASE_DIR/'core/spatial/assets/deep-space.png')))
        self._space_fallback.setGeometry(self._scene_stage.rect())
        self._space_fallback.show();self._space_fallback.lower()
        if self._opening_veil and not self._opening_veil.released:self._opening_veil.raise_()
        if SpatialCoreView and os.environ.get('QT_QPA_PLATFORM')!='offscreen':
            try:
                self._space_view = SpatialCoreView(self._scene_stage,'space.html')
                self._space_view.ready.connect(self._start_environment)
                self._space_view.ultron_unavailable.connect(self._ultron_visual_failed)
                self._space_view.unavailable.connect(self._start_environment)
                self._space_view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                self._space_view.setGeometry(self._scene_stage.rect());self._space_view.show();self._space_view.lower()
                self._space_fallback.lower()
                self._space_view.sync({'motion':'reduced' if _read_full_config().get('reduce_motion',False) else 'full'})
            except Exception:
                self._space_view = None
                self._activate_scene_fallback()
                self._start_environment()
        else:self._start_environment()

    def _reveal_scene_header(self):
        if getattr(self, '_scene_header_visible', False):
            return
        self._scene_header_visible = True
        for label in (self._title_lbl, self._clock_lbl, self._date_lbl):
            label.show()
            label.raise_()

    def _activate_scene_fallback(self):
        """Keep the observatory usable when an optional WebGL view is lost.

        The Qt-painted hologram and the static space image are deliberately
        independent of WebEngine.  A GPU/WebGL failure must therefore never
        turn into a full-screen terminal error.
        """
        if getattr(self, '_scene_fallback_active', False):
            return
        self._scene_fallback_active = True
        for renderer in (getattr(self, '_space_view', None),
                         getattr(self.hud, '_spatial_core', None)):
            if renderer is None:
                continue
            try:
                renderer.hide()
            except (RuntimeError, AttributeError):
                pass
        self._log.append_log('SYS: Renderizador 3D indisponivel; usando a cena local de recuperacao.')

    def _start_environment(self, loaded=True):
        if not loaded:
            return
        if not self.isVisible() or not getattr(self,'_scene_layout_ready',False):return
        if self._overlay is not None and not self._ready:return
        if not hasattr(self,'_space_fallback'):return
        renderer_failed = ((self._space_view and self._space_view.failed) or
                           (self.hud.hud_style=='core' and self.hud._spatial_core and self.hud._spatial_core.failed))
        if renderer_failed:
            self._activate_scene_fallback()
        fallback_active = getattr(self, '_scene_fallback_active', False)
        if not fallback_active and self._space_view and not self._space_view.failed and not self._space_view._ready:return
        core=self.hud._spatial_core
        if self.hud.hud_style=='core' and not fallback_active:
            if os.environ.get('QT_QPA_PLATFORM')!='offscreen' and (SpatialCoreView is None or core is None and self.hud._core_attempted):
                self._activate_scene_fallback()
                fallback_active = True
            waiting_core=core is None and SpatialCoreView is not None and os.environ.get('QT_QPA_PLATFORM')!='offscreen' and not self.hud._core_attempted
            if not fallback_active and (waiting_core or core is not None and not core.failed and not core._ready):return
        first=not self._environment.started
        veil=self._opening_veil
        if first and veil:
            if not veil.released:
                veil.fade.finished.connect(self._start_environment)
                veil.release()
                return
            if veil.isVisible():return
        self._environment.start(self.hud.motion_reduced,delay=400)
        self._reveal_scene_header()
        if first:
            self._ui_sounds.play('startup')
            QTimer.singleShot(4700,self._restore_saved_pins)
        self._ui_sounds.scene(visible=self.isVisible() and not self.isMinimized())
        phase={'INITIALISING':'booting','THINKING':'thinking','PROCESSING':'executing'}.get(self.hud.state,
                    'speaking' if self.hud.speaking else 'idle')
        self._sync_environment(phase, 0)

    def _sync_environment(self, phase=None, level=None):
        if not getattr(self, '_environment', None):
            return
        if phase is None:
            phase={'INITIALISING':'booting','THINKING':'thinking','PROCESSING':'executing','SLEEPING':'sleeping',
                   'WARNING':'warning','ERROR':'error'}.get(self.hud.state,'speaking' if self.hud.speaking else 'idle')
            if self.hud.muted:phase='sleeping'
        if level is None:level=self.hud._amp_disp
        model = (self._presentation or {}).get('model', {}) if self._content_panel.isVisible() else {}
        settings = bool(getattr(self, '_settings_hub', None) and self._settings_hub.isVisible())
        forge=getattr(self,'_forge_controller',None)
        ultron=(getattr(self,'_ultron_payload',None) or {}).get('state',{}).get('phase','idle')!='idle'
        if settings or self._resting or ultron or (forge and forge.active):
            self._cancel_neural_memory()
        payload = self._environment.payload(phase=phase, level=level, domain=model.get('kind'),
            reading=bool(model.get('reading')), resting=self._resting, reduced=self.hud.motion_reduced,
            settings=settings, visible=self.isVisible() and not self.isMinimized() and not settings)
        payload['staging']=not self._environment.started
        stage = self._scene_stage
        center = self._center_split.geometry().center()
        payload['anchor'] = {'x': center.x()/max(1,stage.width()), 'y': center.y()/max(1,stage.height())}
        payload['target'] = None
        domain_tools={'weather':('weather_report',),'system':('system_status',),'tasks':('organizer',),
                      'calendar':('organizer','google_calendar'),'gmail':('gmail_control','gmail_compose'),
                      'whatsapp':('whatsapp_web','send_message'),'news':('news_briefing',)}
        related = self._environment.operation_name in domain_tools.get(model.get('kind'), ())
        target = self._execution if self._execution.isVisible() else self._content_panel if related else None
        if target:
            point = target.geometry().center()
            payload['target'] = {'x': point.x()/max(1,stage.width()), 'y': point.y()/max(1,stage.height())}
        if self._space_view and not self._space_view.failed:
            self._space_view.sync(payload)
        if self.hud._spatial_core and not self.hud._spatial_core.failed:
            self.hud._spatial_core.sync_environment(payload)

    def _ultron_visual_failed(self):
        self._ultron_render_failed=True
        forge=getattr(self,'_forge_controller',None)
        if not (forge and forge.active):self._center_split.show()
        self._log.append_log('SYS: Visual ULTRON indisponivel. Diagnostico e voz continuam no Jarvis.')

    def _show_ultron(self,payload):
        if getattr(self,'_closed_for_shutdown',False):return
        token=payload.get('poll_token')
        if token is not None:
            if token is not self._ultron_polling:return
            self._ultron_polling=False
        if payload.get('poll_error'):return
        state=payload.get('state',{})
        previous=(self._ultron_payload or {}).get('state',{})
        forge=getattr(self,'_forge_controller',None)
        generation=getattr(forge,'generation',0)
        if forge and (forge.active or payload.get('forge_generation',generation)!=generation):
            self._ultron_timer.stop();self._ultron_clock.cancel()
            self._ultron_payload=None
            return
        # Poll identity belongs to Qt, never to the JSON/WebEngine scene.
        payload={key:value for key,value in payload.items() if key not in ('poll_token','forge_generation')}
        serial=state.get('snapshot_serial',0)
        result=payload.get('result') or {}
        if result.get('accepted') is False:return
        if serial and serial<=getattr(self,'_ultron_snapshot_serial',0):
            # A later poll may reach Qt before the command's presentation signal.
            # Keep its newer state, but admit the result only for the same turn.
            if (not result or state.get('last_user_turn') is None
                    or state.get('last_user_turn')!=previous.get('last_user_turn')):return
            state=previous
            payload={**payload,'state':state}
        else:self._ultron_snapshot_serial=serial
        self._ultron_payload=payload
        active=state.get('phase','idle')!='idle'
        entering=active and previous.get('phase','idle')=='idle'
        if entering:
            self._settle_timer.stop()
            self._presentation_clock.cancel()
            if self._presentation:
                self._presentation.pop('dismissal',None)
                self._presentation.update(narration_active=False,paused=True,pending_beats=[])
            self._terminal.hide()
            scene=getattr(self,'_visual_scene',None)
            if scene:
                self._ultron_layer_visible=scene.layer.isVisible()
                scene.clear_all(preserve_pinned=True);scene.cancel();scene.layer.hide()
        elif not active and previous.get('phase','idle')!='idle':
            scene=getattr(self,'_visual_scene',None)
            if scene:scene.layer.setVisible(getattr(self,'_ultron_layer_visible',False))
            if not getattr(self,'_pins_restored',True):QTimer.singleShot(0,self._restore_saved_pins)
        visual=bool(self._space_view and not self._space_view.failed and not getattr(self,'_ultron_render_failed',False))
        self._center_split.setVisible((not active or not visual) and (self._overlay is None or self._ready))
        for preview in self._pin_previews.values():preview['widget'].setVisible(not active)
        if active:
            self._content_panel.hide();self._execution.hide();self._ultron_timer.start()
        else:self._ultron_timer.stop()
        if result:
            self._ultron_silenced=result.get('mode')=='cancelled'
            if not self._ultron_silenced:
                self._ultron_clock.replace_scene()
                self._ultron_clock.elapsed=getattr(self,'_narration_elapsed',0.)
                self._ultron_clock.next_cue=self._ultron_clock.elapsed
        if self._space_view and not self._space_view.failed:self._space_view.sync_ultron(payload)
        if not active or getattr(self,'_ultron_silenced',False):
            self._ultron_clock.cancel()
            if self._space_view:self._space_view.advance_ultron({'cancelled':True,'cues':[]})
        operations=state.get('operations',[])
        waiting=state.get('scan',{}).get('running') or state.get('confirmation_pending') or any(op.get('state') in ('pending','running') for op in operations)
        if not waiting and self._environment.operation_name=='ultron_protocol':
            self._environment.operation_event('completed','ultron_protocol');self._sync_environment()
        completed=state.get('scan',{}).get('finished_at')
        if result.get('mode')=='diagnostic' and completed and not state.get('scan',{}).get('running'):
            self._ultron_announced=completed
        available=(not result and not waiting and not getattr(self,'_ultron_silenced',False)
                   and not self.hud.speaking and self.hud.state not in ('THINKING','PROCESSING'))
        if active and completed and completed!=self._ultron_announced and available and self.on_ultron_ready:
            self._ultron_announced=completed;self.on_ultron_ready(state)
            available=False
        if active and available and self.on_ultron_alert and time.monotonic()-self._ultron_alerted_at>=60:
            from core.ultron_presentation import monitor_alerts
            alerts=monitor_alerts(state)
            if alerts and self.on_ultron_alert(alerts):self._ultron_alerted_at=time.monotonic()
        if previous.get('phase')!=state.get('phase'):self._layout_scene(True)

    def _poll_ultron(self):
        runtime=getattr(self,'_ultron_runtime',None)
        if not runtime or self._ultron_polling or getattr(self,'_closed_for_shutdown',False):return
        forge=getattr(self,'_forge_controller',None)
        if forge and forge.active:
            self._ultron_timer.stop();self._ultron_clock.cancel();self._ultron_payload=None
            return
        token=object()
        self._ultron_polling=token
        generation=getattr(forge,'generation',0)
        def poll():
            try:
                from core.ultron_presentation import projection
                payload={'state':projection(runtime.snapshot()),'result':None}
            except Exception:payload={'poll_error':True}
            self._ultron_sig.emit({**payload,'poll_token':token,'forge_generation':generation})
        threading.Thread(target=poll,name='UltronSnapshot',daemon=True).start()

    def _open_terminal(self):
        self._content_panel.hide()
        if self._scene_stage.width()<900:
            self._execution.hide()
        self._terminal.show_panel(_read_full_config().get('reduce_motion',False))
        self._layout_scene(True)
        self._terminal.input.setFocus()
        self._project_workspace(self._terminal)

    def _terminal_closed(self):
        self._pending_image_pin=False
        self._layout_scene(True)

    def _project_workspace(self,panel):
        if not _read_full_config().get('reduce_motion',False):
            self._projection_trace.begin(self._center_split.geometry().center(),panel.geometry().center(),'#a7dce2',compact=True)

    def _terminal_send(self,text):
        self._log.append_log('Você: '+text)
        self._terminal.add_line('Você: '+text)
        if self.on_text_command:
            threading.Thread(target=self.on_text_command,args=(text,),daemon=True).start()
        else:
            self._terminal.status.setText('Jarvis ainda não conectado')

    def _terminal_log(self,text):
        names=('você:','you:',self._assistant_name.lower()+':','jarvis:','dief jarvis:')
        if str(text).lower().startswith(names):
            self._terminal.add_line(text)

    def _terminal_attach(self,path):
        import uuid
        try:
            p=Path(path).resolve(strict=True)
            if not p.is_file() or p.stat().st_size>100*1024*1024:
                raise ValueError('Escolha um arquivo de até 100 MB.')
            is_image=p.suffix.lower() in ('.png','.jpg','.jpeg','.webp','.bmp','.gif')
            if is_image:
                from core.workspace_panels import image_preview
                image_preview(p)
            identifier=uuid.uuid4().hex[:16]
            if len(self._attachments)>=8:
                oldest=next(key for key in self._attachments if 'photo:'+key not in self._pin_previews)
                self._attachments.pop(oldest)
            self._attachments[identifier]={'path':str(p),'image':is_image,'name':p.name}
            self._terminal.attachment(identifier,p,is_image)
            if is_image:
                self._terminal.show_image(QPixmap.fromImage(image_preview(p)))
            self._drop_zone._set_file(str(p))
            if self._pending_image_pin and is_image:
                self._pin_image(identifier)
        except (OSError,ValueError) as error:
            self._terminal.status.setText(str(error))

    def _pin_image(self,identifier):
        from core.workspace_panels import image_preview
        attachment=self._attachments.get(identifier)
        if not attachment or not attachment['image']:
            raise ValueError('Selecione uma foto no terminal antes de fixar.')
        kind='photo:'+identifier
        if kind in self._pin_previews:
            return
        if kind not in self._pin_capacity() and len(self._pin_capacity())>=6:
            self._terminal.status.setText('Seis previas ja estao fixadas. Remova uma antes de fixar a foto.')
            raise ValueError('Limite de seis previas fixadas.')
        pixmap=QPixmap.fromImage(image_preview(attachment['path']))
        from core.hud_glass import PinnedPreviewFrame
        frame=PinnedPreviewFrame(self._scene_stage);frame.setObjectName('PhotoPin');frame.set_semantic({'kind':'photo'})
        frame.set_motion_reduced(_read_full_config().get('reduce_motion',False))
        frame.setStyleSheet('QFrame#PhotoPin{background:transparent;border:0;} QLabel{background:transparent;border:0;color:#f2f7ff;}')
        layout=QVBoxLayout(frame);layout.setContentsMargins(7,6,7,7);layout.setSpacing(4)
        row=QHBoxLayout();restore=QLabel(attachment['name']);row.addWidget(restore,1);layout.addLayout(row)
        label=QLabel();label.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(label,1)
        self._pin_previews[kind]={'widget':frame,'view':None,'label':label,'restore':restore,'accent':'#a7dce2',
            'data':{'kind':'photo','title':attachment['name'],'attachment_id':identifier},'pixmap':pixmap}
        self._pin_store.assets.mkdir(parents=True,exist_ok=True)
        asset=identifier+'.png'
        target=self._pin_store.assets/asset
        if not target.exists() and not pixmap.save(str(target),'PNG'):
            self._pin_previews.pop(kind);frame.deleteLater();raise ValueError('Nao consegui salvar a foto fixada.')
        self._pin_previews[kind]['asset']=asset
        self._attachments[identifier]['path']=str(target)
        if self._save_pins() is False:
            self._pin_previews.pop(kind);frame.deleteLater();raise ValueError('Nao consegui salvar a foto fixada; cache anterior preservado.')
        self._pending_image_pin=False;frame.show();self._layout_scene(True)
        self._terminal.status.setText('Foto fixada no painel')
        if not _read_full_config().get('reduce_motion',False):
            self._projection_trace.begin(self._center_split.geometry().center(),frame.geometry().center(),'#a7dce2',compact=True)

    def _safe_pin_image(self,identifier):
        try:
            self._pin_image(identifier)
        except (OSError,ValueError) as error:
            self._terminal.status.setText(str(error))

    def _operation_event(self,name,state):
        spectro=getattr(self,'_spectro_controller',None)
        if spectro:spectro.record_event(name,state)
        if isinstance(name,str) and name.split(':',1)[0]=='ultron_protocol':
            self._environment.operation_event(state,name)
            self._execution.hide()
            self._sync_environment()
            return
        if not isinstance(name,str) or not name:return
        if not self._environment.operation_event(state,name):return
        self._execution.record(name,state)
        if state in ('failed','uncertain'):self._ui_sounds.play('warning')
        elif state in ('success','completed','done'):self._ui_sounds.play('refresh-complete')
        self.hud.semantic_cue('analysis' if state=='running' else 'warning' if state in ('failed','uncertain') else 'attention' if state=='pending' else 'settle' if state=='cancelled' else 'resolved')
        if self._environment.operation in ('running','pending') and state not in ('running','pending'):
            name=self._environment.operation_name
            state=self._environment.operation
            self._execution.record(name,state)
        name=name.partition(':')[0]
        if name not in ('app_control','desktop_accessibility','send_message','file_processor','file_controller','browser_control',
            'local_resources','file_library','office_resources','resource_backups','gmail_compose','home_automation','mcp_bridge','resource_diagnostics','notion_service','outlook_service','powershell_control'):
            return
        if state in ('running','pending'):
            self._execution_settle.stop()
            if not self._terminal.isVisible() or self._scene_stage.width()>=900:
                first=not self._execution.isVisible()
                self._execution.show_panel(_read_full_config().get('reduce_motion',False))
                self._layout_scene(True)
                if first:self._project_workspace(self._execution)
        else:
            self._execution_settle.start(10000 if state in ('failed','uncertain') else 5000)

    def _layout_workspace(self,avatar,target,active):
        if not hasattr(self,'_terminal'):return avatar,target
        w,h=self._scene_stage.width(),self._scene_stage.height()
        refresh_view=getattr(self,'_daily_refresh_view',None)
        if refresh_view:refresh_view.reposition()
        terminal=self._terminal.isVisible();execution=self._execution.isVisible()
        if not (terminal or execution): return avatar,target
        bottom_pins=[item['widget'].geometry() for item in self._pin_previews.values() if item['widget'].geometry().center().y()>h*.5]
        reserve=max((h-rect.top()+10 for rect in bottom_pins),default=0)
        available=max(210,h-120-reserve)
        panel_width=min(380,max(240,int(w*.29)))
        if w<900:
            panel_width=min(w-24,430)
            y=max(90,h-reserve-min(available,330)-12)
            for panel in (self._terminal,self._execution):
                if panel.isVisible(): panel.setGeometry(12,y,panel_width,min(available,330));panel.raise_()
            avatar=QRect(int(w*.12),65,int(w*.76),max(160,y-65))
            if active:
                panel_width=min(350,int(w*.42))
                target=QRect(panel_width+24,max(84,target.y()),max(120,w-panel_width-36),min(target.height(),h-max(84,target.y())-12))
                visible=[panel for panel in (self._terminal,self._execution) if panel.isVisible()]
                panel_height=min(available,330)//len(visible)
                for index,panel in enumerate(visible):
                    panel.setGeometry(12,y+index*panel_height,panel_width,panel_height-6)
                avatar=QRect(12,84,panel_width,max(100,y-96))
        else:
            if terminal:
                self._terminal.setGeometry(12,90,panel_width,min(available,int(h*.66)));self._terminal.raise_()
            if execution:
                if active:
                    self._execution.setGeometry(w-panel_width-12,max(90,h-reserve-212),panel_width,200)
                    target.setHeight(max(100,min(target.height(),self._execution.y()-target.y()-12)))
                else:
                    self._execution.setGeometry(w-panel_width-12,110,panel_width,min(available,int(h*.52)))
                self._execution.raise_()
            if not active:
                left=panel_width+28 if terminal else 0;right=w-panel_width-28 if execution else w
                avatar=QRect(left,50,max(240,right-left),h-60)
        for panel in (self._terminal,self._execution):
            if panel.isVisible():panel.setGeometry(self._fit_around_pins(panel.geometry()))
        return avatar,target

    def _show_camera_frame(self, img_bytes: bytes):
        """Slot — display camera preview overlay (main thread)."""
        self._cam_preview.show_frame(img_bytes)
        cw = self.centralWidget()
        pw = _CameraPreview._W
        ph = self._cam_preview.height()
        self._cam_preview.setGeometry(
            cw.width() - _RIGHT_W - pw - 12,
            cw.height() - ph - 28,
            pw, ph,
        )

    # --- Live camera stream in HUD area ------------------------------------
    def _on_cam_stream(self, start: bool) -> None:
        if start:
            self._hud_cam_stack.setCurrentIndex(1)
        else:
            self._hud_cam_stack.setCurrentIndex(0)
            self._cam_live_lbl.clear()

    def _on_cam_frame(self, data: bytes) -> None:
        px = QPixmap()
        px.loadFromData(data)
        if not px.isNull():
            w, h = self._cam_live_lbl.width(), self._cam_live_lbl.height()
            if w > 1 and h > 1:
                self._cam_live_lbl.setPixmap(
                    px.scaled(w, h,
                              Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
                )

    def start_camera_stream(self) -> None:
        self._cam_stop.clear()
        self._cam_stream_sig.emit(True)
        t = threading.Thread(target=self._cam_loop, daemon=True, name="cam-stream")
        t.start()

    def _cam_loop(self) -> None:
        try:
            import cv2
            # Reuse camera index detected by screen_processor (cached in api_keys.json)
            cam_idx = 0
            try:
                import json as _j
                cfg = _j.loads(API_FILE.read_text())
                cam_idx = int(cfg.get("camera_index", 0))
            except Exception:
                pass
            try:
                backend = cv2.CAP_DSHOW if _OS == "Windows" else cv2.CAP_ANY
            except AttributeError:
                backend = 0
            cap = cv2.VideoCapture(cam_idx, backend)
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return
            # warm-up frames
            for _ in range(5):
                cap.read()
            while not self._cam_stop.wait(0.033) and cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
                    self._cam_frame_sig.emit(buf.tobytes())
            cap.release()
        except Exception as e:
            print(f"[Camera] Stream error: {e}")
        finally:
            self._cam_stream_sig.emit(False)

    def stop_camera_stream(self) -> None:
        self._cam_stop.set()

    # --- Video in the HUD area ---------------------------------------------
    #
    # Everything below runs on the Qt thread. Plugins and the assistant reach it
    # through the signals above, the same way every other panel is driven, so a
    # background thread never touches a widget.
    def _on_video_open(self, source: str, title: str, muted: bool,
                       audio_source: str = "") -> None:
        if not HAVE_VIDEO or not self._video_player:
            self.write_log("SYS: Video playback is not available in this Qt "
                           "install.")
            return
        # A video and the live camera cannot share the centre of the HUD.
        self._cam_stop.set()

        self._video_title.setText(f"▶  {(title or 'VIDEO')[:44].upper()}")
        self._video_split = bool(audio_source)
        self._set_video_muted(bool(muted))

        url = (QUrl.fromLocalFile(source) if Path(source).exists()
               else QUrl(source))
        self._video_player.setSource(url)
        if self._video_split:
            self._video_sound.setSource(QUrl(audio_source))
        self._hud_cam_stack.setCurrentIndex(2)
        self._video_on = True
        # Re-run now that the video counts as playing: _set_video_muted ran
        # before this line and saw no video, so its mic check was a no-op.
        self._sync_mic_for_video()
        self._video_player.play()
        if self._video_split:
            self._video_sound.play()
            self._video_sync.start()

    def _fit_video(self, *_a) -> None:
        """Size the picture to the panel, keeping its shape."""
        if not (self._video_item and self._video_widget):
            return
        try:
            native = self._video_item.nativeSize()
            if native.isEmpty():
                return
            view = self._video_widget.viewport().size()
            scale = min(view.width() / native.width(),
                        view.height() / native.height())
            w, h = native.width() * scale, native.height() * scale
            self._video_item.setSize(QSizeF(w, h))
            self._video_scene.setSceneRect(0, 0, w, h)
            self._video_widget.centerOn(self._video_item)
        except Exception:
            pass

    def _on_video_close(self) -> None:
        if self._video_sync:
            self._video_sync.stop()
        for p in (self._video_player, self._video_sound):
            if p:
                p.stop()
                p.setSource(QUrl())
        self._video_split = False
        self._video_on = False
        self._hud_cam_stack.setCurrentIndex(0)
        self._sync_mic_for_video()      # gives the microphone back

    def _set_video_muted(self, muted: bool) -> None:
        """Silence whichever output is carrying the sound for this video."""
        muted = bool(muted)
        if self._video_audio:
            # When the sound is a separate stream this player has none, but
            # muting it too costs nothing and keeps the two paths identical.
            self._video_audio.setMuted(muted)
        if self._video_sound_out:
            self._video_sound_out.setMuted(muted)
        self._sync_video_mute_btn()
        self._sync_mic_for_video()

    def _on_video_mute(self, muted: bool) -> None:
        self._set_video_muted(muted)

    def _sync_mic_for_video(self) -> None:
        """Close the microphone while the video is making sound.

        JARVIS subtracts its OWN output from the microphone — that is what
        core/echo.py does — but a video plays through a different output
        entirely, so the guard has never heard of it and the assistant answers
        the film. There is no arrangement in which an open microphone and a
        loudspeaker in the same room do not do that.

        So the microphone closes for exactly as long as the sound is on, and
        opens again by itself the moment it goes off or the video is closed.
        Only if JARVIS closed it: a microphone the user muted themselves stays
        muted, and pressing the mute key during a video hands the decision back
        to them for good.
        """
        sound_on = bool(self._video_on and self._video_sound_out
                        and not self._video_sound_out.isMuted())
        if sound_on and not self._muted:
            self._video_auto_muted = True
            self._set_muted(True, "The video's sound is on — silence it, close "
                                  "it, or press F4 to talk. Typing still works.")
        elif not sound_on and self._video_auto_muted:
            self._video_auto_muted = False
            self._set_muted(False, 'O vídeo está sem som novamente.')

    def _sync_video_sound(self) -> None:
        """Keep the separate soundtrack in step with the picture.

        Two players started at the same moment do not stay together: they buffer
        independently, and measured on a real stream they were about half a
        second apart after nine seconds. So the sound is nudged back to the
        picture whenever it drifts far enough to hear — and only then, because
        correcting a smaller gap is itself audible.
        """
        if not (self._video_split and self._video_sound and self._video_player):
            return
        try:
            if self._video_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                return
            drift = self._video_sound.position() - self._video_player.position()
            if abs(drift) > 300:
                self._video_sound.setPosition(self._video_player.position())
        except Exception:
            pass

    def _sync_video_mute_btn(self) -> None:
        out = self._video_sound_out if self._video_split else self._video_audio
        muted = bool(out and out.isMuted())
        self._video_mute_btn.setText('🔇  SOM DESLIGADO' if muted else '🔊  SOM LIGADO')

    def _toggle_video_mute(self) -> None:
        out = self._video_sound_out if self._video_split else self._video_audio
        if out:
            self._set_video_muted(not out.isMuted())

    def _on_video_error(self, *_a) -> None:
        err = ""
        try:
            err = self._video_player.errorString()
        except Exception:
            pass
        self.write_log(f"SYS: Não foi possível reproduzir o vídeo{(' — ' + err) if err else ''}.")
        self._on_video_close()

    def stop_video(self) -> None:
        self._video_close_sig.emit()

    def video_is_playing(self) -> bool:
        return bool(self._video_on)

    # ------------------------------------------------------------------
    # Icon generation — arc-reactor style, rendered with Pillow
    # ------------------------------------------------------------------
    @staticmethod
    def _build_jarvis_icon(out_path: Path) -> bool:
        """
        Render a JARVIS arc-reactor icon at 4× resolution and downsample
        for crisp results at all sizes. Saves a multi-res .ico to out_path.
        Returns True on success.
        """
        try:
            import math
            import PIL.Image
            import PIL.ImageDraw
            import PIL.ImageFilter
        except ImportError:
            return False

        CYAN   = (0, 212, 255)
        DIM    = (0, 100, 140)
        DARK   = (0, 6, 10)
        GLOW   = (0, 160, 200)
        WHITE  = (220, 240, 255)

        def _render(sz: int) -> PIL.Image.Image:
            S  = sz * 4                     # draw at 4× then downscale
            img = PIL.Image.new("RGBA", (S, S), (0, 0, 0, 0))
            d   = PIL.ImageDraw.Draw(img)
            cx = cy = S // 2

            # ── filled background circle ──────────────────────────────────
            R = S // 2 - 2
            d.ellipse([cx-R, cy-R, cx+R, cy+R], fill=(*DARK, 255))

            # ── outer border ring ─────────────────────────────────────────
            lw = max(2, S // 40)
            d.ellipse([cx-R, cy-R, cx+R, cy+R],
                      outline=(*CYAN, 220), width=lw)

            # ── mid decorative ring ───────────────────────────────────────
            R2 = int(R * 0.72)
            d.ellipse([cx-R2, cy-R2, cx+R2, cy+R2],
                      outline=(*DIM, 180), width=max(1, lw // 2))

            # ── 6 radial spokes (hex bolt) ────────────────────────────────
            R_inner = int(R * 0.30)
            R_outer = int(R * 0.62)
            spoke_w = max(1, S // 80)
            for i in range(6):
                angle = math.radians(i * 60 - 30)
                x1 = cx + int(R_inner * math.cos(angle))
                y1 = cy + int(R_inner * math.sin(angle))
                x2 = cx + int(R_outer * math.cos(angle))
                y2 = cy + int(R_outer * math.sin(angle))
                d.line([x1, y1, x2, y2], fill=(*GLOW, 200), width=spoke_w)

            # ── 6 tick marks on outer ring ────────────────────────────────
            for i in range(6):
                angle = math.radians(i * 60)
                for dr in range(lw * 2):
                    rx = (R - lw - dr)
                    d.point(
                        [cx + int(rx * math.cos(angle)),
                         cy + int(rx * math.sin(angle))],
                        fill=(*WHITE, 220),
                    )

            # ── inner glowing ring ────────────────────────────────────────
            Ri = int(R * 0.26)
            d.ellipse([cx-Ri, cy-Ri, cx+Ri, cy+Ri],
                      outline=(*CYAN, 255), width=max(2, lw))

            # ── bright glow soft blur applied before core ─────────────────
            # (draw a slightly larger cyan circle on a separate layer)
            glow_layer = PIL.Image.new("RGBA", (S, S), (0, 0, 0, 0))
            gd = PIL.ImageDraw.Draw(glow_layer)
            Rc = int(R * 0.13)
            gd.ellipse([cx-Rc*2, cy-Rc*2, cx+Rc*2, cy+Rc*2],
                       fill=(*CYAN, 110))
            glow_layer = glow_layer.filter(PIL.ImageFilter.GaussianBlur(S // 14))
            img = PIL.Image.alpha_composite(img, glow_layer)
            d   = PIL.ImageDraw.Draw(img)

            # ── core dot ──────────────────────────────────────────────────
            d.ellipse([cx-Rc, cy-Rc, cx+Rc, cy+Rc], fill=(*WHITE, 255))

            # ── downscale to target size ──────────────────────────────────
            return img.resize((sz, sz), PIL.Image.LANCZOS)

        try:
            sizes  = [256, 128, 64, 48, 32, 16]
            frames = [_render(s) for s in sizes]
            frames[0].save(
                out_path,
                format="ICO",
                append_images=frames[1:],
                sizes=[(s, s) for s in sizes],
            )
            return True
        except Exception as e:
            print(f"[Shortcut] ⚠️  Icon generation failed: {e}")
            return False

    @staticmethod
    def _create_lnk_windows(lnk: str, target: str, args: str,
                             work_dir: str, icon_loc: str) -> None:
        """
        Create a Windows .lnk shortcut WITHOUT launching PowerShell or cmd.
        Tries win32com (pywin32) first; falls back to wscript.exe + VBScript.
        wscript.exe is a GUI-mode host — it never opens a console window.
        """
        # ── Option 1: pywin32 (pure Python COM, zero subprocess) ──────────
        try:
            from win32com.client import Dispatch   # type: ignore
            sh = Dispatch("WScript.Shell")
            sc = sh.CreateShortCut(lnk)
            sc.TargetPath       = target
            sc.Arguments        = f'"{args}"'
            sc.WorkingDirectory = work_dir
            sc.Description      = "DIEF JARVIS · Assistente pessoal"
            sc.IconLocation     = icon_loc
            sc.save()
            return
        except ImportError:
            pass

        # ── Option 2: wscript.exe + VBScript (always available on Windows,
        #    GUI-mode executable — never opens a console window) ────────────
        vbs = "\n".join([
            'Set ws = CreateObject("WScript.Shell")',
            f'Set sc = ws.CreateShortcut("{lnk}")',
            f'sc.TargetPath = "{target}"',
            f'sc.Arguments = Chr(34) & "{args}" & Chr(34)',
            f'sc.WorkingDirectory = "{work_dir}"',
            'sc.Description = "DIEF JARVIS - Assistente pessoal"',
            f'sc.IconLocation = "{icon_loc}"',
            'sc.Save',
        ])
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix=".vbs")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(vbs)
            proc = subprocess.Popen(
                ["wscript.exe", "/nologo", tmp],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            )
            proc.wait(timeout=10)
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass

    @staticmethod
    def _get_desktop_dir() -> Path:
        """
        Resolve the user's REAL desktop directory instead of assuming
        ~/Desktop, which breaks when:
          • OneDrive "Known Folder Move" relocates the desktop
            (<perfil>/OneDrive/Desktop) — very common on Win 10/11;
          • the XDG desktop is localized on Linux (~/Masaüstü,
            ~/Schreibtisch, ~/Bureau, …).
        Falls back to ~/Desktop only as a last resort.
        """
        home = Path.home()
        _os = platform.system()

        if _os == "Windows":
            # ── 1) SHGetKnownFolderPath(FOLDERID_Desktop) — the canonical
            #       answer; follows OneDrive redirection. No dependencies. ──
            try:
                import ctypes
                from ctypes import wintypes

                class _GUID(ctypes.Structure):
                    _fields_ = [("Data1", wintypes.DWORD),
                                ("Data2", wintypes.WORD),
                                ("Data3", wintypes.WORD),
                                ("Data4", ctypes.c_ubyte * 8)]

                # FOLDERID_Desktop {B4BFCC3A-DB2C-424C-B029-7FE99A87C641}
                fid = _GUID(0xB4BFCC3A, 0xDB2C, 0x424C,
                            (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9,
                                                 0x9A, 0x87, 0xC6, 0x41))
                buf = ctypes.c_wchar_p()
                if ctypes.windll.shell32.SHGetKnownFolderPath(
                        ctypes.byref(fid), 0, None, ctypes.byref(buf)) == 0:
                    p = Path(buf.value)
                    ctypes.windll.ole32.CoTaskMemFree(buf)
                    if p.is_dir():
                        return p
            except Exception:
                pass

            # ── 2) Registry: User Shell Folders (may contain %VARS%) ──────
            try:
                import winreg
                with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion"
                        r"\Explorer\User Shell Folders") as key:
                    val, _t = winreg.QueryValueEx(key, "Desktop")
                p = Path(os.path.expandvars(val))
                if p.is_dir():
                    return p
            except Exception:
                pass

        elif _os == "Linux":
            # ── xdg-user-dir honours localized names (~/Masaüstü, …) ──────
            try:
                out = subprocess.run(["xdg-user-dir", "DESKTOP"],
                                     capture_output=True, text=True, timeout=5)
                p = Path(out.stdout.strip())
                if out.stdout.strip() and p != home and p.is_dir():
                    return p
            except Exception:
                pass
            try:
                cfg = home / ".config" / "user-dirs.dirs"
                for line in cfg.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("XDG_DESKTOP_DIR"):
                        val = line.split("=", 1)[1].strip().strip('"')
                        p = Path(val.replace("$HOME", str(home)))
                        if p != home and p.is_dir():
                            return p
            except Exception:
                pass

        # macOS: ~/Desktop is always the real path (localization is
        # display-only). Everything else lands here as a last resort.
        return home / "Desktop"

    def _create_desktop_shortcut(self):
        """
        Create a desktop shortcut on Windows / macOS / Linux.
        Never opens a terminal, console, or PowerShell window on any platform.
        """
        import stat as _stat
        script  = Path(__file__).resolve().parent / "main.py"
        python  = Path(sys.executable)
        desktop = self._get_desktop_dir()

        # Arc-reactor icon (.ico — also exported as .png for Linux/macOS)
        from core.branding import ICON, build_icon
        ico_path = ICON
        if not ico_path.exists():
            build_icon(ico_path)

        try:
            _os = platform.system()

            # ── Windows ───────────────────────────────────────────────────────
            if _os == "Windows":
                pythonw  = python.parent / "pythonw.exe"
                target   = str(pythonw if pythonw.exists() else python)
                lnk      = str(desktop / "DIEF JARVIS.lnk")
                icon_loc = str(ico_path) if ico_path.exists() else f"{target},0"
                self._create_lnk_windows(lnk, target, str(script),
                                         str(script.parent), icon_loc)

            # ── macOS — proper .app bundle (no Terminal window) ───────────────
            elif _os == "Darwin":
                app     = desktop / "DIEF JARVIS.app"
                mac_dir = app / "Contents" / "MacOS"
                res_dir = app / "Contents" / "Resources"
                mac_dir.mkdir(parents=True, exist_ok=True)
                res_dir.mkdir(exist_ok=True)

                # Launcher executable (bash — runs as background process,
                # macOS does NOT open Terminal for executables inside .app bundles)
                launcher = mac_dir / "JARVIS"
                launcher.write_text(
                    "#!/usr/bin/env bash\n"
                    f'cd "{script.parent}"\n'
                    f'exec "{python}" "{script}"\n'
                )
                launcher.chmod(launcher.stat().st_mode
                               | _stat.S_IEXEC | _stat.S_IXGRP | _stat.S_IXOTH)

                # Minimal Info.plist (required for .app recognition)
                (app / "Contents" / "Info.plist").write_text(
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                    '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                    '<plist version="1.0"><dict>\n'
                    '  <key>CFBundleExecutable</key><string>JARVIS</string>\n'
                    '  <key>CFBundleIdentifier</key>'
                    '<string>com.jarvis.assistant</string>\n'
                    '  <key>CFBundleName</key><string>DIEF JARVIS</string>\n'
                    '  <key>CFBundlePackageType</key><string>APPL</string>\n'
                    '  <key>CFBundleVersion</key><string>1.0</string>\n'
                    '</dict></plist>\n'
                )

                # Optional: copy icon as .icns (skip silently if Pillow is missing)
                try:
                    import PIL.Image
                    icns = res_dir / "AppIcon.icns"
                    PIL.Image.open(ico_path).save(icns, format="ICNS")
                    # Inject icon reference into plist
                    plist = app / "Contents" / "Info.plist"
                    txt = plist.read_text()
                    plist.write_text(
                        txt.replace(
                            '</dict></plist>',
                            '  <key>CFBundleIconFile</key>'
                            '<string>AppIcon</string>\n</dict></plist>\n',
                        )
                    )
                except Exception:
                    pass  # icon is optional

            # ── Linux — .desktop file (Terminal=false, no console) ────────────
            else:
                # Export .ico → .png for better desktop integration
                png_path = ico_path.with_suffix(".png")
                if not png_path.exists() and ico_path.exists():
                    try:
                        import PIL.Image
                        PIL.Image.open(ico_path).resize(
                            (256, 256), PIL.Image.LANCZOS
                        ).save(png_path, format="PNG")
                    except Exception:
                        png_path = ico_path  # fallback to .ico

                icon_line = f"Icon={png_path}\n" if png_path.exists() else ""
                desk = desktop / "DIEF JARVIS.desktop"
                desk.write_text(
                    "[Desktop Entry]\n"
                    "Name=DIEF JARVIS\n"
                    f"Exec={python} {script}\n"
                    f"Path={script.parent}\n"
                    "Type=Application\n"
                    "Terminal=false\n"
                    "Categories=Utility;\n"
                    + icon_line
                )
                desk.chmod(desk.stat().st_mode | 0o755)

            self._log.append_log('SYS: Atalho criado na área de trabalho.')
        except Exception as e:
            self._log.append_log(f"ERR: Falha ao criar atalho: {e}")

    def _toggle_fullscreen(self, target=None):
        if not isinstance(target,QWidget):target=QApplication.activeWindow()
        if target is not getattr(self,'_settings_hub',None):target=self
        if target is None:target=self
        if target.isFullScreen():
            target.showNormal()
            rect=getattr(target,'_normal_scene_rect',target.normalGeometry())
            screen=target.screen().availableGeometry()
            if not rect.isValid() or rect.width()>=screen.width()*.95 and rect.height()>=screen.height()*.95:
                rect=QRect(0,0,min(1200,int(screen.width()*.8)),min(800,int(screen.height()*.8)))
                rect.moveCenter(screen.center())
            target.setGeometry(rect)
        else:
            target._normal_scene_rect=target.geometry()
            target.showFullScreen()

    def _fullscreen_key(self,target=None):
        now=time.monotonic()
        if now-getattr(self,'_fullscreen_key_at',0)<.15:return
        self._fullscreen_key_at=now
        self._toggle_fullscreen(target)

    def _apply_forge_request(self,packet):
        if not isinstance(packet,dict):return
        if packet.get('action')=='pin_artifact':
            try:
                from core.forge_artifacts import pin_artifact
                pin_artifact(self,packet['data']);packet['result']={'ok':True}
            except Exception as error:packet['result']={'ok':False,'error':str(error)}
            if packet.get('done'):packet['done'].set()
            return
        if getattr(self,'_closed_for_shutdown',False):
            packet['result']={'ok':False,'error':'Jarvis encerrando.'}
            if packet.get('done'):packet['done'].set()
            return
        if self._forge_controller is None:
            if packet.get('action')!='enter':
                packet['result']={'ok':packet.get('action')=='exit','phase':'normal'}
                if packet.get('done'):packet['done'].set()
                return
            from core.forge_controller import ForgeController
            self._forge_controller=ForgeController(self)
        self._forge_controller.request(packet)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self,'_opening_veil',None) and not self._opening_veil.released:
            self._opening_veil.setGeometry(self._scene_stage.rect());self._opening_veil.raise_()
        if hasattr(self, "_floating_controls"):
            self._floating_controls.raise_()
        QTimer.singleShot(0, self._layout_scene)
        QTimer.singleShot(0, self._position_overlays)

    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.Type.WindowStateChange and hasattr(self,'_ui_sounds'):
            self._ui_sounds.scene(visible=self.isVisible() and not self.isMinimized() and self._environment.started)
        if event.type()==QEvent.Type.WindowStateChange and getattr(self,'_visual_scene',None):
            self._visual_scene.reflow(force=True)
        if event.type()==QEvent.Type.WindowStateChange and getattr(self,'_space_view',None):
            self._space_view.sync({'visible':self.isVisible() and not self.isMinimized(),
                'motion':'reduced' if _read_full_config().get('reduce_motion',False) else 'full'})

    def hideEvent(self,event):
        if hasattr(self,'_ui_sounds'):self._ui_sounds.stop()
        if getattr(self,'_space_view',None): self._space_view.sync({'visible':False})
        super().hideEvent(event)

    def closeEvent(self,event):
        self._closed_for_shutdown=True
        if getattr(self,'_spectro_controller',None):self._spectro_controller.close()
        if getattr(self,'_live_pins',None):self._live_pins.close()
        controller=getattr(self,'_forge_controller',None)
        if controller:controller.close()
        forge=getattr(self,'_forge_runtime',None)
        if forge:threading.Thread(target=forge.close,name='ForgeShutdown',daemon=True).start()
        runtime=getattr(self,'_ultron_runtime',None)
        if runtime:threading.Thread(target=runtime.close,name='UltronShutdown',daemon=True).start()
        from core.extension_suite import shutdown as shutdown_extensions
        shutdown_extensions()
        app=QApplication.instance()
        if app:app.removeEventFilter(self)
        cursor=getattr(self,'_idle_cursor',None)
        if cursor:cursor.dispose()
        if hasattr(self,'_ui_sounds'):self._ui_sounds.close()
        for timer in self.findChildren(QTimer):timer.stop()
        if SpatialCoreView:
            for view in self.findChildren(SpatialCoreView):
                view.stop();view.close()
        super().closeEvent(event)

    def showEvent(self,event):
        super().showEvent(event)
        QTimer.singleShot(0,self._prepare_initial_scene)
        if hasattr(self,'_ui_sounds') and self._environment.started:self._ui_sounds.scene(visible=not self.isMinimized())
        if getattr(self,'_space_view',None):self._space_view.sync({'visible':not self.isMinimized()})

    def _prepare_initial_scene(self):
        if getattr(self,'_closed_for_shutdown',False):return
        self.centralWidget().layout().activate()
        self._layout_scene()
        self._position_overlays()
        self._scene_layout_ready=True
        self._start_environment()

    def eventFilter(self, watched, event):
        from PyQt6 import sip
        if getattr(self,'_closed_for_shutdown',False) or sip.isdeleted(self) or isinstance(watched,QWidget) and sip.isdeleted(watched):return False
        owned=isinstance(watched,QWidget) and (watched is self or self.isAncestorOf(watched))
        settings=getattr(self,'_settings_hub',None)
        owned=owned or isinstance(watched,QWidget) and settings is not None and (watched is settings or settings.isAncestorOf(watched))
        mouse=event.type()==QEvent.Type.MouseButtonRelease and event.button()==Qt.MouseButton.LeftButton
        keyboard=event.type()==QEvent.Type.KeyPress and not event.isAutoRepeat() and event.key() in (Qt.Key.Key_Space,Qt.Key.Key_Return,Qt.Key.Key_Enter)
        if owned and isinstance(watched,QAbstractButton) and watched.isEnabled() and (keyboard or mouse and watched.rect().contains(event.position().toPoint())):
            if hasattr(self,'_ui_sounds'):self._ui_sounds.play('toggle' if watched.isCheckable() else 'click')
        elif owned and mouse and isinstance(watched,(QTabBar,QListWidget)):
            if hasattr(self,'_ui_sounds'):self._ui_sounds.play('navigation')
        if owned and event.type()==QEvent.Type.KeyPress and event.key()==Qt.Key.Key_F11:
            event.accept()
            if not event.isAutoRepeat():self._fullscreen_key(watched.window())
            return True
        if watched in (getattr(self,"_title_lbl",None),getattr(self,"_clock_lbl",None),getattr(self,"_date_lbl",None)):
            if event.type()==QEvent.Type.MouseButtonPress and event.button()==Qt.MouseButton.LeftButton:
                if self.windowHandle():
                    self.windowHandle().startSystemMove()
                return True
            if event.type()==QEvent.Type.MouseButtonDblClick:
                self.showNormal() if self.isMaximized() else self.showMaximized()
                return True
        if watched is getattr(self,"_scene_stage",None) and event.type()==QEvent.Type.Resize:
            self._layout_scene()
        return super().eventFilter(watched,event)

    def _connection_changed(self, connected, model):
        revision=getattr(self,'_connection_status',{}).get('revision',0)+1
        self._connection_status = {"connected":connected,"model":model,'revision':revision}
        if connected and not getattr(self,'_arrival_done',False):
            self._arrival_done = True
            self._ensure_content_renderer()
            if not _read_full_config().get('reduce_motion',False) and not self._environment.entrance:
                rect = self._center_split.geometry()
                initial = QRect(rect)
                initial.setSize(QSize(int(rect.width()*.82),int(rect.height()*.82)))
                initial.moveCenter(rect.center())
                self._center_split.setGeometry(initial)
                self._layout_scene(True, duration=1100)

    def _layout_scene(self, animate=False, duration=420):
        if not hasattr(self,"_scene_stage"):
            return
        animate=bool(animate and not self.hud.motion_reduced)
        forge=getattr(self,'_forge_controller',None)
        if forge and forge.active:
            forge.layout();return
        w,h=self._scene_stage.width(),self._scene_stage.height()
        veil=getattr(self,'_opening_veil',None)
        if veil and (not veil.released or veil.isVisible()):
            veil.setGeometry(self._scene_stage.rect())
        self._pin_layout_reserved=False
        self._position_pin()
        for layer in (getattr(self,'_space_fallback',None),self._space_view):
            if layer: layer.setGeometry(self._scene_stage.rect());layer.lower()
        if getattr(self,'_space_fallback',None):self._space_fallback.lower()
        active=self._content_panel.isVisible()
        kind=(self._presentation or {}).get("model",{}).get("kind","data")
        self.hud.news_projection=active and kind in ('news','status')
        if not active or kind != 'news':
            self.hud.news_content=None
            if self.hud._spatial_core:
                self.hud._spatial_core.sync_news(None)
        avatar=QRect(0,0,w,h)
        if not active and self._environment.override == 'exploration':
            avatar=QRect(int(w*.38),0,int(w*.62),h)
        elif not active and self._scene_position in ('left','right'):
            width=int(w*.65)
            avatar=QRect(0 if self._scene_position=='left' else w-width,0,width,h)
        target=QRect(int(w*.52),int(h*.1),int(w*.46),int(h*.87))
        if active:
            avatar=QRect(0,0,int(w*.57),h)
            if kind in ("news", "status"):
                avatar=QRect(0,0,w,h)
                target=QRect(int(w*.15),int(h*.15),int(w*.7),int(h*.7))
                if kind=='status' and (self._presentation or {}).get('model',{}).get('refreshTransaction'):
                    width=min(540,max(260,w-32));height=min(420,max(220,h-100))
                    target=QRect((w-width)//2,max(84,(h-height)//2),width,height)
            elif kind=="calendar":
                target=QRect(int(w*.44),int(h*.24),int(w*.53),int(h*.74))
            elif kind in ('gmail','whatsapp'):
                top=max(84,int(h*.10))
                height=int(h*.37)
                avatar_top=top+height+12
                avatar=QRect(int(w*.08),avatar_top,int(w*.84),max(100,h-avatar_top))
                target=QRect(int(w*.08),top,int(w*.84),height)
            if self._scene_position=="left" and kind not in ('news','status','gmail','whatsapp'):
                target.moveLeft(int(w*.02)); avatar.moveLeft(int(w*.43))
            elif self._scene_position=="center" and kind not in ('news','status','gmail','whatsapp'):
                target.moveLeft(int((w-target.width())/2)); avatar=QRect(0,0,int(w*.42),h)
        if self._avatar_anchor:
            x,y=self._avatar_anchor
            if not active:
                avatar.setWidth(int(w*.65));avatar.setHeight(int(h*.86))
            avatar.moveLeft(max(0,min(w-avatar.width(),int(w*x-avatar.width()/2))))
            avatar.moveTop(max(0,min(h-avatar.height(),int(h*y-avatar.height()/2))))
            if active and kind in ('news','status'):
                target=QRect(avatar.x()+int(avatar.width()*.15),avatar.y()+int(avatar.height()*.15),int(avatar.width()*.7),int(avatar.height()*.7))
        avatar,target=self._layout_workspace(avatar,target,active)
        workspace=[panel.geometry() for panel in (self._terminal,self._execution) if panel.isVisible()]
        if active and (self._pin_previews or workspace):
            target=self._fit_around_pins(target,workspace)
            if any(target.intersects(item['widget'].geometry()) for item in self._pin_previews.values()):
                # Temporarily condense previews rather than covering them with a
                # new answer. Saved user placements are restored when it closes.
                self._pin_layout_reserved=True
                self._position_pin()
                target=QRect(int(w*.51),84,max(1,int(w*.47)-12),max(1,h-96))
                target=self._fit_around_pins(target,workspace)
            if kind in ('news','status'):avatar=self._fit_around_pins(avatar,workspace)
            elif kind in ('gmail','whatsapp'):
                avatar_top=target.bottom()+12
                avatar=QRect(int(w*.08),avatar_top,int(w*.84),max(100,h-avatar_top))
        previous_animations=list(self._scene_animations)
        self._scene_animations=[]
        for widget,rect in ((self._center_split,avatar),(self._content_panel,target)):
            continuing=next((animation for animation in previous_animations
                if animation.targetObject() is widget and animation.endValue()==rect
                and animation.state()==QPropertyAnimation.State.Running),None)
            if animate and self.isVisible() and continuing:
                self._scene_animations.append(continuing);previous_animations.remove(continuing)
                continue
            for animation in list(previous_animations):
                if animation.targetObject() is widget:
                    animation.stop();animation.deleteLater();previous_animations.remove(animation)
            if animate and self.isVisible() and widget.geometry()!=rect:
                animation=QPropertyAnimation(widget,b"geometry",self)
                animation.setDuration(duration); animation.setEasingCurve(QEasingCurve.Type.OutCubic)
                animation.setStartValue(widget.geometry()); animation.setEndValue(rect)
                animation.start(); self._scene_animations.append(animation)
            else:
                widget.setGeometry(rect)
        for animation in previous_animations:
            animation.stop();animation.deleteLater()
        width=w
        for label,y,height in ((self._title_lbl,16,18),(self._clock_lbl,36,23),(self._date_lbl,60,15)):
            label.setGeometry(max(0,(width-220)//2),y,min(width,220),height)
            label.raise_()
        self._content_panel.raise_()
        self._position_pin()
        if animate and active and kind not in ('news','status') and not _read_full_config().get('reduce_motion',False):
            accents={'weather':'#8bcfea','tasks':'#70dfb7','calendar':'#efcc87','gmail':'#ee8881','whatsapp':'#71e2b0','memory':'#bdafe9'}
            self._projection_trace.begin(self._center_split.geometry().center(),target.center(),accents.get(kind,'#9bd0e8'))
        self._floating_controls.raise_()

        if veil and not veil.released:veil.raise_()
        if getattr(self,'_overlay',None) is not None and not self._ready:
            self._center_split.hide()
            self._overlay.raise_()

        if getattr(self,'_visual_scene',None):
            self._visual_scene.reflow()

    def _fit_around_pins(self, preferred, extra=()):
        obstacles=[rect.adjusted(-8,-8,8,8) for rect in [item['widget'].geometry() for item in self._pin_previews.values()]+list(extra)]
        if not any(preferred.intersects(obstacle) for obstacle in obstacles):return preferred
        stage=self._scene_stage
        candidates=[QRect(12,84,max(1,stage.width()-24),max(1,stage.height()-96))]
        # Subtract the pinned rectangles; choose the largest readable remaining region.
        for obstacle in obstacles:
            remaining=[]
            for rect in candidates:
                cut=rect.intersected(obstacle)
                if cut.isEmpty():remaining.append(rect);continue
                remaining.extend(candidate for candidate in (
                    QRect(rect.left(),rect.top(),cut.left()-rect.left(),rect.height()),
                    QRect(cut.right()+1,rect.top(),rect.right()-cut.right(),rect.height()),
                    QRect(rect.left(),rect.top(),rect.width(),cut.top()-rect.top()),
                    QRect(rect.left(),cut.bottom()+1,rect.width(),rect.bottom()-cut.bottom()))
                    if candidate.width()>=120 and candidate.height()>=100)
            candidates=remaining
        if not candidates:return preferred
        fitted=[]
        for region in candidates:
            width=min(region.width(),preferred.width());height=min(region.height(),preferred.height())
            x=max(region.left(),min(preferred.left(),region.right()-width+1))
            y=max(region.top(),min(preferred.top(),region.bottom()-height+1))
            fitted.append(QRect(x,y,width,height))
        return max(fitted,key=lambda rect:rect.width()*rect.height()-.1*(rect.center()-preferred.center()).manhattanLength())

    def _settle_presentation(self):
        if self._presentation and not self._pinned and not self.hud.speaking:
            token=self._presentation
            dismissal=uuid.uuid4().hex
            token['dismissal']=dismissal
            if self._content_spatial:
                self._content_spatial.page().runJavaScript("window.dismissPresentation && window.dismissPresentation()")
            def finish():
                if self._presentation is token and token.get('dismissal')==dismissal and not self.hud.speaking and not self._pinned:
                    self._presentation_history = (self._presentation_history + [token.copy()])[-8:]
                    self._presentation = None
                    self._presentation_clock.replace_scene()
                    self._content_panel.hide()
                    self._layout_scene(True)
            QTimer.singleShot(280,finish)

    def _open_existing_domain(self,kind):
        if self._resting:raise ValueError('O Jarvis está em repouso. Ative-o antes de abrir informações.')
        if (self._presentation or {}).get('model',{}).get('kind')!=kind:
            if kind in self._pin_previews:
                self._expand_pin(kind)
                return
            for index in range(len(self._presentation_history)-1,-1,-1):
                model=self._presentation_history[index]
                if model.get('model',{}).get('kind')==kind:
                    self._presentation_history.pop(index)
                    self._show_manifestation({**model['model'],'narrationDriven':False,'focus':model.get('focus',0)})
                    return
            raise ValueError('Consulte os dados com a ferramenta do domínio antes de apresentá-los.')
        self._presentation.pop('dismissal',None)
        self._settle_timer.stop()
        self._render_presentation()
        self._content_panel.show();self._layout_scene(True)

    def _narrate_presentation(self,text):
        content=text.get('text') if isinstance(text,dict) else text
        if not isinstance(content,str) or not content.strip():return
        neural_clock=getattr(self,'_neural_clock',None)
        if neural_clock and getattr(self,'_neural_request',None):
            neural_clock.enqueue(content,text.get('at') if isinstance(text,dict) else None,text.get('duration') if isinstance(text,dict) else None)
        if self._ultron_payload and self._ultron_payload.get('state',{}).get('phase')!='idle':
            self._ultron_clock.enqueue(content,text.get('at') if isinstance(text,dict) else None,text.get('duration') if isinstance(text,dict) else None)
        if getattr(self,'_visual_scene',None):self._visual_scene.enqueue(text)
        if self._presentation and self._presentation.get('narration_active') and not self._resting:
            if isinstance(text,dict):
                self._presentation_clock.enqueue(content,text.get('at'),text.get('duration'))
            else:
                self._presentation_clock.enqueue(text)

    def _reset_narration_timeline(self):
        self._narration_elapsed=0.
        clock=getattr(self,'_neural_clock',None)
        if clock:clock.reset()

    def _advance_presentation(self,seconds):
        from core.presentation_clock import valid_time
        if not valid_time(seconds) or seconds==0:return
        self._narration_elapsed=getattr(self,'_narration_elapsed',0.)+seconds
        neural_clock=getattr(self,'_neural_clock',None)
        if neural_clock and getattr(self,'_neural_request',None):
            neural_beat=neural_clock.advance(seconds)
            view=getattr(self.hud,'_spatial_core',None)
            if view:
                for cue in neural_beat.get('cues',[]):view.narrate_neural(cue)
        ultron_beat=self._ultron_clock.advance(seconds)
        if self._ultron_payload and self._ultron_payload.get('state',{}).get('phase')!='idle' and self._space_view:self._space_view.advance_ultron(ultron_beat)
        if getattr(self,'_visual_scene',None):self._visual_scene.advance(seconds)
        beat=self._presentation_clock.advance(seconds)
        if beat.get('cues'):
            self._environment.emit('attention')
        if self._presentation and self._presentation.get('narration_active') and not self._resting:
            self._presentation['audio_started']=True
            beat={**beat,'presentationId':self._presentation.get('model',{}).get('presentationId')}
            if self._content_spatial and not self._content_spatial.failed and self._content_spatial._loaded and self._content_panel.isVisible():
                self._content_spatial.page().runJavaScript("window.advancePresentation && window.advancePresentation("+json.dumps(beat,ensure_ascii=False)+")")
            elif beat.get('cues'):
                self._presentation['pending_beats']=(self._presentation.get('pending_beats',[])+[beat])[-32:]

    def _cancel_presentation(self):
        self._cancel_neural_memory()
        self._ultron_clock.cancel()
        if self._space_view:self._space_view.advance_ultron({'cancelled':True,'cues':[]})
        self._refresh_lock=None
        self._settle_timer.stop()
        if self._presentation:
            dismissing=self._presentation.pop('dismissal',None)
            self._presentation['narration_active']=False
            self._presentation['paused']=True
            self._presentation['pending_beats']=[]
            if dismissing:self._render_presentation()
        self._environment.interrupt()
        if getattr(self,'hud',None):self.hud.cancel_audio_animation()
        if getattr(self,'_visual_scene',None):self._visual_scene.cancel()
        self._presentation_clock.cancel()
        if self.hud.news_content and self.hud.news_content.get('mode') != 'front':
            self._set_news_phase('paused')
        self._projection_trace.stop()
        if self._content_spatial:
            self._content_spatial.page().runJavaScript("window.cancelPresentation && window.cancelPresentation()")

    def _resume_presentation(self):
        if self._resting:raise ValueError('O Jarvis está em repouso. Ative-o antes de retomar a apresentação.')
        if not self._presentation or not self._presentation.get('paused'):
            raise ValueError('Não há apresentação pausada. Consulte os dados ou selecione o contexto desejado.')
        self._presentation.update(narration_active=True,paused=False,audio_started=False,completed=False)
        self._presentation.setdefault('model',{})['narrationDriven']=True
        self._presentation_clock.resume()
        self._presentation.pop('dismissal',None)
        self._set_news_phase('fused')
        self._content_panel.show()
        self._render_presentation()
        self._layout_scene(True)
        if self._content_spatial:
            self._content_spatial.page().runJavaScript('window.resumePresentation && window.resumePresentation('+json.dumps(self._presentation_clock.elapsed)+')')

    def _avatar_interaction(self,action,x,y):
        if action=="touch":
            if self.hud.speaking:
                self._do_interrupt()
            self._resting=not self._resting
            self.hud.resting=self._resting
            if self._resting:
                self._content_panel.hide();self._layout_scene(True)
            self._cancel_presentation()
            if self.on_rest_toggle:
                self.on_rest_toggle(self._resting)
            self._apply_state("SLEEPING" if self._resting else "LISTENING")
        elif action=="move":
            rect=self._center_split.geometry()
            self._avatar_anchor=((rect.x()+x*rect.width())/max(1,self._scene_stage.width()),(rect.y()+y*rect.height())/max(1,self._scene_stage.height()))
            self._layout_scene(True)

    def _position_overlays(self):
        if not hasattr(self,"_cam_preview"):
            return
        if hasattr(self, "_pin_button"):
            self._position_pin()
        cw = self.centralWidget()
        if self._overlay and self._overlay.isVisible():
            ow, oh = 460, 390
            self._overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
            self._overlay.raise_()
        if self._remote_overlay and self._remote_overlay.isVisible():
            ow, oh = RemoteKeyOverlay._OW, RemoteKeyOverlay._OH
            self._remote_overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        if self._customize_overlay and self._customize_overlay.isVisible():
            ow, oh = CustomizeOverlay._OW, CustomizeOverlay._OH
            self._customize_overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        # Camera preview — bottom-right corner of the center/HUD area
        pw = _CameraPreview._W
        ph = self._cam_preview.height() or _CameraPreview._H
        self._cam_preview.setGeometry(
            cw.width() - _RIGHT_W - pw - 12,
            cw.height() - ph - 28,
            pw, ph,
        )
        # Clipboard panel — bottom-center
        if hasattr(self, '_clipboard_panel') and self._clipboard_panel.isVisible():
            self._position_clipboard_panel()
        # Quick drawer — reposition if open
        if hasattr(self, '_quick_drawer') and self._quick_drawer.isVisible():
            self._position_quick_drawer()
        if hasattr(self, '_ctrl_drawer') and self._ctrl_drawer.isVisible():
            self._position_ctrl_drawer()
        self._fit_video()

    def _update_metrics(self):
        snap = _metrics.snapshot()

        # CPU
        cpu = snap["cpu"]
        self._bar_cpu.set_value(cpu, f"{cpu:.0f}%")

        # MEM
        mem = snap["mem"]
        self._bar_mem.set_value(mem, f"{mem:.0f}%")

        # NET
        net = snap["net"]
        if net < 1.0:
            net_str = f"{net*1024:.0f}KB/s"
        else:
            net_str = f"{net:.1f}MB/s"
        net_pct = min(100, net * 10)  # 10 MB/s = %100
        self._bar_net.set_value(net_pct, net_str)

        # GPU
        gpu = snap["gpu"]
        if gpu >= 0:
            self._bar_gpu.set_value(gpu, f"{gpu:.0f}%")
        else:
            self._bar_gpu.set_value(0, "N/A")

        # TMP
        tmp = snap["tmp"]
        if tmp >= 0:
            tmp_pct = min(100, (tmp / 100) * 100)
            self._bar_tmp.set_value(tmp_pct, f"{tmp:.0f}°C")
        else:
            self._bar_tmp.set_value(0, "N/A")

        try:
            boot_t  = psutil.boot_time()
            elapsed = time.time() - boot_t
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            self._uptime_lbl.setText(f"TEMPO {h:02d}:{m:02d}")
        except Exception:
            self._uptime_lbl.setText('TEMPO --:--')

        try:
            proc_count = len(psutil.pids())
            self._proc_lbl.setText(f"PROC  {proc_count}")
        except Exception:
            self._proc_lbl.setText("PROC  --")


    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(42)
        w.setStyleSheet("background: transparent; border: none;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)

        def _badge(txt, color=C.TEXT_MED):
            l = QLabel(txt)
            l.setFont(QFont("Courier New", 8))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        from core.branding import StarButton
        self._drawer_btn = StarButton('Configurações do assistente',points=5)
        self._drawer_btn.setFont(QFont("Courier New", 11))
        self._drawer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._drawer_btn.setToolTip('Configurações e controles')
        self._drawer_btn.setCheckable(True)
        self._drawer_btn.setToolTip('Configurações do assistente')
        self._drawer_btn.clicked.connect(self._toggle_drawer)
        lay.addWidget(self._drawer_btn)

        from PyQt6.QtWidgets import QStyle
        from core.workspace_panels import panel_icon
        terminal_button=QPushButton()
        terminal_button.setIcon(panel_icon(self.style(),QStyle.StandardPixmap.SP_MessageBoxInformation))
        terminal_button.setFixedSize(26,26);terminal_button.setToolTip('Terminal de conversa')
        terminal_button.setAccessibleName('Terminal de conversa');terminal_button.setStyleSheet(self._drawer_btn.styleSheet())
        terminal_button.clicked.connect(self._open_terminal);lay.addWidget(terminal_button)
        lay.addStretch()

        mid = QVBoxLayout(); mid.setSpacing(1)
        _disp = self._assistant_name.upper()
        self._title_lbl = QLabel(_disp)
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_lbl.setFont(QFont("Courier New", 17, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        mid.addWidget(self._title_lbl)
        _sub_text = ('Seu assistente pessoal'
                     if _disp in ("JARVIS", "J.A.R.V.I.S")
                     else 'Assistente pessoal de IA')
        self._sub_lbl = QLabel(_sub_text)
        self._sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub_lbl.setFont(QFont("Courier New", 7))
        self._sub_lbl.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        mid.addWidget(self._sub_lbl)
        self._identity_layout = mid
        self._sub_lbl.hide()
        lay.addStretch()

        right_col = QVBoxLayout(); right_col.setSpacing(2)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._clock_lbl)
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(QFont("Courier New", 7))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        self._clock_layout = right_col
        return w

    def _tick_clock(self):
        self._clock_lbl.setText(time.strftime("%H:%M:%S"))
        self._date_lbl.setText(PT_BR.toString(QDate.currentDate(), "ddd dd MMM yyyy"))
        if (self._presentation and self._presentation.get("model", {}).get("kind") == "system"
                and self._content_panel.isVisible() and self.isVisible() and not self.isMinimized()
                and not self._telemetry_busy and time.monotonic() - self._telemetry_at >= 3):
            token = self._presentation
            self._telemetry_busy = True
            self._telemetry_at = time.monotonic()

            def sample():
                try:
                    from actions.system_monitor import get_system_status
                    metrics = get_system_status()
                except Exception:
                    metrics = None
                try:
                    self._telemetry_sig.emit(token, metrics)
                except RuntimeError:
                    pass

            threading.Thread(target=sample, daemon=True).start()

    def _receive_telemetry(self, token, metrics):
        self._telemetry_busy = False
        # An old sample must never reopen a scene the user dismissed or replaced.
        if metrics and self._presentation is token and self._content_panel.isVisible():
            self._presentation["model"].update(metrics)
            self._render_presentation()

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_LEFT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-right: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(6)

        hdr = QLabel('◈ SISTEMA')
        hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; "
                          f"border-bottom: 1px solid {C.BORDER}; padding-bottom: 4px;")
        lay.addWidget(hdr)
        lay.addSpacing(2)

        self._bar_cpu = MetricBar("CPU", C.PRI)
        self._bar_mem = MetricBar("MEM", C.ACC2)
        self._bar_net = MetricBar("NET", C.GREEN)
        self._bar_gpu = MetricBar("GPU", C.ACC)
        self._bar_tmp = MetricBar("TMP", "#ff6688")

        for bar in [self._bar_cpu, self._bar_mem, self._bar_net,
                    self._bar_gpu, self._bar_tmp]:
            lay.addWidget(bar)

        lay.addSpacing(4)

        info_panel = QWidget()
        info_panel.setStyleSheet(
            f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 4px;"
        )
        ip_lay = QVBoxLayout(info_panel)
        ip_lay.setContentsMargins(6, 5, 6, 5)
        ip_lay.setSpacing(3)

        self._uptime_lbl = QLabel('TEMPO --:--')
        self._uptime_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._uptime_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
        ip_lay.addWidget(self._uptime_lbl)

        self._proc_lbl = QLabel("PROC  --")
        self._proc_lbl.setFont(QFont("Courier New", 8))
        self._proc_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
        ip_lay.addWidget(self._proc_lbl)

        os_name = {"Windows": "WIN", "Darwin": "macOS", "Linux": "LINUX"}.get(_OS, _OS.upper())
        os_lbl = QLabel(f"SO  {os_name}")
        os_lbl.setFont(QFont("Courier New", 8))
        os_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent; border: none;")
        ip_lay.addWidget(os_lbl)

        lay.addWidget(info_panel)
        lay.addSpacing(4)

        lay.addStretch()

        for txt, col in [
            ('NÚCLEO IA\nATIVO',  C.GREEN),
            ('ACESSO\nPRONTO',     C.PRI),
            ('PROTOCOLO\n' + APP_PROTOCOL,   C.TEXT_DIM),
        ]:
            lbl = QLabel(txt)
            lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {col}; background: {C.PANEL2};"
                f"border: 1px solid {C.BORDER_A}; border-radius: 3px; padding: 4px;"
            )
            lay.addWidget(lbl)

        return w
    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_RIGHT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-left: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        def _sec(txt):
            l = QLabel(f"▸ {txt}")
            l.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            l.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            return l

        lay.addWidget(_sec('ATIVIDADE'))
        self._log = LogWidget()
        lay.addWidget(self._log, stretch=1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        lay.addWidget(_sec('ARQUIVOS'))
        self._drop_zone = FileDropZone()
        self._drop_zone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self._drop_zone)

        self._file_hint = QLabel('Nenhum arquivo. Solte ou clique acima.')
        self._file_hint.setFont(QFont("Courier New", 7))
        self._file_hint.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._file_hint.setWordWrap(True)
        lay.addWidget(self._file_hint)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep2)

        lay.addWidget(_sec('COMANDOS'))
        lay.addLayout(self._build_input_row())

        self._interrupt_btn = QPushButton('✋  INTERROMPER [ESC]')
        self._interrupt_btn.setFixedHeight(34)
        self._interrupt_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._interrupt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._interrupt_btn.setStyleSheet(f"""
            QPushButton {{
                background: #140008; color: {C.MUTED_C};
                border: 1px solid {C.MUTED_C}; border-radius: 3px;
            }}
            QPushButton:hover {{
                background: #200010; border: 1px solid #ff6688;
            }}
            QPushButton:pressed {{
                background: #300018;
            }}
        """)
        self._interrupt_btn.clicked.connect(self._do_interrupt)
        lay.addWidget(self._interrupt_btn)

        self._mute_btn = QPushButton('🎙  MICROFONE ATIVO')
        self._mute_btn.setFixedHeight(30)
        self._mute_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._style_mute_btn()
        lay.addWidget(self._mute_btn)

        return w

    def _build_quick_drawer(self) -> QWidget:
        """Floating overlay panel shown when the ⚙ header button is toggled."""
        _BTN_STYLE_PRI = f"""
            QPushButton {{
                background: #00091a; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
                text-align: left; padding: 0 8px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
        """
        _BTN_STYLE_DIM = f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
                text-align: left; padding: 0 8px;
            }}
            QPushButton:hover {{ color: {C.PRI}; border-color: {C.BORDER_B}; }}
        """

        self._BTN_PRI, self._BTN_DIM = _BTN_STYLE_PRI, _BTN_STYLE_DIM
        w = _FuiOverlay(self.centralWidget())
        w.setObjectName("QuickDrawer")
        w.setStyleSheet(f"""
            QWidget#QuickDrawer {{
                background: {C.DARK};
                border: 1px solid {C.BORDER_B};
                border-top: none;
                border-radius: 0 0 6px 6px;
            }}
        """)
        w.hide()

        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(5)

        hdr = QLabel('◈ CONFIGURAÇÕES')
        hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent; "
                          f"border-bottom: 1px solid {C.BORDER}; padding-bottom: 4px;")
        lay.addWidget(hdr)

        remote_btn = QPushButton('◉  ACESSO REMOTO')
        remote_btn.setFixedHeight(30)
        remote_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        remote_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remote_btn.setStyleSheet(_BTN_STYLE_PRI)
        remote_btn.clicked.connect(self._open_remote)
        lay.addWidget(remote_btn)

        sc_btn = QPushButton('⊞  CRIAR ATALHO')
        sc_btn.setFixedHeight(26)
        sc_btn.setFont(QFont("Courier New", 7))
        sc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sc_btn.setStyleSheet(_BTN_STYLE_DIM)
        sc_btn.clicked.connect(self._create_desktop_shortcut)
        lay.addWidget(sc_btn)

        self._autostart_btn = QPushButton('◉  INÍCIO AUTOM.: NÃO')
        self._autostart_btn.setFixedHeight(26)
        self._autostart_btn.setFont(QFont("Courier New", 7))
        self._autostart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._autostart_btn.clicked.connect(self._toggle_autostart)
        lay.addWidget(self._autostart_btn)

        cust_btn = QPushButton('⚙  PERSONALIZAR')
        cust_btn.setFixedHeight(26)
        cust_btn.setFont(QFont("Courier New", 7))
        cust_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cust_btn.setStyleSheet(_BTN_STYLE_DIM)
        cust_btn.clicked.connect(self._open_customize)
        lay.addWidget(cust_btn)

        audio_btn = QPushButton('🎧  ÁUDIO')
        audio_btn.setFixedHeight(26)
        audio_btn.setFont(QFont("Courier New", 7))
        audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        audio_btn.setStyleSheet(_BTN_STYLE_DIM)
        audio_btn.clicked.connect(self._open_audio_devices)
        lay.addWidget(audio_btn)

        mem_btn = QPushButton('🧠  MEMÓRIA')
        mem_btn.setFixedHeight(26)
        mem_btn.setFont(QFont("Courier New", 7))
        mem_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mem_btn.setStyleSheet(_BTN_STYLE_DIM)
        mem_btn.clicked.connect(self._open_memory_panel)
        lay.addWidget(mem_btn)

        plugin_btn = QPushButton("🧩  PLUGINS")
        plugin_btn.setFixedHeight(26)
        plugin_btn.setFont(QFont("Courier New", 7))
        plugin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        plugin_btn.setStyleSheet(_BTN_STYLE_DIM)
        plugin_btn.clicked.connect(self._open_plugin_manager)
        lay.addWidget(plugin_btn)

        settings_btn = QPushButton('⚙  CONFIG. PLUGINS')
        settings_btn.setFixedHeight(26)
        settings_btn.setFont(QFont("Courier New", 7))
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setStyleSheet(_BTN_STYLE_DIM)
        settings_btn.clicked.connect(self._open_plugin_settings)
        lay.addWidget(settings_btn)

        w.adjustSize()
        return w

    def _build_controls_drawer(self) -> QWidget:
        """The switches that get flicked every day, in their own panel."""
        w = _FuiOverlay(self.centralWidget())
        w.setObjectName("QuickDrawer")
        w.setStyleSheet(self._quick_drawer.styleSheet())
        w.hide()

        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(5)

        hdr = QLabel('◈ CONTROLES')
        hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent; "
                          f"border-bottom: 1px solid {C.BORDER}; padding-bottom: 4px;")
        lay.addWidget(hdr)

        def _row(button, style=None, height=26):
            button.setFixedHeight(height)
            button.setFont(QFont("Courier New", 7))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if style:
                button.setStyleSheet(style)
            lay.addWidget(button)
            return button

        fs_btn = _row(QPushButton('⛶  TELA CHEIA [F11]'), self._BTN_DIM)
        fs_btn.clicked.connect(self._toggle_fullscreen)

        self._brief_btn = _row(QPushButton())
        self._brief_btn.setToolTip("Apresentar um resumo ao iniciar o assistente.")
        self._brief_btn.clicked.connect(self._toggle_brief)

        self._wake_btn = _row(QPushButton())
        self._wake_btn.setToolTip("Ouvir apenas após a chamada 'Hey Jarvis'.")
        self._wake_btn.clicked.connect(self._toggle_wake_word)
        self._wake_sleep_btn = _row(QPushButton())
        self._wake_sleep_btn.clicked.connect(self._tap_wake_manual)
        # Neutral until the real state lands from the background warm-up.
        self._wake_btn.setText('🎙  ATIVAÇÃO POR VOZ')
        self._wake_btn.setStyleSheet(self._BTN_DIM)
        self._wake_sleep_btn.hide()

        self._ptt_btn = _row(QPushButton())
        self._ptt_btn.clicked.connect(self._toggle_ptt)
        self._refresh_talk_btns()

        self._hud_btn = _row(QPushButton())
        self._hud_btn.clicked.connect(self._toggle_hud_style)
        self._refresh_hud_btn()

        w.adjustSize()
        return w

    def _warm_wake_state(self) -> None:
        """Work out the wake-word state off the UI thread, once.

        It used to be resolved when the drawer opened, and that made opening the
        drawer take two seconds the first time — measured at 2.10s, all of it
        `import openwakeword` dragging in onnxruntime behind it. The button
        count had nothing to do with it; the Qt thread was simply waiting on an
        import. Afterwards the same check costs about a millisecond, so it only
        ever needed to happen somewhere other than in front of the user.
        """
        def work():
            try:
                self._wake_state()
            except Exception:
                pass
            try:
                self._wake_btns_sig.emit()
            except RuntimeError:
                pass  # The window may close while the background import finishes.
        threading.Thread(target=work, daemon=True, name="wake-state-warm").start()

    def _toggle_drawer(self, checked: bool):
        if checked:
            from core.settings_hub import SettingsHub
            if getattr(self,"_settings_hub",None):
                self._settings_hub.close()
                self._settings_hub.deleteLater()
            self._settings_hub=SettingsHub(self,API_FILE,C)
            self._settings_hub.showFullScreen()
            self._drawer_btn.setChecked(False)
            return
            self._close_controls()
            self._position_quick_drawer()
            self._quick_drawer.show()
            self._quick_drawer.raise_()
        else:
            self._quick_drawer.hide()

    def _open_settings_tab(self,index):
        self._toggle_drawer(True)
        if isinstance(index,str):
            self._settings_hub.open_page(index)
            return
        self._settings_hub.tabs.setCurrentIndex(index)
        self._settings_hub.navigation.setCurrentRow(index)

    def _toggle_controls(self, checked: bool):
        if checked:
            self._open_settings_tab('profile')

    def _close_setup(self):
        if getattr(self,"_settings_hub",None):
            self._settings_hub.close()
        if hasattr(self, "_quick_drawer"):
            self._quick_drawer.hide()
        if hasattr(self, "_drawer_btn"):
            self._drawer_btn.setChecked(False)

    def _close_controls(self):
        if hasattr(self, "_ctrl_drawer"):
            self._ctrl_drawer.hide()
        if hasattr(self, "_ctrl_btn"):
            self._ctrl_btn.setChecked(False)

    def _place_drawer(self, drawer, left: int):
        _W = 220
        drawer.setFixedWidth(_W)
        drawer.adjustSize()
        drawer.setGeometry(left, 54, _W, drawer.sizeHint().height())

    def _position_quick_drawer(self):
        if hasattr(self, "_quick_drawer"):
            self._place_drawer(self._quick_drawer, 12)

    def _position_ctrl_drawer(self):
        # Under its own header button rather than under the other one's.
        if hasattr(self, "_ctrl_drawer"):
            left = 12
            try:
                left = max(12, self._ctrl_btn.mapTo(self.centralWidget(),
                                                    QPoint(0, 0)).x() - 8)
            except Exception:
                pass
            self._place_drawer(self._ctrl_drawer, left)

    def _build_input_row(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(5)
        self._input = QLineEdit()
        self._input.setPlaceholderText('Digite um comando ou pergunta…')
        self._input.setFont(QFont("Courier New", 9))
        self._input.setFixedHeight(30)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d14; color: {C.WHITE};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 3px 7px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input)

        send = QPushButton("▸")
        send.setFixedSize(30, 30)
        send.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        send.clicked.connect(self._send)
        row.addWidget(send)
        return row

    def _build_content_panel(self) -> QWidget:
        """
        Collapsible panel below the HUD — shows search results, news, briefings.
        Hidden by default; appears when show_content() is called.
        """
        w = QWidget()
        w.setObjectName("ContentPanel")
        w.setStyleSheet(f"""
            QWidget#ContentPanel {{
                background: transparent;
                border: none;
            }}
        """)
        w.hide()

        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 7, 12, 8)
        lay.setSpacing(5)

        # ── header row ───────────────────────────────────────────────────────
        hdr = QHBoxLayout(); hdr.setSpacing(6)

        dot = QLabel("◈")
        dot.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        dot.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(dot)

        self._content_title_lbl = QLabel('RESUMO')
        self._content_title_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._content_title_lbl.setStyleSheet(
            f"color: {C.PRI}; background: transparent; letter-spacing: 1px;"
        )
        hdr.addWidget(self._content_title_lbl)
        hdr.addStretch()

        self._content_ts_lbl = QLabel("")
        self._content_ts_lbl.setFont(QFont("Courier New", 7))
        self._content_ts_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        hdr.addWidget(self._content_ts_lbl)

        lay.addLayout(hdr)

        # ── separator ─────────────────────────────────────────────────────────
        self._presentation_header = QWidget()
        # The native header is only the fallback; spatial content has its own controls.
        self._presentation_header.hide()

        # ── text display ──────────────────────────────────────────────────────
        self._content_display = QTextEdit()
        self._content_display.setReadOnly(True)
        self._content_display.setFont(QFont("Segoe UI", 12))
        self._content_display.setMinimumHeight(60)
        self._content_display.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._content_display.setStyleSheet(f"""
            QTextEdit {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #0d2029,stop:1 #061218);
                color: {C.WHITE};
                border: 1px solid #368798;
                border-top-color: #ff5862;
                border-bottom-color: #ff5862;
                border-radius: 6px;
                padding: 13px 17px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: {C.BG}; width: 6px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B}; border-radius: 3px; min-height: 16px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0; border: none;
            }}
        """)
        lay.addWidget(self._content_display)
        self._content_spatial = None
        self._content_layout = lay
        self._native_content_header = hdr

        return w

    def _show_content(self, title: str, text: str, model_data=None):
        """Slot — runs on Qt main thread. Updates and shows the content panel."""
        spectro=getattr(self,'_spectro_controller',None)
        if spectro and spectro.active:
            if spectro.ready:spectro.apply('note',{'text':str(title)+': '+str(text)[:180]})
            return
        import time as _time
        previous_data=(self._presentation or {}).get('model',{})
        changed_context=any(previous_data.get(key)!=(model_data or {}).get(key) for key in ('kind','city','period','contact','reading'))
        if self._presentation and (self._presentation.get("title") != title or changed_context) and previous_data.get('kind') != 'status':
            self._presentation_history.append(self._presentation.copy())
            self._presentation_history = self._presentation_history[-8:]
        self._presentation = {"title": title, "text": text, "focus": 0}
        self._presentation['narration_active']=bool((model_data or {}).get('narrationDriven'))
        self._presentation['audio_started']=False
        self._presentation['paused']=False
        self._presentation['pending_beats']=[]
        if model_data:
            self._presentation["model"] = dict(model_data)
            self._presentation["focus"] = model_data.get("focus", 0)
        self._pinned = False
        if not model_data or model_data.get('kind') not in ('status','news'):
            self.hud.glance(0.7, 0.0, hold=1.3)
        self._content_title_lbl.setText(title.upper()[:48])
        self._content_ts_lbl.setText(_time.strftime("%H:%M:%S"))
        self._render_presentation()
        self._content_display.moveCursor(
            self._content_display.textCursor().MoveOperation.Start
        )
        first_show = not self._content_panel.isVisible()
        self._content_panel.show()
        self._settle_timer.stop()
        if not self.hud.speaking and not self._presentation['narration_active'] and (model_data or {}).get('kind') != 'status':
            hold = _read_full_config().get('presentation_hold', 15)
            if isinstance(hold, (int, float)) and hold > 0:
                self._settle_timer.start(int(min(120, hold) * 1000))
        self._scene_position="auto"
        self._layout_scene(first_show)

    def _cancel_neural_memory(self):
        if getattr(self,'_neural_request',None) is None:return
        self._neural_request=None
        clock=getattr(self,'_neural_clock',None)
        if clock:clock.cancel()
        view=getattr(self.hud,'_spatial_core',None)
        if view:view.cancel_neural()

    def _finish_neural_memory(self,request_id):
        if request_id!=getattr(self,'_neural_request',None):return
        self._neural_request=None
        clock=getattr(self,'_neural_clock',None)
        if clock:clock.cancel()

    def _update_neural_memory(self, payload):
        if not isinstance(payload,dict):return
        view=getattr(self.hud,'_spatial_core',None)
        forge=getattr(self,'_forge_controller',None)
        settings=getattr(self,'_settings_hub',None)
        if self._resting or (forge and forge.active) or (settings and settings.isVisible()):return
        if (getattr(self,'_ultron_payload',None) or {}).get('state',{}).get('phase','idle')!='idle':return
        if payload.get('pending'):
            self._neural_request=payload.get('requestId')
            from core.presentation_clock import PresentationClock
            self._neural_clock=PresentationClock()
            self._neural_clock.elapsed=getattr(self,'_narration_elapsed',0.)
            self._neural_clock.next_cue=self._neural_clock.elapsed
            self.hud.news_content=None
            if view:view.sync_news(None)
            if self._presentation and not self._pinned:
                self._presentation_history=(self._presentation_history+[self._presentation.copy()])[-8:]
                self._presentation=None
                self._presentation_clock.replace_scene()
                self._settle_timer.stop()
                self._content_panel.hide()
                self._layout_scene(True)
        elif payload.get('requestId')!=getattr(self,'_neural_request',None):return
        if view and not view.failed:view.sync_neural(payload)
        elif payload.get('active'):
            items=payload.get('items',[])
            text=json.dumps(items,ensure_ascii=False) if items else 'Qual assunto deseja consultar?' if payload.get('awaitingTopic') else 'Consulta sem lembrancas disponiveis para projetar.'
            self._show_content('MEMORIA',text,{'kind':'memory','items':items})
            self._finish_neural_memory(payload.get('requestId'))
        if not payload.get('pending') and payload.get('active') is False:self._finish_neural_memory(payload.get('requestId'))

    def _show_verified_manifestation(self, packet):
        if packet['cancelled'].is_set():return
        previous=self._presentation
        try:
            self._show_manifestation(packet['model'])
            packet['accepted']=self._presentation is not None and self._presentation is not previous
        except Exception:
            packet['accepted']=False
        finally:
            packet['done'].set()

    def _show_manifestation(self, data):
        spectro=getattr(self,'_spectro_controller',None)
        if spectro and spectro.active and isinstance(data,dict):
            if data.get('kind')=='status-end':return
            if spectro.ready:
                from core.spectro_summary import summary
                spectro.apply('note',{'text':summary(data)})
            return
        if isinstance(data,dict) and data.get('kind')=='memory':
            if getattr(self,'_neural_request',None):return
            from core.neural_memory import retrieval_payload
            identifier=uuid.uuid4().hex
            self._update_neural_memory({'requestId':identifier,'pending':True})
            self._update_neural_memory(retrieval_payload({'ok':True,'items':data.get('items',[]),'source':data.get('source')},identifier))
            return
        if isinstance(data,dict) and data.get('kind') not in ('status','status-end'):self._cancel_neural_memory()
        if isinstance(data,dict) and data.get('kind') == 'status-end':
            if getattr(self,'_refresh_lock',None)==data.get('id'):self._refresh_lock=None
            refresh_view=getattr(self,'_daily_refresh_view',None)
            if refresh_view:refresh_view.finish(data.get('id'),failed=bool(data.get('retain')))
            current = (self._presentation or {}).get('model',{})
            if data.get('retain') and current.get('kind')=='status' and current.get('id')==data.get('id'):
                self._settle_timer.start(15000)
                return
            if data.get('id') is not None and current.get('kind') == 'status' and current.get('id') == data.get('id'):
                self._content_panel.hide(); self._presentation=None; self._layout_scene(True)
            return
        forge=getattr(self,'_forge_controller',None)
        if forge and forge.active:return
        if not isinstance(data, dict) or data.get("kind") not in ("weather", "system", "tasks", "calendar", "news", "files", "data", "memory", "search", "status", "gmail", "whatsapp"):
            return
        lock=getattr(self,'_refresh_lock',None)
        if lock and data.get('id')!=lock and data.get('refreshOwner')!=lock:return
        if data.get('refreshTransaction') and data.get('id'):
            if not lock:
                self._ui_sounds.play('refresh-start')
                if self._presentation and not self._pinned:
                    self._presentation_history=(self._presentation_history+[self._presentation.copy()])[-8:]
                    self._presentation=None
                    self._content_panel.hide()
                    self._settle_timer.stop()
                    self._presentation_clock.replace_scene()
                    self._layout_scene(True)
                scene=getattr(self,'_visual_scene',None)
                if scene:scene.clear_all(preserve_pinned=True)
            self._refresh_lock=data['id']
            if not getattr(self,'_daily_refresh_view',None):
                from core.daily_refresh_view import DailyRefreshView
                self._daily_refresh_view=DailyRefreshView(self._scene_stage)
            self._daily_refresh_view.update_model(data)
            return
        if data.get('refreshOwner') and getattr(self,'_daily_refresh_view',None):
            self._daily_refresh_view.finish(data['refreshOwner'])
        from core.presentation_model import normalize_model
        data=normalize_model(data)
        if not self._pending_image_pin:self._terminal.hide()
        if self._environment.operation not in ('running','pending'):self._execution.hide()
        self.hud.semantic_cue('projection')
        if data.get('kind')!='status':self._ui_sounds.play('projection')
        if data['kind'] in self._pin_previews:
            from core.live_pins import specification
            previous_pin=self._pin_previews[data['kind']]['data']
            current_spec=specification(data)
            same_source=current_spec is not None and current_spec==specification(previous_pin)
            if same_source:self._update_pin(data['kind'],data)
        data={**data,'compact':False,'framed':False}
        previous=(self._presentation or {}).get('model',{})
        if data.get('kind') == 'status' and data.get('id') is not None and previous.get('kind')=='status' and previous.get('id') == data.get('id'):
            data['presentationId']=previous.get('presentationId')
            self._presentation.update(model=data,title=data.get('title') or self._presentation['title'],text=json.dumps(data,ensure_ascii=False))
            self._render_presentation()
            return
        if self._resting:
            self._presentation_history=(self._presentation_history+[{'title':data.get('title','INFORMAÇÕES'),'text':json.dumps(data,ensure_ascii=False),'model':dict(data),'focus':0}])[-8:]
            return
        self._presentation_clock.replace_scene()
        self._avatar_anchor=None
        data={**data,'presentationId':uuid.uuid4().hex}
        self._show_content(data.get("title", "INFORMAÇÕES"), json.dumps(data, ensure_ascii=False), data)

    def _spatial_navigation(self, url):
        fragment = url.fragment()
        if fragment.startswith('speech-focus-') and self._presentation:
            if self._presentation.get('paused') or self._presentation.get('completed'):return
            try:
                index=int(fragment.split('-')[2])
                parts=fragment.split('-',4)
                if len(parts)!=5 or str(self._presentation.get('model',{}).get('presentationId')) != parts[4]:
                    return
                if 0<=index<len(self._presentation.get('items',[])):
                    self._presentation['focus']=index
                    if self.hud.news_content:
                        self.hud.news_content={**self.hud.news_content,'focus':index}
                        if self.hud._spatial_core and not self.hud._spatial_core.failed:
                            self.hud._spatial_core.sync_news(self.hud.news_content)
            except (ValueError,IndexError):
                pass
            return
        if fragment.startswith("dismiss"):
            self._apply_interface_request({"action": "clear", "done": threading.Event()})
        elif fragment.startswith("focus-") and self._presentation:
            try:
                self._apply_interface_request({"action": "focus", "value": str(int(fragment[6:].split("-")[0]) + 1), "done": threading.Event()})
            except ValueError:
                pass

    def _ensure_content_renderer(self):
        if self._content_spatial is None and SpatialCoreView and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            self._content_spatial = SpatialCoreView(self._content_panel, "presentation.html")
            self._content_spatial.page().setBackgroundColor(QColor(Qt.GlobalColor.transparent))
            self._content_spatial.unavailable.connect(self._render_presentation)
            self._content_spatial.page().urlChanged.connect(self._spatial_navigation)
            self._content_spatial.loadFinished.connect(self._presentation_loaded)
            self._content_layout.addWidget(self._content_spatial, stretch=1)
            self._content_spatial.sync({'visible':False})

    def _presentation_loaded(self, loaded):
        if not loaded or not self._presentation:return
        self._render_presentation()
        pending=self._presentation.get('pending_beats',[])
        self._presentation['pending_beats']=[]
        if (pending or self._presentation.get('audio_started')) and self._content_spatial and not self._content_spatial.failed:
            beat={'elapsed':self._presentation_clock.elapsed,'cues':[text for entry in pending for text in entry.get('cues',[])],
                  'presentationId':self._presentation.get('model',{}).get('presentationId')}
            self._content_spatial.page().runJavaScript('window.advancePresentation && window.advancePresentation('+json.dumps(beat)+')')
        if self._presentation.get('paused') and self._content_spatial:
            self._content_spatial.page().runJavaScript('window.cancelPresentation && window.cancelPresentation()')
        if self._presentation.get('completed') and self._content_spatial:
            self._content_spatial.page().runJavaScript('window.finishPresentation && window.finishPresentation()')

    def _sync_presentation_view(self, data):
        self._ensure_content_renderer()
        ready = self._content_spatial and not self._content_spatial.failed
        self._content_display.setStyleSheet(f'QTextEdit {{ background:transparent; color:{C.WHITE}; border:0; padding:4px; }}')
        self._content_display.setVisible(not ready)
        for i in range(self._native_content_header.count()):
            widget = self._native_content_header.itemAt(i).widget()
            if widget:
                widget.setVisible(not ready)
        if ready:
            self._content_spatial.show()
            core=self.hud._spatial_core
            fused=(data.get('kind')=='news'
                   and self.hud.hud_style=='core' and core is not None and not core.failed and bool(core._loaded)
                   and bool(data.get('items')))
            if fused:
                self.hud.news_content={'id':data.get('newsSequenceId',data.get('presentationId')),
                    'items':data['items'],'focus':self._presentation.get('focus',0),
                    'mode':'paused' if data.get('newsPhase')=='paused' else 'fused' if self._presentation.get('narration_active') else 'settled','color':C.PRI}
                core.sync_news(self.hud.news_content)
            else:
                self.hud.news_content=None
                if core:core.sync_news(None)
            self._content_spatial.sync({**data, "narrationDriven":bool(data.get('narrationDriven') and (self._presentation.get('narration_active') or self._presentation.get('paused'))), "audioOrigin": self._presentation_clock.elapsed,
                "newsFusion":fused,"color": C.PRI, "focus": self._presentation.get("focus", 0),"motion":"reduced" if _read_full_config().get('reduce_motion',False) else 'full'})
        elif self.hud._spatial_core:
            self.hud.news_content=None
            self.hud._spatial_core.sync_news(None)

    def _set_news_phase(self, phase):
        if phase=='front':phase='settled'
        data=(self._presentation or {}).get('model',{})
        if data.get('kind')!='news':
            return
        data['newsPhase']=phase
        if not self.hud.news_content:
            if phase=='front' and self._content_spatial:
                self._content_spatial.page().runJavaScript('window.setNewsFusion && window.setNewsFusion(false)')
            return
        self.hud.news_content={**self.hud.news_content,'mode':phase}
        self.hud._spatial_core.sync_news(self.hud.news_content)
        if phase=='front' and self._content_spatial:
            self._content_spatial.page().runJavaScript('window.setNewsFusion && window.setNewsFusion(false)')

    def _render_presentation(self):
        if not self._presentation:return
        import re
        model = self._presentation or {}
        text = model.get("text", "")
        items = [item.strip() for item in re.split(r"(?m)^\d+[.)]\s+", text)[1:]][:12]
        model["items"] = items
        data = model.get("model")
        if data:
            from core.presentation_model import shown_number,record_text
            model["items"] = data.get("items", [])
            lines = [data.get("city", ""), data.get("condition", ""), data.get("error", "")]
            if data["kind"] == "weather" and "temperature" in data:
                lines += [f'{shown_number(data["temperature"])}°C', f'Chuva: {shown_number(data.get("rain"))}% · Vento: {shown_number(data.get("wind"))} km/h']
            elif data["kind"] == "system":
                lines += [f'{label}: {shown_number(data.get(key))}{unit}' for key,label,unit in
                          (('cpu_percent','CPU','%'),('ram_percent','RAM','%'),('gpu_percent','GPU','%'),('cpu_temp_c','Temperatura','°C'))]
            elif data['kind']=='tasks':
                lines += [f'{shown_number(data.get("count"))} tarefas pendentes']
            lines += [record_text(item) for item in data.get("items", [])]
            if not any(lines):
                lines = ["Nenhum registro local disponível."]
            self._content_display.setPlainText("\n\n".join(line for line in lines if line))
            self._sync_presentation_view(data)
            return
        if items and "NOTÍCIA" in model.get("title", "").upper():
            focus = min(model.get("focus", 0), len(items) - 1)
            blocks = []
            for i, item in enumerate(items):
                lines = item.splitlines()
                size = 20 if i == focus else 12
                color = C.WHITE if i == focus else C.TEXT_MED
                blocks.append(f'<div style="margin:12px 0 22px 0;color:{color}"><small>{i+1:02d}</small><h2 style="font-size:{size}px;font-weight:normal;margin:7px 0">{self._esc(lines[0])}</h2>')
                if i == focus:
                    blocks.append(f'<p style="font-size:13px;line-height:1.5">{self._esc(chr(10).join(lines[1:]))}</p>')
                blocks.append('</div>')
            self._content_display.setHtml(''.join(blocks))
        else:
            self._content_display.setPlainText(text)
        kind = "news" if "NOTÍCIA" in model.get("title", "").upper() else "data"
        self._sync_presentation_view({"kind": kind, "title": model.get("title", ""), "text": text,
            "items": [{"title": item.splitlines()[0], "detail": "\n".join(item.splitlines()[1:])} for item in items]})

    def _toggle_command_bar(self):
        self._command_bar.setVisible(not self._command_bar.isVisible())
        if self._command_bar.isVisible():
            self._input.setFocus()

    def _restore_pin(self):
        if self._pinned_context:
            kind=self._pinned_context.get('model',{}).get('kind')
            if kind in self._pin_previews:
                self._expand_pin(kind)
                self._pinned_context=copy.deepcopy(self._presentation)
                self._pinned=True
                return
            model = self._pinned_context.copy()
            if model.get("model"):
                self._show_manifestation({**model["model"],"narrationDriven":False})
            else:
                self._show_content(model["title"], model["text"])
            self._presentation["focus"] = model.get("focus", 0)
            self._render_presentation()
            self._pinned = True

    def _pin_data(self, data):
        if isinstance(data,dict) and data.get('kind')=='forge_artifact':
            from core.forge_artifacts import pin_artifact
            return pin_artifact(self,data)
        self._ui_sounds.play('pin')
        from core.presentation_model import normalize_model
        data=normalize_model(data)
        kind=data['kind']
        prior_keys=self._pin_capacity()
        previous=copy.deepcopy(self._pin_previews[kind]['data']) if kind in self._pin_previews else None
        if kind not in self._pin_previews:
            if kind not in prior_keys and len(prior_keys)>=6:
                raise ValueError('Ja ha seis previas fixadas. Desfixe uma antes de adicionar outra.')
            from core.hud_glass import PinnedPreviewFrame
            frame=PinnedPreviewFrame(self._scene_stage)
            frame.set_motion_reduced(_read_full_config().get('reduce_motion',False))
            frame.setObjectName('PinnedPreview')
            from core.observatory_theme import ACCENTS
            accent=ACCENTS.get(kind,'#8dcaff')
            frame.set_accent(accent)
            frame.setStyleSheet(f'QFrame#PinnedPreview {{ background:transparent; border:0; border-radius:14px; }} QLabel {{ border:0; background:transparent; color:#edfaff; }} QPushButton {{ border:0; color:{accent}; background:transparent; padding:3px; }} QPushButton:hover {{ background:#1c2b34; }}')
            layout=QVBoxLayout(frame);layout.setContentsMargins(12,12,12,10);layout.setSpacing(3)
            header=QHBoxLayout()
            from core.ui_assets import SERVICES,symbol_pixmap
            mark=QLabel(frame);mark.setPixmap(symbol_pixmap(SERVICES.get(kind,('box',accent))[0],accent,18));mark.setFixedSize(22,22);header.addWidget(mark)
            restore=QLabel(data.get('title',kind),frame)
            restore.setTextFormat(Qt.TextFormat.PlainText)
            restore.setFont(QFont('Segoe UI',10,QFont.Weight.DemiBold))
            header.addWidget(restore,1);layout.addLayout(header)
            label=QLabel(frame);label.setTextFormat(Qt.TextFormat.PlainText);label.setWordWrap(True)
            label.setMinimumSize(1,1);label.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Ignored);layout.addWidget(label,1)
            view=None
            if SpatialCoreView and os.environ.get('QT_QPA_PLATFORM')!='offscreen':
                view=SpatialCoreView(frame,'presentation.html');layout.addWidget(view,1)
                view.page().setBackgroundColor(QColor(Qt.GlobalColor.transparent))
                view.unavailable.connect(lambda k=kind:self._pin_fallback(k))
                view.ready.connect(lambda k=kind,v=view:self._pin_ready(k,v))
            self._pin_previews[kind]={'widget':frame,'view':view,'label':label,'data':{},'restore':restore,'accent':accent}
        if self._update_pin(kind,data) is False:
            if previous is None:
                rejected=self._pin_previews.pop(kind)
                if rejected['view']:rejected['view'].sync({'visible':False})
                rejected['widget'].hide();rejected['widget'].deleteLater()
            else:
                self._update_pin(kind,previous,persist=False)
            raise ValueError('Nao consegui salvar a previa. O cache anterior foi preservado.')
        self._pin_previews[kind]['widget'].show()
        self._position_pin()
        if not _read_full_config().get('reduce_motion',False):
            self._projection_trace.begin(self._center_split.geometry().center(),self._pin_previews[kind]['widget'].geometry().center(),self._pin_previews[kind]['accent'],compact=True)

    def _pin_fallback(self,kind):
        preview=self._pin_previews.get(kind)
        if preview:
            preview['label'].show()
            if preview['view']:
                preview['view'].hide()

    def _pin_ready(self,kind,view):
        preview=self._pin_previews.get(kind)
        if preview and preview['view'] is view and not view.failed:
            preview['label'].hide()

    def _tick_live_pins(self):
        if getattr(self,'_closed_for_shutdown',False) or not self._ready or self.isMinimized() or not self.isVisible():return
        forge=getattr(self,'_forge_controller',None)
        if (forge and forge.active) or not any(pin['widget'].isVisible() for pin in self._pin_previews.values()):return
        self._live_pins.tick(self._pin_previews)

    def _apply_live_pin(self,result):
        if not self._live_pins.accept(result,self._pin_previews):return
        key=result['key'];previous=self._pin_previews[key]['data']
        if result['error']:
            model={**previous,'live':{**previous.get('live',{}),'stale':True,'message':result['error']}}
        else:
            model={**result['model'],'refresh':previous.get('refresh',result['model'].get('refresh')),
                   'live':{'updated_at':result['updated_at'],'stale':False}}
        self._update_pin(key,model,persist=False,live=True)

    def _update_pin(self,kind,data,persist=True,live=False):
        from core.presentation_model import normalize_model,shown_number,record_text
        data=normalize_model(data)
        preview=self._pin_previews[kind]
        if not live:preview['live_token']=uuid.uuid4().hex
        preview['data']=copy.deepcopy(data)
        if hasattr(preview['widget'],'set_semantic'):preview['widget'].set_semantic(data)
        preview['restore'].setText(data.get('title',kind)[:36])
        if kind=='weather':
            summary=f"{shown_number(data.get('temperature'))}° · {data.get('condition') or 'Indisponível'}\n{data.get('city','')} · Chuva {shown_number(data.get('rain'))}%"
        elif kind=='system':
            summary=f"CPU {shown_number(data.get('cpu_percent'))}% · RAM {shown_number(data.get('ram_percent'))}%"
        else:
            items=data.get('items',[])
            summary='\n'.join(text for item in items[:2] if (text:=record_text(item))) or data.get('emptyText') or data.get('text') or 'Nenhum item disponível.'
            if kind=='tasks':
                summary=f"{shown_number(data.get('count'))} pendentes\n"+summary
        preview['label'].setText(summary[:500]);preview['widget'].setAccessibleName(data.get('title',kind)+' · '+summary[:500])
        state=data.get('live') or {}
        if state.get('stale'):
            preview['label'].setText(summary[:400]+'\n'+state.get('message','Consulta desatualizada.'))
            preview['restore'].setText(data.get('title',kind)[:22]+' · DESATUALIZADO')
        preview['widget'].setToolTip(state.get('message','') if state.get('stale') else 'Ultima consulta: '+state['updated_at'] if state.get('updated_at') else '')
        view=preview['view']
        ready=view and not view.failed
        preview['label'].setVisible(not (ready and view._ready))
        if ready:
            payload={**data,'compact':True,'framed':True,'narrationDriven':False,'rebuild':not live,'color':preview['accent'],
                     'motion':'reduced' if _read_full_config().get('reduce_motion',False) else 'full'}
            visible_data={**payload,'live':{key:value for key,value in (data.get('live') or {}).items() if key!='updated_at'}}
            signature=json.dumps(visible_data,sort_keys=True,ensure_ascii=False)
            view.show()
            if preview.get('view_signature')!=signature:
                view.sync(payload);preview['view_signature']=signature
        return self._save_pins() if persist else True

    def _expand_pin(self,kind):
        preview=self._pin_previews.get(kind)
        if preview and kind.startswith('forge:'):
            self._log.append_log('SYS: Artefato FORJA fixado: '+str(preview['data'].get('title','')))
            return
        if preview and kind.startswith('photo:'):
            self._open_terminal()
            self._terminal.attachment(preview['data']['attachment_id'],preview['data']['title'],True)
            self._terminal.show_image(preview['pixmap'])
            return
        if preview:
            self._show_manifestation({**preview['data'],'narrationDriven':False})

    def _remove_pin(self,kind):
        saved=self._load_pin_snapshots()
        self._pending_saved_pins=[pin for pin in saved if pin['key']!=kind]
        previous=dict(self._pin_previews)
        preview=self._pin_previews.pop(kind,None)
        if not self._save_pins():
            self._pin_previews=previous
            self._pending_saved_pins=saved
            raise ValueError('Não consegui salvar a remoção. O card foi mantido; tente novamente.')
        if preview:
            if preview['view']:
                preview['view'].sync({'visible':False})
            preview['widget'].hide();preview['widget'].deleteLater()
        if (self._presentation or {}).get('model',{}).get('kind')==kind:self._pinned=False
        if (self._pinned_context or {}).get('model',{}).get('kind')==kind:self._pinned_context=None
        self._layout_scene(True)

    def _position_pin(self):
        self._pin_button.hide()
        w,h=self._scene_stage.width(),self._scene_stage.height()
        if getattr(self,'_pin_layout_reserved',False):w=max(1,int(w*.49))
        from core.pin_layout import arrange
        rectangles=arrange(self._pin_previews,w,h)
        for kind,preview in self._pin_previews.items():
            x,y,width,height=rectangles[kind]
            preview['widget'].setGeometry(x,y,width,height);preview['widget'].raise_()
            if 'pixmap' in preview:
                preview['label'].setMinimumSize(1,1)
                preview['label'].setPixmap(preview['pixmap'].scaled(max(20,width-16),max(20,height-44),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            title=preview['data'].get('title',kind)
            preview['restore'].setText(preview['restore'].fontMetrics().elidedText(title,Qt.TextElideMode.ElideRight,max(40,width-52)))

    def interface_snapshot(self):
        model = self._presentation or {}
        scene=self._visual_scene.snapshot() if getattr(self,'_visual_scene',None) else {'count':0,'elements':[],'library_available':True}
        refresh_view=getattr(self,'_daily_refresh_view',None)
        refresh_visible=bool(refresh_view and refresh_view.isVisible())
        ultron_payload=getattr(self,'_ultron_payload',None)
        ultron_state=ultron_payload.get('state',{}) if isinstance(ultron_payload,dict) else {}
        ultron_visible=ultron_state.get('phase','idle')!='idle'
        forge_active=getattr(getattr(self,'_forge_controller',None),'active',False) is True
        neural_view=getattr(self.hud,'_spatial_core',None)
        neural_state=getattr(neural_view,'_neural_observed',{}) if neural_view and not neural_view.failed else {}
        neural_visible=bool(neural_state.get('progress',0)>.01 and neural_view.isVisible())
        visible_content=bool(refresh_visible or ultron_visible or forge_active or self._content_panel.isVisible() or any(item['widget'].isVisible() for item in self._pin_previews.values()) or any(item.get('visible') for item in scene['elements']) or self._terminal.isVisible() or self._execution.isVisible())
        visible_content=visible_content or neural_visible
        from core.panel_catalog import catalog,item_references
        references=item_references(model)
        selected=next((item for item in references if item['position']==model.get('focus',0)+1),{})
        return {"assistant": self._assistant_name, "visual": self.hud.hud_style,
                'spectro':self._spectro_controller.snapshot() if self._spectro_controller else {'active':False,'observing_screen':False},
                'neural_memory':{**neural_state,'visible':neural_visible,'observed':True if neural_state else False},
                'environment': {**self._environment.snapshot(), 'renderer': 'fallback' if not self._space_view or self._space_view.failed
                                else 'webgl' if self._space_view._loaded else 'loading'},
                'catalog':catalog(),'references':references,
                "state": self.hud.state, "accent": C.PRI,
                'visual_scene':scene,
                'protocols':{'ultron':{'visible':ultron_visible,'state':copy.deepcopy(ultron_state) if ultron_visible else None},
                    'forge':{'active':forge_active}},
                'daily_refresh':{'visible':refresh_visible,'transaction':refresh_view.transaction if refresh_visible else None,
                    'detail':refresh_view.detail.text() if refresh_visible else None,
                    'completed':refresh_view.bar.value() if refresh_visible else None,
                    'total':refresh_view.bar.maximum() if refresh_visible else None},
                'observation':{'source':'application_state','screen_capture':False,
                    'window_visible':self.isVisible() and not self.isMinimized(),
                    'has_visible_content':visible_content and self.isVisible() and not self.isMinimized()},
                "viewport": {"width": self.width(), "height": self.height()},
                'scene_viewport':{'width':self._scene_stage.width(),'height':self._scene_stage.height(),
                    'coordinates':'scene_stage_pixels','origin_in_window':{'x':self._scene_stage.x(),'y':self._scene_stage.y()}},
                'scene_position':self._scene_position,
                'layout_animating':any(animation.state()==QPropertyAnimation.State.Running for animation in self._scene_animations),
                "avatar_bounds": {"x":self._center_split.x(),"y":self._center_split.y(),"width":self._center_split.width(),"height":self._center_split.height()},
                "resting": self._resting,
                "workspace": {'terminal_open':self._terminal.isVisible(),'execution_open':self._execution.isVisible(),
                    'awaiting_photo':self._pending_image_pin,'attachments':[{'id':key,'name':item['name'],'image':item['image']} for key,item in self._attachments.items()]},
                "presentation": {"visible": self._content_panel.isVisible(),
                                 "kind": model.get("model", {}).get("kind"),
                                 'content':copy.deepcopy(model.get('model') or {'text':model.get('text','')}) if self._content_panel.isVisible() else None,
                                 'paused':bool(model.get('paused')),'narration_active':bool(model.get('narration_active')),
                                 'reading':bool(model.get('model',{}).get('reading')),'contact':model.get('model',{}).get('contact'),
                                 "city": model.get("model", {}).get("city"),
                                 "selected_id":selected.get('id'),
                                 "title": model.get("title"), "focus": model.get("focus", 0),
                                 "items": len(model.get("items", [])), "pinned": self._pinned,
                                 "position": self._scene_position if self._content_panel.isVisible() else None,
                                 "bounds": {"x":self._content_panel.x(),"y":self._content_panel.y(),"width":self._content_panel.width(),"height":self._content_panel.height()}},
                "settings_open": self._quick_drawer.isVisible() or bool(getattr(self,"_settings_hub",None) and self._settings_hub.isVisible()),
                "pinned_context": (self._pinned_context or {}).get("title"),
                "pin_layout": {'capacity':6,'arrangements':['free','row','column'],
                    'coordinates':'normalized_top_left','viewport':{'width':self._scene_stage.width(),'height':self._scene_stage.height()}},
                "pinned_previews": [{'kind':kind,'title':item['data'].get('title'),'slot':item.get('slot'),
                    'visible':item['widget'].isVisible(),'content':copy.deepcopy(item['data']) if item['widget'].isVisible() else None,
                    'placement':item.get('placement'),'capacity':6,
                    'temperature':item['data'].get('temperature'),'items':len(item['data'].get('items',[])),
                    'bounds':{'x':item['widget'].x(),'y':item['widget'].y(),'width':item['widget'].width(),'height':item['widget'].height()}}
                    for kind,item in self._pin_previews.items()],
                "history": [item["title"] for item in self._presentation_history]}

    def _start_screen_observation(self):
        if getattr(self,'_closed_for_shutdown',False) or os.environ.get('QT_QPA_PLATFORM')=='offscreen':return
        try:
            from core.spectro import SpectroController
            if self._spectro_controller is None:self._spectro_controller=SpectroController(self)
            self._spectro_controller.start_observation()
        except (OSError,ValueError) as error:
            self.hud.append_log('SYS: Observacao indisponivel: '+type(error).__name__)

    def _apply_interface_request(self, request):
        try:
            if request.get("cancelled"):
                request["result"] = {"ok": False, "error": "Comando expirado."}
                return
            action, value = request["action"], request.get("value", "")
            if action == "inspect":
                pass
            elif action == 'spectro':
                if getattr(self,'_closed_for_shutdown',False):raise ValueError('O Jarvis esta encerrando; o Espectro nao sera reaberto.')
                if value in ('observe_current','resume_observation'):
                    provider=getattr(self,'_spectro_context_provider',None)
                    current=provider() if callable(provider) else None
                    from core.spectro_commands import request as spectro_request
                    parsed=spectro_request((current or {}).get('text',''),True)
                    if current!=request.get('spectro_context') or not parsed or parsed[0]!=value:
                        raise ValueError('Observacao exige a autorizacao atual para acompanhar este aplicativo.')
                    used=getattr(self,'_spectro_consent_serial',None)
                    if used==current.get('serial'):raise ValueError('Esta autorizacao ja foi usada. Para acompanhar outro aplicativo, faca um novo pedido.')
                from core.spectro import SpectroController
                if self._spectro_controller is None:self._spectro_controller=SpectroController(self)
                settings=json.loads(request.get('setting') or '{}')
                if not isinstance(settings,dict):raise ValueError('Informe os ajustes do Espectro como objeto.')
                if value=='observe_current':
                    target=current.get('spectro_target')
                    if not isinstance(target,dict) or not target.get('ok'):raise ValueError('Selecione um aplicativo valido antes de autorizar.')
                    settings['expected_target']=target
                request['result']=self._spectro_controller.apply(value,settings)
                if value in ('observe_current','resume_observation') and request['result'].get('ok'):
                    self._spectro_consent_serial=current.get('serial')
                return
            elif action == 'environment':
                self._environment.command(value)
                self._ui_sounds.play('space')
                self._layout_scene(True)
                self._sync_environment()
            elif action == 'resume':
                self._resume_presentation()
            elif action=='visual_scene':
                from core.visual_scene import VisualSceneController
                if not getattr(self,'_visual_scene',None):self._visual_scene=VisualSceneController(self)
                request['result']=self._visual_scene.apply(json.loads(value))
                return
            elif action=='catalog':
                pass
            elif action=='rest':
                if value not in ('on','off'):raise ValueError('Escolha on ou off para o repouso.')
                if self._resting!=(value=='on'):self._avatar_interaction('touch',.5,.5)
            elif action=='close':
                if value=='terminal':self._terminal.close_panel()
                elif value=='execution':self._execution.close_panel()
                elif value in ('','presentation',(self._presentation or {}).get('model',{}).get('kind')):
                    self._content_panel.hide();self._settle_timer.stop();self._cancel_presentation();self._layout_scene(True)
                else:raise ValueError('Este alvo não está aberto; não apaguei prévias fixadas.')
            elif action=='move_pin':
                old_places={key:(copy.deepcopy(item.get('placement')),item.get('slot')) for key,item in self._pin_previews.items()}
                preview=self._pin_previews.get(value)
                corners={'bottom_left':0,'bottom_right':1,'upper_left':2,'upper_right':3,'middle_left':4,'middle_right':5}
                corner=request.get('setting','')
                if preview and corner not in ('row','column'):
                    self._position_pin()
                    width=max(1,self._scene_stage.width());height=max(1,self._scene_stage.height())
                    for item in self._pin_previews.values():
                        if item.get('placement',{}).get('layout'):
                            rect=item['widget'].geometry()
                            item['placement']={'x':rect.x()/width,'y':rect.y()/height,'width':rect.width()/width,'height':rect.height()/height}
                if not preview and (value or corner not in ('row','column')):raise ValueError('Informe a chave real da previa fixada.')
                if not self._pin_previews:raise ValueError('Nao ha previas fixadas para organizar.')
                if corner in ('row','column'):
                    keys=list(self._pin_previews);total=len(keys)
                    for index,key in enumerate(keys):
                        self._pin_previews[key]['placement']={'x':0,'y':0,'layout':corner}
                elif corner in corners:
                    from core.pin_layout import arrange
                    width,height=self._scene_stage.width(),self._scene_stage.height()
                    current=arrange(self._pin_previews,width,height)
                    top=min(84,max(12,height//5));available=max(1,height-top-12)
                    for key,item in self._pin_previews.items():
                        if item.get('placement'):continue
                        x,y,rw,rh=current[key];right=max(12,width-rw-12)
                        bottom=max(top,height-rh-12);middle=top+max(0,(available-rh)//2)
                        anchors=((12,bottom),(right,bottom),(12,top),(right,top),(12,middle),(right,middle))
                        item['slot']=min(range(6),key=lambda i:(x-anchors[i][0])**2+(y-anchors[i][1])**2)
                    old_slot=preview.get('slot',0)
                    for key,item in self._pin_previews.items():
                        if key!=value and not item.get('placement') and item.get('slot')==corners[corner]:
                            item['slot']=old_slot
                    preview.pop('placement',None);preview['slot']=corners[corner]
                else:
                    from core.pin_layout import validate_placement
                    try:placement=validate_placement(json.loads(corner))
                    except (ValueError,TypeError):
                        for key,(placement,slot) in old_places.items():
                            self._pin_previews[key].pop('placement',None)
                            if placement is not None:self._pin_previews[key]['placement']=placement
                        raise
                    preview['placement']=placement
                from core.pin_layout import arrange
                layout_error=None
                try:
                    rectangles=arrange(self._pin_previews,self._scene_stage.width(),self._scene_stage.height(),strict=True)
                    if corner in corners:
                        x,y,rw,rh=rectangles[value]
                        right=max(12,width-rw-12);bottom=max(top,height-rh-12);middle=top+max(0,(available-rh)//2)
                        wanted=((12,bottom),(right,bottom),(12,top),(right,top),(12,middle),(right,middle))[corners[corner]]
                        if (x,y)!=wanted:raise ValueError('O canto solicitado não está livre para este tamanho. Mova outra prévia ou escolha outra posição.')
                    saved=self._save_pins()
                except ValueError as error:
                    saved=False;layout_error=str(error)
                if not saved:
                    for key,(placement,slot) in old_places.items():
                        item=self._pin_previews[key]
                        item.pop('placement',None);item.pop('slot',None)
                        if placement is not None:item['placement']=placement
                        if slot is not None:item['slot']=slot
                    raise ValueError(layout_error or 'Nao consegui salvar as novas posicoes.')
                self._layout_scene(True)
            elif action == "clear":
                if getattr(self,'_visual_scene',None):self._visual_scene.clear_all(preserve_pinned=True)
                self._terminal.hide();self._execution.hide();self._execution_settle.stop();self._pending_image_pin=False
                self._content_panel.hide(); self._quiz_panel.hide()
                self._left_panel.hide(); self._right_panel.hide()
                self._close_setup(); self._close_controls()
                self._command_bar.hide()
                self._pin_button.hide()
                if self._confirm_overlay:
                    self._on_confirm_answered(False)
                for overlay in (self._customize_overlay, self._remote_overlay):
                    if overlay:
                        overlay.hide()
                if self._presentation:
                    self._presentation_history = (self._presentation_history + [self._presentation.copy()])[-8:]
                self._presentation = None
                self._pinned = False
                self._settle_timer.stop()
                self._cancel_presentation()
                self._environment.command('normal')
                self._layout_scene(True)
                self._sync_environment()
            elif action == "move":
                if value not in ("left","right","center","auto"):
                    raise ValueError("Posição inválida.")
                self._scene_position=value
                self._layout_scene(True)
            elif action == "settle":
                self._settle_presentation()
            elif action == "open":
                handlers = {"settings": lambda: self._toggle_drawer(True),
                            "news":lambda:self._open_existing_domain('news'),"weather":lambda:self._open_existing_domain('weather'),
                            "tasks":lambda:self._open_existing_domain('tasks'),"calendar":lambda:self._open_existing_domain('calendar'),"system":lambda:self._open_existing_domain('system'),
                            "gmail":lambda:self._open_existing_domain('gmail'),"whatsapp":lambda:self._open_existing_domain('whatsapp'),
                            "controls": lambda: self._toggle_controls(True),
                            "profile": lambda:self._open_settings_tab('profile'), "audio": self._open_audio_devices,
                            "memory": self._open_memory_panel, "plugins": self._open_plugin_manager,
                            "connections": lambda:self._open_settings_tab('connections'), "remote": self._open_remote,
                            "commands": self._open_terminal,"terminal":self._open_terminal,
                            "execution":lambda:(self._execution.show_panel(_read_full_config().get('reduce_motion',False)),self._layout_scene(True)),
                            "activity": lambda:self._open_settings_tab('activity'), "chat": self._open_terminal,
                            "ai": lambda:self._open_settings_tab('ai')}
                if value not in handlers:
                    raise ValueError("Tela desconhecida.")
                handlers[value]()
            elif action == 'request_image':
                self._pending_image_pin=True
                self._open_terminal()
                self._terminal.status.setText('Aguardando a foto que você quer fixar')
            elif action == 'pin_image':
                self._pin_image(value or self._terminal.attachment_id)
            elif action == 'close_terminal':
                self._terminal.close_panel();self._pending_image_pin=False
            elif action == "visual":
                if value not in ("face", "core"):
                    raise ValueError("Escolha face ou core.")
                from memory.config_manager import save_hud_style
                save_hud_style(value); self.hud.hud_style = value; self._refresh_hud_btn()
            elif action == "color":
                old = current_palette()
                if not apply_ui_accent(value):
                    raise ValueError("Cor hexadecimal inválida.")
                retheme_all_widgets(old, current_palette())
                if self._presentation:
                    self._render_presentation()
                config = _read_full_config(); config["ui_color"] = value
                API_FILE.write_text(json.dumps(config, indent=4), encoding="utf-8")
            elif action == "focus":
                if not self._presentation or not self._presentation.get("items"):
                    raise ValueError("Não há itens para selecionar.")
                index = int(value) - 1
                if not 0 <= index < len(self._presentation["items"]):
                    raise ValueError("Item fora dos limites.")
                self._presentation["focus"] = index
                if self._presentation.get("model"):
                    self._presentation["model"]["narrationDriven"]=False
                self._render_presentation()
            elif action in ("pin", "unpin"):
                from core.pin_targets import pin_target
                value=pin_target(value)
                if action=='unpin':
                    kind=value or (self._presentation or {}).get('model',{}).get('kind')
                    if not kind or kind not in self._pin_previews:
                        raise ValueError('Nenhuma prévia desse assunto está fixada.')
                    self._remove_pin(kind)
                    request['result']={'ok':True,'screen':self.interface_snapshot()}
                    return
                textual_current=value=='data' and self._presentation and not self._presentation.get('model')
                if value and not textual_current and (self._presentation or {}).get('model',{}).get('kind')!=value:
                    self._open_existing_domain(value)
                if not self._presentation:
                    raise ValueError("Nenhuma apresentação visível.")
                data=self._presentation.get('model')
                if not data:
                    data={'kind':'data','title':self._presentation.get('title','Informacao'),
                          'text':self._presentation.get('text',''),'items':[]}
                if data.get('kind')=='status':
                    raise ValueError('A atualizacao e temporaria. Fixe os resultados depois da consulta.')
                self._pin_data({**data,'focus':self._presentation.get('focus',0)})
                self._pinned = True
                self._pinned_context = copy.deepcopy(self._presentation)
                if self._pinned:
                    self._content_panel.hide()
                    self._settle_timer.stop()
                    self._layout_scene(True)
            elif action == "setting":
                setting = request.get("setting")
                config = _read_full_config()
                if setting in ("assistant_name", "user_name", "voice"):
                    if setting == "voice":
                        from memory.config_manager import AVAILABLE_VOICES
                        if value not in AVAILABLE_VOICES:
                            raise ValueError("Voz não disponível.")
                    self._apply_name_update(value if setting == "assistant_name" else self._assistant_name,
                                            value if setting == "user_name" else config.get("user_name", ""),
                                            voice=value if setting == "voice" else "")
                elif setting == "microphone":
                    if value not in ("on", "off"):
                        raise ValueError("Escolha on ou off.")
                    if self._muted == (value == "on"):
                        self._toggle_mute()
                elif setting == "briefing":
                    if value not in ("on", "off"):
                        raise ValueError("Escolha on ou off.")
                    from memory.config_manager import save_brief_enabled
                    save_brief_enabled(value == "on"); self._update_brief_btn(value == "on")
                else:
                    raise ValueError("Ajuste não disponível por este comando.")
            elif action == "return":
                if not self._presentation_history:
                    raise ValueError("Não há apresentação anterior.")
                model = self._presentation_history.pop()
                current = self._presentation
                self._presentation = None
                if model.get("model"):
                    self._show_manifestation({**model['model'],'narrationDriven':False,'focus':model.get('focus',0),'newsPhase':'front'})
                else:
                    self._presentation_clock.replace_scene()
                    self._show_content(model['title'],model['text'])
                    self._presentation['focus']=model.get('focus',0)
                    self._render_presentation()
                if current:
                    self._presentation_history = (self._presentation_history + [current])[-8:]
            elif action == "fullscreen":
                self._toggle_fullscreen()
            else:
                raise ValueError("Comando de interface desconhecido.")
            request["result"] = {"ok": True, "screen": self.interface_snapshot()}
        except Exception as error:
            request["result"] = {"ok": False, "error": str(error)}
            try:request['result']['screen']=self.interface_snapshot()
            except Exception:pass
        finally:
            request["done"].set()

    # ── document review ──────────────────────────────────────────────────────
    # Rendered as rich text into the content panel that already exists, rather
    # than into a panel of its own. A review is read, not clicked, so QTextEdit
    # gives scrolling, selection and copy for nothing, and the HUD gains no
    # widget it has to lay out. Severity decides colour and order here because
    # that is presentation; the plugin supplies no styling and knows no palette,
    # which is also what lets a re-theme repaint a review correctly.

    # Severity is marked by a symbol and a colour, not by a word. The findings
    # themselves are in the user's language, and "[SERIOUS]" sitting inside a
    # Turkish sentence is the kind of seam this project tries not to have —
    # while translating the tag would mean a table per language, which is worse.
    # A shape carries it in every language, and shape plus colour still reads
    # for someone who cannot separate red from amber. What the marks mean
    # arrives the way everything else does: JARVIS says it out loud.
    _REVIEW_MARKS = {"serious": ("RED", "▲"), "caution": ("ACC2", "●"), "note": ("PRI_DIM", "·")}

    @staticmethod
    def _esc(s) -> str:
        return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace("\n", "<br>"))

    def _show_review(self, title: str, summary: str, findings, unclear):
        """Slot — Qt main thread. Lays a document review into the content panel."""
        if self._content_spatial:
            self._content_spatial.hide()
        self._content_display.show()
        e = self._esc
        parts = [f'<div style="color:{C.TEXT}; font-family:Courier New;">']

        if summary:
            parts.append(
                f'<div style="color:{C.WHITE}; border-left:2px solid {C.PRI};'
                f' padding-left:8px; margin-bottom:10px;">{e(summary)}</div>')

        for f in (findings or []):
            key, mark = self._REVIEW_MARKS.get(f.get("severity"), ("PRI_DIM", "·"))
            colour = getattr(C, key)
            parts.append(f'<div style="margin-bottom:11px;">')
            parts.append(
                f'<span style="color:{colour}; font-weight:bold;">{mark}</span> '
                f'<span style="color:{C.WHITE}; font-weight:bold;">'
                f'{e(f.get("heading"))}</span>')
            if f.get("detail"):
                parts.append(f'<div style="margin-left:12px;">{e(f["detail"])}</div>')
            if f.get("quote"):
                # The document's own wording, visually separated from the
                # explanation so the two are never mistaken for each other.
                parts.append(
                    f'<div style="margin-left:12px; color:{C.TEXT_DIM};'
                    f' border-left:1px solid {C.BORDER}; padding-left:7px;">'
                    f'&ldquo;{e(f["quote"])}&rdquo;</div>')
            if f.get("suggestion"):
                parts.append(
                    f'<div style="margin-left:12px; color:{C.PRI};">'
                    f'&rarr; {e(f["suggestion"])}</div>')
            parts.append('</div>')

        if unclear:
            parts.append(
                f'<div style="margin-top:6px; border-top:1px solid {C.BORDER};'
                f' padding-top:7px; color:{C.TEXT_MED};">'
                'Pontos não esclarecidos pelo documento:</div>')
            for u in unclear:
                parts.append(
                    f'<div style="margin-left:12px; color:{C.TEXT_MED};">'
                    f'&middot; {e(u)}</div>')
        parts.append('</div>')

        import time as _time
        self.hud.glance(0.0, -0.85, hold=1.3)
        # Left as written, not upper-cased. The other content-panel titles are
        # the app's own English labels, but this one is the document's name in
        # the user's language, and str.upper() applies English casing rules to
        # it: Turkish "Sözleşmesi" comes back "SÖZLEŞMESI", having lost the
        # dotted capital İ. Python has no locale-aware upper to reach for, and
        # imposing one language's rules on all of them is the bug, not the fix.
        self._content_title_lbl.setText((title or 'Documento')[:48])
        self._content_ts_lbl.setText(_time.strftime("%H:%M:%S"))
        self._content_display.setHtml("".join(parts))
        self._content_display.moveCursor(
            self._content_display.textCursor().MoveOperation.Start)
        first_show = not self._content_panel.isVisible()
        self._content_panel.show()
        if first_show:
            total = self._center_split.width()
            self._center_split.setSizes([int(total * 0.45), int(total * 0.55), 0])

    # ── quiz panel ───────────────────────────────────────────────────────────
    # An interactive twin of the content panel. The plugin only ever hands over
    # questions; everything about asking, marking and reporting happens here,
    # and the finished result is pushed back into the conversation the same way
    # a dropped file is — as a message JARVIS reads and responds to. That keeps
    # the tool call short (it returns the moment the board is up) and leaves the
    # talking to the assistant, in the user's own language.

    def _quiz_btn(self, text: str, primary: bool = False) -> QPushButton:
        b = QPushButton(text)
        b.setFont(QFont("Courier New", 8))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setMinimumHeight(24)
        edge = C.BORDER_B if primary else C.BORDER
        col = C.PRI if primary else C.TEXT_MED
        b.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2}; color: {col};
                border: 1px solid {edge}; border-radius: 2px;
                padding: 3px 9px; text-align: left;
            }}
            QPushButton:hover {{ color: {C.WHITE}; border-color: {C.PRI_DIM}; }}
            QPushButton:disabled {{ color: {C.TEXT_DIM}; border-color: {C.BORDER}; }}
        """)
        return b

    def _build_quiz_panel(self) -> QWidget:
        w = _FuiOverlay()
        w.setObjectName("QuizPanel")
        w.setStyleSheet(f"""
            QWidget#QuizPanel {{
                background: {C.PANEL};
                border-top: 1px solid {C.BORDER_B};
            }}
        """)
        w.hide()

        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 7, 12, 8)
        lay.setSpacing(6)

        hdr = QHBoxLayout(); hdr.setSpacing(6)
        dot = QLabel("◈")
        dot.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        dot.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(dot)

        self._quiz_title_lbl = QLabel('QUESTIONÁRIO')
        self._quiz_title_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._quiz_title_lbl.setStyleSheet(
            f"color: {C.PRI}; background: transparent; letter-spacing: 1px;")
        hdr.addWidget(self._quiz_title_lbl)
        hdr.addStretch()

        self._quiz_count_lbl = QLabel("")
        self._quiz_count_lbl.setFont(QFont("Courier New", 7))
        self._quiz_count_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        hdr.addWidget(self._quiz_count_lbl)

        quit_btn = QPushButton('FECHAR  ✕')
        quit_btn.setFont(QFont("Courier New", 7))
        quit_btn.setFixedHeight(18)
        quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quit_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_DIM};
                border: 1px solid {C.BORDER}; border-radius: 2px; padding: 0 5px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        quit_btn.clicked.connect(self._hide_quiz)
        hdr.addWidget(quit_btn)
        lay.addLayout(hdr)

        rule = QFrame(); rule.setFixedHeight(1)
        rule.setStyleSheet(f"background: {C.BORDER};")
        lay.addWidget(rule)

        self._quiz_q_lbl = QLabel("")
        self._quiz_q_lbl.setWordWrap(True)
        self._quiz_q_lbl.setFont(QFont("Courier New", 9))
        self._quiz_q_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(self._quiz_q_lbl)

        self._quiz_answers = QWidget()
        self._quiz_answers.setStyleSheet("background: transparent;")
        self._quiz_answers_lay = QVBoxLayout(self._quiz_answers)
        self._quiz_answers_lay.setContentsMargins(0, 2, 0, 0)
        self._quiz_answers_lay.setSpacing(4)
        lay.addWidget(self._quiz_answers)

        self._quiz_note_lbl = QLabel("")
        self._quiz_note_lbl.setWordWrap(True)
        self._quiz_note_lbl.setFont(QFont("Courier New", 8))
        self._quiz_note_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._quiz_note_lbl.hide()
        lay.addWidget(self._quiz_note_lbl)

        foot = QHBoxLayout()
        foot.addStretch()
        self._quiz_next_btn = self._quiz_btn('PRÓXIMA  →', primary=True)
        self._quiz_next_btn.setFixedWidth(110)
        self._quiz_next_btn.clicked.connect(self._quiz_next)
        self._quiz_next_btn.hide()
        foot.addWidget(self._quiz_next_btn)
        lay.addLayout(foot)

        self._quiz = None
        return w

    def _show_quiz(self, topic: str, questions, grader=None):
        """Slot — Qt main thread. Puts a fresh quiz on the board."""
        if not questions:
            return
        self._quiz = {
            "topic": topic or "",
            "questions": list(questions),
            "grader": grader,
            "i": 0,
            "results": [],
            "answered": False,
        }
        self._quiz_title_lbl.setText((topic or "questionário").upper()[:48])
        self.hud.glance(0.0, -0.85, hold=1.3)
        first_show = not self._quiz_panel.isVisible()
        self._quiz_panel.show()
        if first_show:
            total = self._center_split.width()
            self._center_split.setSizes([int(total * 0.45), 0, int(total * 0.55)])
        self._quiz_render()

    def _hide_quiz(self):
        self._quiz = None
        self._quiz_panel.hide()

    def _quiz_clear_answers(self):
        while self._quiz_answers_lay.count():
            item = self._quiz_answers_lay.takeAt(0)
            child = item.widget()
            if child is not None:
                child.setParent(None)
                child.deleteLater()

    def _quiz_render(self):
        q = self._quiz["questions"][self._quiz["i"]]
        n, total = self._quiz["i"] + 1, len(self._quiz["questions"])
        self._quiz_count_lbl.setText(f"{n} / {total}")
        self._quiz_q_lbl.setText(q.get("question", ""))
        self._quiz_note_lbl.hide()
        self._quiz_next_btn.hide()
        self._quiz["answered"] = False
        self._quiz_clear_answers()

        opts = q.get("options") or []
        if opts:
            for text in opts:
                b = self._quiz_btn("   " + text)
                b.clicked.connect(lambda _=False, t=text: self._quiz_submit(t))
                self._quiz_answers_lay.addWidget(b)
        else:
            row = QWidget(); row.setStyleSheet("background: transparent;")
            h = QHBoxLayout(row); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(6)
            field = QLineEdit()
            field.setFont(QFont("Courier New", 9))
            field.setPlaceholderText('sua resposta')
            field.setStyleSheet(f"""
                QLineEdit {{
                    background: {C.PANEL2}; color: {C.WHITE};
                    border: 1px solid {C.BORDER}; border-radius: 2px; padding: 4px 7px;
                }}
                QLineEdit:focus {{ border-color: {C.PRI_DIM}; }}
            """)
            send = self._quiz_btn('RESPONDER', primary=True)
            send.setFixedWidth(90)
            field.returnPressed.connect(lambda: self._quiz_submit(field.text()))
            send.clicked.connect(lambda: self._quiz_submit(field.text()))
            h.addWidget(field, stretch=1)
            h.addWidget(send)
            self._quiz_answers_lay.addWidget(row)
            field.setFocus()

    def _quiz_submit(self, given: str):
        if self._quiz is None or self._quiz["answered"]:
            return
        self._quiz["answered"] = True
        q = self._quiz["questions"][self._quiz["i"]]
        grader = self._quiz.get("grader")
        verdict = None
        if callable(grader):
            try:
                verdict = grader(q, given)
            except Exception:
                verdict = None
        self._quiz["results"].append({
            "question": q.get("question", ""),
            "type": q.get("type", ""),
            "given": str(given or "").strip(),
            "answer": q.get("answer", ""),
            "correct": verdict,
        })

        for i in range(self._quiz_answers_lay.count()):
            wdg = self._quiz_answers_lay.itemAt(i).widget()
            if wdg is not None:
                wdg.setEnabled(False)

        if verdict is True:
            mark, colour = '✓  correto', C.GREEN
        elif verdict is False:
            mark, colour = "✕  " + str(q.get("answer", "")), C.RED
        else:
            # Open answers and near-miss gap-fills are JARVIS's to judge. Saying
            # so is honest; marking it wrong here would be a guess.
            mark, colour = '… anotado. Vou revisar esta com você', C.ACC2
        note = q.get("note") or ""
        self._quiz_note_lbl.setText(mark + (("\n" + note) if note else ""))
        self._quiz_note_lbl.setStyleSheet(f"color: {colour}; background: transparent;")
        self._quiz_note_lbl.show()

        last = self._quiz["i"] >= len(self._quiz["questions"]) - 1
        self._quiz_next_btn.setText('CONCLUIR  →' if last else 'PRÓXIMA  →')
        self._quiz_next_btn.show()
        self._quiz_next_btn.setFocus()

    def _quiz_next(self):
        if self._quiz is None:
            return
        if self._quiz["i"] >= len(self._quiz["questions"]) - 1:
            self._quiz_finish()
        else:
            self._quiz["i"] += 1
            self._quiz_render()

    def _quiz_finish(self):
        if self._quiz is None:
            return
        topic = self._quiz["topic"]
        results = self._quiz["results"]
        right = sum(1 for r in results if r["correct"] is True)
        unsure = sum(1 for r in results if r["correct"] is None)
        total = len(results)
        self._quiz_panel.hide()
        self._quiz = None

        self._log.append_log(f"QUESTIONÁRIO: {topic or 'quiz'} — {right}/{total} corretas")

        # Hand it back to JARVIS as a message, not as a tool return: the tool
        # call ended minutes ago. This is the same channel a dropped file uses.
        lines = [f"[QUIZ_DONE] topic={topic or 'general'} | "
                 f"auto-marked {right}/{total} corretas"
                 + (f", {unsure} still need your marking" if unsure else "")]
        for i, r in enumerate(results, 1):
            state = ("correct" if r["correct"] is True
                     else 'incorreta' if r["correct"] is False else 'PRECISA DE CORREÇÃO')
            lines.append(
                f"{i}. [{r['type']}] {r['question']} | they answered: "
                f"{r['given'] or '(blank)'} | expected: {r['answer']} | {state}")
        lines.append(
            'Corrija cada questão marcada PRECISA DE CORREÇÃO: aceite uma resposta '
            "that means the same thing. Then tell them how they did in their own "
            "language: the score, what they got wrong and why, in a couple of "
            "sentences. Offer another round only if it fits. "
            "Remember something only if it would still matter next week — that they "
            "are working through a subject, or keep missing the same thing. A score "
            "from one session is not worth a memory, and a memory per quiz would "
            "bury the things that are.")
        msg = "\n".join(lines)
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(22)
        w.setStyleSheet(f"background: {C.DARK}; border-top: 1px solid {C.BORDER};")
        lay = QHBoxLayout(w); lay.setContentsMargins(14, 0, 14, 0)

        def _fl(txt, color=C.TEXT_MED):
            l = QLabel(txt); l.setFont(QFont("Courier New", 7))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_fl('[F4] Microfone · [F11] Tela cheia'))
        lay.addStretch()
        return w

    def _on_file_selected(self, path: str):
        self._current_file = path
        p    = Path(path)
        cat  = _file_category(p)
        icon, _ = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size = _fmt_size(p.stat().st_size)
        self._file_hint.setText(f"{icon}  {p.name}  ·  {size}  ·  Diga ao {self._assistant_name} o que fazer com o arquivo")
        self._log.append_log(f"FILE: {p.name} ({size}) carregado")
        if self.on_text_command:
            msg = (
                f"[FILE_UPLOADED] path={path} | name={p.name} | "
                f"type={p.suffix.lstrip('.')} | size={size} | "
                f"An attachment was selected by the user in the local interface. "
                f"Use interface_control inspect for its attachment_id; pin_image only if requested. "
                f"Briefly tell the user you can see the file '{p.name}' "
                f"({size}) has been uploaded and ask what they'd like to do with it."
            )
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def notify_phone_connected(self) -> None:
        if self._remote_overlay and self._remote_overlay.isVisible():
            self._remote_overlay.mark_connected()

    def _open_remote(self):
        if not self.on_remote_clicked:
            self._log.append_log('SYS: Painel remoto indisponível.')
            return
        result = self.on_remote_clicked()
        if not result:
            self._log.append_log('SYS: Não foi possível gerar a chave remota.')
            return
        url    = result[0]
        key    = result[1]
        auto   = result[2] if len(result) >= 3 else ""
        manual = result[3] if len(result) >= 4 else url
        if self._remote_overlay:
            self._remote_overlay._do_close()
        cw  = self.centralWidget()
        ow, oh = RemoteKeyOverlay._OW, RemoteKeyOverlay._OH
        ov  = RemoteKeyOverlay(url, key, auto_login_url=auto, manual_url=manual,
                               expiry_secs=600, parent=cw)
        ov.set_new_key_callback(self.on_remote_clicked)
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.closed.connect(lambda: setattr(self, '_remote_overlay', None))
        ov.show()
        self._remote_overlay = ov
        self._log.append_log(f"SYS: Chave remota gerada. Endereço: {manual or url}")

    # ── Auto-start ──────────────────────────────────────────────────────────────

    def _check_autostart(self) -> bool:
        """Returns True if auto-start is currently registered on this OS."""
        try:
            if _OS == "Windows":
                from core.windows_autostart import enabled
                return enabled()
            elif _OS == "Darwin":
                return (Path.home() / "Library" / "LaunchAgents"
                        / "com.jarvis.assistant.plist").exists()
            else:
                return (Path.home() / ".config" / "autostart" / "jarvis.desktop").exists()
        except Exception:
            return False

    def _toggle_autostart(self):
        currently_on = self._check_autostart()
        try:
            script = str(Path(__file__).resolve().parent / "main.py")
            if _OS == "Windows":
                from core.windows_autostart import set_enabled
                set_enabled(not currently_on)
            elif _OS == "Darwin":
                plist_dir = Path.home() / "Library" / "LaunchAgents"
                plist_dir.mkdir(parents=True, exist_ok=True)
                plist = plist_dir / "com.jarvis.assistant.plist"
                if currently_on:
                    plist.unlink(missing_ok=True)
                else:
                    plist.write_text(
                        '<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                        '<plist version="1.0"><dict>\n'
                        '  <key>Label</key><string>com.jarvis.assistant</string>\n'
                        '  <key>ProgramArguments</key><array>\n'
                        f'    <string>{sys.executable}</string>\n'
                        f'    <string>{script}</string>\n'
                        '  </array>\n'
                        '  <key>RunAtLoad</key><true/>\n'
                        '</dict></plist>\n'
                    )
            else:
                desk_dir = Path.home() / ".config" / "autostart"
                desk_dir.mkdir(parents=True, exist_ok=True)
                desk = desk_dir / "jarvis.desktop"
                if currently_on:
                    desk.unlink(missing_ok=True)
                else:
                    desk.write_text(
                        "[Desktop Entry]\n"
                        f"Name={self._assistant_name}\n"
                        f"Exec={sys.executable} {script}\n"
                        "Type=Application\nTerminal=false\n"
                        "X-GNOME-Autostart-enabled=true\n"
                    )
            enabled = not currently_on
            self._update_autostart_btn(enabled)
            self._log.append_log(
                f"SYS: Início automático {'enabled' if enabled else 'disabled'}.")
        except Exception as e:
            self._log.append_log(f"ERR: Falha no início automático: {e}")

    def _update_autostart_btn(self, enabled: bool):
        if not hasattr(self, '_autostart_btn'):
            return
        if enabled:
            self._autostart_btn.setText('◉  INÍCIO AUTOM.: SIM')
            self._autostart_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #001a08; color: {C.GREEN};
                    border: 1px solid {C.GREEN_D}; border-radius: 3px;
                }}
                QPushButton:hover {{ background: #002010; }}
            """)
        else:
            self._autostart_btn.setText('◉  INÍCIO AUTOM.: NÃO')
            self._autostart_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER}; border-radius: 3px;
                }}
                QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
            """)

    def _toggle_brief(self):
        from memory.config_manager import get_brief_enabled, save_brief_enabled
        new_val = not get_brief_enabled()
        save_brief_enabled(new_val)
        self._update_brief_btn(new_val)

    # ── Wake word settings ───────────────────────────────────────────────────

    def _wake_state(self) -> dict:
        """Combined state for the two wake-word buttons. Readiness is a cheap,
        deterministic on-disk check now (see core.wake_word.is_ready), so there
        is nothing to cache — the button never flickers to a stale value."""
        if self.wake_get_state:
            try:
                s = self.wake_get_state()
                return {"ready": bool(s.get("ready")),
                        "enabled": bool(s.get("enabled")),
                        "awake": bool(s.get("awake"))}
            except Exception:
                pass
        # Before JarvisLive has wired its callback (drawer built at startup).
        ready, enabled = False, False
        try:
            from core.wake_word import is_ready
            from memory.config_manager import get_wake_word_enabled
            ready, enabled = is_ready(), get_wake_word_enabled()
        except Exception:
            pass
        return {"ready": ready, "enabled": enabled, "awake": True}

    def _refresh_wake_btns(self):
        if not hasattr(self, '_wake_btn'):
            return
        st = self._wake_state()
        _on = f"""
            QPushButton {{ background: #001a08; color: {C.GREEN};
                border: 1px solid {C.GREEN_D}; border-radius: 3px;
                text-align: left; padding: 0 8px; }}
            QPushButton:hover {{ background: #002010; }}"""
        _off = f"""
            QPushButton {{ background: transparent; color: {C.TEXT_DIM};
                border: 1px solid {C.BORDER}; border-radius: 3px;
                text-align: left; padding: 0 8px; }}
            QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}"""
        self._wake_btn.setEnabled(True)
        if not st["ready"]:
            self._wake_btn.setText('⬇  BAIXAR ATIVAÇÃO')
            self._wake_btn.setStyleSheet(_off)
            self._wake_sleep_btn.hide()
        elif st["enabled"]:
            self._wake_btn.setText('🎙  CHAMADA: SIM')
            self._wake_btn.setStyleSheet(_on)
            self._wake_sleep_btn.show()
            self._wake_sleep_btn.setText('😴  ENTRAR EM REPOUSO' if st["awake"] else '👂  ATIVAR AGORA')
            self._wake_sleep_btn.setStyleSheet(_off)
        else:
            self._wake_btn.setText('🎙  CHAMADA: NÃO')
            self._wake_btn.setStyleSheet(_off)
            self._wake_sleep_btn.hide()

    def _refresh_talk_btns(self):
        """Repaint the push-to-talk row from the saved setting."""
        if not hasattr(self, "_ptt_btn"):
            return
        from core.hotkey import chord_label
        from memory.config_manager import get_push_to_talk_enabled
        _on = f"""
            QPushButton {{ background: #001a08; color: {C.GREEN};
                border: 1px solid {C.GREEN_D}; border-radius: 3px;
                text-align: left; padding: 0 8px; }}
            QPushButton:hover {{ background: #002010; }}"""
        _off = f"""
            QPushButton {{ background: transparent; color: {C.TEXT_DIM};
                border: 1px solid {C.BORDER}; border-radius: 3px;
                text-align: left; padding: 0 8px; }}
            QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}"""

        ptt = get_push_to_talk_enabled()
        self._ptt_btn.setText(f"🎚  FALAR: {chord_label()}" if ptt
                              else '🎚  FALAR: NÃO')
        self._ptt_btn.setStyleSheet(_on if ptt else _off)
        self._ptt_btn.setToolTip(
            "Microphone stays closed until you hold the key — nothing is sent "
            "while you are not holding it." if ptt
            else 'Mantenha uma tecla pressionada para falar, sem transmitir o microfone continuamente.')


    def _refresh_hud_btn(self):
        if not hasattr(self,'_hud_btn'):return
        from memory.config_manager import get_hud_style
        face = get_hud_style() == "face"
        # Neither state is "off", so both read as active — this is a choice
        # between two things, not a switch with a disabled side.
        style = f"""
            QPushButton {{ background: {C.PANEL2}; color: {C.PRI};
                border: 1px solid {C.BORDER_A}; border-radius: 3px;
                text-align: left; padding: 0 8px; }}
            QPushButton:hover {{ color: {C.WHITE}; border: 1px solid {C.BORDER_B}; }}"""
        self._hud_btn.setText('🧑  VISUAL: ROSTO' if face
                              else '◉  VISUAL: NÚCLEO')
        self._hud_btn.setStyleSheet(style)
        self._hud_btn.setToolTip(
            "Rosto animado que acompanha a fala. Clique para usar nosso núcleo espacial."
            if face else
            "Nosso núcleo espacial, reativo à fala e à escuta. Clique para usar o rosto.")

    def _toggle_hud_style(self):
        """Swap the centrepiece. Both objects stay in memory, so the change is
        instant and switching back costs nothing."""
        from memory.config_manager import get_hud_style, save_hud_style
        want = "core" if get_hud_style() == "face" else "face"
        save_hud_style(want)
        try:
            self.hud.hud_style = want
            self.hud.update()
        except Exception:
            pass
        self._refresh_hud_btn()
        self._log.append_log(
            'SYS: Visual alterado para rosto animado.' if want == "face"
            else 'SYS: Visual alterado para núcleo.')

    def _toggle_ptt(self):
        from memory.config_manager import (get_push_to_talk_enabled,
                                           save_push_to_talk_enabled)
        want = not get_push_to_talk_enabled()
        save_push_to_talk_enabled(want)
        scope = None
        if self.on_push_to_talk:
            try:
                scope = self.on_push_to_talk(want)
            except Exception as e:
                self._log.append_log(f"ERR: Falha no controle do microfone: {e}")
                save_push_to_talk_enabled(False)
                want = False
        self._apply_ptt_shortcut(want and scope != "global")
        self._refresh_talk_btns()

    def _apply_ptt_shortcut(self, needed: bool):
        """Bind the chord inside the window when no global hook is available.

        On macOS and Linux there is no dependency-free way to read global key
        state, so the chord is at least live whenever this window has focus.
        Qt gives no key-release for a QShortcut, so a press latches the mic open
        and a short timer closes it; held down, auto-repeat keeps pushing that
        timer out, which behaves like holding a key.
        """
        from PyQt6.QtGui import QKeySequence, QShortcut
        from core.hotkey import qt_sequence

        if not needed:
            sc = getattr(self, "_ptt_sc", None)
            if sc is not None:
                sc.setEnabled(False)
                self._ptt_sc = None
            self._ptt_hold(False)
            return
        if getattr(self, "_ptt_sc", None) is not None:
            return

        self._ptt_release = QTimer(self)
        self._ptt_release.setSingleShot(True)
        self._ptt_release.setInterval(420)
        self._ptt_release.timeout.connect(lambda: self._ptt_hold(False))

        def _press():
            self._ptt_hold(True)
            self._ptt_release.start()

        self._ptt_sc = QShortcut(QKeySequence(qt_sequence()), self)
        self._ptt_sc.setAutoRepeat(True)
        self._ptt_sc.activated.connect(_press)

    def _ptt_hold(self, held: bool):
        """Report a windowed press/release to whoever owns the microphone."""
        cb = getattr(self, "ptt_hold", None)
        if cb:
            try:
                cb(bool(held))
            except Exception:
                pass

    def _toggle_wake_word(self):
        st = self._wake_state()
        if not st["ready"]:
            # First time: download openwakeword + model in a worker thread.
            self._wake_btn.setText('⬇  BAIXANDO…')
            self._wake_btn.setEnabled(False)
            def _work():
                try:
                    from core.wake_word import install_and_download
                    ok, msg = install_and_download(
                        logger=lambda m: self._log_sig.emit(f"SYS: {m}"))
                except Exception as e:
                    ok, msg = False, str(e)
                if ok and self.on_wake_toggle:
                    try:
                        self.on_wake_toggle(True)   # auto-enable after a successful download
                    except Exception:
                        pass
                self._wake_dl_sig.emit(ok, msg)
            threading.Thread(target=_work, daemon=True).start()
            return
        # Already downloaded → just flip enabled/disabled through JarvisLive.
        if self.on_wake_toggle:
            try:
                self.on_wake_toggle(not st["enabled"])
            except Exception:
                pass
        self._refresh_wake_btns()

    def _on_wake_install_done(self, ok: bool, msg: str):
        self._log_sig.emit(f"SYS: {'Ativação por voz pronta.' if ok else 'Falha na ativação por voz: ' + msg}")
        self._refresh_wake_btns()

    def _tap_wake_manual(self):
        if self.on_wake_manual:
            try:
                self.on_wake_manual()
            except Exception:
                pass
        self._refresh_wake_btns()

    def _update_brief_btn(self, enabled: bool):
        if not hasattr(self, '_brief_btn'):
            return
        if enabled:
            self._brief_btn.setText('☀  RESUMO INIC.: SIM')
            self._brief_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #001a08; color: {C.GREEN};
                    border: 1px solid {C.GREEN_D}; border-radius: 3px;
                    text-align: left; padding: 0 8px;
                }}
                QPushButton:hover {{ background: #002010; }}
            """)
        else:
            self._brief_btn.setText('☀  RESUMO INIC.: NÃO')
            self._brief_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER}; border-radius: 3px;
                    text-align: left; padding: 0 8px;
                }}
                QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
            """)

    # ── Customization ────────────────────────────────────────────────────────────

    def _open_customize(self):
        cfg = _read_full_config()
        if self._customize_overlay:
            self._customize_overlay.hide()
        cw = self.centralWidget()
        ov = CustomizeOverlay(
            cfg.get("assistant_name", "DIEF JARVIS") or "DIEF JARVIS",
            cfg.get("user_name", ""),
            cfg.get("ui_color", "") or DEFAULT_UI_COLOR,
            cfg.get("voice_name", ""),
            parent=cw,
        )
        ow, oh = CustomizeOverlay._OW, CustomizeOverlay._OH
        oh = min(oh, cw.height() - 16)
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.on_preview = self._preview_ui_color
        ov.saved.connect(self._apply_name_update)
        ov.show()
        self._customize_overlay = ov

    def _preview_ui_color(self, hex_color: str):
        """Live preview — paints the whole interface the new colour (does NOT write to config)."""
        old = current_palette()
        if apply_ui_accent(hex_color):
            retheme_all_widgets(old, current_palette())

    def _apply_name_update(self, name: str, user_name: str, ui_color: str = "",
                           voice: str = ""):
        """Update all name/theme-dependent UI elements and persist to config."""
        self._assistant_name = name.strip() or "DIEF JARVIS"
        display = self._assistant_name.upper()
        self.setWindowTitle("DIEF JARVIS")
        self._title_lbl.setText(display)
        if display in ("JARVIS", "J.A.R.V.I.S"):
            self._sub_lbl.setText('Assistente pessoal de inteligência artificial')
        else:
            self._sub_lbl.setText('Assistente pessoal de IA')
        self._log._ai_name_lc = self._assistant_name.lower()
        self.hud._assistant_name = display

        color_changed = False
        if ui_color:
            old = current_palette()
            if apply_ui_accent(ui_color):
                # Live-paint the whole interface (panels, buttons, borders, HUD)
                retheme_all_widgets(old, current_palette())
                color_changed = old["PRI"] != C.PRI

        # Voice change → persist and, if it actually changed, rebuild the Live
        # session so the new voice takes effect (it's fixed at connect time).
        voice_changed = False
        if voice:
            from memory.config_manager import get_voice, save_voice
            if voice != get_voice():
                save_voice(voice)
                voice_changed = True

        try:
            data = _read_full_config()
            data["assistant_name"] = self._assistant_name
            data["user_name"] = user_name.strip()
            if ui_color:
                data["ui_color"] = ui_color.strip().lower()
            API_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
            self._log.append_log(f"SYS: Identidade atualizada: {display}")
            if color_changed:
                self._log.append_log(f"SYS: Cor aplicada: {ui_color}")
            if voice_changed:
                self._log.append_log(f"SYS: Voz definida: {voice}")
        except Exception as e:
            self._log.append_log(f"ERR: Falha ao salvar configurações: {e}")

        if voice_changed and self.on_voice_change:
            self.on_voice_change()

    def _centre_overlay(self, ov) -> None:
        """Place a floating overlay in the middle of the HUD and show it."""
        cw = self.centralWidget()
        ov.adjustSize()
        ov.setGeometry(
            max(0, (cw.width()  - ov.width())  // 2),
            max(0, (cw.height() - ov.height()) // 2),
            ov.width(), ov.height(),
        )
        ov.show()
        ov.raise_()

    # ── Audio devices ────────────────────────────────────────────────────────

    def _open_audio_devices(self):
        ov = AudioDeviceOverlay(parent=self.centralWidget())
        ov.picked.connect(self._on_audio_devices_applied)
        self._centre_overlay(ov)
        self._audio_overlay = ov            # keep a reference so it isn't GC'd

    def _on_audio_devices_applied(self):
        self._log.append_log('SYS: Dispositivos de áudio atualizados.')
        if self.on_audio_device_change:
            self.on_audio_device_change()

    # ── Memory panel ─────────────────────────────────────────────────────────

    def _open_memory_panel(self):
        ov = MemoryOverlay(parent=self.centralWidget())
        self._centre_overlay(ov)
        self._memory_overlay = ov

    # ── Irreversible-action confirmation ─────────────────────────────────────

    def _show_confirm_banner(self, title: str, detail: str):
        self._hide_confirm_banner()
        ov = ConfirmBanner(title, detail, parent=self)
        ov.setWindowFlag(Qt.WindowType.Dialog,True)
        ov.setWindowModality(Qt.WindowModality.ApplicationModal)
        ov.answered.connect(self._on_confirm_answered)
        ov.adjustSize()
        center=self.frameGeometry().center()
        ov.move(center.x()-ov.width()//2,center.y()-ov.height()//2)
        ov.show();ov.raise_();ov.activateWindow()
        self._confirm_overlay = ov

    def _hide_confirm_banner(self):
        ov = getattr(self, "_confirm_overlay", None)
        if ov is not None:
            ov.hide()
            ov.deleteLater()
            self._confirm_overlay = None

    def _on_confirm_answered(self, accepted: bool):
        # Tear the banner down first: core.confirm.resolve() may be about to
        # shut the machine down, and a live widget mid-callback is not where you
        # want to be when that happens.
        self._hide_confirm_banner()
        try:
            from core.confirm import resolve
            resolve(bool(accepted))
        except Exception as e:
            self._log.append_log(f"ERR: Falha na confirmação: {e}")

    def _open_plugin_manager(self):
        plugins = self.get_plugins() if self.get_plugins else []
        cw = self.centralWidget()
        ov = PluginManagerOverlay(plugins, parent=cw)
        ov.adjustSize()
        ov.setGeometry(
            (cw.width()  - ov.width())  // 2,
            (cw.height() - ov.height()) // 2,
            ov.width(), ov.height(),
        )
        ov.show()
        ov.raise_()
        self._plugin_manager_overlay = ov   # keep a reference so it isn't GC'd

    def _open_plugin_settings(self):
        sections = self.get_plugin_settings() if self.get_plugin_settings else []
        cw = self.centralWidget()
        ov = PluginSettingsOverlay(sections, parent=cw)
        ow = PluginSettingsOverlay._OW
        oh = min(560, cw.height() - 16)
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.show()
        ov.raise_()
        self._plugin_settings_overlay = ov   # keep a reference so it isn't GC'd

    # ── Clipboard intelligence ───────────────────────────────────────────────────

    def _on_clipboard_changed(self):
        try:
            text = QApplication.clipboard().text().strip()
            if len(text) >= 10:
                self._clipboard_sig.emit(text)
        except Exception:
            pass

    def _show_clipboard_panel(self, text: str):
        self._clipboard_panel.show_clipboard(text)
        self._position_clipboard_panel()

    def _position_clipboard_panel(self):
        cw = self.centralWidget()
        pw = ClipboardPanel._W
        ph = self._clipboard_panel.sizeHint().height() or ClipboardPanel._H
        x = (cw.width() - pw) // 2
        y = cw.height() - ph - 6
        self._clipboard_panel.setGeometry(x, y, pw, ph)
        self._clipboard_panel.raise_()

    def _on_clipboard_action(self, cmd: str):
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(cmd,), daemon=True).start()

    # ────────────────────────────────────────────────────────────────────────────

    def _do_interrupt(self):
        if self.on_interrupt:
            self.on_interrupt()

    def _toggle_mute(self):
        # A deliberate press settles the question: whatever the video did, or is
        # about to do, the user has now said what they want.
        self._video_auto_muted = False
        self._set_muted(not self._muted)

    def _set_muted(self, muted: bool, note: str = ""):
        muted = bool(muted)
        if muted == self._muted:
            return
        self._muted = muted
        self.hud.muted = muted
        self._style_mute_btn()
        if muted:
            self._apply_state("MUTED")
            self._log.append_log('SYS: Microfone desligado.' + (f" {note}" if note else ""))
        else:
            self._apply_state("LISTENING")
            self._log.append_log('SYS: Microfone ativo.' + (f" {note}" if note else ""))

    def _style_mute_btn(self):
        if self._muted:
            self._mute_btn.setText('🔇  MICROFONE DESLIGADO')
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #140006; color: {C.MUTED_C};
                    border: 1px solid {C.MUTED_C}; border-radius: 3px;
                }}
            """)
        else:
            self._mute_btn.setText('🎙  MICROFONE ATIVO')
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #00140a; color: {C.GREEN};
                    border: 1px solid {C.GREEN}; border-radius: 3px;
                }}
                QPushButton:hover {{ background: #001f10; }}
            """)

    def _send(self):
        txt = self._input.text().strip()
        if not txt: return
        self._input.clear()
        self._log.append_log(f"Você: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _apply_state(self, state: str):
        if self._resting:
            state='SLEEPING'
        prior_state=self.hud.state
        was_speaking=self.hud.speaking
        if state=='SPEAKING' and not was_speaking and self._presentation and self._presentation.get('completed') and not self._pinned and not getattr(self,'_refresh_lock',None):
            self._presentation_history=(self._presentation_history+[self._presentation.copy()])[-8:]
            self._presentation=None
            self._presentation_clock.replace_scene()
            self._content_panel.hide()
            self._layout_scene(True)
        if state=='SPEAKING' and not was_speaking and self._ultron_clock.cancelled:
            self._ultron_clock.resume()
            self._ultron_clock.elapsed=getattr(self,'_narration_elapsed',0.)
            self._ultron_clock.next_cue=self._ultron_clock.elapsed
        if state=='LISTENING' and (was_speaking or prior_state=='THINKING') and getattr(self,'_visual_scene',None):
            self._visual_scene.finish()
        if state=='SPEAKING' and not was_speaking and getattr(self,'_visual_scene',None):
            self._visual_scene.resume()
        if state=="SPEAKING" and not was_speaking and self._presentation_clock.cancelled:
            self._presentation_clock.resume()
        elif state=='SPEAKING' and not was_speaking and self._presentation_clock.finished:
            self._presentation_clock.resume()
        self.hud.state    = state
        self.hud.speaking = (state == "SPEAKING")
        self._ui_sounds.voice(state in ('SPEAKING','THINKING'))
        self._ui_sounds.scene(resting=state=='SLEEPING')
        if state!=prior_state:
            if state=='SLEEPING':self._ui_sounds.play('rest')
            elif prior_state=='SLEEPING':self._ui_sounds.play('awake')
            elif state=='LISTENING':self._ui_sounds.play('listening')
            elif state=='THINKING':self._ui_sounds.play('thinking')
        if state == "SPEAKING":
            self._settle_timer.stop()
        elif state=='LISTENING' and self._presentation and self._presentation.get('narration_active') and self._presentation.get('audio_started'):
            if self._content_spatial and self._presentation_clock.active:
                self._content_spatial.page().runJavaScript("window.finishPresentation && window.finishPresentation()")
            final=self._presentation.get('model',{}).get('newsLast',True)
            if not self._presentation_clock.cancelled and final:
                self._set_news_phase('settled')
                self._presentation.update(narration_active=False,completed=True)
            self._presentation['audio_started']=False
            self._presentation['pending_beats']=[]
            self._presentation_clock.finish()
            hold=_read_full_config().get("presentation_hold",15)
            if final and not self._pinned and not getattr(self,'_refresh_lock',None) and not self._presentation_clock.cancelled and isinstance(hold,(int,float)) and hold>0:
                self._settle_timer.start(int(min(120,hold)*1000))

    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(d.get("gemini_api_key")) and bool(d.get("os_system"))
        except Exception:
            return False

    def _show_setup(self):
        if self._overlay is not None:
            self._overlay.raise_()
            return
        self._ready=False
        self._center_split.hide()
        self._scene_header_visible=False
        for label in (self._title_lbl,self._clock_lbl,self._date_lbl):
            label.hide()
        if getattr(self,'_opening_veil',None):
            self._opening_veil.hub_visible=False
            self._opening_veil.update()
        ov = SetupOverlay(self.centralWidget())
        cw = self.centralWidget()
        ow, oh = 460, 390
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.done.connect(self._on_setup_done)
        ov.show()
        ov.raise_()
        self._overlay = ov

    def _on_setup_done(self, key: str, os_name: str):
        from core.local_data import LOCK,atomic_write
        try:
            with LOCK:
                config = _read_full_config()
                config.update(gemini_api_key=key, os_system=os_name, language="pt-BR")
                atomic_write(API_FILE,json.dumps(config,indent=4,ensure_ascii=False).encode('utf-8'))
        except Exception as error:
            from core.connection_errors import describe
            message=describe(error)
            if isinstance(self._overlay,SetupOverlay):
                self._overlay.save_status.setText(message);self._overlay.save_status.show()
            self._log.append_log('ERR: '+message)
            return
        self._ready = True
        if self._overlay:
            self._overlay.hide()
            self._overlay.deleteLater()
            self._overlay = None
        if self._opening_veil:
            self._opening_veil.hub_visible=True
            self._opening_veil.update()
        self._center_split.show()
        self._layout_scene()
        self._start_environment()
        self._apply_state("LISTENING")
        self._assistant_name = _read_full_config().get("assistant_name", "DIEF JARVIS") or "DIEF JARVIS"
        self._log.append_log(f"SYS: Inicializado. SO={os_name.upper()}. {self._assistant_name} conectado.")


class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass


class JarvisUI:
    @property
    def forge_runtime(self):
        from core.forge_host import runtime_for
        return runtime_for(self._win)

    def control_forge(self,action):
        packet={'action':action,'done':threading.Event()}
        self._win._forge_sig.emit(packet)
        if not packet['done'].wait(30):return {'ok':False,'error':'A cena da Forja nao confirmou a transicao.'}
        return packet.get('result',{'ok':False,'error':'Cena indisponivel.'})

    def pin_forge_artifact(self,artifact):
        packet={'action':'pin_artifact','data':{'kind':'forge_artifact','artifact_id':artifact['id'],'title':artifact['name'],'narrationDriven':False},'done':threading.Event()}
        self._win._forge_sig.emit(packet)
        if not packet['done'].wait(10):return {'ok':False,'error':'O painel nao confirmou o artefato.'}
        return packet.get('result',{'ok':False})

    @property
    def ultron_runtime(self):
        with self._ultron_context_lock:
            if self._ultron_runtime is None:
                from core.ultron import Runtime
                self._ultron_runtime=Runtime()
                self._win._ultron_runtime=self._ultron_runtime
            return self._ultron_runtime

    def record_ultron_user(self,text):
        if not isinstance(text,str) or not text.strip():return
        target=None
        from core.spectro_commands import request as spectro_request
        parsed=spectro_request(text,True)
        if parsed and parsed[0]=='observe_current':
            from core.spectro_perception import foreground
            try:target=foreground()
            except Exception:target={'ok':False}
        with self._ultron_context_lock:
            self._ultron_user={'text':text[:4096],'serial':self._ultron_user['serial']+1}
            if target is not None:self._ultron_user['spectro_target']=target

    def invalidate_ultron_user(self):
        with self._ultron_context_lock:self._ultron_user={**self._ultron_user,'text':''}

    def ultron_authorization(self,context):
        from contextlib import contextmanager
        @contextmanager
        def guard():
            with self._ultron_context_lock:
                if context!=self._ultron_user or not self._ultron_user.get('text'):
                    raise ValueError('Pedido substituido por um novo turno.')
                yield
        return guard()

    def ultron_user_context(self):
        with self._ultron_context_lock:return dict(self._ultron_user)

    def present_ultron(self,snapshot,result):
        from core.ultron_presentation import projection
        self._win._ultron_sig.emit({'state':projection(snapshot),'result':result})

    def update_environment_media(self, playback):
        self._win._environment_media_sig.emit(playback if isinstance(playback,dict) else {})

    def reset_presentation_timeline(self):
        self._win._presentation_reset_sig.emit()

    def operation_event(self,name,state):
        self._win._operation_sig.emit(name,state)
    def presentation_audio(self,seconds):
        self._win._presentation_audio_sig.emit(seconds)

    def play_sound(self,name):
        self._win._sound_sig.emit(name)

    def cancel_presentation_speech(self):
        self._win._presentation_cancel_sig.emit()
    def narration_text(self,text,at=None,duration=None):
        self._win._narration_sig.emit({'text':text,'at':at,'duration':duration})

    def connection_status(self,connected,model=""):
        self._win._connection_sig.emit(connected,model)
    def show_manifestation(self, model):
        self._win._manifestation_sig.emit({**model,"narrationDriven":model.get('kind') not in ('status','status-end')})

    def show_verified_manifestation(self, model):
        packet={'model':dict(model),'done':threading.Event(),'cancelled':threading.Event(),'accepted':False}
        self._win._verified_manifestation_sig.emit(packet)
        if not packet['done'].wait(3):
            packet['cancelled'].set()
            return False
        return packet['accepted']

    def show_neural_memory(self, payload):
        self._win._neural_sig.emit(payload)

    def control_interface(self, action, value="", setting="", *, user_context=None):
        request = {"action": action, "value": value, "setting": setting, "done": threading.Event()}
        if action=='spectro' and value in ('observe_current','resume_observation'):
            request['spectro_context']=dict(user_context) if user_context is not None else self.ultron_user_context()
        if QThread.currentThread() == self._win.thread():
            self._win._apply_interface_request(request)
        else:
            self._win._interface_sig.emit(request)
        if not request["done"].wait(5):
            request["cancelled"] = True
            return {"ok": False, "error": "A interface não respondeu a tempo."}
        return request["result"]

    def __init__(self, face_path: str, size=None):
        self._ultron_context_lock=threading.RLock()
        self._ultron_user={'text':'','serial':0}
        self._ultron_runtime=None
        self._app = QApplication.instance() or QApplication(sys.argv)
        from core.branding import initialize_application
        initialize_application(self._app)
        QLocale.setDefault(PT_BR)
        self._translator = QTranslator(self._app)
        if self._translator.load(
            "qtbase_pt_BR", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        ):
            self._app.installTranslator(self._translator)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
        self._win._spectro_context_provider=self.ultron_user_context
        from core import confirm
        confirm.bind(self.show_confirm,self.hide_confirm,self.write_log)
        self.root = _RootShim(self._app)
        from core.window_behavior import IdleCursor
        self._win._idle_cursor = IdleCursor(self._win)
        self._win.showFullScreen()
        ready_file=os.environ.get('DIEF_READY_FILE')
        if os.environ.get('DIEF_VALIDATION')=='1':
            from core.distribution_visual_probe import schedule
            schedule(self._win,self._app)
        elif ready_file:
            from core.distribution_health import confirm_window
            QTimer.singleShot(1000,lambda:confirm_window(ready_file))

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._drop_zone.current_file()

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    @property
    def on_remote_clicked(self):
        return self._win.on_remote_clicked

    @on_remote_clicked.setter
    def on_remote_clicked(self, cb):
        self._win.on_remote_clicked = cb

    @property
    def on_interrupt(self):
        return self._win.on_interrupt

    @on_interrupt.setter
    def on_interrupt(self, cb):
        self._win.on_interrupt = cb

    @property
    def on_voice_change(self):
        return self._win.on_voice_change

    @on_voice_change.setter
    def on_voice_change(self, cb):
        self._win.on_voice_change = cb

    @property
    def on_connection_test(self):
        return self._win.on_connection_test

    @on_connection_test.setter
    def on_connection_test(self, cb):
        self._win.on_connection_test = cb

    @property
    def on_audio_device_change(self):
        return self._win.on_audio_device_change

    @on_audio_device_change.setter
    def on_audio_device_change(self, cb):
        self._win.on_audio_device_change = cb

    def show_confirm(self, title: str, detail: str) -> None:
        """Thread-safe: raise the irreversible-action gate. Called from action
        handlers running in executor threads, so it goes through a signal."""
        self._win._confirm_sig.emit(str(title)[:120], str(detail)[:300])

    def hide_confirm(self) -> None:
        """Thread-safe: take the gate down."""
        self._win._confirm_hide_sig.emit()

    @property
    def get_plugins(self):
        return self._win.get_plugins

    @get_plugins.setter
    def get_plugins(self, cb):
        self._win.get_plugins = cb

    @property
    def get_plugin_settings(self):
        return self._win.get_plugin_settings

    @get_plugin_settings.setter
    def get_plugin_settings(self, cb):
        self._win.get_plugin_settings = cb

    @property
    def on_wake_toggle(self):
        return self._win.on_wake_toggle

    @on_wake_toggle.setter
    def on_wake_toggle(self, cb):
        self._win.on_wake_toggle = cb

    @property
    def on_wake_manual(self):
        return self._win.on_wake_manual

    @on_wake_manual.setter
    def on_wake_manual(self, cb):
        self._win.on_wake_manual = cb

    @property
    def wake_get_state(self):
        return self._win.wake_get_state

    @wake_get_state.setter
    def wake_get_state(self, cb):
        self._win.wake_get_state = cb

    def set_audio_level(self, level: float) -> None:
        """Thread-safe: feed a 0.0–1.0 live audio level to the HUD waveform.
        Called from the audio threads; a plain float store is atomic under the
        GIL, so no signal/lock is needed for this cosmetic value."""
        try:
            self._win.hud.set_audio_level(level)
        except Exception:
            pass

    def glance(self, dx: float, dy: float, hold: float = 1.1) -> None:
        """Ask the avatar to look somewhere for a moment (see HoloAvatar.glance)."""
        try:
            if self._avatar is not None:
                self._avatar.glance(dx, dy, hold)
        except Exception:
            pass

    @property
    def ptt_hold(self):
        return self._win.ptt_hold

    @ptt_hold.setter
    def ptt_hold(self, cb):
        self._win.ptt_hold = cb

    @property
    def on_push_to_talk(self):
        return self._win.on_push_to_talk

    @on_push_to_talk.setter
    def on_push_to_talk(self, cb):
        self._win.on_push_to_talk = cb

    def push_visemes(self, frames, hop: float, at: float) -> None:
        """Thread-safe: post a schedule of (level, openness, width) mouth frames
        for JARVIS's own speech. `at` is the wall-clock time the batch begins to
        sound, not the time of the call. See HudCanvas.push_visemes()."""
        try:
            self._win.hud.push_visemes(frames, hop, at)
        except Exception:
            pass

    def notify_phone_connected(self) -> None:
        self._win.notify_phone_connected()

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def show_content(self, title: str, text: str):
        """Thread-safe presentation beside either avatar, in the same scene."""
        self._win._manifestation_sig.emit({"kind":"data","title":title[:48],"text":text[:4000],"narrationDriven":True})

    def show_quiz(self, topic: str, questions, grade=None) -> None:
        """Thread-safe: put an interactive quiz on the board.

        `grade(question, given)` decides each answer — the plugin supplies it so
        the marking rules live with the questions rather than being duplicated
        here. Returning None from it means "JARVIS should judge this one", which
        is how open answers and near-miss gap-fills are handled.

        Returns immediately: the user answers at their own pace and the finished
        result is delivered back through on_text_command.
        """
        self._win._quiz_sig.emit(str(topic or ""), list(questions or []), grade)

    def hide_quiz(self) -> None:
        """Thread-safe: clear any quiz currently on the board."""
        self._win._quiz_hide_sig.emit()

    def show_review(self, title: str, summary: str, findings, unclear=None) -> None:
        """Thread-safe: lay a document review into the panel below the HUD.

        `findings` is a list of {heading, detail, severity, quote, suggestion};
        severity is one of 'serious' / 'caution' / 'note' and decides colour and
        order here, so the caller supplies no styling of its own.
        """
        self._win._review_sig.emit(str(title or ""), str(summary or ""),
                                   list(findings or []), list(unclear or []))

    def prompt_reconfig(self):
        """Thread-safe: show the API key setup overlay (e.g. after an auth error)."""
        self._win._ready = False
        self._win._reconfig_sig.emit()

    def show_camera_frame(self, img_bytes: bytes):
        """Thread-safe: show a webcam frame in the small overlay (screen captures)."""
        self._win._camera_sig.emit(img_bytes)

    def show_video(self, source: str, title: str = "", muted: bool = True,
                   audio_source: str = "") -> None:
        """Thread-safe: play a video where the avatar normally is.

        `source` is a local path or a direct media URL. `audio_source` is for
        the case where the sound arrives as its own stream — YouTube serves no
        combined format any more — and when it is given the two are played
        together and kept in step.

        Muted by default, and that is a decision rather than a default: a
        soundtrack talking over JARVIS is the one way this could make the
        assistant worse. The user turns sound on from the header button or by
        asking, and closes it the same two ways.
        """
        self._win._video_open_sig.emit(str(source or ""), str(title or ""),
                                       bool(muted), str(audio_source or ""))

    def stop_video(self) -> None:
        """Thread-safe: close the video and give the HUD back to the avatar."""
        self._win._video_close_sig.emit()

    def set_video_muted(self, muted: bool) -> None:
        """Thread-safe: silence or unsilence whatever is playing."""
        self._win._video_mute_sig.emit(bool(muted))

    def video_is_playing(self) -> bool:
        return bool(self._win.video_is_playing())

    def start_camera_stream(self) -> None:
        """Thread-safe: start live camera feed in the full HUD area."""
        self._win.start_camera_stream()

    def stop_camera_stream(self) -> None:
        """Thread-safe: stop the live camera feed."""
        self._win.stop_camera_stream()

    @property
    def assistant_name(self) -> str:
        return self._win._assistant_name

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")
