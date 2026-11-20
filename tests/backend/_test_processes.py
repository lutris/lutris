"""Running a command with the Lutris runtime through the backend."""

import asyncio

from lutris.backend import processes


class FakeMonitoredCommand:
    def __init__(self, return_code: str | None):
        self.game_process = object()
        self.return_code = return_code
        self.stop_func = lambda: True
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True
        self.stop_func()


def test_waits_for_the_command_and_returns_its_status(monkeypatch):
    command = FakeMonitoredCommand("3")
    monkeypatch.setattr(processes, "exec_command", lambda _command: command)

    async def run() -> int:
        task = asyncio.create_task(processes.run_command("true"))
        await asyncio.sleep(0)
        assert not task.done()  # Until the command stops
        command.stop_func()
        return await task

    assert asyncio.run(run()) == 3


def test_a_killed_command_reports_its_signal(monkeypatch):
    command = FakeMonitoredCommand("-9")
    monkeypatch.setattr(processes, "exec_command", lambda _command: command)

    async def run() -> int:
        task = asyncio.create_task(processes.run_command("sleep 100"))
        await asyncio.sleep(0)
        command.stop_func()
        return await task

    assert asyncio.run(run()) == 137


def test_cancelling_stops_the_command(monkeypatch):
    command = FakeMonitoredCommand(None)
    monkeypatch.setattr(processes, "exec_command", lambda _command: command)

    async def run() -> None:
        task = asyncio.create_task(processes.run_command("sleep 100"))
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run())
    assert command.stopped
