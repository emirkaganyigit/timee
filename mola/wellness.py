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
ROTATION_VERSION = 1
EYE_ORDERS = (("distance", "blink"), ("blink", "distance"))
SHORT_MOVEMENT_IDS = ("shoulders", "hands", "chest", "sitstand", "calf")
MOVEMENT_BREAK_SECONDS = 5 * 60
SCREEN_REST = {
    "id": "screen_rest",
    "title": "Molayı ekran dışında tamamla",
    "kind": "movement",
    "animation": "walk",
    "duration": 0,
    "reps": "Kalan süre · ekrandan uzakta",
    "instruction": "Kısa hareketleri tamamladın. Şimdi ekrandan uzaklaş; rahatça yürü, su al veya duruşunu değiştir. Sayaç bitene kadar ekrana bakman gerekmiyor.",
    "source": "hse",
    "place": "Ekran dışında",
}


def _rotation_cursor(value, modulo):
    return value % modulo if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def normalize_rotation(value):
    """Return a safe, JSON-friendly automatic-exercise rotation state."""
    if (not isinstance(value, dict)
            or ("version" in value and value.get("version") != ROTATION_VERSION)):
        value = {}
    return {
        "version": ROTATION_VERSION,
        "eye": _rotation_cursor(value.get("eye"), len(EYE_ORDERS)),
        "movement": _rotation_cursor(value.get("movement"), len(SHORT_MOVEMENT_IDS)),
    }


def _catalog_step(identifier):
    item = dict(EXERCISE_MAP[identifier])
    return item, int(item["duration"])


def plan_automatic_break(kinds, rotation):
    """Build a varied, deterministic break plan and its next cursor state.

    Eye plans always retain the sourced 20-second distant-view step. Movement
    plans contain three sourced short activities and a screen-away remainder,
    so the complete movement portion remains exactly five minutes.
    """
    kinds = tuple(kind for kind in ("eye", "movement") if kind in kinds)
    if not kinds:
        raise ValueError("a break needs 'eye' and/or 'movement'")
    current = normalize_rotation(rotation)
    following = dict(current)
    steps = []
    if "eye" in kinds:
        cursor = current["eye"]
        steps.extend(_catalog_step(identifier) for identifier in EYE_ORDERS[cursor])
        following["eye"] = (cursor + 1) % len(EYE_ORDERS)
    if "movement" in kinds:
        cursor = current["movement"]
        identifiers = tuple(
            SHORT_MOVEMENT_IDS[(cursor + offset) % len(SHORT_MOVEMENT_IDS)]
            for offset in range(3)
        )
        movement_steps = [_catalog_step(identifier) for identifier in identifiers]
        used = sum(duration for _, duration in movement_steps)
        remainder = MOVEMENT_BREAK_SECONDS - used
        if remainder <= 0:
            raise ValueError("short movement plan must leave screen-away time")
        steps.extend(movement_steps)
        steps.append((dict(SCREEN_REST), remainder))
        following["movement"] = (cursor + 3) % len(SHORT_MOVEMENT_IDS)
    return steps, following


class BreakDialog(QDialog):
    completed = Signal(bool)

    def __init__(self, kinds, parent=None, exercise=None, reduced=False, sound=False,
                 planned_steps=None):
        super().__init__(parent)
        self.setWindowTitle("Timee · Kendine kısa bir ara ver")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(560)
        self.resize(580, 650)
        self.reduced, self.sound = reduced, sound
        self.steps = []
        self.finished_once, self.started_at, self.elapsed = False, None, 0.0
        self.step = 0
        if planned_steps is not None:
            self.steps = [(dict(item), int(duration)) for item, duration in planned_steps]
        elif exercise:
            item = EXERCISE_MAP[exercise]
            self.steps.append((dict(item), item["duration"]))
        else:
            self.steps, _ = plan_automatic_break(kinds, None)
        if not self.steps:
            raise ValueError("a break needs at least one exercise step")
        self.manual = bool(exercise and len(self.steps) == 1)

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
        self.chooser.setVisible(self.manual and self.item["kind"] == "movement")
        self.chooser.setEnabled(True)
        self.set_exercise(self.item)
        self.primary.setText("Molayı başlat" if self.item["id"] == "screen_rest" else "Egzersizi başlat")
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
        if item["id"] == "screen_rest":
            hint = "Bu kalan süre ekran dışı mola içindir; animasyonu izlemen gerekmiyor."
        elif item["kind"] == "movement":
            hint = "Rahat hareket aralığında uygula; ağrı olursa dur."
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
            # The cue explains the step before it begins. Once the instructions
            # are read, stop it so the timed activity never requires watching
            # the screen.
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
            if self.step + 1 < len(self.steps):
                next_item = self.steps[self.step + 1][0]
                self.primary.setText(f"Sıradaki: {next_item['title']}  →")
            else:
                self.primary.setText("Molayı tamamla ve devam et")
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
