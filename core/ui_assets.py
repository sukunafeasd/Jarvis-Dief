"""Bundled, offline service marks and Lucide controls."""
from functools import lru_cache
from pathlib import Path
from PyQt6.QtCore import Qt, QRectF, QByteArray
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap, QLinearGradient
from PyQt6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1] / 'resources' / 'ui-icons'
SERVICES = {
    'spotify_control': ('spotify', '#1ed760'), 'gmail': ('gmail', '#ff646b'),
    'gmail_compose': ('gmail', '#ff646b'), 'whatsapp': ('whatsapp', '#25e879'),
    'ai': ('googlegemini', '#a38bff'), 'google_calendar': ('googlecalendar', '#55b3ff'),
    'google_drive': ('googledrive', '#ffda55'), 'notion_service': ('notion', '#f4f8ff'),
    'github_mcp': ('github', '#f4f8ff'), 'home_automation': ('homeassistant', '#36c5ff'),
    'forge': ('terminal', '#45d4ff'), 'iphone': ('smartphone', '#65cdff'),
    'context7': ('book-open', '#44cfff'), 'deep_research': ('search', '#9adfff'),
    'fish_audio': ('volume-2', '#ffa1c8'), 'outlook_service': ('message-circle', '#52adff'),
    'weather': ('cloud-rain', '#57d5ff'), 'calendar': ('calendar-days', '#ffd58a'),
    'tasks': ('list-checks', '#62edbf'), 'system': ('cpu', '#74dfff'),
    'news': ('newspaper', '#b9c6ff'), 'files': ('folder', '#7bc5ff'),
}

@lru_cache(maxsize=160)
def symbol_pixmap(name, color='#75d9ff', size=24):
    path = ROOT / (name + '.svg')
    if not path.is_file(): path = ROOT / 'plug.svg'
    renderer = QSvgRenderer(QByteArray(path.read_bytes()))
    pix = QPixmap(size * 2, size * 2); pix.setDevicePixelRatio(2); pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix); renderer.render(p, QRectF(0, 0, size, size))
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(0, 0, size, size, QColor(color)); p.end()
    return pix

def glyph(name, color='#85dfff'):
    return QIcon(symbol_pixmap(name, color))

@lru_cache(maxsize=96)
def service_badge(identifier, size=54):
    key = identifier.removeprefix('plugin:')
    name, color = SERVICES.get(key, ('sparkles' if ':' in key else 'plug', '#5ed6ff'))
    pix = QPixmap(size * 2, size * 2); pix.setDevicePixelRatio(2); pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    rect = QRectF(3, 3, size-6, size-6)
    glass = QLinearGradient(0, 0, size, size)
    glass.setColorAt(0, QColor('#123c59')); glass.setColorAt(.45, QColor('#031323')); glass.setColorAt(1, QColor('#071b2e'))
    p.setBrush(glass)
    from PyQt6.QtGui import QPen
    for width, alpha in ((6, 18), (3, 40), (1, 165)):
        edge = QColor(color); edge.setAlpha(alpha); p.setPen(QPen(edge, width))
        p.drawRoundedRect(rect, 9, 9)
    mark = symbol_pixmap(name, color, round(size*.55))
    p.drawPixmap(round((size-mark.deviceIndependentSize().width())/2), round((size-mark.deviceIndependentSize().height())/2), mark)
    p.end(); return pix
