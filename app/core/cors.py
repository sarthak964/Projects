from urllib.parse import urlsplit


def parse_allowed_origins(raw):
    origins = []
    for value in raw.split(","):
        value = value.strip()
        if not value:
            continue
        try:
            url = urlsplit(value)
            valid = (
                url.scheme in ("http", "https") and url.hostname is not None
                and url.username is None and url.password is None
                and url.path in ("", "/") and not url.query and not url.fragment
                and "*" not in url.netloc and "\\" not in url.netloc
                and not any(char.isspace() for char in url.netloc)
            )
            _ = url.port
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("CORS_ALLOWED_ORIGINS must contain explicit http(s) origins, without paths or wildcards")
        origin = url.scheme + "://" + url.netloc.lower()
        if origin not in origins:
            origins.append(origin)
    return origins
