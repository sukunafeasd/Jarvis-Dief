"""Presentation markup is not speech. Keep facts while removing visual syntax."""
import html
import re


def speech_text(value):
    text=html.unescape(str(value))
    text=re.sub(r'```[\s\S]*?```',' trecho de codigo exibido na tela. ',text)
    text=re.sub(r'!?\[([^\]]+)\]\(https?://[^)]+\)',r'\1',text)
    text=re.sub(r'https?://\S+',' link disponivel na tela ',text)
    text=re.sub(r'</?[A-Za-z][A-Za-z0-9]*(?:\s+[^>]*)?/?>',' ',text)
    text=re.sub(r'(?m)^\s*(?:#{1,6}\s*|[-*+]\s+|>\s*)','',text)
    text=text.replace('**','').replace('__','').replace('`','')
    text=re.sub(r'(?<=\w)\*(?=\w)',' vezes ',text)
    text=text.replace('*','').replace('°C',' graus Celsius').replace('ºC',' graus Celsius')
    text=text.replace('km/h',' quilometros por hora')
    text=re.sub(r'R\$\s*([\d.,]+)',r'\1 reais',text)
    text=re.sub(r'(?<=\d)\s*%', ' por cento', text)
    text=text.replace('&',' e ').replace('→',' para ').replace('≥',' maior ou igual a ').replace('≤',' menor ou igual a ')
    text=text.replace('|',', ').replace('•',', ')
    return re.sub(r'\s+',' ',text).strip()
