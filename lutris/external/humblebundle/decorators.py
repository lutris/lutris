__author__ = "Joel Pedraza"
__copyright__ = "Copyright 2014, Joel Pedraza"
__license__ = "MIT"

from lutris.external.humblebundle import logger


def callback(func):
    """
    A decorator to add a keyword arg 'callback' to execute a method on the
    return value of a function

    Used to add callbacks to the API calls

    :param func: The function to decorate
    :return: The wrapped function
    """

    def wrap(*args, **kwargs):
        callback_ = kwargs.pop('callback', None)
        result = func(*args, **kwargs)
        if callback_:
            callback_(result)
        return result

    return wrap
