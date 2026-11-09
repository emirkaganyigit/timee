"""Clock-independent work session model used by every Timee window.

Only active work advances counters. Public controls synchronize elapsed time;
events caused by those controls remain queued until the next ``tick()``. Call
``tick`` at least every five seconds while running (the UI uses 200 ms): a longer
gap is treated as sleep / a stalled event loop and pauses without crediting it.
On Linux the default clock is CLOCK_BOOTTIME, which includes system suspend;
other platforms fall back to monotonic time without a suspend guarantee.

When a reminder becomes due, another reminder due within three minutes joins
the same break. Completion takes precedence over reminders, but does not imply
that a rest was taken: an overdue reminder opens on the next active tick after
restarting. Completing or skipping an exercise resets the relevant cadence.
"""

from __future__ import annotations

from datetime import date
import math
import time
from typing import Callable


EPSILON = 1e-7
MAX_TICK_GAP = 5.0
COALESCE_WINDOW = 180.0


def default_clock() -> float:
    """Use Linux boot time so waking from system suspend creates a detectable gap."""
    clock_id = getattr(time, "CLOCK_BOOTTIME", None)
    if clock_id is not None:
        try:
            return time.clock_gettime(clock_id)
        except (AttributeError, OSError):
            pass
    return time.monotonic()


def _number(value: object, fallback: float, low: float = 0.0,
            high: float = 10 * 365 * 86400.0) -> float:
    """Accept finite numbers from persisted data without accepting booleans."""
    try:
        if isinstance(value, bool):
            raise ValueError
        result = float(value)
        if not math.isfinite(result):
            raise ValueError
        return min(high, max(low, result))
    except (TypeError, ValueError, OverflowError):
        return fallback


