"""Small vector animations: instruction cues, never a vision-treatment game."""
import math
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QPainterPath
from PySide6.QtWidgets import QWidget


class ExerciseAnimation(QWidget):
    def __init__(self, kind="distance", reduced=False, parent=None):
        super().__init__(parent)
        self.kind, self.reduced, self.phase = kind, reduced, 0.0
        self.setMinimumHeight(150)
        self.setAccessibleName("Egzersiz yönergesinin animasyonlu gösterimi")
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.advance)

    def showEvent(self, event):
        if not self.reduced:
            self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def advance(self):
        self.phase += .04
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#101b2d"))
        p.translate(self.width()/2, self.height()/2)
        scale = min(self.width()/420, self.height()/210)
        p.scale(scale, scale)
        accent, pale = QColor("#7dd3fc"), QColor("#315b85")
        t = math.sin(self.phase*1.6) if not self.reduced else .25
        if self.kind in ("distance", "blink"):
            if self.kind == "distance":
                # A window and a distant landscape: look beyond the actual screen.
                p.setPen(QPen(pale, 3))
                p.setBrush(QColor("#0c1627"))
                p.drawRoundedRect(QRectF(-130,-75,260,140),16,16)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#d9c47f"))
                p.drawEllipse(QPointF(72,-38),15,15)
                path = QPainterPath(QPointF(-127,45))
                path.cubicTo(-80,-25,-45,48,10,7)
                path.cubicTo(64,-28,88,24,127,5)
                path.lineTo(127,62); path.lineTo(-127,62)
                p.setBrush(pale); p.drawPath(path)
                p.setPen(QPen(accent,3)); p.drawLine(QPointF(0,-72),QPointF(0,62))
                p.drawLine(QPointF(-128,-6),QPointF(128,-6))
                p.setFont(QFont("Adwaita Sans",12)); p.drawText(QRectF(-150,77,300,24),Qt.AlignmentFlag.AlignCenter,"Yaklaşık 6 metre uzağa bak")
            else:
                openness = max(.08, abs(math.cos(self.phase*.65))) if not self.reduced else 1
                p.setPen(QPen(accent,4)); p.setBrush(Qt.BrushStyle.NoBrush)
                path = QPainterPath(QPointF(-83,0))
                path.cubicTo(-35,-55*openness,35,-55*openness,83,0)
                path.cubicTo(35,55*openness,-35,55*openness,-83,0)
                p.drawPath(path); p.setBrush(accent)
                p.drawEllipse(QRectF(-15,-15*openness,30,30*openness))
        elif self.kind == "hands":
            p.setPen(QPen(accent,8,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            for side in (-1,1):
                for i in range(5):
                    x = side*55+(i-2)*12
                    p.drawLine(QPointF(x,25),QPointF(x+(i-2)*(t+1)*5,-22-(2-abs(i-2))*10))
                p.drawLine(QPointF(side*55,25),QPointF(side*55,65))
        else:
            # Supported standing / seated stick figure with gentle range of motion.
            seated = self.kind in ("chest","shoulders","sitstand")
            lift = (t+1)*15 if self.kind == "sitstand" else (t+1)*5 if self.kind == "calf" else 0
            p.setPen(QPen(pale,6,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(-95,85),QPointF(95,85))
            if seated or self.kind == "calf":
                cx = 45 if self.kind == "calf" else -14
                p.drawLine(QPointF(cx-28,-16),QPointF(cx-28,40))
                p.drawLine(QPointF(cx-28,40),QPointF(cx+28,40))
                p.drawLine(QPointF(cx-25,40),QPointF(cx-25,80))
                p.drawLine(QPointF(cx+25,40),QPointF(cx+25,80))
            p.setPen(QPen(accent,6,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            p.setBrush(QColor("#101b2d"))
            head = -50-lift
            p.drawEllipse(QPointF(0,head),14,14)
            p.drawLine(QPointF(0,head+20),QPointF(0,30-lift))
            swing = t*24 if self.kind == "walk" else 0
            if seated:
                p.drawLine(QPointF(0,30-lift),QPointF(32,43-lift*.4))
                p.drawLine(QPointF(32,43-lift*.4),QPointF(33,80))
                p.drawLine(QPointF(0,30-lift),QPointF(-15,48-lift*.4))
                p.drawLine(QPointF(-15,48-lift*.4),QPointF(-17,80))
            else:
                p.drawLine(QPointF(0,30-lift),QPointF(-18-swing,78-lift))
                p.drawLine(QPointF(0,30-lift),QPointF(18+swing,78-lift))
            arm = -20-t*9 if self.kind in ("chest","shoulders") else 14
            spread = 60+(t+1)*9 if self.kind == "chest" else 32
            p.drawLine(QPointF(0,head+25),QPointF(-spread,arm-lift-swing*.4))
            p.drawLine(QPointF(0,head+25),QPointF(spread,arm-lift+swing*.4))
        p.end()


class TimerDial(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.text, self.subtitle, self.progress = "00:00:00", "BAŞLAMAYA HAZIR", 0
        self.setMinimumSize(330,300)
        self.setAccessibleName("Çalışma sayacı")

    def set_value(self, text, subtitle, progress):
        self.text, self.subtitle, self.progress = text, subtitle, min(1,max(0,progress))
        self.setAccessibleDescription(f"{text}, {subtitle}")
        self.update()

    def paintEvent(self, event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        side=min(self.width()-26,self.height()-24,310)
        box=QRectF((self.width()-side)/2,(self.height()-side)/2,side,side)
        p.setPen(QPen(QColor("#263a55"),7)); p.drawEllipse(box)
        p.setPen(QPen(QColor("#60a5fa"),7,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        p.drawArc(box,90*16,-max(4,int(self.progress*360*16)))
        p.setPen(QColor("#eaf2ff"))
        font=QFont("Adwaita Mono",35); font.setWeight(QFont.Weight.Medium); p.setFont(font)
        p.drawText(QRectF(0,self.height()/2-37,self.width(),65),Qt.AlignmentFlag.AlignCenter,self.text)
        p.setFont(QFont("Adwaita Sans",9)); p.setPen(QColor("#9fb2cc"))
        p.drawText(QRectF(0,self.height()/2+31,self.width(),25),Qt.AlignmentFlag.AlignCenter,self.subtitle)
        p.end()
