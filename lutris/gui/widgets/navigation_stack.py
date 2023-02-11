"""Window used for game installers"""
# pylint: disable=too-many-lines
from gi.repository import Gtk


class NavigationStack(Gtk.Stack):
    """
    This is a Stack widget that supports a back button and
    lazy-creation of pages.

    Pages should be set up via add_named_factory(), then displayed
    with present_page().

    However, you are meant to have 'present_X_page' functions
    that you pass to navigate_to_page(); this tracks the pages
    you visit, and when you navigate back,the presenter function
    will be called again.

    A presenter function can do more than just call present_page();
    it can configure other aspects of the InstallerWindow. Packaging
    all this into a presenter function keeps things in sync as you navigate.

    A presenter function can return an exit function, called when you navigate away
    from the page again.
    """

    def __init__(self, back_button, cancel_button=None, **kwargs):
        super().__init__(**kwargs)

        self.back_button = back_button
        self.cancel_button = cancel_button
        self.page_factories = {}
        self.stack_pages = {}
        self.navigation_stack = []
        self.navigation_exit_handler = None
        self.current_page_presenter = None
        self.current_navigated_page_presenter = None
        self.back_allowed = True
        self.cancel_allowed = True

    def add_named_factory(self, name, factory):
        """This specifies the factory functioin for the page named;
        this function takes no arguments, but returns the page's widget."""
        self.page_factories[name] = factory

    def set_back_allowed(self, is_allowed=True):
        """This turns the back button off, or back on."""
        self.back_allowed = is_allowed
        self._update_back_button()

    def set_cancel_allowed(self, is_allowed=True):
        """This turns the back button off, or back on."""
        self.cancel_allowed = is_allowed
        self._update_back_button()

    def _update_back_button(self):
        can_go_back = self.back_allowed and self.navigation_stack
        self.back_button.set_visible(can_go_back)
        self.cancel_button.set_visible(not can_go_back and self.cancel_allowed)

    def navigate_to_page(self, page_presenter):
        """Navigates to a page, by invoking 'page_presenter'.

        In addition, this updates the navigation state so navigate_back()
        and such work, they may call the presenter again.
        """
        if self.current_navigated_page_presenter:
            self.navigation_stack.append(self.current_navigated_page_presenter)
            self._update_back_button()

        self._go_to_page(page_presenter, True, Gtk.StackTransitionType.SLIDE_LEFT)

    def jump_to_page(self, page_presenter):
        """Jumps to a page, without updating navigation state.

        This does not disturb the behavior of navigate_back().
        This does invoke the exit handler of the current page.
        """
        self._go_to_page(page_presenter, False, Gtk.StackTransitionType.NONE)

    def navigate_back(self):
        """This navigates to the previous page, if any. This will invoke the
        current page's exit function, and the previous page's presenter function.
        """
        if self.navigation_stack and self.back_allowed:
            try:
                back_to = self.navigation_stack.pop()
                self._go_to_page(back_to, True, Gtk.StackTransitionType.SLIDE_RIGHT)
            finally:
                self._update_back_button()

    def navigate_home(self):
        """This navigates to the first page, effectively navigating back until it
        can go no further back. It does not actually traverse the intermediate pages
        though, but goes directly to the first."""
        if self.navigation_stack and self.back_allowed:
            try:
                home = self.navigation_stack[0]
                self.navigation_stack.clear()
                self._go_to_page(home, True, Gtk.StackTransitionType.SLIDE_RIGHT)
            finally:
                self._update_back_button()

    def navigation_reset(self):
        """This reverse the effect of jump_to_page(), returning to the last
        page actually navigate to."""
        if self.current_navigated_page_presenter:
            if self.current_page_presenter != self.current_navigated_page_presenter:
                self._go_to_page(self.current_navigated_page_presenter, True, Gtk.StackTransitionType.SLIDE_RIGHT)

    def save_current_page(self):
        """Returns a tuple containing information about the current page,
        to pass to restore_current_page()."""
        return (self.current_page_presenter, self.current_navigated_page_presenter)

    def restore_current_page(self, state):
        """Restores the current page to the one in effect when the state was generated.
        This does not disturb the navigation stack."""
        page_presenter, navigated_presenter = state
        navigated = page_presenter == navigated_presenter
        self._go_to_page(page_presenter, navigated, Gtk.StackTransitionType.NONE)

    def _go_to_page(self, page_presenter, navigated, transition_type):
        """Switches to a page. If 'navigated' is True, then when you navigate
        away from this page, it can go on the navigation stack. It should be
        False for 'temporary' pages that are not part of normal navigation."""
        exit_handler = self.navigation_exit_handler
        self.set_transition_type(transition_type)
        self.navigation_exit_handler = page_presenter()
        self.current_page_presenter = page_presenter
        if navigated:
            self.current_navigated_page_presenter = page_presenter
        if exit_handler:
            exit_handler()
        self._update_back_button()

    def discard_navigation(self):
        """This throws away the navigation history, so the back
        button is disabled. Previous pages before the current become
        inaccessible."""
        self.navigation_stack.clear()
        self._update_back_button()

    def present_page(self, name):
        """This displays the page names, creating it if required. It
        also calls show_all() on newly created pages.

        This should be called by your presenter functions."""
        if name not in self.stack_pages:
            factory = self.page_factories[name]
            page = factory()
            page.show_all()

            self.add_named(page, name)
            self.stack_pages[name] = page

        self.set_visible_child_name(name)
        return self.stack_pages[name]

    def present_replacement_page(self, name, page):
        """This displays a page that is given, rather than lazy-creating one. It
        still needs a name, but if you re-use a name this will replace the old page.

        This is useful for pages that need special initialization each time they
        appear, but generally such pages can't be returned to via the back
        button. The caller must protect against this if required.
        """
        old_page = self.stack_pages.get(name)

        if old_page != page:
            if old_page:
                self.remove(old_page)

            page.show_all()

            self.add_named(page, name)
            self.stack_pages[name] = page

        self.set_visible_child_name(name)
        return page
