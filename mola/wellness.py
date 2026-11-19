from __future__ import annotations

import math
import time

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QGridLayout, QHBoxLayout, QProgressBar,
    QScrollArea, QVBoxLayout, QWidget,
)

from .animation import ExerciseAnimation
from .content import EXERCISES, SOURCES
from .theme import button, card, clock_text, label

SOURCE_MAP = {source["id"]: source for source in SOURCES}
EXERCISE_MAP = {exercise["id"]: exercise for exercise in EXERCISES}
ROTATION_VERSION = 2

# Each automatic eye routine contains one sourced 20-second distant-view cue
# and one short natural-blink or eyes-closed rest cue. The extra catalog items
# remain presentation variants of those sourced recommendations, not vision
# training or unsupported tracking drills. Filtering keeps old installations
# importable while a packaged catalog is being upgraded.
_EYE_ORDER_CANDIDATES = (
    ("distance", "blink"),
    ("eyes_closed", "distance_window"),
    ("distance_room", "blink"),
    ("blink", "distance_window"),
    ("distance_room", "eyes_closed"),
    ("eyes_closed", "distance"),
)
EYE_ORDERS = tuple(
    order for order in _EYE_ORDER_CANDIDATES
    if all(identifier in EXERCISE_MAP for identifier in order)
) or (("distance", "blink"), ("blink", "distance"))

SHORT_MOVEMENT_IDS = ("shoulders", "hands", "chest", "sitstand", "calf")
MOVEMENT_IDS = SHORT_MOVEMENT_IDS + ("walk",)
MOVEMENT_SNOOZE_SECONDS = 10 * 60


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
        "movement": _rotation_cursor(value.get("movement"), len(MOVEMENT_IDS)),
    }


def _catalog_step(identifier):
    item = dict(EXERCISE_MAP[identifier])
    return item, int(item["duration"])


