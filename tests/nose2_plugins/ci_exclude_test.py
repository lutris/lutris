"""nose2 plugin that skips tests when running with the CI config file"""

import logging

from nose2.events import MatchPathEvent, Plugin

TEST_TO_SKIP = ["_test_dialogs.py"]


log = logging.getLogger("nose2.plugins.ci_exclude_test")


class ExcludeTestCI(Plugin):
    configSection = "exclude-ci"
    commandLineSwitch = (None, "exclude-ci", "True")

    def matchPath(self, event: MatchPathEvent) -> bool:
        if event.name in TEST_TO_SKIP:
            log.info(f'Skipping test for module "{event.name}')
            event.handled = True
            return False
        return True
