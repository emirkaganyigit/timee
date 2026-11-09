from __future__ import annotations

import argparse
from datetime import datetime
import math
import os
from pathlib import Path
import sys

from PySide6.QtCore import QEvent, QLockFile, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QDialog, QFrame, QHBoxLayout,
    QMainWindow, QMessageBox, QProgressBar, QScrollArea, QSpinBox, QLayout,
    QSizeGrip, QStackedWidget, QVBoxLayout, QWidget,
)

from .animation import TimerDial
from .content import SOURCES
from .engine import Engine
from .planner import DAYS, PlannerWidget
from .storage import Store
from .theme import apply_theme, button, card, clock_text, human_time, label
from .wellness import BreakDialog, EXERCISE_MAP, LibraryWidget

MONTHS = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")


def app_icon():
    image = QPixmap(128, 128); image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#2563eb")); p.drawRoundedRect(3,3,122,122,30,30)
    p.setBrush(QColor("#dbeafe")); p.drawRoundedRect(35,31,19,66,8,8); p.drawRoundedRect(73,31,19,66,8,8)
    p.end()
    return QIcon(image)


class MiniWindow(QWidget):
    def __init__(self, owner):
        # Tool + stays-on-top gives every compositor the strongest standard Qt
        # hint.  On KDE/Wayland the installer also adds a narrowly matched KWin
        # overlay rule, because the compositor is free to ignore client hints.
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.owner = owner
        self.setWindowTitle("Timee · Mini sayaç")
        self.setWindowIcon(app_icon())
        self.setObjectName("miniWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(220, 120)
        self.setMaximumSize(640, 360)
        saved_size = owner.preferences.get("mini_size", [300, 145])
        if (isinstance(saved_size, list) and len(saved_size) == 2
                and all(isinstance(value, int) for value in saved_size)):
            initial_size = (max(220, min(640, saved_size[0])), max(120, min(360, saved_size[1])))
        else:
            initial_size = (300, 145)
        self.setStyleSheet("QWidget#miniWindow { background: transparent; }")
        window_layout = QVBoxLayout(self)
        window_layout.setContentsMargins(0, 0, 0, 0)
        self.surface = QFrame()
        self.surface.setObjectName("miniSurface")
        window_layout.addWidget(self.surface)
        layout = QVBoxLayout(self.surface); layout.setContentsMargins(14,10,10,9); layout.setSpacing(3)
        row = QHBoxLayout()
        self.mode = label("KRONOMETRE", "eyebrow"); row.addWidget(self.mode); row.addStretch()
        close = button("×", self.close, "link"); close.setAccessibleName("Yüzen pencereyi kapat")
        close.setToolTip("Yalnızca mini pencereyi kapat; sayaç çalışmaya devam eder")
        close.setFixedSize(28, 28)
        row.addWidget(close); layout.addLayout(row)
        self.time = label("00:00:00"); self.time.setStyleSheet("font-family: 'Adwaita Mono'; font-size: 36px; font-weight: 600;")
        layout.addWidget(self.time)
        row = QHBoxLayout()
        self.state = label("Hazır", "muted"); row.addWidget(self.state); row.addStretch()
        self.toggle = button("Başlat", owner.toggle_running, "primary"); row.addWidget(self.toggle)
        self.grip = QSizeGrip(self.surface)
        self.grip.setAccessibleName("Mini pencereyi boyutlandır")
        self.grip.setToolTip("Küçültmek veya büyütmek için sürükle")
        row.addWidget(self.grip, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(row)
        self.setToolTip("Mini sayaç diğer uygulamaların üstünde kalır. Boş bir alandan sürükleyerek taşı.")
        for draggable in (self.surface, self.mode, self.time, self.state):
            draggable.installEventFilter(self)
        self.resize(*initial_size)

    def eventFilter(self, watched, event):
        if (event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
                and self.windowHandle() is not None):
            self.windowHandle().startSystemMove()
            return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        width = event.size().width()
        font_size = 24 if width < 260 else 30 if width < 340 else 36
        self.time.setStyleSheet(
            f"font-family: 'Adwaita Mono'; font-size: {font_size}px; font-weight: 600;"
        )
        self.state.setVisible(width >= 275)
        self.owner.preferences["mini_size"] = [event.size().width(), event.size().height()]
        super().resizeEvent(event)

    def closeEvent(self, event):
        self.owner.save()
        super().closeEvent(event)

    def refresh(self):
        e=self.owner.engine
        self.mode.setText("KRONOMETRE" if e.mode=="stopwatch" else "ZAMANLAYICI")
        self.time.setText(clock_text(e.stopwatch_elapsed if e.mode=="stopwatch" else math.ceil(e.timer_remaining)))
        self.state.setText("Mola zamanı" if e.state=="break" else "Çalışıyorsun" if e.state=="running" else "Duraklatıldı" if e.state=="paused" else "Başlamaya hazır")
        self.toggle.setText("Duraklat" if e.state=="running" else "Başlat")
        self.toggle.setEnabled(e.state!="break")


class SettingsWidget(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.setSpacing(16)
        outer.addWidget(label("Ritmini kendin belirle.", "title"))
        outer.addWidget(label("Kısa molalar, sessiz hatırlatmalar ve sana uygun bir çalışma günü.", "muted", True))
        scroll=QScrollArea(); scroll.setWidgetResizable(True)
        content=QWidget(); layout=QVBoxLayout(content); layout.setContentsMargins(0,4,8,8); layout.setSpacing(16)
        frame,box=card(); box.addWidget(label("Mola düzeni", "sectionTitle"))
        self.eye = QCheckBox("Göz dinlendirme hatırlatıcıları"); self.eye.setChecked(owner.engine.eye_enabled)
        self.movement = QCheckBox("Ayağa kalkma ve hareket hatırlatıcıları"); self.movement.setChecked(owner.engine.movement_enabled)
        self.eye_minutes = QSpinBox(); self.eye_minutes.setRange(10,120); self.eye_minutes.setSuffix(" dakikada bir"); self.eye_minutes.setValue(round(owner.engine.eye_interval/60))
        self.movement_minutes=QSpinBox(); self.movement_minutes.setRange(20,120); self.movement_minutes.setSuffix(" dakikada bir"); self.movement_minutes.setValue(round(owner.engine.movement_interval/60))
        self.eye_minutes.setAccessibleName("Göz molası sıklığı")
        self.movement_minutes.setAccessibleName("Hareket molası sıklığı")
        for check,spin in ((self.eye,self.eye_minutes),(self.movement,self.movement_minutes)):
            row=QHBoxLayout(); row.addWidget(check,1); row.addWidget(spin); box.addLayout(row)
        box.addWidget(label("Önerilen başlangıç: 20 dakikada 20 saniye uzağa bakış; 60 dakikada 5 dakika hareket. Aralarında en fazla 3 dakika olan molalar birleşir. Sayaç dururken hatırlatma süresi ilerlemez.","muted",True))
        save=button("Mola düzenini kaydet", self.save_intervals,"primary"); box.addWidget(save,alignment=Qt.AlignmentFlag.AlignLeft)
        self.saved=label("", "hint"); box.addWidget(self.saved)
        layout.addWidget(frame)
        frame,box=card(); box.addWidget(label("Sakin bir deneyim", "sectionTitle"))
        self.reduced=QCheckBox("Animasyonları azalt"); self.reduced.setChecked(owner.preferences["reduced_motion"])
        self.sound=QCheckBox("Egzersiz süresi dolunca kısa ses çal"); self.sound.setChecked(owner.preferences["sound"])
        self.reduced.toggled.connect(lambda checked:self.preference("reduced_motion",checked))
        self.sound.toggled.connect(lambda checked:self.preference("sound",checked))
        box.addWidget(self.reduced); box.addWidget(self.sound)
        box.addWidget(label("Varsayılan deneyim sessizdir; kütüphanede de kullanabilirsin. Tüm kayıtlar bu bilgisayarda kalır.","muted",True)); layout.addWidget(frame)
        frame,box=card(); box.addWidget(label("Kaynaklar ve yaklaşım", "sectionTitle"))
        box.addWidget(label("Sıklıklar herkes için kesin tıbbi sınırlar değildir. 20–20–20 bir kurum önerisidir; hareket için 60 dakika / 5 dakika, rehbere dayalı başlangıç ayarıdır. İhtiyacına göre değiştirebilirsin.","muted",True))
        for source in SOURCES:
            link=button(source["title"]+"  ↗",lambda checked=False,url=source["url"]:QDesktopServices.openUrl(QUrl(url)),"link")
            link.setStyleSheet("text-align: left; padding-left: 0;")
            box.addWidget(link); box.addWidget(label(source["summary"],"hint",True))
        layout.addWidget(frame); layout.addStretch(); scroll.setWidget(content); outer.addWidget(scroll)

    def preference(self, key, checked):
        self.owner.preferences[key]=checked; self.owner.save()

    def save_intervals(self):
        self.owner.pulse()
        e=self.owner.engine
        e.eye_enabled=self.eye.isChecked(); e.movement_enabled=self.movement.isChecked()
        e.eye_interval=self.eye_minutes.value()*60; e.movement_interval=self.movement_minutes.value()*60
        e.since_eye=e.since_movement=0
        self.owner.save(); self.owner.refresh()
        self.saved.setText("Kaydedildi. Yeni mola aralıkları şimdi başlıyor.")


class Window(QMainWindow):
    def __init__(self, store=None, engine=None):
        super().__init__()
        self.store=store or Store()
        data=self.store.load()
        self.engine=engine or Engine()
        if engine is None and data.get("engine"):
            self.engine.restore(data.get("engine",{}))
        prefs=data.get("preferences",{})
        prefs=prefs if isinstance(prefs,dict) else {}
        mini_size = prefs.get("mini_size", [300, 145])
        if not (isinstance(mini_size, list) and len(mini_size) == 2
                and all(isinstance(value, int) for value in mini_size)):
            mini_size = [300, 145]
        self.preferences={
            "reduced_motion": prefs.get("reduced_motion") is True,
            "sound": prefs.get("sound") is True,
            "mini_size": mini_size,
        }
        self.break_dialog=None
        self.mini=None
        self.notice=None
        self.pending_notice=None
        self.closing=False
        self.setWindowTitle("Timee · Çalışma alanın")
        self.setWindowIcon(app_icon())
        self.resize(1220,850); self.setMinimumSize(1060,760)
        root=QWidget(); outer=QHBoxLayout(root); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        sidebar=QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(205)
        side=QVBoxLayout(sidebar); side.setContentsMargins(20,30,20,26); side.setSpacing(8)
        brand=QHBoxLayout(); icon=label("Ⅱ"); icon.setStyleSheet("font-size: 25px; color: #60a5fa; font-weight: 800;")
        brand.addWidget(icon); brand.addWidget(label("timee", "brand")); brand.addStretch(); side.addLayout(brand)
        side.addWidget(label("DAHA DENGELİ ÇALIŞ", "eyebrow")); side.addSpacing(36)
        self.nav_group=QButtonGroup(self); self.nav_group.setExclusive(True)
        self.nav=[]
        for i,text in enumerate(("◷   Odak alanı","▦   Haftalık plan","✳   Egzersizler","⚙   Ayarlar")):
            b=button(text,lambda checked=False,index=i:self.navigate(index),"nav"); b.setCheckable(True)
            self.nav_group.addButton(b,i); self.nav.append(b); side.addWidget(b)
        side.addStretch()
        note,box=card("softCard",16)
        box.addWidget(label("Bir nefeslik alan.","sectionTitle",True))
        box.addWidget(label("İyi bir çalışma günü, küçük molalarla başlar.","muted",True))
        side.addWidget(note); side.addSpacing(10); side.addWidget(label("Yalnızca senin bilgisayarında.","hint",True))
        outer.addWidget(sidebar)
        main=QWidget(); main.setObjectName("page"); main_layout=QVBoxLayout(main)
        main_layout.setContentsMargins(30,27,30,20); main_layout.setSpacing(18)
        header=QHBoxLayout(); self.date_label=label("", "eyebrow"); header.addWidget(self.date_label); header.addStretch()
        self.status=label("●  Başlamaya hazır","badge"); header.addWidget(self.status); main_layout.addLayout(header)
        self.banner=label("", "error",True); self.banner.hide(); main_layout.addWidget(self.banner)
        self.stack=QStackedWidget(); main_layout.addWidget(self.stack,1)
        self.home=self.build_home()
        home_scroll=QScrollArea(); home_scroll.setWidgetResizable(True)
        home_scroll.setWidget(self.home); self.stack.addWidget(home_scroll)
        self.planner=PlannerWidget(data.get("planner",[])); self.planner.changed.connect(lambda entries:self.save())
        self.stack.addWidget(self.planner)
        self.library=LibraryWidget(); self.library.requested.connect(self.open_exercise); self.stack.addWidget(self.library)
        self.settings=SettingsWidget(self); self.stack.addWidget(self.settings)
        outer.addWidget(main,1); self.setCentralWidget(root)
        self.navigate(0); self.refresh()
        if self.store.error:
            self.show_banner(self.store.error)
        self.ticker=QTimer(self); self.ticker.setInterval(200); self.ticker.timeout.connect(self.pulse); self.ticker.start()
        self.saver=QTimer(self); self.saver.setInterval(5000); self.saver.timeout.connect(self.save); self.saver.start()

    def build_home(self):
        page=QWidget(); page.setObjectName("page"); layout=QVBoxLayout(page); layout.setContentsMargins(0,0,0,0); layout.setSpacing(18)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.addWidget(label("Kendine alan aç.","title"))
        layout.addWidget(label("Tek bir işe odaklan. Geri kalanını ritmine bırak.","muted"))
        columns=QHBoxLayout(); columns.setSpacing(18)
        focus,box=card(margins=24)
        segments=QHBoxLayout(); segments.addStretch(); self.mode_group=QButtonGroup(self); self.mode_group.setExclusive(True)
        self.mode_buttons={}
        for mode,title in (("stopwatch","Kronometre"),("timer","Zamanlayıcı")):
            b=button(title,lambda checked=False,m=mode:self.change_mode(m),"segment"); b.setCheckable(True)
            self.mode_group.addButton(b); self.mode_buttons[mode]=b; segments.addWidget(b)
        segments.addStretch(); box.addLayout(segments)
        self.duration_button=button("25 dakika · süreyi düzenle",self.edit_duration,"link")
        box.addWidget(self.duration_button,alignment=Qt.AlignmentFlag.AlignHCenter)
        self.dial=TimerDial(); box.addWidget(self.dial,1)
        controls=QHBoxLayout(); controls.addStretch()
        self.start_button=button("▶   Başlat",self.toggle_running,"primary"); self.start_button.setMinimumSize(158,46)
        controls.addWidget(self.start_button)
        self.reset_button=button("Sıfırla",self.reset_current); self.reset_button.setMinimumHeight(46); controls.addWidget(self.reset_button); controls.addStretch()
        box.addLayout(controls)
        mini=button("↗  Mini pencereyi aç",self.open_mini,"link"); box.addWidget(mini,alignment=Qt.AlignmentFlag.AlignHCenter)
        line=QFrame(); line.setObjectName("separator"); line.setFixedHeight(1); box.addWidget(line)
        stats=QHBoxLayout()
        left=QVBoxLayout(); left.addWidget(label("BUGÜN ODAKLANDIN", "eyebrow")); self.today=label("0 dk","number"); left.addWidget(self.today)
        right=QVBoxLayout(); right.addWidget(label("TAMAMLANAN MOLA", "eyebrow")); self.breaks=label("0","number"); right.addWidget(self.breaks)
        stats.addLayout(left,1); stats.addLayout(right,1); box.addLayout(stats)
        columns.addWidget(focus,3)
        right=QVBoxLayout(); right.setSpacing(16)
        goal,box=card("softCard",18); box.setSpacing(8)
        row=QHBoxLayout(); row.addWidget(label("Günlük çalışma hedefi","sectionTitle")); row.addStretch()
        edit=button("Düzenle",self.edit_goal,"link"); row.addWidget(edit); box.addLayout(row)
        self.goal_remaining=label("4 sa 00 dk", "number"); box.addWidget(self.goal_remaining)
        self.goal_caption=label("hedefine kalan süre", "muted"); box.addWidget(self.goal_caption)
        self.goal_progress=QProgressBar(); self.goal_progress.setRange(0,1000); self.goal_progress.setTextVisible(False); box.addWidget(self.goal_progress)
        self.goal_toggle=QCheckBox("Hedefe ulaşınca dur"); self.goal_toggle.setChecked(self.engine.goal_enabled)
        self.goal_toggle.toggled.connect(self.toggle_goal); box.addWidget(self.goal_toggle)
        box.addWidget(label("İki sayaç da bugünkü aktif çalışmana sayılır.","hint",True)); right.addWidget(goal)
        reminders,box=card(margins=18); box.setSpacing(6); box.addWidget(label("Sıradaki molalar", "sectionTitle"))
        self.eye_next=label("20 dk sonra","sectionTitle"); self.move_next=label("60 dk sonra","sectionTitle")
        for title,info,widget in (("GÖZLERİNE BİR ARA","20 saniye uzağa bakış",self.eye_next),("BİRAZ HAREKET","5 dakikalık ekran dışı mola",self.move_next)):
            box.addWidget(label(title,"eyebrow")); box.addWidget(widget); box.addWidget(label(info,"hint"))
        box.addWidget(label("Çakışan molalar tek pencerede birleşir.","muted",True)); right.addWidget(reminders)
        plan,box=card(margins=18); box.setSpacing(8); box.addWidget(label("Şimdi planında", "eyebrow"))
        self.current_task=label("Kendine bir odak alanı seç.","sectionTitle",True); box.addWidget(self.current_task)
        self.current_time=label("Haftana küçük bir plan ekle.","muted",True); box.addWidget(self.current_time)
        box.addWidget(button("Haftalık planı aç  →",lambda:self.navigate(1),"link")); right.addWidget(plan)
        right.addStretch(); columns.addLayout(right,2); layout.addLayout(columns,1)
        footer=QHBoxLayout(); footer.addWidget(label("Mola zamanı, çalışma sürene eklenmez.","hint")); footer.addStretch()
        footer.addWidget(button("Mola düzeni ve kaynaklar  ↗",lambda:self.navigate(3),"link")); layout.addLayout(footer)
        return page

    def navigate(self,index):
        self.stack.setCurrentIndex(index); self.nav[index].setChecked(True)

    def show_banner(self,text):
        self.banner.setText(text); self.banner.show()

    def save(self):
        if not hasattr(self,"planner"):
            return
        state={"version":1,"engine":self.engine.snapshot(),"planner":self.planner.entries,"preferences":self.preferences}
        if not self.store.save(state):
            self.show_banner(self.store.error)

    def pulse(self):
        events=self.engine.tick()
        if "break" in events:
            self.open_break()
        if "goal_done" in events:
            self.show_notice("Bugünkü hedefine ulaştın.","Aktif çalışma hedefin tamamlandı. Yeni bir hedef belirleyebilir ya da hedefte durmayı kapatabilirsin.")
        elif "timer_done" in events:
            self.show_notice("Odak süren tamamlandı.","Güzel bir ara verme zamanı. Başlat düğmesiyle yeni bir zamanlayıcı başlatabilirsin.")
        if "suspended" in events:
            self.show_banner("Uzun bir kesinti algılandı; sayaç duraklatıldı. Hazır olduğunda Başlat ile devam et.")
        self.refresh()

    def refresh(self):
        e=self.engine
        now=datetime.now()
        self.date_label.setText(f"{now.day} {MONTHS[now.month-1].upper()} {now.year}  /  {DAYS[now.weekday()].upper()}")
        status={"idle":"Başlamaya hazır","paused":"Duraklatıldı","running":"Odak zamanı","break":"Kısa bir mola"}[e.state]
        self.status.setText("●  "+status)
        self.mode_buttons[e.mode].setChecked(True)
        duration=e.stopwatch_elapsed if e.mode=="stopwatch" else math.ceil(e.timer_remaining)
        progress=(e.stopwatch_elapsed%3600)/3600 if e.mode=="stopwatch" else 1-e.timer_remaining/e.timer_duration
        self.dial.set_value(clock_text(duration),status.upper(),progress)
        self.duration_button.setVisible(e.mode=="timer")
        self.duration_button.setText(human_time(e.timer_duration)+" · süreyi düzenle")
        self.start_button.setText("Ⅱ   Duraklat" if e.state=="running" else "▶   Devam et" if e.state=="paused" else "▶   Başlat")
        self.start_button.setEnabled(e.state!="break")
        self.reset_button.setEnabled(e.state!="break")
        self.today.setText(human_time(e.today_work)); self.breaks.setText(str(e.break_count))
        self.goal_remaining.setText(clock_text(math.ceil(e.remaining_goal)) if e.goal_enabled else human_time(math.ceil(e.remaining_goal/60)*60))
        self.goal_caption.setText("hedefin tamamlandı" if e.remaining_goal<=0 else "hedefine kalan süre / "+human_time(e.goal_seconds))
        self.goal_progress.setValue(min(1000,int(1000*e.today_work/e.goal_seconds)))
        self.eye_next.setText(f"{math.ceil(e.next_eye/60)} dk çalışma sonrası" if e.eye_enabled else "Hatırlatma kapalı")
        self.move_next.setText(f"{math.ceil(e.next_movement/60)} dk çalışma sonrası" if e.movement_enabled else "Hatırlatma kapalı")
        if hasattr(self,"planner"):
            task=self.planner.current_task()
            self.current_task.setText(task["title"] if task else "Şu an için serbest alan.")
            self.current_time.setText(task["start"]+" – "+task["end"] if task else "Haftanı istediğin gibi şekillendir.")
            self.planner.refresh_if_needed()
        if self.mini:
            self.mini.refresh()

    def toggle_running(self):
        if self.engine.state=="running":
            self.engine.pause()
        elif not self.engine.start() and self.engine.remaining_goal<=0:
            self.show_banner("Bugünkü hedefin tamamlandı. Düzenle ile hedefi artırabilir veya hedefte durmayı kapatabilirsin.")
        else:
            self.banner.hide()
        self.pulse(); self.save()

    def change_mode(self,mode):
        self.engine.switch_mode(mode); self.pulse(); self.save()

    def reset_current(self):
        self.engine.reset_current(); self.pulse(); self.save()

    def toggle_goal(self,checked):
        self.pulse(); self.engine.goal_enabled=checked; self.pulse(); self.save()

    def duration_dialog(self,title,minutes,maximum,apply):
        dialog=QDialog(self); dialog.setWindowTitle(title); dialog.setMinimumWidth(360)
        layout=QVBoxLayout(dialog); layout.setContentsMargins(26,26,26,26); layout.setSpacing(18)
        layout.addWidget(label(title,"sectionTitle"))
        spin=QSpinBox(); spin.setRange(1,maximum); spin.setSuffix(" dakika"); spin.setValue(max(1,round(minutes)))
        spin.setAccessibleName(title); layout.addWidget(spin)
        row=QHBoxLayout(); row.addWidget(button("Vazgeç",dialog.reject))
        row.addWidget(button("Kaydet",dialog.accept,"primary")); layout.addLayout(row)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            apply(spin.value()*60); self.pulse(); self.save()

    def edit_duration(self):
        self.duration_dialog("Zamanlayıcı süresi",self.engine.timer_duration/60,1440,self.engine.set_timer)

    def edit_goal(self):
        self.duration_dialog("Günlük hedef süresi",self.engine.goal_seconds/60,1440,lambda seconds:setattr(self.engine,"goal_seconds",seconds))

    def open_mini(self):
        if self.mini is None:
            self.mini=MiniWindow(self)
        self.mini.refresh(); self.mini.show(); self.mini.raise_()

    def open_exercise(self,key):
        if self.break_dialog is not None:
            self.break_dialog.raise_(); return
        self.engine.begin_break((EXERCISE_MAP[key]["kind"],))
        self.open_break(key)

    def open_break(self,exercise=None):
        if self.break_dialog is not None or not self.engine.pending_break:
            return
        self.break_dialog=BreakDialog(self.engine.pending_break,self,exercise,self.preferences["reduced_motion"],self.preferences["sound"])
        self.break_dialog.completed.connect(self.finish_break)
        self.break_dialog.show(); self.break_dialog.raise_(); self.break_dialog.activateWindow()
        QApplication.alert(self,0)
        self.refresh(); self.save()

    def finish_break(self,completed):
        dialog=self.break_dialog
        self.break_dialog=None
        self.engine.finish_break(completed)
        if dialog:
            dialog.deleteLater()
        self.refresh(); self.save()
        if self.pending_notice:
            title,text=self.pending_notice
            self.pending_notice=None
            QTimer.singleShot(0,lambda:self.show_notice(title,text))

    def show_notice(self,title,text):
        if self.closing:
            return
        if self.break_dialog is not None:
            self.pending_notice=(title,text)
            return
        if self.notice:
            self.notice.close()
        dialog=QDialog(self); dialog.setWindowTitle("Timee"); dialog.setMinimumWidth(460)
        dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,True)
        layout=QVBoxLayout(dialog); layout.setContentsMargins(28,28,28,28); layout.setSpacing(18)
        layout.addWidget(label(title,"sectionTitle",True)); layout.addWidget(label(text,"muted",True))
        layout.addWidget(button("Devam",dialog.accept,"primary"))
        self.notice=dialog; dialog.show(); dialog.raise_(); QApplication.alert(self)

    def closeEvent(self,event):
        self.closing=True; self.pending_notice=None
        self.ticker.stop(); self.saver.stop(); self.engine.pause()
        if self.break_dialog:
            self.break_dialog.finish(False)
        if self.mini:
            self.mini.close()
        self.save(); event.accept()


def main():
    parser=argparse.ArgumentParser(description="Timee — Fedora için odak ve hareket molaları")
    parser.add_argument("--data-dir",help="Kayıt klasörünü değiştir")
    args=parser.parse_args()
    app=QApplication(sys.argv)
    app.setApplicationName("Timee"); app.setOrganizationName("Timee")
    app.setDesktopFileName("io.github.emirkaganyigit.timee")
    app.setFont(QFont("Adwaita Sans",10)); apply_theme(app); app.setWindowIcon(app_icon())
    store=Store(args.data_dir)
    lock=None
    try:
        store.directory.mkdir(parents=True,exist_ok=True)
        lock=QLockFile(str(store.directory/"timee.lock")); lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            QMessageBox.information(None,"Timee zaten açık","Timee bu kayıt klasörüyle zaten açık. Açık pencereye geçebilirsin.")
            return 0
    except OSError:
        pass  # The window gives a visible save error if the directory is unwritable.
    window=Window(store); window.show()
    result=app.exec()
    if lock:
        lock.unlock()
    return result


if __name__=="__main__":
    raise SystemExit(main())
