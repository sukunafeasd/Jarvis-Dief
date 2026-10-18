"""Dependency-light entry HUD. Tk works even when Qt and Pillow are missing."""
import math
import tkinter as tk
from pathlib import Path
from core.fui_geometry import core_lines,BACKGROUND,CYAN,RED,TEXT,MUTED

NAMES=('Dependências','Arquivos','Áudio','IA','Gmail','WhatsApp')


def rounded_box(canvas,x,y,w,h,radius=14,**options):
    r=min(radius,w/2,h/2)
    points=(x+r,y,x+w-r,y,x+w,y,x+w,y+r,
        x+w,y+h-r,x+w,y+h,x+w-r,y+h,
        x+r,y+h,x,y+h,x,y+h-r,x,y+r,x,y)
    return canvas.create_polygon(points,smooth=True,splinesteps=24,**options)


class BootstrapSurface:
    def __init__(self,root,width=660,height=440,mode='startup',reduced=False,names=NAMES):
        self.root=root;self.width=width;self.height=height
        self.motion_reduced=bool(reduced)
        self.names=tuple(names)
        self.center=(width/2,191) if mode=='admin' else (101,213)
        self.canvas=tk.Canvas(root,width=width,height=height,bg=BACKGROUND,highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        c=self.canvas
        self.photo=None
        # Raster atmosphere is optional: dependency repair must not require Pillow.
        try:
            from PIL import Image,ImageTk,ImageEnhance
            from PIL.ImageOps import fit
            path=Path(__file__).resolve().parent/'spatial/assets/deep-space.png'
            with Image.open(path) as source:image=fit(source.convert('RGB'),(width,height))
            image=ImageEnhance.Brightness(image).enhance(.28)
            self.photo=ImageTk.PhotoImage(image,master=root)
            c.create_image(0,0,image=self.photo,anchor='nw')
        except (ImportError,OSError,tk.TclError):
            pass
        for stroke,color in ((12,'#092c43'),(7,'#164a65'),(2,'#64c6f5'),(1,'#c3efff')):
            rounded_box(c,6,6,width-12,height-12,fill='',outline=color,width=stroke)
        rounded_box(c,11,11,width-22,height-22,fill='',outline='#275975',width=1)
        c.create_line(26,7,width-26,7,fill='#91d9ff')
        x=width*.65
        c.create_line(x-36,7,x-28,14,x+28,14,x+36,7,fill='#54bdf5')
        c.create_text(34,42,text='DIEF JARVIS',fill=TEXT,font=('Segoe UI',21,'bold'),anchor='w')
        c.create_text(36,76,text='ACESSO AO SISTEMA' if mode=='admin' else 'INICIALIZANDO AMBIENTE',fill=CYAN,font=('Segoe UI',10),anchor='w')
        c.create_line(34,96,width-34,96,fill='#295967')
        c.create_line(34,96,100,96,fill='#8adaff',width=2)
        c.create_text(width-32,36,text='×',fill=MUTED,font=('Segoe UI',19),tags='close')
        self.rows={};self.indicators={};self.states={};self.checked=set()
        for index,name in enumerate(self.names if mode=='startup' else ()):
            y=115+index*44
            rounded_box(c,195,y,width-206,41,8,fill='#061827',outline='#27658d',width=1)
            c.create_line(197,y+9,197,y+31,fill=CYAN,width=2)
            c.create_text(212,y+9,text=name,fill=TEXT,font=('Segoe UI',9,'bold'),anchor='w')
            label=tk.Label(root,text='Aguardando',anchor='w',fg=MUTED,bg='#061827',font=('Segoe UI',9),wraplength=365)
            c.create_window(212,y+29,window=label,anchor='w',width=365,height=22)
            self.rows[name]=label
            self.indicators[name]=c.create_oval(width-34,y+8,width-28,y+14,fill='#4a6370',outline='')
            self.states[name]='pending'
        lines,_=core_lines(0)
        self.wires=[c.create_line(0,0,0,0,fill='#ff5862',width=1) for _ in lines]
        cx,cy=self.center
        c.create_oval(cx-86,cy-86,cx+86,cy+86,outline='#e74d58',width=1)
        self.ring=c.create_arc(cx-92,cy-92,cx+92,cy+92,start=0,extent=68,style='arc',outline=RED,width=3)
        self.orbit=c.create_oval(cx-93,cy-23,cx+93,cy+27,outline='#3d91a3',width=1)
        self.nodes=[c.create_oval(0,0,0,0,fill='#a2f2ff',outline=CYAN) for _ in range(3)]
        c.create_oval(cx-78,cy+103,cx+78,cy+116,outline='#286774')
        if mode=='startup':c.create_text(102,352,text='VERIFICAÇÃO LOCAL',fill=CYAN,font=('Segoe UI',8),anchor='center')
        c.create_line(34,397,width-34,397,fill='#264955',width=2)
        self.progress=c.create_line(34,397,34,397,fill=CYAN,width=2)
        self.beam=c.create_line(22,6,75,6,fill='#abf2ff',width=2)
        self.notice=tk.Label(root,text='Verificação local e de contas conectadas',fg=MUTED,bg=BACKGROUND,font=('Segoe UI',9))
        c.create_window(width/2,336 if mode=='admin' else 418,window=self.notice,width=width-60,height=40 if mode=='admin' else 21)
        self.animate(0)

    def update_status(self,name,text,state):
        if name not in self.rows:return
        color={'ok':'#83e2ba','working':CYAN,'warning':'#ffc079','error':'#ff8791'}.get(state,MUTED)
        self.rows[name].configure(text=text,fg=color)
        self.states[name]=state
        self.canvas.itemconfigure(self.indicators[name],fill=color)
        if state=='working':self.checked.discard(name)
        else:self.checked.add(name)
        self.canvas.coords(self.progress,34,397,34+(self.width-68)*len(self.checked)/max(1,len(self.names)),397)

    def animate(self,seconds):
        if self.motion_reduced:seconds=0
        c=self.canvas
        cx,cy=self.center
        lines,_=core_lines(seconds)
        for identifier,(a,b,kind) in zip(self.wires,lines):
            c.coords(identifier,cx+a[0]*77,cy+a[1]*77,cx+b[0]*77,cy+b[1]*77)
            c.itemconfigure(identifier,fill='#ffb69a' if kind=='heart' else '#e1535f' if a[2]+b[2]>0 else '#56212e')
        c.itemconfigure(self.ring,start=seconds*7)
        for i,node in enumerate(self.nodes):
            a=seconds*.16+i*math.tau/3;x=cx+math.cos(a)*93;y=cy+math.sin(a)*25
            c.coords(node,x-2,y-2,x+2,y+2)
        x=25+(self.width-100)*((seconds/9)%1)
        c.coords(self.beam,x,6,x+45,6)
