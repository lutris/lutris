from lutris.monitored_command import MonitoredCommand
from lutris.util.log_buffer import LogBuffer


def follow(log_buffer):
    """Replay a LogBuffer's notifications onto a list of text, as a frontend would."""
    shown = [log_buffer.text]

    def on_changed(text, replaced):
        shown[0] = text if replaced else shown[0] + text

    log_buffer.changed.register(on_changed)
    return shown


def test_text_accumulates():
    log_buffer = LogBuffer("start\n")
    log_buffer.append("one\n")
    log_buffer.append("")
    log_buffer.append("two\n")
    assert log_buffer.text == "start\none\ntwo\n"


def test_followers_see_appends_and_clears_in_order(fake_main_loop):
    log_buffer = LogBuffer()
    shown = follow(log_buffer)

    log_buffer.append("old output\n")
    log_buffer.clear()
    log_buffer.append("new output\n")
    fake_main_loop.run_pending()

    assert shown == ["new output\n"]
    assert log_buffer.text == "new output\n"


def test_late_follower_starts_from_current_text(fake_main_loop):
    log_buffer = LogBuffer()
    log_buffer.append("before\n")
    shown = follow(log_buffer)
    log_buffer.append("after\n")
    fake_main_loop.run_pending()

    assert shown == ["before\nafter\n"]


def test_command_writes_its_output_to_the_log_buffer():
    log_buffer = LogBuffer()
    command = MonitoredCommand(["true"], log_buffer=log_buffer)

    for handler in command.log_handlers:
        handler("a line\n")

    assert log_buffer.text == "a line\n"
