import sys, math
from PIL import Image, ImageDraw, ImageFont
W=H=1080
BG=(10,14,20); OR=(255,92,31); CY=(34,211,238); WH=(245,247,250)
F=lambda n,s: ImageFont.truetype(f"/usr/share/fonts/opentype/inter/{n}",s)
def base(accent):
    im=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(im)
    d.ellipse((140,140,940,940),outline=accent,width=18)
    return im,d
def icon(d,kind,c):
    cx,cy=540,470
    if kind=="start":
        d.polygon([(470,350),(470,590),(660,470)],fill=c)
    elif kind=="sleep":
        d.ellipse((400,330,640,570),fill=c); d.ellipse((470,300,700,530),fill=BG)
        for x,y,s in ((640,380,60),(700,330,44)): d.text((x,y),"z",font=F("InterDisplay-Black.otf",s),fill=c,anchor="mm")
    elif kind=="desk":
        d.rounded_rectangle((380,330,700,520),radius=20,outline=c,width=16)
        d.rectangle((520,520,560,580),fill=c); d.rounded_rectangle((440,580,640,610),radius=10,fill=c)
    elif kind=="phone":
        d.rounded_rectangle((460,300,620,600),radius=30,outline=c,width=16); d.ellipse((528,560,552,584),fill=c)
    elif kind=="myth":
        d.text((cx,cy),"?!",font=F("InterDisplay-Black.otf",260),fill=c,anchor="mm")
    elif kind=="qa":
        d.rounded_rectangle((370,330,710,560),radius=60,fill=c)
        d.polygon([(450,550),(430,630),(520,555)],fill=c)
        d.text((540,445),"Q&A",font=F("InterDisplay-Black.otf",110),fill=BG,anchor="mm")
items=[("start","START HERE",OR),("sleep","SLEEP",CY),("desk","DESK & SITTING",OR),("phone","PHONE & NECK",CY),("myth","MYTHS",OR),("qa","ASK A PHYSIO",CY)]
for kind,label,c in items:
    im,d=base(c); icon(d,kind,c)
    fs=78 if len(label)<12 else 60
    d.text((540,720),label,font=F("InterDisplay-Black.otf",fs),fill=WH,anchor="mm")
    im.save(f"{sys.argv[1]}/Highlight - {label.title()}.png")
# contact sheet
import glob
fs=sorted(glob.glob(f"{sys.argv[1]}/Highlight - *.png"))
sheet=Image.new("RGB",(3*360,2*360),BG)
for i,f in enumerate(fs): sheet.paste(Image.open(f).resize((360,360)),((i%3)*360,(i//3)*360))
sheet.save(f"{sys.argv[1]}/sheet.jpg",quality=88)
