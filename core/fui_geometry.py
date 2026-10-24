"""Original hologram geometry usable before Qt or WebGL dependencies load."""
import math
from functools import lru_cache

BACKGROUND='#050d12'
CYAN='#69e7f3'
RED='#ff4a58'
TEXT='#edfaff'
MUTED='#a1bdc9'


@lru_cache(maxsize=1)
def _shell():
    points=[]
    for i in range(104):
        y=1-2*i/103
        angle=i*math.pi*(3-math.sqrt(5))
        radius=math.sqrt(max(0,1-y*y))
        points.append((math.cos(angle)*radius,y,math.sin(angle)*radius))
    links=[]
    for i,a in enumerate(points):
        nearest=sorted(range(len(points)),key=lambda j:sum((a[k]-points[j][k])**2 for k in range(3)))
        links.extend((i,j) for j in nearest[1:5] if j>i)
    return tuple(points),tuple(links)


def core_lines(seconds):
    """Perspective-projected wires and filaments, not a second UI render engine."""
    angle=seconds*.10
    def project(point):
        x,y,z=point
        x,z=x*math.cos(angle)+z*math.sin(angle),z*math.cos(angle)-x*math.sin(angle)
        y,z=y*math.cos(.20)-z*math.sin(.20),z*math.cos(.20)+y*math.sin(.20)
        perspective=1/(1-z*.10)
        return x*perspective,y*perspective,z
    points,links=_shell()
    vertices=[project(point) for point in points]
    lines=[(vertices[a],vertices[b],'shell') for a,b in links]
    for band in range(7):
        latitude=(band+1)/8*math.pi
        ring=[project((math.cos(a)*math.sin(latitude),math.cos(latitude),math.sin(a)*math.sin(latitude)))
              for a in (i*math.tau/64 for i in range(65))]
        lines.extend((ring[i],ring[i+1],'shell') for i in range(64) if i%9!=0)
    for strand in range(7):
        ring=[]
        for i in range(49):
            a=i*math.tau/48+seconds*.16+strand
            radius=.27+.045*math.sin(a*3+strand)
            ring.append(project((math.cos(a)*radius,math.sin(a)*radius*math.cos(strand),math.sin(a)*radius*math.sin(strand))))
        lines.extend((ring[i],ring[i+1],'heart') for i in range(48))
    return lines,vertices


def entry_lines(seconds):
    """Independent entry reactor: depth-sorted shell, plasma and tilted orbits."""
    def project(x,y,z):
        a=seconds*.13
        x,z=x*math.cos(a)+z*math.sin(a),z*math.cos(a)-x*math.sin(a)
        y,z=y*.94-z*.34,y*.34+z*.94
        scale=1/(1-z*.13)
        return x*scale,y*scale,z
    lines=[]
    points,links=_shell()
    vertices=[project(*p) for p in points]
    lines.extend((vertices[a],vertices[b],'shell') for a,b in links)
    for band in range(11):
        latitude=(band+1)*math.pi/12
        ring=[project(math.cos(a)*math.sin(latitude),math.cos(latitude),math.sin(a)*math.sin(latitude)) for a in (i*math.tau/64 for i in range(65))]
        lines.extend((ring[i],ring[i+1],'shell') for i in range(64) if i%16<12)
    for strand in range(5):
        ring=[]
        for i in range(73):
            a=i*math.tau/72
            r=.25+.08*math.sin(a*5+seconds*1.1+strand)
            ring.append(project(r*math.cos(a),r*math.sin(a)*math.cos(strand),r*math.sin(a)*math.sin(strand)))
        lines.extend((ring[i],ring[i+1],'heart') for i in range(72))
    for band in range(3):
        ring=[]
        tilt=.35+band*.85
        for i in range(97):
            a=i*math.tau/96+seconds*(.08 if band%2 else -.10)
            x,y=1.24*math.cos(a),1.24*math.sin(a)
            ring.append(project(x,y*math.cos(tilt),y*math.sin(tilt)))
        lines.extend((ring[i],ring[i+1],'orbit') for i in range(96) if i%24<19)
    return lines,vertices


def chamfer_points(width,height,inset=5,cut=16):
    return (inset+cut,inset,width-inset-cut,inset,width-inset,inset+cut,
        width-inset,height-inset-cut,width-inset-cut,height-inset,
        inset+cut,height-inset,inset,height-inset-cut,inset,inset+cut)
