"""Dependency-light entry HUD. Tk works even when Qt and Pillow are missing."""
import math
import tkinter as tk
from pathlib import Path
from core.fui_geometry import entry_lines as core_lines,BACKGROUND,CYAN,RED,TEXT,MUTED

NAMES=('Dependências','Arquivos','Áudio','IA','Gmail','WhatsApp')


def rounded_box(canvas,x,y,w,h,radius=14,**options):
    r=min(radius,w/2,h/2)
    points=(x+r,y,x+w-r,y,x+w,y,x+w,y+r,
        x+w,y+h-r,x+w,y+h,x+w-r,y+h,
        x+r,y+h,x,y+h,x,y+h-r,x,y+r,x,y)
    return canvas.create_polygon(points,smooth=True,splinesteps=24,**options)


class BootstrapSurface:
    def __init__(self,root,width=840,height=580,mode='startup',reduced=False,names=NAMES):
        self.root=root;self.width=width;self.height=height
        self.motion_reduced=bool(reduced)
        self.names=tuple(names)
        self.mode=mode
        self.rail=max(176,int(width*.37))
        self.center=(self.rail/2+10,height*.46)
        self.core_radius=min(101,self.rail*.33)
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
            image=ImageEnhance.Brightness(image).enhance(.42)
            image=Image.blend(image,Image.new('RGB',(width,height),'#041827'),.64)
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
        c.create_text(30,39,text='DIEF JARVIS',fill=TEXT,font=('Segoe UI',19,'bold'),anchor='w')
        c.create_text(32,70,text='Acesso ao sistema' if mode=='admin' else 'Preparando seu ambiente',fill=CYAN,font=('Segoe UI',11),anchor='w')
        c.create_line(34,96,width-34,96,fill='#295967')
        c.create_line(34,96,100,96,fill='#8adaff',width=2)
        c.create_text(width-32,36,text='×',fill=MUTED,font=('Segoe UI',19),tags='close')
        c.create_line(self.rail,115,self.rail,height-118,fill='#20445e')
        c.create_line(self.rail,115,self.rail,160,fill=RED,width=2)
        self.rows={};self.indicators={};self.states={};self.checked=set();self.row_edges={}
        row_x=self.rail+20
        columns=2 if width>=800 else 1
        row_height=(height-216)/max(1,math.ceil(len(self.names)/columns))
        card_width=(width-row_x-28-(columns-1)*10)/columns
        for index,name in enumerate(self.names if mode=='startup' else ()):
            y=112+(index//columns)*row_height
            card_x=row_x+(index%columns)*(card_width+10)
            edge=rounded_box(c,card_x,y,card_width,row_height-10,8,fill='#061827',outline='#38789b',width=1)
            self.row_edges[name]=edge
            c.create_line(card_x+14,y+35,card_x+card_width-14,y+35,fill='#19394f')
            c.create_text(card_x+15,y+19,text=name,fill=TEXT,font=('Segoe UI',10,'bold'),anchor='w')
            label_width=card_width-30
            label=tk.Label(root,text='Aguardando',anchor='nw',justify='left',fg=MUTED,bg='#061827',font=('Segoe UI',9),wraplength=label_width)
            c.create_window(card_x+15,y+46,window=label,anchor='nw',width=label_width,height=max(16,row_height-62))
            self.rows[name]=label
            self.indicators[name]=c.create_text(card_x+card_width-18,y+19,text='·',fill='#4a6370',font=('Segoe UI',12,'bold'))
            self.states[name]='pending'
        cx,cy=self.center
        # Static concentric light remains cheap even before graphics dependencies load.
        for radius,color in ((115,'#101a2b'),(95,'#211526'),(72,'#301523'),(45,'#481824'),(24,'#692b31')):
            c.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,fill=color,outline='')
        for radius in (119,131,140):
            c.create_arc(cx-radius,cy-radius,cx+radius,cy+radius,start=35+radius,extent=145,style='arc',outline='#225572',width=1)
        lines,_=core_lines(0)
        self.wires=[c.create_line(0,0,0,0,fill='#ff5862',width=1) for _ in lines]
        cx,cy=self.center
        self.ring=c.create_arc(cx-112,cy-112,cx+112,cy+112,start=0,extent=48,style='arc',outline=RED,width=3)
        self.orbit=c.create_oval(cx-122,cy+126,cx+122,cy+144,outline='#3d91a3',width=1)
        self.nodes=[c.create_oval(0,0,0,0,fill='#a2f2ff',outline=CYAN) for _ in range(3)]
        c.create_oval(cx-90,cy+130,cx+90,cy+141,outline='#286774')
        self.summary=c.create_text(self.center[0],height-141,text='Verificação local' if mode=='startup' else 'Acesso protegido',fill=CYAN,font=('Segoe UI',10),anchor='center')
        self.counter=c.create_text(self.center[0],height-121,text='Aguardando verificações' if mode=='startup' else 'Confirmação do Windows',fill=MUTED,font=('Segoe UI',8),anchor='center')
        self.progress_y=height-98
        c.create_rectangle(16,self.progress_y+2,width-16,height-16,fill=BACKGROUND,outline='')
        c.create_line(30,self.progress_y,width-30,self.progress_y,fill='#264955',width=2)
        self.progress=c.create_line(30,self.progress_y,30,self.progress_y,fill=CYAN,width=2)
        self.beam=c.create_line(22,6,75,6,fill='#abf2ff',width=2)
        self.notice=tk.Label(root,text='Verificando os componentes necessários para iniciar.',fg=MUTED,bg=BACKGROUND,font=('Segoe UI',10),anchor='nw',justify='left',wraplength=width-215)
        c.create_window(32,height-82,window=self.notice,anchor='nw',width=width-215,height=64)
        self.retry_position={'x':width-166,'y':height-66,'width':134,'height':36}
        if mode=='admin':
            c.create_text(row_x+4,140,text='Permissão para iniciar',fill=TEXT,font=('Segoe UI',18,'bold'),anchor='nw',width=width-row_x-40)
            c.create_text(row_x+4,204,text='O Windows solicitará sua autorização.\nSuas contas e ferramentas só serão iniciadas depois dessa confirmação.',fill=MUTED,font=('Segoe UI',11),anchor='nw',width=width-row_x-40)
        self._drag=None
        c.tag_bind('close','<Enter>',lambda _:c.configure(cursor='hand2'))
        c.tag_bind('close','<Leave>',lambda _:c.configure(cursor=''))
        c.bind('<ButtonPress-1>',self._start_drag)
        c.bind('<B1-Motion>',self._move)
        self.animate(0)

    def _start_drag(self,event):
        self._drag=(event.x_root-self.root.winfo_x(),event.y_root-self.root.winfo_y()) if event.y<90 and event.x<self.width-64 else None

    def _move(self,event):
        if self._drag:self.root.geometry(f'+{max(0,event.x_root-self._drag[0])}+{max(0,event.y_root-self._drag[1])}')

    def update_status(self,name,text,state):
        if name not in self.rows:return
        color={'ok':'#83e2ba','working':CYAN,'warning':'#ffc079','error':'#ff8791'}.get(state,MUTED)
        self.rows[name].configure(text=text,fg=color)
        self.states[name]=state
        self.canvas.itemconfigure(self.indicators[name],fill=color,text={'ok':'✓','error':'!','warning':'!','working':'›'}.get(state,'·'))
        self.canvas.itemconfigure(self.row_edges[name],outline=color if state in ('working','error') else '#20455e',width=2 if state=='working' else 1)
        if state=='ok':self.checked.add(name)
        else:self.checked.discard(name)
        self.canvas.itemconfigure(self.counter,text=f'{len(self.checked)} de {len(self.names)} verificações OK')
        if state in ('working','error'):self.canvas.itemconfigure(self.summary,text=name,fill=color)
        self.canvas.coords(self.progress,30,self.progress_y,30+(self.width-60)*len(self.checked)/max(1,len(self.names)),self.progress_y)

    def animate(self,seconds):
        if self.motion_reduced:seconds=0
        c=self.canvas
        cx,cy=self.center
        lines,_=core_lines(seconds)
        for identifier,(a,b,kind) in zip(self.wires,lines):
            c.coords(identifier,cx+a[0]*self.core_radius,cy+a[1]*self.core_radius,cx+b[0]*self.core_radius,cy+b[1]*self.core_radius)
            c.itemconfigure(identifier,fill=('#b4f0ff' if a[2]+b[2]>0 else '#28516c') if kind=='orbit' else '#ffe1b8' if kind=='heart' else '#ff5262' if a[2]+b[2]>0 else '#6b283d')
        c.itemconfigure(self.ring,start=seconds*7)
        for i,node in enumerate(self.nodes):
            a=seconds*.16+i*math.tau/3;x=cx+math.cos(a)*93;y=cy+math.sin(a)*25
            c.coords(node,x-2,y-2,x+2,y+2)
        x=25+(self.width-100)*((seconds/9)%1)
        c.coords(self.beam,x,6,x+45,6)
