"""Normalize native Tk wheel events, including X11 button events."""
def wheel_steps(event):
    number = getattr(event, 'num', None)
    if number in (4, 5):
        return 1 if number == 4 else -1
    delta = getattr(event, 'delta', 0)
    if not delta:
        return 0
    return int(delta / 120) if abs(delta) >= 120 else (1 if delta > 0 else -1)
