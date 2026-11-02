import re


class Redactor:
    def __init__(self):
        self.secrets = set()

    def register(self, value):
        if value:
            self.secrets.add(str(value))

    def clean(self, value, limit=4000):
        text = str(value)
        for secret in sorted(self.secrets, key=len, reverse=True):
            text = text.replace(secret, '[masqué]')
        text = re.sub(r'(?i)\b(?:Bearer|Basic)\s+[a-z0-9+/_.=~-]+', '[masqué]', text)
        text = re.sub(r'(?i)(https?://|wss?://)[^\s/@]+:[^\s/@]+@', r'\1[masqué]@', text)
        keys = r'authorization|password|passwd|secret|(?:access_|refresh_)?token|code_verifier|id_?tag|vin|code'
        text = re.sub(rf'''(?ix)(["']?\b(?:{keys})\b["']?\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s&,;}}]+)''',
                      r'\1[masqué]', text)
        # One logical entry per line; strip terminal control characters too.
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', text)
        return text[:limit] + ('…' if len(text) > limit else '')
