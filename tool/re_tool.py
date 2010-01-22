import re

class RE_tool():
    def __init__(self):
        self.flags = re.MULTILINE | re.IGNORECASE | re.DOTALL


    def findall(self,regex,content,flags = None):
        """regex module abstraction"""
        if not flags:
            flags = self.flags
        found_values = re.findall(regex,content,flags)
        if found_values:
            return found_values
        else:
            return False

    def findfirst(self,regex,content,flags = None):
        """Similar to findall but only returns the first item, not an array"""
        values = self.findall(regex,content,flags)
        if values:
            return values[0]
        else:
            return False


