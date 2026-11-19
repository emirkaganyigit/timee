"""Clock-independent work session model used by every Timee window.

Active work and time spent at the desk are deliberately separate. Work controls
advance the stopwatch/countdown and daily goal, while desk presence advances the
eye and movement reminder clocks even when work is paused. Public controls
synchronize elapsed time; events caused by those controls remain queued until
the next ``tick()``. Call ``tick`` at least every five seconds while either clock
is running (the UI uses 200 ms): a longer gap is treated as sleep / a stalled
event loop and pauses both clocks without crediting it.
On Linux the default clock is CLOCK_BOOTTIME, which includes system suspend;
other platforms fall back to monotonic time without a suspend guarantee.

When a reminder becomes due, another reminder due within three minutes joins
the same break. Completion takes precedence over reminders. Pausing work never
claims that a break happened: reminder cadence changes only when the user
resolves, skips, or explicitly snoozes a reminder.
"""

from __future__ import annotations

from datetime import date, datetime, time as datetime_time, timedelta
import math
import time
from typing import Callable


EPSILON = 1e-7
MAX_TICK_GAP = 5.0
COALESCE_WINDOW = 180.0
DEFAULT_DAY_RESET_MINUTES = 5 * 60
DEFAULT_MOVEMENT_SNOOZE_SECONDS = 10 * 60.0


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


def _nonnegative_number(value: object, fallback: float, high: float) -> float:
    """Accept a finite non-negative value without clamping invalid negatives."""
    try:
        if isinstance(value, bool):
            raise ValueError
        result = float(value)
        if not math.isfinite(result) or result < 0:
            raise ValueError
        return min(high, result)
    except (TypeError, ValueError, OverflowError):
        return fallback


