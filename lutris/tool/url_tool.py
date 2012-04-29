import cookielib
import urllib2
import xml.dom.minidom


class UrlTool:
    """
    Various method for retrieving webpages
    """
    def __init__(self):
        """Class init"""
        self.local = False
        self.verbose = False
        self.cookie_jar = cookielib.LWPCookieJar()
        self.user_agent = 'Mozilla/5.0 '\
                        + '(X11; U; Linux x86_64; en-US; rv:1.9.0.10) '\
                        + 'Gecko/2009042523 Ubuntu/9.04 (jaunty) '\
                        + 'Firefox/3.0.10'
        self.headers = {'User-agent': self.user_agent}
        self.webpage = None

    def request_url(self, url, data=None, headers=None):
        """Get a webpage"""
        opener = urllib2.build_opener(
                urllib2.HTTPCookieProcessor(self.cookie_jar)
            )
        urllib2.install_opener(opener)
        if not headers:
            headers = self.headers
        request = urllib2.Request(url, data, headers)
        try:
            request_content = urllib2.urlopen(request)
            return request_content
        except:
            return False

    def set_local_file(self, file):
        self.local_file = file

    def read_html(self, url):
        """Read html content from url"""
        if self.local:
            #For tests use a local file
            html_output = open(self.local_file, "r")
            content = html_output.read()
            html_output.close()
        else:
            request = self.request_url(url)
            if request != False:
                content = request.read()
            else:
                content = "error"
        if self.verbose:
            print content
        return content

    def save_to(self, dest=None, url=None):
        request = self.request_url(url)
        if request != False:
            file(dest, "w").write(request.read())

    def parse_xml(self, url):
        file = urllib2.urlopen(url)
        xml_doc = xml.dom.minidom.parse(file)
        links = xml_doc.getElementsByTagName("a")
        seen = set()
        for a in links:
            value = a.getAttribute('href')
            if value and value not in seen:
                seen.add(value)
        return seen

    def parse_html(self, url):
        html_content = self.read_html(url)
