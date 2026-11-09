"""Recurring weekly planner and its validation rules.

Entries are local-time, recurring weekly blocks. Their end is exclusive; blocks
on one day may touch, but may not overlap or continue past midnight.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import re
from uuid import uuid4

from PySide6.QtCore import Qt, QTime, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSizePolicy, QTimeEdit,
    QVBoxLayout, QWidget,
)

DAYS = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")
SHORT_DAYS = ("PZT", "SAL", "ÇAR", "PER", "CUM", "CMT", "PAZ")


def time_minutes(value: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value):
        raise ValueError("Saatleri SS:DD biçiminde gir.")
    hour, minute = map(int, value.split(":"))
    if hour > 23 or minute > 59:
        raise ValueError("Geçerli bir saat seç.")
    return hour * 60 + minute


def validate_entry(entry: dict, entries: list[dict], ignore_id: str | None = None) -> dict:
    """Return a normalized task or raise a user-readable ValueError."""
    day = entry.get("day")
    if isinstance(day, bool) or not isinstance(day, int) or not 0 <= day <= 6:
        raise ValueError("Haftanın bir gününü seç.")
    title = entry.get("title", "")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Göreve bir isim ver.")
    title = " ".join(title.split())
    if len(title) > 140:
        raise ValueError("Görev adı en fazla 140 karakter olabilir.")
    start, end = time_minutes(entry.get("start")), time_minutes(entry.get("end"))
    if end <= start:
        raise ValueError("Bitiş saati başlangıçtan sonra olmalı. Geceyi aşan görevleri iki güne böl.")
    for existing in entries:
        if existing["day"] != day or (ignore_id is not None and existing["id"] == ignore_id):
            continue
        other_start, other_end = time_minutes(existing["start"]), time_minutes(existing["end"])
        if start < other_end and other_start < end:
            raise ValueError(
                f"Bu saatler “{existing['title']}” ({existing['start']}–{existing['end']}) ile çakışıyor."
            )
    return {
        "id": str(entry.get("id") or uuid4()), "day": day,
        "start": entry["start"], "end": entry["end"], "title": title,
    }


def normalize_entries(entries: object) -> list[dict]:
    """Ignore malformed saved entries without preventing the app from opening."""
    clean: list[dict] = []
    if not isinstance(entries, list):
        return clean
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            task = validate_entry(entry, clean)
            if any(other["id"] == task["id"] for other in clean):
                task["id"] = str(uuid4())
            clean.append(task)
        except (TypeError, ValueError, KeyError):
            continue
    return sorted(clean, key=lambda task: (task["day"], task["start"]))


def active_task(entries: list[dict], now: datetime | None = None) -> dict | None:
    now = now or datetime.now()
    minute = now.hour * 60 + now.minute
    for task in entries:
        if task["day"] == now.weekday() and time_minutes(task["start"]) <= minute < time_minutes(task["end"]):
            return deepcopy(task)
    return None


def duration_label(minutes: int) -> str:
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours} sa {remainder} dk"
    return f"{hours} sa" if hours else f"{remainder} dk"


class TaskDialog(QDialog):
    def __init__(self, entries: list[dict], day: int, task: dict | None = None, parent=None):
        super().__init__(parent)
        self.entries = entries
        self.task = task
        self.result_entry: dict | None = None
        self.delete_requested = False
        self.setWindowTitle("Görevi düzenle" if task else "Yeni görev")
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        title = QLabel("Planına bir yer aç" if task is None else "Görevini düzenle")
        title.setObjectName("title")
        layout.addWidget(title)
        note = QLabel("Bu görev, seçtiğin gün ve saatlerde her hafta tekrarlanır.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QGridLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        form.addWidget(QLabel("Görev"), 0, 0, 1, 2)
        self.title_input = QLineEdit(task["title"] if task else "")
        self.title_input.setPlaceholderText("Örn. Proje üzerinde odaklı çalışma")
        self.title_input.setMaxLength(140)
        self.title_input.setMinimumHeight(40)
        form.addWidget(self.title_input, 1, 0, 1, 2)
        form.addWidget(QLabel("Gün"), 2, 0, 1, 2)
        self.day_input = QComboBox()
        self.day_input.addItems(DAYS)
        self.day_input.setCurrentIndex(task["day"] if task else day)
        self.day_input.setMinimumHeight(40)
        form.addWidget(self.day_input, 3, 0, 1, 2)
        form.addWidget(QLabel("Başlangıç"), 4, 0)
        form.addWidget(QLabel("Bitiş"), 4, 1)
        self.start_input = QTimeEdit()
        self.end_input = QTimeEdit()
        for widget, value in ((self.start_input, task["start"] if task else "08:00"),
                              (self.end_input, task["end"] if task else "09:00")):
            widget.setDisplayFormat("HH:mm")
            widget.setTime(QTime.fromString(value, "HH:mm"))
            widget.setMinimumHeight(40)
        form.addWidget(self.start_input, 5, 0)
        form.addWidget(self.end_input, 5, 1)
        layout.addLayout(form)
        self.error_label = QLabel("")
        self.error_label.setTextFormat(Qt.TextFormat.PlainText)
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #ffb5a3; font-size: 12px;")
        layout.addWidget(self.error_label)
        actions = QHBoxLayout()
        if task:
            delete = QPushButton("Görevi sil")
            delete.setObjectName("danger")
            delete.clicked.connect(self._delete)
            actions.addWidget(delete)
        actions.addStretch()
        cancel = QPushButton("Vazgeç")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        save = QPushButton("Kaydet")
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        actions.addWidget(save)
        layout.addLayout(actions)
        self.title_input.setFocus()

    def _save(self):
        entry = {
            "id": self.task["id"] if self.task else str(uuid4()),
            "day": self.day_input.currentIndex(), "title": self.title_input.text(),
            "start": self.start_input.time().toString("HH:mm"),
            "end": self.end_input.time().toString("HH:mm"),
        }
        try:
            self.result_entry = validate_entry(entry, self.entries, self.task["id"] if self.task else None)
        except ValueError as exc:
            self.error_label.setText(str(exc))
            return
        self.accept()

    def _delete(self):
        self.delete_requested = True
        self.accept()


class TaskCard(QPushButton):
    def __init__(self, task: dict, current: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("plannerTask")
        self.setProperty("current", current)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f"{task['title']}, {task['start']}–{task['end']}, düzenle")
        self.setToolTip(f"{task['title']}\n{task['start']}–{task['end']} · Düzenlemek için tıkla")
        self.setMinimumHeight(94)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(7)
        time_label = QLabel(f"{task['start']}–{task['end']}")
        time_label.setStyleSheet("font-size: 10px; font-weight: 700; color: #7dd3fc; background: transparent;")
        title = QLabel(task["title"])
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 12px; font-weight: 600; color: #eaf2ff; background: transparent;")
        for child in (time_label, title):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(child)
        if current:
            label = QLabel("ŞİMDİ")
            label.setStyleSheet("font-size: 9px; font-weight: 700; color: #93c5fd; background: transparent;")
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(label)


class PlannerWidget(QWidget):
    changed = Signal(list)

    def __init__(self, entries: list[dict], parent=None):
        super().__init__(parent)
        self.entries = normalize_entries(entries)
        self.selected_day = datetime.now().weekday()
        self._last_minute: tuple | None = None
        self.setStyleSheet("""
            QLabel { background: transparent; }
            QFrame#dayColumn { background: #111c2e; border: 1px solid #233550; border-radius: 14px; }
            QFrame#dayColumn[selected="true"] { border: 1px solid #3b82f6; background: #142a47; }
            QPushButton#dayHeading { color: #9fb2cc; border: 0; border-radius: 7px; padding: 9px 2px; font-weight: 700; font-size: 11px; background: transparent; }
            QPushButton#dayHeading:hover { color: #bfdbfe; background: #193c63; }
            QPushButton#dayHeading[selected="true"] { color: #bfdbfe; background: #193c63; }
            QPushButton#plannerTask { background: #172740; border: 1px solid #304a6c; border-radius: 9px; text-align: left; }
            QPushButton#plannerTask:hover { background: #1e3554; border: 1px solid #4f81b4; }
            QPushButton#plannerTask:focus { border: 2px solid #60a5fa; }
            QPushButton#plannerTask[current="true"] { background: #193c63; border: 1px solid #60a5fa; }
            QPushButton#dayAdd { background: transparent; color: #9fb2cc; border: 1px dashed #355372; border-radius: 8px; padding: 9px 2px; font-size: 11px; }
            QPushButton#dayAdd:hover { background: #142a47; color: #93c5fd; }
            QScrollArea { border: 0; background: transparent; }
            QScrollArea > QWidget > QWidget { background: transparent; }
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(20)
        header = QHBoxLayout()
        title_column = QVBoxLayout()
        title_column.setSpacing(7)
        eyebrow = QLabel("HAFTALIK PLAN")
        eyebrow.setObjectName("eyebrow")
        title_column.addWidget(eyebrow)
        title = QLabel("Haftanı şekillendir")
        title.setObjectName("title")
        title_column.addWidget(title)
        description = QLabel("Çalışmana zaman ayır. Aralara nefes alacak yer bırak.")
        description.setObjectName("muted")
        description.setWordWrap(True)
        title_column.addWidget(description)
        header.addLayout(title_column, 1)
        add = QPushButton("+  Görev ekle")
        add.setObjectName("primary")
        add.setMinimumHeight(42)
        add.clicked.connect(lambda: self.edit_task(day=self.selected_day))
        header.addWidget(add, 0, Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(header)
        self.summary = QLabel()
        self.summary.setObjectName("muted")
        self.summary.setWordWrap(True)
        outer.addWidget(self.summary)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.board = QWidget()
        self.board.setMinimumWidth(805)
        self.columns = QHBoxLayout(self.board)
        self.columns.setContentsMargins(0, 0, 0, 8)
        self.columns.setSpacing(8)
        self.scroll.setWidget(self.board)
        outer.addWidget(self.scroll, 1)
        footer = QLabel("Her hafta tekrar eder  ·  Bir göreve tıklayarak saatlerini düzenleyebilir veya silebilirsin.")
        footer.setObjectName("muted")
        footer.setWordWrap(True)
        footer.setStyleSheet("font-size: 11px;")
        outer.addWidget(footer)
        self.refresh()

    def current_task(self, now: datetime | None = None) -> dict | None:
        return active_task(self.entries, now)

    def refresh(self):
        while self.columns.count():
            item = self.columns.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        current = self.current_task()
        total = sum(time_minutes(task["end"]) - time_minutes(task["start"]) for task in self.entries)
        self.summary.setText(f"{len(self.entries)} görev  ·  Haftada {duration_label(total)} planlı çalışma  ·  Seçili gün: {DAYS[self.selected_day]}")
        for day in range(7):
            column = QFrame()
            column.setObjectName("dayColumn")
            column.setProperty("selected", day == self.selected_day)
            content = QVBoxLayout(column)
            content.setContentsMargins(8, 8, 8, 12)
            content.setSpacing(10)
            heading = QPushButton(SHORT_DAYS[day] + ("  •" if day == datetime.now().weekday() else ""))
            heading.setToolTip(DAYS[day])
            heading.setAccessibleName(DAYS[day] + " gününü seç")
            heading.setObjectName("dayHeading")
            heading.setProperty("selected", day == self.selected_day)
            heading.clicked.connect(lambda checked=False, selected=day: self.select_day(selected))
            content.addWidget(heading)
            day_tasks = [task for task in self.entries if task["day"] == day]
            minutes = sum(time_minutes(task["end"]) - time_minutes(task["start"]) for task in day_tasks)
            total_label = QLabel(duration_label(minutes) if day_tasks else "Plan yok")
            total_label.setObjectName("muted")
            total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            total_label.setStyleSheet("font-size: 10px;")
            content.addWidget(total_label)
            for task in day_tasks:
                card = TaskCard(task, bool(current and current["id"] == task["id"]))
                card.clicked.connect(lambda checked=False, selected=task: self.edit_task(task=selected))
                content.addWidget(card)
            add = QPushButton("+ Ekle")
            add.setObjectName("dayAdd")
            add.setAccessibleName(DAYS[day] + " için görev ekle")
            add.clicked.connect(lambda checked=False, selected=day: self.edit_task(day=selected))
            content.addWidget(add)
            content.addStretch(1)
            self.columns.addWidget(column, 1)
        now = datetime.now()
        self._last_minute = (now.weekday(), now.hour, now.minute)

    def refresh_if_needed(self):
        now = datetime.now()
        if self._last_minute != (now.weekday(), now.hour, now.minute):
            self.refresh()

    def select_day(self, day: int):
        self.selected_day = day
        self.refresh()

    def edit_task(self, day: int | None = None, task: dict | None = None):
        dialog = TaskDialog(self.entries, self.selected_day if day is None else day, task, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if task:
            self.entries = [entry for entry in self.entries if entry["id"] != task["id"]]
        if not dialog.delete_requested and dialog.result_entry:
            self.entries.append(dialog.result_entry)
            self.selected_day = dialog.result_entry["day"]
        self.entries.sort(key=lambda entry: (entry["day"], entry["start"]))
        self.refresh()
        self.changed.emit(deepcopy(self.entries))
