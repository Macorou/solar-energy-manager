class Timers:
    def __init__(self):
        self.since = {}

    def reached(self, key, condition, duration, now):
        if not condition:
            self.since.pop(key,None)
            return False
        self.since.setdefault(key,now)
        return now-self.since[key] >= duration

    def remaining(self, key, duration, now):
        return max(0, duration-(now-self.since.get(key,now)))

