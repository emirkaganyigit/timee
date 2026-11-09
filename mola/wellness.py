from __future__ import annotations

import math
import time
from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QGridLayout, QHBoxLayout, QProgressBar, QScrollArea, QVBoxLayout, QWidget

from .animation import ExerciseAnimation
from .content import EXERCISES, SOURCES
from .theme import button, card, clock_text, label

SOURCE_MAP = {source["id"]: source for source in SOURCES}
EXERCISE_MAP = {exercise["id"]: exercise for exercise in EXERCISES}


class BreakDialog(QDialog):
    completed = Signal(bool)

    def __init__(self, kinds, parent=None, exercise=None, reduced=False, sound=False):
        super().__init__(parent)
        self.setWindowTitle("Timee · Kendine kısa bir ara ver")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(560)
        self.resize(580, 650)
        self.reduced, self.sound = reduced, sound
        self.steps = []
        self.manual = bool(exercise and len(kinds) == 1)
        self.finished_once, self.started_at, self.elapsed = False, None, 0.0
        self.step = 0
        if exercise and len(kinds) == 1:
            item = EXERCISE_MAP[exercise]
            self.steps.append((item, item["duration"]))
        else:
            if "eye" in kinds:
                self.steps.append((EXERCISE_MAP["distance"], 20))
            if "movement" in kinds:
                self.steps.append((EXERCISE_MAP["walk"], 300))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 25, 28, 25)
        outer.setSpacing(13)
        self.top = label("SAYAÇ DURAKLATILDI", "eyebrow")
        outer.addWidget(self.top)
        self.heading = label("", "title", True); outer.addWidget(self.heading)
        self.meta = label("", "muted", True); outer.addWidget(self.meta)
        self.animation = ExerciseAnimation(reduced=reduced)
        self.animation.setFixedHeight(190)
        outer.addWidget(self.animation)
        self.chooser = QComboBox()
        self.chooser.setAccessibleName("Hareket seç")
        for item in EXERCISES:
            if item["kind"] == "movement":
                self.chooser.addItem(item["title"], item["id"])
        self.chooser.currentIndexChanged.connect(self.choose_exercise)
        outer.addWidget(self.chooser)
        self.instruction = label("", "", True); outer.addWidget(self.instruction)
        self.safety = label("", "hint", True); outer.addWidget(self.safety)
        self.source_button = button("", self.open_source, "link")
        self.source_button.setStyleSheet("text-align: left; padding-left: 0;")
        outer.addWidget(self.source_button)
        self.countdown = label("", "number"); outer.addWidget(self.countdown)
        self.progress = QProgressBar(); self.progress.setTextVisible(False)
        self.progress.setRange(0, 1000); outer.addWidget(self.progress)
        self.primary = button("Egzersizi başlat", self.primary_action, "primary")
        self.primary.setMinimumHeight(44); outer.addWidget(self.primary)
        self.skip = button("Şimdi atla ve devam et", lambda: self.finish(False), "link")
        outer.addWidget(self.skip)
        self.timer = QTimer(self); self.timer.setInterval(100)
        self.timer.timeout.connect(self.tick)
        self.load_step()

    def load_step(self):
        self.item, self.duration = self.steps[self.step]
        self.started_at, self.elapsed = None, 0
        self.top.setText(f"SAYAÇ DURAKLATILDI  ·  {self.step + 1} / {len(self.steps)}")
        self.chooser.blockSignals(True)
        self.chooser.setCurrentIndex(max(0, self.chooser.findData(self.item["id"])))
        self.chooser.blockSignals(False)
        self.chooser.setVisible(self.item["kind"] == "movement")
        self.chooser.setEnabled(True)
        self.set_exercise(self.item)
        self.primary.setText("Egzersizi başlat")
        self.primary.setEnabled(True)
        self.countdown.setText(clock_text(self.duration, False))
        self.progress.setValue(0)

    def set_exercise(self, item):
        self.item = item
        self.heading.setText(item["title"])
        self.animation.kind = item["animation"]
        self.animation.phase = 0
        self.animation.update()
        self.meta.setText(item["reps"] + "  ·  " + item["place"])
        self.instruction.setText(item["instruction"])
        if item["kind"] == "movement":
            hint = "Rahat hareket aralığında uygula; ağrı olursa dur."
            if self.duration == 300:
                hint += " Hareketini bitirince molanın kalanında ekrandan uzak kal."
        else:
            hint = "Animasyon yalnızca yönergedir. Molada ekrana bakman gerekmiyor."
        self.safety.setText(hint)
        self.source_button.setText("Kaynak: " + SOURCE_MAP[item["source"]]["title"] + " ↗")

    def choose_exercise(self):
        if self.chooser.currentData():
            item = EXERCISE_MAP[self.chooser.currentData()]
            if self.manual:
                if self.started_at is not None:
                    return
                self.duration = item["duration"]
                self.steps[self.step] = (item, self.duration)
                self.countdown.setText(clock_text(self.duration, False))
                self.progress.setValue(0)
            self.set_exercise(item)

    def open_source(self):
        QDesktopServices.openUrl(QUrl(SOURCE_MAP[self.item["source"]]["url"]))

    def primary_action(self):
        if self.started_at is None:
            self.started_at = time.monotonic()
            self.primary.setEnabled(False)
            self.primary.setText("Kendine bu zamanı ayır…")
            if self.manual:
                self.chooser.setEnabled(False)
            self.timer.start()
            # Once instructions are read, the cue need not keep moving.
            if self.item["kind"] == "eye":
                self.animation.timer.stop()
        elif self.elapsed >= self.duration:
            if self.step + 1 < len(self.steps):
                self.step += 1
                self.load_step()
                if not self.reduced:
                    self.animation.timer.start()
            else:
                self.finish(True)

    def tick(self):
        if self.started_at is None:
            return
        self.elapsed = min(self.duration, time.monotonic() - self.started_at)
        self.countdown.setText(clock_text(math.ceil(self.duration - self.elapsed), False))
        self.progress.setValue(int(1000*self.elapsed/self.duration))
        if self.elapsed >= self.duration:
            self.timer.stop()
            self.primary.setEnabled(True)
            self.primary.setText("Hareket molasına geç →" if self.step+1 < len(self.steps) else "Egzersizi tamamla ve devam et")
            if self.sound:
                QApplication.beep()

    def finish(self, completed):
        if self.finished_once:
            return
        self.finished_once = True
        self.timer.stop()
        self.animation.timer.stop()
        self.completed.emit(completed)
        self.accept()

    def reject(self):
        self.finish(False)

    def closeEvent(self, event):
        self.finish(False)
        event.accept()


class LibraryWidget(QWidget):
    requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(16)
        layout.addWidget(label("Küçük hareketler, iyi gelen aralar.", "title"))
        layout.addWidget(label("Ofiste ve kütüphanede uygulanabilecek, kurum rehberlerine dayalı seçenekler.", "muted", True))
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(); grid = QGridLayout(content); grid.setContentsMargins(0,4,8,8); grid.setSpacing(14)
        for i,item in enumerate(EXERCISES):
            frame, box = card(margins=20)
            box.addWidget(label("GÖZ DİNLENDİRME" if item["kind"]=="eye" else "HAREKET MOLASI", "eyebrow"))
            box.addWidget(label(item["title"], "sectionTitle", True))
            box.addWidget(label(item["reps"], "muted", True))
            box.addWidget(label(item["place"], "hint", True))
            box.addStretch()
            start = button("Birlikte yapalım  →", lambda checked=False, key=item["id"]: self.requested.emit(key))
            box.addWidget(start)
            grid.addWidget(frame,i//2,i%2)
        scroll.setWidget(content); layout.addWidget(scroll)
        layout.addWidget(label("Rehber süreleri tıbbi doz değildir. Göz dinlendirme hareketleri görme tedavisi olarak sunulmaz.","hint",True))
