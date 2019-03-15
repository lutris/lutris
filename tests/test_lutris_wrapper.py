import sys
import os
import os.path
import unittest
import subprocess


if os.path.isfile('bin/lutris-wrapper'):
    lutris_wrapper_bin = 'bin/lutris-wrapper'
else:
    lutris_wrapper_bin = 'lutris-wrapper'


class LutrisWrapperTestCase(unittest.TestCase):
    def test_cleanup_children(self):
        "Test that nonresponsive child processes can be killed with 2x sigterm"
        env = os.environ.copy()
        env['PYTHONPATH'] = ':'.join(sys.path)
        # First, we run the lutris-wrapper with a bash subshell which ignores
        # SIGTERMs, emits a message to indicate readiness, and then closes
        # stdout.
        wrapper_proc = subprocess.Popen(
            [
                sys.executable,
                lutris_wrapper_bin,
                '0',
                '0',
                'bash',
                '-c',
                "trap '' SIGTERM; echo Hello World; exec 1>&-; while sleep infinity; do true; done"
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            env=env,
        )
        try:
            # Wait for the "Hello World" message that indicates that the process
            # tree has started. This message arrives on stdout.
            for line in wrapper_proc.stdout:
                if b'Hello World' == line.strip():
                    # We found the output we're looking for.
                    break
            else:
                self.fail("stdout EOF unexpectedly")

            # Send first SIGTERM
            wrapper_proc.terminate()

            # Wait for confirmation that lutris-wrapper got our signal.
            for line in wrapper_proc.stdout:
                if b'--terminated processes--' == line.strip():
                    break
            else:
                self.fail("stdout EOF unexpectedly")

            wrapper_proc.stdout.close()  # don't need this anymore.

            # Wait a short while to see if lutris-wrapper will exit (it shouldn't)
            try:
                wrapper_proc.wait(0.5)
            except subprocess.TimeoutExpired:
                # as expected, the process is still alive.
                pass
            else:
                # the test failed because the process exited for some reason.
                self.fail("Process exited unexpectedly")

            # Send second SIGTERM
            wrapper_proc.terminate()

            # verify that lutris-wrapper closes.
            wrapper_proc.wait(30)
        finally:
            if wrapper_proc.returncode is None:
                wrapper_proc.kill()
                wrapper_proc.wait(30)
            wrapper_proc.stdout.close()
