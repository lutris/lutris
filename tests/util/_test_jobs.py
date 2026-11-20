"""lutris.util.jobs schedules onto whichever main loop is installed, not GLib's directly."""

import pytest

from lutris.util import mainloop
from lutris.util.jobs import run_until_complete, schedule_at_idle, schedule_repeating_at_idle
from lutris.util.notifications import NotificationSource


def test_default_main_loop_is_glib(monkeypatch):
    monkeypatch.setattr(mainloop, "_main_loop", None)
    assert isinstance(mainloop.get_main_loop(), mainloop.GLibMainLoop)


def test_schedule_at_idle_runs_once_with_its_arguments(fake_main_loop):
    calls = []
    task = schedule_at_idle(calls.append, "hello", delay_seconds=0.5)

    assert [delay for _callback, delay in fake_main_loop.scheduled.values()] == [0.5]
    fake_main_loop.run_pending()
    fake_main_loop.run_pending()

    assert calls == ["hello"]
    assert not fake_main_loop.scheduled
    task.unschedule()  # Already ran: nothing left to cancel
    assert fake_main_loop.cancelled == []


def test_unschedule_cancels_on_the_main_loop(fake_main_loop):
    calls = []
    task = schedule_at_idle(calls.append, "never")

    task.unschedule()
    fake_main_loop.run_pending()

    assert calls == []
    assert fake_main_loop.cancelled == [1]


def test_repeating_task_runs_until_it_returns_false(fake_main_loop):
    remaining = [3]

    def tick() -> bool:
        remaining[0] -= 1
        return remaining[0] > 0

    schedule_repeating_at_idle(tick, interval_seconds=1.0)
    for _ in range(5):
        fake_main_loop.run_pending()

    assert remaining == [0]


def test_notifications_are_delivered_through_the_main_loop(fake_main_loop):
    received = []
    source = NotificationSource()
    source.register(received.append)

    source.fire("event")
    assert received == []  # Deferred to the loop, never run inline
    fake_main_loop.run_pending()

    assert received == ["event"]


def test_run_until_complete_iterates_the_installed_loop(fake_main_loop):
    def operation(completion_function, error_function):
        fake_main_loop.on_iterate = completion_function

    run_until_complete(operation, timeout_seconds=1.0)


def test_run_until_complete_raises_the_reported_error(fake_main_loop):
    def operation(completion_function, error_function):
        fake_main_loop.on_iterate = lambda: error_function(ValueError("broken"))

    with pytest.raises(ValueError, match="broken"):
        run_until_complete(operation, timeout_seconds=1.0)
