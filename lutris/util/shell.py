"""Controls execution of programs in separate shells"""
import os
from textwrap import dedent

from lutris import settings


def get_terminal_script(command, cwd, env):
    """Write command in a script file and run it.

    Running it from a file is likely the only way to set env vars only
    for the command (not for the terminal app).
    It's also the only reliable way to keep the term open when the
    game is quit.
    """
    script_path = os.path.join(settings.CACHE_DIR, "run_in_term.sh")
    env["TERM"] = "xterm"
    exported_environment = "\n".join('export %s="%s" ' % (key, value) for key, value in env.items())
    command = " ".join(['"%s"' % token for token in command])
    with open(script_path, "w") as script_file:
        script_file.write(
            dedent(
                """#!/bin/sh
            cd "%s"
            %s
            exec %s
            """ % (cwd, exported_environment, command)
            )
        )
        os.chmod(script_path, 0o744)
    return script_path


def get_bash_rc_file(cwd, env, aliases=None):
    """Return a bash prompt configured with pre-defined environment variables and aliases"""
    script_path = os.path.join(settings.CACHE_DIR, "bashrc.sh")
    env["TERM"] = "xterm"
    exported_environment = "\n".join('export %s="%s"' % (key, value) for key, value in env.items())
    aliases = aliases or {}
    alias_commands = "\n".join('alias %s="%s"' % (key, value) for key, value in aliases.items())
    current_bashrc = os.path.expanduser("~/.bashrc")
    with open(script_path, "w") as script_file:
        script_file.write(
            dedent(
                """
            . %s

            %s
            %s
            cd "%s"
            """ % (
                    current_bashrc,
                    exported_environment,
                    alias_commands,
                    cwd,
                )
            )
        )
    return script_path


def get_shell_command(cwd, env, aliases=None):
    bashrc_file = get_bash_rc_file(cwd, env, aliases)
    script_path = get_terminal_script(["bash", "--rcfile", bashrc_file], cwd, env)
    return script_path
