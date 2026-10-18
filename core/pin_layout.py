"""Free spatial placements and semantic preview sizes, independent of Qt."""
import math

MAX_PINS=6
PROFILES={
    'weather':(320,210),'tasks':(350,230),'calendar':(360,245),
    'gmail':(430,230),'whatsapp':(400,225),'news':(420,250),
    'system':(360,215),'memory':(340,220),'files':(370,230),
    'search':(390,225),'photo':(320,265),'data':(340,200),
}


def validate_placement(value):
    if not isinstance(value,dict) or set(value)-{'x','y','width','height','layout'} or not {'x','y'}<=set(value):
        raise ValueError('Informe x e y entre 0 e 1; largura e altura sao opcionais.')
    for key,number in value.items():
        if key=='layout':
            if number not in ('row','column'):raise ValueError('Organizacao invalida.')
            continue
        if isinstance(number,bool) or not isinstance(number,(int,float)) or not math.isfinite(number):
            raise ValueError('Posicao e tamanho precisam ser numeros finitos.')
        if not (0<=number<=1) or key in ('width','height') and number==0:
            raise ValueError('Coordenadas e proporcoes precisam estar entre 0 e 1.')
    return dict(value)


def arrange(entries,width,height,strict=False):
    margin=12;top=min(84,max(12,height//5));gap=12
    available=max(1,height-top-margin)
    count=max(1,len(entries));rows=math.ceil(count/2)
    max_width=max(1,min(460,(width-3*margin)//2))
    max_height=max(1,min(285,(available-gap*(rows-1))//rows))
    placed={}
    layouts={entry.get('placement',{}).get('layout') for entry in entries.values()}
    if len(layouts)==1 and next(iter(layouts),None) in ('row','column'):
        layout=next(iter(layouts))
        if layout=='row':
            w=max(1,(width-2*margin-gap*(count-1))//count);h=min(240,available)
            return {key:(margin+i*(w+gap),height-margin-h,w,h) for i,key in enumerate(entries)}
        h=max(1,(available-gap*(count-1))//count);w=min(390,max(1,width-2*margin))
        return {key:(margin,top+i*(h+gap),w,h) for i,key in enumerate(entries)}
    def intersects(a,b):
        return a[0]<b[0]+b[2]+gap and a[0]+a[2]+gap>b[0] and a[1]<b[1]+b[3]+gap and a[1]+a[3]+gap>b[1]
    for index,(key,entry) in enumerate(entries.items()):
        data=entry.get('data',{});kind=data.get('kind',key)
        base_w,base_h=PROFILES.get(kind,PROFILES['data'])
        if len(data.get('items') or [])>2:base_w+=35;base_h+=15
        pos=entry.get('placement')
        w=min(max(1,width-2*margin),max(80,round(width*pos['width']))) if pos and 'width' in pos else min(max_width,base_w)
        h=min(available,max(70,round(height*pos['height']))) if pos and 'height' in pos else min(max_height,base_h)
        left=margin;right=max(margin,width-w-margin);bottom=max(top,height-h-margin)
        middle=top+max(0,(available-h)//2)
        candidates=[(left,bottom),(right,bottom),(left,top),(right,top),(left,middle),(right,middle)]
        if pos:
            wanted=(max(margin,min(right,round(pos['x']*width))),max(top,min(bottom,round(pos['y']*height))))
            candidates=[wanted] if strict else [wanted]+[(wanted[0],wanted[1]+dy) for dy in (h+gap,-h-gap)]+candidates
        else:
            slot=entry.get('slot',0 if kind=='weather' else 1 if kind=='calendar' else index%6)
            candidates=[candidates[slot]]+candidates
        # Dense/stacked layouts are valid; no four-corner identity constraint.
        if not (strict and pos):
            for row in range(max(1,available//max(1,h+gap))):
                for column in range(max(1,(width-margin)//max(1,w+gap))):
                    candidates.append((margin+column*(w+gap),top+row*(h+gap)))
        chosen=None
        for x,y in candidates:
            rect=(max(margin,min(right,x)),max(top,min(bottom,y)),w,h)
            if not any(intersects(rect,other) for other in placed.values()):chosen=rect;break
        if chosen is None and not (strict and pos) and not (pos and ('width' in pos or 'height' in pos)):
            for factor in (.85,.7,.55,.4):
                rw=max(130,round(w*factor));rh=max(100,round(h*factor))
                for y in range(top,max(top+1,height-margin-rh+1),8):
                    for x in range(margin,max(margin+1,width-margin-rw+1),8):
                        rect=(x,y,rw,rh)
                        if not any(intersects(rect,other) for other in placed.values()):chosen=rect;break
                    if chosen:break
                if chosen:break
        if chosen is None:
            if strict:raise ValueError('Este tamanho/posicao nao cabe sem sobrepor outra previa. Reduza o tamanho ou mova outra previa.')
            # Viewport shrinking must still keep every saved preview reachable.
            cols=2;rw=max(1,(width-3*margin)//cols);rh=max(1,(available-gap*(rows-1))//rows)
            return {k:(margin+(i%cols)*(rw+margin),top+(i//cols)*(rh+gap),rw,rh) for i,k in enumerate(entries)}
        placed[key]=chosen
    return placed
