"""Small deterministic polish for host narration, without changing its facts."""
import re


def protocol_text(text):
    if re.fullmatch(r'Bem[- ]vindo,\s+senhor[.!]?',text.strip(),flags=re.IGNORECASE):return text
    # Remove only the stock trailing vocative, not titles, names or quoted content.
    return re.sub(r',\s+senhor([.!?]?)\s*$',r'\1',text,flags=re.IGNORECASE)