class Engine:
    def __init__(self, clock: Callable[[], float] = default_clock,
                 today: Callable[[], date] | None = None):
        self._clock = clock
        self._today = today or date.today
        self._last = float(clock())
        self._day = self._today_key()
        self._events: list[str] = []
        self._resume_after_break = False
        self._state_before_break = "idle"
        self.mode = "stopwatch"
        self.state = "idle"
        self.stopwatch_elapsed = 0.0
        self.timer_duration = 25 * 60.0
        self.timer_remaining = self.timer_duration
        self.goal_enabled = False
        self.goal_seconds = 4 * 3600.0
        self.today_work = 0.0
        self.total_work = 0.0
        self.eye_enabled = True
        self.movement_enabled = True
        self.eye_interval = 20 * 60.0
        self.movement_interval = 60 * 60.0
        self.since_eye = 0.0
        self.since_movement = 0.0
        self.pending_break: tuple[str, ...] = ()
        self.break_count = 0

    def _today_key(self) -> str:
        value = self._today()
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    @property
    def remaining_goal(self) -> float:
        return max(0.0, self.goal_seconds - self.today_work)

    @property
    def next_eye(self) -> float:
        return max(0.0, self.eye_interval - self.since_eye)

    @property
    def next_movement(self) -> float:
        return max(0.0, self.movement_interval - self.since_movement)

    def _sanitize(self) -> None:
        self.stopwatch_elapsed = _number(self.stopwatch_elapsed, 0)
        self.timer_duration = _number(self.timer_duration, 1500, 1, 7 * 86400)
        self.timer_remaining = _number(self.timer_remaining, self.timer_duration,
                                       0, self.timer_duration)
        self.goal_seconds = _number(self.goal_seconds, 14400, 1, 7 * 86400)
        self.today_work = _number(self.today_work, 0)
        self.total_work = max(_number(self.total_work, 0), self.today_work)
        self.eye_interval = _number(self.eye_interval, 1200, 1, 86400)
        self.movement_interval = _number(self.movement_interval, 3600, 1, 86400)
        self.since_eye = _number(self.since_eye, 0) if self.eye_enabled else 0.0
        self.since_movement = _number(self.since_movement, 0) if self.movement_enabled else 0.0

    def _advance(self) -> None:
        now = float(self._clock())
        delta = max(0.0, now - self._last)
        self._last = now
        self._sanitize()
        day = self._today_key()
        if day != self._day:
            self._day = day
            self.today_work = 0.0
            self.break_count = 0
            self._events.append("day_changed")
        if self.state != "running":
            return
        if delta > MAX_TICK_GAP:
            self.state = "paused"
            self._events.append("suspended")
            return

        boundaries = [delta]
        if self.mode == "timer":
            boundaries.append(self.timer_remaining)
        if self.goal_enabled:
            boundaries.append(self.remaining_goal)
        if self.eye_enabled:
            boundaries.append(self.next_eye)
        if self.movement_enabled:
            boundaries.append(self.next_movement)
        worked = max(0.0, min(boundaries))
        if self.mode == "stopwatch":
            self.stopwatch_elapsed += worked
        else:
            self.timer_remaining = max(0.0, self.timer_remaining - worked)
        self.today_work += worked
        self.total_work += worked
        if self.eye_enabled:
            self.since_eye += worked
        if self.movement_enabled:
            self.since_movement += worked

        # Finishing a task must never immediately open an exercise popup.
        goal_done = self.goal_enabled and self.remaining_goal <= EPSILON
        timer_done = self.mode == "timer" and self.timer_remaining <= EPSILON
        if goal_done or timer_done:
            self.state = "paused"
            if goal_done:
                self._events.append("goal_done")
            if timer_done:
                self.timer_remaining = 0.0
                self._events.append("timer_done")
            return

        reminders = (
            ("eye", self.eye_enabled, self.next_eye),
            ("movement", self.movement_enabled, self.next_movement),
        )
        if any(enabled and remaining <= EPSILON for _, enabled, remaining in reminders):
            # Only coalesce once something is actually due, never open early
            # simply because both reminders are inside the three-minute window.
            combined = tuple(kind for kind, enabled, remaining in reminders
                             if enabled and remaining <= COALESCE_WINDOW + EPSILON)
            self._open_break(combined)
            self._events.append("break")

    def tick(self) -> list[str]:
        """Advance the session and return each pending event exactly once."""
        self._advance()
        events, self._events = self._events, []
        return events

    def start(self) -> bool:
        self._advance()
        if self.state == "break" or (self.goal_enabled and self.remaining_goal <= EPSILON):
            return False
        if self.mode == "timer" and self.timer_remaining <= EPSILON:
            self.timer_remaining = self.timer_duration
        self.state = "running"
        return True

    def pause(self) -> None:
        self._advance()
        if self.state == "running":
            self.state = "paused"
        elif self.state == "break":
            self._resume_after_break = False
            self._state_before_break = "paused"

    def switch_mode(self, mode: str) -> None:
        if mode not in ("stopwatch", "timer"):
            raise ValueError("mode must be 'stopwatch' or 'timer'")
        self._advance()
        if mode == self.mode:
            return
        self.pause()
        self.mode = mode

    def reset_current(self) -> None:
        """Reset the selected counter, preserving work totals and break cadence."""
        self.pause()
        if self.mode == "stopwatch":
            self.stopwatch_elapsed = 0.0
        else:
            self.timer_remaining = self.timer_duration
        if self.state != "break":
            self.state = "idle"

    def set_timer(self, seconds: float) -> None:
        """Set the countdown length; changing it pauses an active countdown."""
        value = _number(seconds, -1, 1, 7 * 86400)
        if value < 0:
            raise ValueError("timer duration must be a finite number")
        self._advance()
        if self.mode == "timer":
            self.pause()
        self.timer_duration = value
        self.timer_remaining = value

    def _open_break(self, kinds: tuple[str, ...]) -> None:
        if self.state == "break":
            self.pending_break = tuple(k for k in ("eye", "movement")
                                       if k in self.pending_break or k in kinds)
            return
        self._state_before_break = self.state
        self._resume_after_break = self.state == "running"
        self.pending_break = kinds
        self.state = "break"

    def begin_break(self, kinds: tuple[str, ...]) -> None:
        """Pause for a manually opened exercise; the caller opens its dialog.

        The automatic ``break`` event is only emitted by the reminder scheduler.
        A manually opened library exercise does not create a second popup event.
        """
        kinds = tuple(k for k in ("eye", "movement") if k in kinds)
        if not kinds:
            raise ValueError("a break needs 'eye' and/or 'movement'")
        self._advance()
        self._open_break(kinds)
        # The caller is already opening this break. A reminder may have become
        # due in the synchronization above; consume just that popup event so
        # the next UI tick does not open another dialog for the same break.
        self._events = [event for event in self._events if event != "break"]

    def finish_break(self, completed: bool = True) -> None:
        """Resume a break; skips reset its cadence but do not count completion."""
        self._advance()
        if self.state != "break":
            return
        if "eye" in self.pending_break:
            self.since_eye = 0.0
        if "movement" in self.pending_break:
            self.since_movement = 0.0
        if completed:
            self.break_count += 1
        self.pending_break = ()
        can_resume = (not self.goal_enabled or self.remaining_goal > EPSILON)
        can_resume = can_resume and (self.mode != "timer" or self.timer_remaining > EPSILON)
        if self._resume_after_break and can_resume:
            self.state = "running"
        else:
            self.state = "idle" if self._state_before_break == "idle" else "paused"
        self._resume_after_break = False

    def snapshot(self) -> dict:
        """Return JSON-safe state; saving never consumes queued UI events."""
        self._advance()
        names = (
            "mode", "state", "stopwatch_elapsed", "timer_duration", "timer_remaining",
            "goal_enabled", "goal_seconds", "today_work", "total_work", "eye_enabled",
            "movement_enabled", "eye_interval", "movement_interval", "since_eye",
            "since_movement", "break_count",
        )
        return {"version": 1, "day": self._day,
                **{name: getattr(self, name) for name in names}}

    def restore(self, data: dict) -> None:
        """Restore saved counters without counting time while the app was closed."""
        if not isinstance(data, dict):
            return
        self.mode = data.get("mode") if data.get("mode") in ("timer", "stopwatch") else "stopwatch"
        for name in ("stopwatch_elapsed", "timer_duration", "timer_remaining", "goal_seconds",
                     "today_work", "total_work", "eye_interval", "movement_interval",
                     "since_eye", "since_movement"):
            if name in data:
                setattr(self, name, _number(data[name], getattr(self, name)))
        for name in ("goal_enabled", "eye_enabled", "movement_enabled"):
            if isinstance(data.get(name), bool):
                setattr(self, name, data[name])
        self.break_count = int(_number(data.get("break_count"), 0, 0, 1000000))
        self._sanitize()
        self._day = self._today_key()
        if data.get("day") != self._day:
            self.today_work = 0.0
            self.break_count = 0
        self.state = "idle" if data.get("state") == "idle" else "paused"
        self.pending_break = ()
        self._resume_after_break = False
        self._state_before_break = self.state
        self._last = float(self._clock())
        self._events = []
