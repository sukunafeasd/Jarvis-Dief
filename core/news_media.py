"""Bounded public news thumbnails, converted to inert local image data."""
import base64
import io
import ipaddress
import socket
import json
import time
from urllib.parse import urlsplit, urljoin
from html.parser import HTMLParser
import requests
from PIL import Image

def public_url(url):
    try:
        parts=urlsplit(url)
        if parts.scheme!='https' or not parts.hostname or parts.username or parts.port not in (None,443):
            return False
        addresses=socket.getaddrinfo(parts.hostname,443,type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(entry[4][0]).is_global for entry in addresses)
    except (OSError,ValueError):
        return False

def public_response(url):
    if url.startswith('http://'):
        url='https://'+url[7:]
    deadline=time.monotonic()+5
    for _ in range(3):
        if not public_url(url) or time.monotonic()>deadline:
            raise ValueError('URL de mídia indisponível.')
        response=requests.get(url,timeout=(2,3),stream=True,allow_redirects=False)
        if response.status_code not in (301,302,303,307,308):
            return response
        target=urljoin(url,response.headers.get('Location',''))
        response.close();url=target
    raise ValueError('Redirecionamentos demais.')

class ImageMetadata(HTMLParser):
    def __init__(self):
        super().__init__();self.image='';self.structured=False
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag=='meta' and (values.get('property',values.get('name','')) or '').lower() in ('og:image','twitter:image'):
            self.image=self.image or values.get('content','')
        if tag=='script':self.structured=values.get('type')=='application/ld+json'

    def handle_endtag(self,tag):
        if tag=='script':self.structured=False

    def handle_data(self,data):
        if not self.structured or self.image:return
        try:payload=json.loads(data)
        except (ValueError,TypeError):return
        entries=payload if isinstance(payload,list) else [payload]
        for index,entry in enumerate(entries):
            if index>=32:break
            if not isinstance(entry,dict):continue
            graph=entry.get('@graph',[])
            if isinstance(graph,list):entries.extend(graph[:12])
            image=entry.get('image')
            if isinstance(image,list):image=image[0] if image else None
            if isinstance(image,dict):image=image.get('url') or image.get('contentUrl')
            if isinstance(image,str):self.image=image;break

def article_thumbnail(url):
    if not public_url(url):
        return ''
    try:
        with public_response(url) as response:
            resolved_url=response.url
            if response.status_code!=200 or 'html' not in response.headers.get('Content-Type',''):
                return ''
            data=bytearray()
            for chunk in response.iter_content(32768):
                data.extend(chunk)
                if len(data)>=300000:break
        parser=ImageMetadata();parser.feed(data.decode('utf-8',errors='replace'))
        return thumbnail(urljoin(resolved_url,parser.image)) if parser.image else ''
    except (OSError,ValueError,requests.RequestException):
        return ''

def thumbnail(url):
    try:
        with public_response(url) as response:
            if response.status_code!=200 or not response.headers.get("Content-Type","").startswith("image/"):
                return ""
            data=bytearray()
            for chunk in response.iter_content(32768):
                data.extend(chunk)
                if len(data)>2_000_000:
                    return ""
        with Image.open(io.BytesIO(data)) as image:
            if image.width*image.height>16_000_000:
                return ""
            image.thumbnail((1000,600)); image=image.convert("RGB")
            out=io.BytesIO(); image.save(out,format="JPEG",quality=80)
        return "data:image/jpeg;base64,"+base64.b64encode(out.getvalue()).decode("ascii")
    except (OSError,ValueError,requests.RequestException):
        return ""
