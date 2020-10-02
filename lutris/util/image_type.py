# Standard Library
from enum import Flag


class ImageType(Flag):
    """`ImageType` Enum that tracks what kind of image this is

    Used instead of a string to track if an image is a banner
    or an icon, and if it is small
    """

    _ignore_ = "small"
    NONE = 0
    small = 1 << 0
    icon = 1 << 1
    icon_small = small | icon
    banner = 1 << 2
    banner_small = small | banner

    @classmethod
    def _missing_(cls, value):
        """`_missing_` Raises exception when an invalid value is created

        Enum class calls this function automatically when it creates a
        value that is not in the named values for this enum.  Prevents
        creation of invalid values for example:

        `ImageType.icon | ImageType.banner`

        Args:
        - `value` (`Any`): used in exception error message

        Raises:
        ``
        - `ValueError`: on call
        """
        raise ValueError("Unsupported value %s" % value)