class Engine:
    def __init__(self, clock: Callable[[], float] = default_clock,
                 today: Callable[[], date] | None = None,
                 wall_clock: Callable[[], float] = time.time,
                 now: Callable[[], datetime] | None = None):
        self._clock = clock
        self._today = today or date.today
        # Existing tests and integrations often provide only a date callback.
        # Noon preserves their calendar-day behavior while real app instances
        # use the actual local time required by a configurable rollover hour.
        self._now = now if now is not None else (datetime.now if today is None else None)
        self._wall_clock = wall_clock
        self._last = float(clock())
        self.day_reset_minutes = DEFAULT_DAY_RESET_MINUTES
        self._day = self._workday_key()
        self._events: list[str] = []
        self._resume_after_break = False
        self._desk_resume_after_break = False
        self._break_had_completion = False
        self._state_before_break = "idle"
        self.mode = "stopwatch"
        self.state = "idle"
        self.desk_active = False
        self.desk_elapsed = 0.0
        self.stopwatch_elapsed = 0.0
        self.timer_duration = 25 * 60.0
        self.timer_remaining = self.timer_duration
        self.goal_enabled = False
        self.goal_seconds = 4 * 3600.0
        self.today_work = 0.0
        self.goal_baseline = 0.0
        self.total_work = 0.0
        self.eye_enabled = True
        self.movement_enabled = True
        self.eye_interval = 20 * 60.0
        self.movement_interval = 60 * 60.0
        self.since_eye = 0.0
        self.since_movement = 0.0
        self.movement_snooze_remaining = 0.0
        self.pending_break: tuple[str, ...] = ()
        self.break_count = 0

    def _today_key(self) -> str:
        value = self._today()
        if isinstance(value, datetime):
            value = value.date()
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    def _local_now(self) -> datetime:
        value = self._now() if self._now is not None else self._today()
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime_time(12, 0))
        return datetime.combine(date.fromisoformat(str(value)), datetime_time(12, 0))

    def _workday_key(self) -> str:
        shifted = self._local_now() - timedelta(minutes=self.day_reset_minutes)
        return shifted.date().isoformat()

    @property
    def desk_state(self) -> str:
        if self.desk_active:
            return "running"
        return "paused" if self.desk_elapsed > EPSILON else "idle"

    @property
    def goal_work(self) -> float:
        return max(0.0, self.today_work - self.goal_baseline)

    @property
    def remaining_goal(self) -> float:
        return max(0.0, self.goal_seconds - self.goal_work)

    @property
    def next_eye(self) -> float:
        return max(0.0, self.eye_interval - self.since_eye)

    @property
    def next_movement(self) -> float:
        if self.movement_snooze_remaining > EPSILON:
            return self.movement_snooze_remaining
        return max(0.0, self.movement_interval - self.since_movement)

    def _sanitize(self) -> None:
        self.stopwatch_elapsed = _number(self.stopwatch_elapsed, 0)
        self.timer_duration = _number(self.timer_duration, 1500, 1, 7 * 86400)
        self.timer_remaining = _number(self.timer_remaining, self.timer_duration,
                                       0, self.timer_duration)
        self.desk_elapsed = _number(self.desk_elapsed, 0)
        self.goal_seconds = _number(self.goal_seconds, 14400, 1, 7 * 86400)
        self.today_work = _number(self.today_work, 0)
        self.goal_baseline = min(
            self.today_work, _number(self.goal_baseline, 0, 0, self.today_work)
        )
        self.total_work = max(_number(self.total_work, 0), self.today_work)
        self.eye_interval = _number(self.eye_interval, 1200, 1, 86400)
        self.movement_interval = _number(self.movement_interval, 3600, 1, 86400)
        self.day_reset_minutes = int(_number(
            self.day_reset_minutes, DEFAULT_DAY_RESET_MINUTES, 0, 1439
        ))
        self.since_eye = _number(self.since_eye, 0) if self.eye_enabled else 0.0
        self.since_movement = _number(self.since_movement, 0) if self.movement_enabled else 0.0
        self.movement_snooze_remaining = (
            _number(self.movement_snooze_remaining, 0)
            if self.movement_enabled else 0.0
        )

    def _advance(self) -> None:
        now = float(self._clock())
        delta = max(0.0, now - self._last)
        self._last = now
        self._sanitize()
        day = self._workday_key()
        if day != self._day:
            self._day = day
            self.today_work = 0.0
            self.goal_baseline = 0.0
            self.desk_elapsed = 0.0
            self.break_count = 0
            self._events.append("day_changed")
        if delta > MAX_TICK_GAP and (self.state == "running" or self.desk_active):
            if self.state == "running":
                self.state = "paused"
            self.desk_active = False
            self._resume_after_break = False
            self._desk_resume_after_break = False
            self._events.append("suspended")
            return
        if delta <= EPSILON or (self.state != "running" and not self.desk_active):
            return

        was_working = self.state == "running"
        reminder_boundary = delta
        if self.desk_active:
            reminder_boundaries = [delta]
            if self.eye_enabled:
                reminder_boundaries.append(self.next_eye)
            if self.movement_enabled:
                reminder_boundaries.append(self.next_movement)
            reminder_boundary = max(0.0, min(reminder_boundaries))
            self.desk_elapsed += reminder_boundary
            if self.eye_enabled:
                self.since_eye += reminder_boundary
            if self.movement_enabled:
                self.since_movement += reminder_boundary
                self.movement_snooze_remaining = max(
                    0.0, self.movement_snooze_remaining - reminder_boundary
                )

        if was_working:
            work_boundaries = [delta]
            if self.desk_active:
                work_boundaries.append(reminder_boundary)
            if self.mode == "timer":
                work_boundaries.append(self.timer_remaining)
            if self.goal_enabled:
                work_boundaries.append(self.remaining_goal)
            worked = max(0.0, min(work_boundaries))
            if self.mode == "stopwatch":
                self.stopwatch_elapsed += worked
            else:
                self.timer_remaining = max(0.0, self.timer_remaining - worked)
            self.today_work += worked
            self.total_work += worked

        # Finishing a task must never immediately open an exercise popup.
        goal_done = was_working and self.goal_enabled and self.remaining_goal <= EPSILON
        timer_done = was_working and self.mode == "timer" and self.timer_remaining <= EPSILON
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
            combined = tuple(
                kind for kind, enabled, remaining in reminders
                if enabled and remaining <= COALESCE_WINDOW + EPSILON
                and not (
                    kind == "movement"
                    and self.movement_snooze_remaining > EPSILON
                )
            )
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
        # Starting focused work is strong evidence that the user is at the
        # desk. The inverse is intentionally not true: pausing work leaves the
        # independent desk clock running.
        self.desk_active = True
        self.state = "running"
        return True

    def pause(self) -> None:
        self._advance()
        if self.state == "running":
            self.state = "paused"
        elif self.state == "break":
            self._resume_after_break = False
            self._state_before_break = "paused"

    def start_desk(self) -> bool:
        """Start desk presence without starting focused work."""
        self._advance()
        if self.state == "break":
            return False
        self.desk_active = True
        return True

    def pause_desk(self) -> None:
        """Stop desk presence; active focused work is paused for consistency."""
        self._advance()
        self.desk_active = False
        if self.state == "running":
            self.state = "paused"
        elif self.state == "break":
            self._desk_resume_after_break = False
            self._resume_after_break = False
            self._state_before_break = "paused"

    def toggle_desk(self) -> bool:
        if self.desk_active:
            self.pause_desk()
            return False
        return self.start_desk()

    def reset_desk_elapsed(self) -> None:
        """Reset only the visible desk timer, never reminder cadence."""
        self._advance()
        self.desk_elapsed = 0.0

    def set_day_reset(self, minutes_after_midnight: int) -> None:
        """Change the local daily-goal rollover without erasing today's work."""
        if isinstance(minutes_after_midnight, bool):
            raise ValueError("daily reset must be a minute from 0 through 1439")
        try:
            value = int(minutes_after_midnight)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("daily reset must be a minute from 0 through 1439") from exc
        if value < 0 or value > 1439:
            raise ValueError("daily reset must be a minute from 0 through 1439")
        self._advance()
        self.day_reset_minutes = value
        self._day = self._workday_key()

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

    def reset_goal_progress(self) -> None:
        """Restart the daily goal without erasing today's actual work total."""
        self._advance()
        self.goal_baseline = self.today_work
        # A reset performed at the exact goal boundary intentionally unlocks
        # the goal again, so a queued completion notice is no longer relevant.
        self._events = [event for event in self._events if event != "goal_done"]

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
        self._desk_resume_after_break = self.desk_active
        self._break_had_completion = False
        self.desk_active = False
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

    def _close_break(self) -> None:
        if self._break_had_completion:
            self.break_count += 1
        can_resume = (not self.goal_enabled or self.remaining_goal > EPSILON)
        can_resume = can_resume and (self.mode != "timer" or self.timer_remaining > EPSILON)
        if self._resume_after_break and can_resume:
            self.state = "running"
        else:
            self.state = "idle" if self._state_before_break == "idle" else "paused"
        self.desk_active = self._desk_resume_after_break
        self._resume_after_break = False
        self._desk_resume_after_break = False
        self._break_had_completion = False

    def finish_break(self, completed: bool = True,
                     kinds: tuple[str, ...] | None = None) -> None:
        """Resolve selected reminders and resume when none remain.

        Skipping still resets the selected reminder to its normal interval but
        does not add completion credit. Passing no ``kinds`` preserves the
        original API and resolves the whole popup.
        """
        self._advance()
        if self.state != "break":
            return
        requested = self.pending_break if kinds is None else tuple(kinds)
        resolved = tuple(kind for kind in self.pending_break if kind in requested)
        if not resolved:
            return
        if "eye" in resolved:
            self.since_eye = 0.0
        if "movement" in resolved:
            self.since_movement = 0.0
            self.movement_snooze_remaining = 0.0
        if completed:
            self._break_had_completion = True
        self.pending_break = tuple(
            kind for kind in self.pending_break if kind not in resolved
        )
        if not self.pending_break:
            self._close_break()

    def snooze_movement(self, seconds: float = DEFAULT_MOVEMENT_SNOOZE_SECONDS) -> None:
        """Postpone only a due movement reminder by desk-presence time."""
        value = _number(seconds, -1, 1, 86400)
        if value < 0:
            raise ValueError("movement snooze must be a finite positive duration")
        self._advance()
        self.movement_snooze_remaining = value
        if self.state == "break" and "movement" in self.pending_break:
            self.pending_break = tuple(
                kind for kind in self.pending_break if kind != "movement"
            )
            if not self.pending_break:
                self._close_break()

    def acknowledge_movement(self) -> None:
        """Record that movement happened and restart its normal interval."""
        self._advance()
        self.since_movement = 0.0
        self.movement_snooze_remaining = 0.0
        if self.state == "break" and "movement" in self.pending_break:
            self.pending_break = tuple(
                kind for kind in self.pending_break if kind != "movement"
            )
            self._break_had_completion = True
            if not self.pending_break:
                self._close_break()

    def snapshot(self) -> dict:
        """Return JSON-safe state; saving never consumes queued UI events."""
        self._advance()
        names = (
            "mode", "state", "desk_active", "desk_elapsed", "stopwatch_elapsed",
            "timer_duration", "timer_remaining",
            "goal_enabled", "goal_seconds", "today_work", "goal_baseline", "total_work", "eye_enabled",
            "movement_enabled", "eye_interval", "movement_interval", "since_eye",
            "since_movement", "movement_snooze_remaining", "break_count",
        )
        return {"version": 2, "day": self._day,
                "day_reset_minutes": self.day_reset_minutes,
                "saved_at": _nonnegative_number(
                    self._wall_clock(), 0.0, 100_000_000_000.0
                ),
                **{name: getattr(self, name) for name in names}}

    def restore(self, data: dict) -> None:
        """Restore saved counters without counting time while the app was closed."""
        if not isinstance(data, dict):
            return
        self.mode = data.get("mode") if data.get("mode") in ("timer", "stopwatch") else "stopwatch"
        for name in ("desk_elapsed", "stopwatch_elapsed", "timer_duration", "timer_remaining", "goal_seconds",
                     "today_work", "goal_baseline", "total_work", "eye_interval", "movement_interval",
                     "since_eye", "since_movement", "movement_snooze_remaining"):
            if name in data:
                setattr(self, name, _number(data[name], getattr(self, name)))
        if "desk_elapsed" not in data:
            self.desk_elapsed = self.today_work
        if "day_reset_minutes" in data:
            self.day_reset_minutes = int(_number(
                data.get("day_reset_minutes"), DEFAULT_DAY_RESET_MINUTES, 0, 1439
            ))
        for name in ("goal_enabled", "eye_enabled", "movement_enabled"):
            if isinstance(data.get(name), bool):
                setattr(self, name, data[name])
        self.break_count = int(_number(data.get("break_count"), 0, 0, 1000000))
        self._sanitize()
        current_day = self._workday_key()
        if "day_reset_minutes" in data:
            same_day = data.get("day") == current_day
        else:
            # Version-one snapshots used the calendar date. Preserve them on
            # their first load instead of erasing pre-05:00 work unexpectedly,
            # including a snapshot written just before midnight.
            local_now = self._local_now()
            legacy_days = {local_now.date().isoformat()}
            minute_of_day = local_now.hour * 60 + local_now.minute
            if minute_of_day < self.day_reset_minutes:
                legacy_days.add((local_now.date() - timedelta(days=1)).isoformat())
            same_day = data.get("day") in legacy_days
        self._day = current_day
        if not same_day:
            self.today_work = 0.0
            self.goal_baseline = 0.0
            self.desk_elapsed = 0.0
            self.break_count = 0
        self.state = "idle" if data.get("state") == "idle" else "paused"
        self.desk_active = False
        self.pending_break = ()
        self._resume_after_break = False
        self._desk_resume_after_break = False
        self._break_had_completion = False
        self._state_before_break = self.state
        self._last = float(self._clock())
        self._events = []
