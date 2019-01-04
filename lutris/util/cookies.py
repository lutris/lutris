import time
from http.cookiejar import MozillaCookieJar, Cookie, _warn_unhandled_exception


class WebkitCookieJar(MozillaCookieJar):
    """Subclass of MozillaCookieJar for compatibility with cookies
    coming from Webkit2.
    This disables the magic_re header which is not present and adds
    compatibility with HttpOnly cookies (See http://bugs.python.org/issue2190)
    """

    def _really_load(self, f, filename, ignore_discard, ignore_expires):
        now = time.time()
        try:
            while 1:
                line = f.readline()
                if line == "":
                    break

                # last field may be absent, so keep any trailing tab
                if line.endswith("\n"):
                    line = line[:-1]

                sline = line.strip()
                # support HttpOnly cookies (as stored by curl or old Firefox).
                if sline.startswith("#HttpOnly_"):
                    line = sline[10:]
                elif sline.startswith("#") or sline == "":
                    continue

                domain, domain_specified, path, secure, expires, name, value = line.split(
                    "\t"
                )
                secure = secure == "TRUE"
                domain_specified = domain_specified == "TRUE"
                if name == "":
                    # cookies.txt regards 'Set-Cookie: foo' as a cookie
                    # with no name, whereas http.cookiejar regards it as a
                    # cookie with no value.
                    name = value
                    value = None

                initial_dot = domain.startswith(".")
                assert domain_specified == initial_dot

                discard = False
                if expires == "":
                    expires = None
                    discard = True

                # assume path_specified is false
                c = Cookie(
                    0,
                    name,
                    value,
                    None,
                    False,
                    domain,
                    domain_specified,
                    initial_dot,
                    path,
                    False,
                    secure,
                    expires,
                    discard,
                    None,
                    None,
                    {},
                )
                if not ignore_discard and c.discard:
                    continue
                if not ignore_expires and c.is_expired(now):
                    continue
                self.set_cookie(c)

        except OSError:
            raise
        except Exception:
            _warn_unhandled_exception()
            raise OSError(
                "invalid Netscape format cookies file %r: %r" % (filename, line)
            )