def plan_automatic_break(kinds, rotation):
    """Build a varied deterministic plan and return its next cursor state.

    Eye plans keep one 20-second distant-view cue plus one short rest cue. A
    movement reminder offers exactly one exercise; completion, snooze,
    acknowledgement, and skip are separate dialog outcomes.
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
        steps.append(_catalog_step(MOVEMENT_IDS[cursor]))
        following["movement"] = (cursor + 1) % len(MOVEMENT_IDS)
    return steps, following


class BreakDialog(QDialog):
    """Modal break chooser with independent per-reminder outcomes.

    ``resolved`` emits a mapping with ``eye`` and/or ``movement`` values from
    ``completed``, ``skipped``, ``snoozed``, and ``acknowledged``. The legacy
    boolean ``completed`` signal remains for older integrations.
    """

    completed = Signal(bool)
    resolved = Signal(dict)

    def __init__(self, kinds, parent=None, exercise=None, reduced=False, sound=False,
                 planned_steps=None):
        super().__init__(parent)
        self.setWindowTitle("Timee · Kendine kısa bir ara ver")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(580)
        self.resize(610, 690)
        self.reduced, self.sound = reduced, sound
        self.finished_once, self.started_at, self.elapsed = False, None, 0.0
        self.active_kind = None
        self.active_indices = []
        self.active_position = 0
        self.step = 0

        if planned_steps is not None:
            self.steps = [(dict(item), int(duration)) for item, duration in planned_steps]
        elif exercise:
            item = EXERCISE_MAP[exercise]
            self.steps = [(dict(item), int(item["duration"]))]
        else:
            self.steps, _ = plan_automatic_break(kinds, None)
        if not self.steps:
            raise ValueError("a break needs at least one exercise step")
        self.manual = bool(exercise and len(self.steps) == 1)
        self.requested_kinds = tuple(
            kind for kind in ("eye", "movement")
            if any(item["kind"] == kind for item, _ in self.steps)
        )
        self.outcomes = {kind: None for kind in self.requested_kinds}
        self.result = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 25, 28, 25)
        outer.setSpacing(13)
        self.top = label("MOLA SEÇİMİ", "eyebrow")
        outer.addWidget(self.top)

        self.selector = QWidget()
        selector_layout = QVBoxLayout(self.selector)
        selector_layout.setContentsMargins(0, 0, 0, 0)
        selector_layout.setSpacing(12)
        self.selection_title = label("Önce hangi molayı yapmak istersin?", "title", True)
        selector_layout.addWidget(self.selection_title)
        selector_layout.addWidget(label(
            "Çakışan molaları ayrı ayrı başlatabilir, erteleyebilir veya atlayabilirsin.",
            "muted", True,
        ))
        self.kind_cards = {}
        self.kind_actions = {}
        for kind in self.requested_kinds:
            frame, box = card("softCard", 16)
            title = "Göz molası" if kind == "eye" else "Hareket molası"
            detail = (
                "Uzağa bakış ve kısa dinlenme adımları ilk başlangıçtan sonra otomatik ilerler."
                if kind == "eye" else
                "Tek bir hareket seçeneği; istersen 10 dakika ertele."
            )
            box.addWidget(label(title, "sectionTitle"))
            box.addWidget(label(detail, "muted", True))
            first = QHBoxLayout()
            start = button(
                f"{title}na başla",
                lambda checked=False, value=kind: self.start_kind(value),
                "primary",
            )
            skip = button(
                f"{title}nı atla",
                lambda checked=False, value=kind: self.skip_kind(value),
                "link",
            )
            first.addWidget(start)
            first.addWidget(skip)
            box.addLayout(first)
            actions = {"start": start, "skip": skip}
            if kind == "movement":
                second = QHBoxLayout()
                snooze = button("10 dk ertele", self.snooze_movement, "link")
                acknowledged = button("Molada hareket ettim", self.acknowledge_movement, "link")
                second.addWidget(snooze)
                second.addWidget(acknowledged)
                box.addLayout(second)
                actions.update({"snooze": snooze, "acknowledged": acknowledged})
            selector_layout.addWidget(frame)
            self.kind_cards[kind] = frame
            self.kind_actions[kind] = actions
        selector_layout.addStretch()
        outer.addWidget(self.selector, 1)

        self.exercise_panel = QWidget()
        exercise_layout = QVBoxLayout(self.exercise_panel)
        exercise_layout.setContentsMargins(0, 0, 0, 0)
        exercise_layout.setSpacing(13)
        self.heading = label("", "title", True)
        exercise_layout.addWidget(self.heading)
        self.meta = label("", "muted", True)
        exercise_layout.addWidget(self.meta)
        self.animation = ExerciseAnimation(reduced=reduced)
        self.animation.setFixedHeight(190)
        exercise_layout.addWidget(self.animation)
        self.chooser = QComboBox()
        self.chooser.setAccessibleName("Hareket seç")
        for item in EXERCISES:
            if item["kind"] == "movement":
                self.chooser.addItem(item["title"], item["id"])
        self.chooser.currentIndexChanged.connect(self.choose_exercise)
        exercise_layout.addWidget(self.chooser)
        self.instruction = label("", "", True)
        exercise_layout.addWidget(self.instruction)
        self.safety = label("", "hint", True)
        exercise_layout.addWidget(self.safety)
        self.source_button = button("", self.open_source, "link")
        self.source_button.setStyleSheet("text-align: left; padding-left: 0;")
        exercise_layout.addWidget(self.source_button)
        self.countdown = label("", "number")
        exercise_layout.addWidget(self.countdown)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1000)
        exercise_layout.addWidget(self.progress)
        self.primary = button("Egzersizi başlat", self.primary_action, "primary")
        self.primary.setMinimumHeight(44)
        exercise_layout.addWidget(self.primary)
        self.skip = button("Bu molayı atla", self.skip_active, "link")
        exercise_layout.addWidget(self.skip)
        outer.addWidget(self.exercise_panel, 1)

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.tick)
        if self.manual:
            self.start_kind(self.requested_kinds[0])
        else:
            self.show_selection()

    def show_selection(self):
        self.timer.stop()
        self.started_at, self.elapsed = None, 0.0
        self.active_kind = None
        self.exercise_panel.hide()
        for kind, frame in self.kind_cards.items():
            frame.setVisible(self.outcomes[kind] is None)
        if all(value is not None for value in self.outcomes.values()):
            self._emit_result()
            return
        self.top.setText("MOLA SEÇİMİ")
        self.selector.show()

    def start_kind(self, kind):
        if kind not in self.outcomes or self.outcomes[kind] is not None:
            return
        self.active_kind = kind
        self.active_indices = [
            index for index, (item, _) in enumerate(self.steps) if item["kind"] == kind
        ]
        if not self.active_indices:
            return
        self.active_position = 0
        self.step = self.active_indices[0]
        self.selector.hide()
        self.exercise_panel.show()
        self.load_step()

    def load_step(self, auto_start=False):
        self.item, self.duration = self.steps[self.step]
        self.started_at, self.elapsed = None, 0.0
        prefix = "GÖZ" if self.active_kind == "eye" else "HAREKET"
        self.top.setText(
            f"{prefix} MOLASI  ·  {self.active_position + 1} / {len(self.active_indices)}"
        )
        self.chooser.blockSignals(True)
        self.chooser.setCurrentIndex(max(0, self.chooser.findData(self.item["id"])))
        self.chooser.blockSignals(False)
        self.chooser.setVisible(self.manual and self.item["kind"] == "movement")
        self.chooser.setEnabled(True)
        self.set_exercise(self.item)
        self.primary.setText("Egzersizi başlat")
        self.primary.setEnabled(True)
        self.countdown.setText(clock_text(self.duration, False))
        self.progress.setValue(0)
        if auto_start:
            self._start_timer()

    def set_exercise(self, item):
        self.item = item
        self.heading.setText(item["title"])
        self.animation.kind = item["animation"]
        self.animation.phase = 0
        self.animation.update()
        if not self.reduced and self.exercise_panel.isVisible():
            self.animation.timer.start()
        self.meta.setText(item["reps"] + "  ·  " + item["place"])
        self.instruction.setText(item["instruction"])
        if item["kind"] == "movement":
            hint = "Rahat hareket aralığında uygula; ağrı olursa dur."
        else:
            hint = "Hareketli görsel yalnızca yönergedir; uzağa bakışta gerçek bir nesne seç."
        self.safety.setText(hint)
        self.source_button.setText("Kaynak: " + SOURCE_MAP[item["source"]]["title"] + " ↗")

    def choose_exercise(self):
        if not self.chooser.currentData():
            return
        item = EXERCISE_MAP[self.chooser.currentData()]
        if self.manual:
            if self.started_at is not None:
                return
            self.duration = int(item["duration"])
            self.steps[self.step] = (dict(item), self.duration)
            self.countdown.setText(clock_text(self.duration, False))
            self.progress.setValue(0)
        self.set_exercise(item)

    def open_source(self):
        QDesktopServices.openUrl(QUrl(SOURCE_MAP[self.item["source"]]["url"]))

    def _start_timer(self):
        self.started_at = time.monotonic()
        self.primary.setEnabled(False)
        self.primary.setText("Kendine bu zamanı ayır…")
        if self.manual:
            self.chooser.setEnabled(False)
        # Keep the cue moving for the whole timed exercise. Reduced-motion mode
        # is the explicit accessibility exception.
        if not self.reduced:
            self.animation.timer.start()
        self.timer.start()

    def primary_action(self):
        if self.started_at is None:
            self._start_timer()
        elif self.elapsed >= self.duration:
            self._complete_current_step()

    def tick(self):
        if self.started_at is None:
            return
        self.elapsed = min(self.duration, time.monotonic() - self.started_at)
        self.countdown.setText(clock_text(math.ceil(self.duration - self.elapsed), False))
        self.progress.setValue(int(1000 * self.elapsed / self.duration))
        if self.elapsed < self.duration:
            return
        self.timer.stop()
        if self.active_kind == "eye" and not self.manual:
            # Once started, eye cues proceed hands-free without a Next click.
            self._complete_current_step()
            return
        self.primary.setEnabled(True)
        self.primary.setText("Egzersizi tamamla")
        if self.sound:
            QApplication.beep()

    def _complete_current_step(self):
        if self.active_position + 1 < len(self.active_indices):
            self.active_position += 1
            self.step = self.active_indices[self.active_position]
            self.load_step(auto_start=True)
            return
        kind = self.active_kind
        self.outcomes[kind] = "completed"
        if self.manual:
            self._emit_result()
        else:
            self.show_selection()

    def skip_active(self):
        if self.active_kind is None:
            return
        self.outcomes[self.active_kind] = "skipped"
        if self.manual:
            self._emit_result()
        else:
            self.show_selection()

    def skip_kind(self, kind):
        if kind in self.outcomes and self.outcomes[kind] is None:
            self.outcomes[kind] = "skipped"
            self.show_selection()

    def snooze_movement(self):
        if self.outcomes.get("movement") is None:
            self.outcomes["movement"] = "snoozed"
            self.show_selection()

    def acknowledge_movement(self):
        if self.outcomes.get("movement") is None:
            self.outcomes["movement"] = "acknowledged"
            self.show_selection()

    def _emit_result(self):
        if self.finished_once:
            return
        self.finished_once = True
        self.timer.stop()
        self.animation.timer.stop()
        for kind, value in tuple(self.outcomes.items()):
            if value is None:
                self.outcomes[kind] = "skipped"
        self.result = dict(self.outcomes)
        completed = all(
            value in ("completed", "acknowledged")
            for value in self.result.values()
        )
        self.resolved.emit(dict(self.result))
        self.completed.emit(completed)
        super().accept()

    def finish(self, completed):
        """Compatibility endpoint for older callers and direct tests."""
        outcome = "completed" if completed else "skipped"
        if self.active_kind is not None and self.outcomes[self.active_kind] is None:
            self.outcomes[self.active_kind] = outcome
        for kind, value in tuple(self.outcomes.items()):
            if value is None:
                self.outcomes[kind] = outcome if completed else "skipped"
        self._emit_result()

    def reject(self):
        self.finish(False)

    def closeEvent(self, event):
        self.finish(False)
        event.accept()


class LibraryWidget(QWidget):
    requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(label("Küçük hareketler, iyi gelen aralar.", "title"))
        layout.addWidget(label(
            "Ofiste ve kütüphanede uygulanabilecek, kurum rehberlerine dayalı seçenekler.",
            "muted", True,
        ))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 4, 8, 8)
        grid.setSpacing(14)
        for index, item in enumerate(EXERCISES):
            frame, box = card(margins=20)
            box.addWidget(label(
                "GÖZ DİNLENDİRME" if item["kind"] == "eye" else "HAREKET MOLASI",
                "eyebrow",
            ))
            box.addWidget(label(item["title"], "sectionTitle", True))
            box.addWidget(label(item["reps"], "muted", True))
            box.addWidget(label(item["place"], "hint", True))
            box.addStretch()
            start = button(
                "Birlikte yapalım  →",
                lambda checked=False, key=item["id"]: self.requested.emit(key),
            )
            box.addWidget(start)
            grid.addWidget(frame, index // 2, index % 2)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        layout.addWidget(label(
            "Rehber süreleri tıbbi doz değildir. Göz dinlendirme hareketleri görme tedavisi olarak sunulmaz.",
            "hint", True,
        ))
