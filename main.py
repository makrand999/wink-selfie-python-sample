"""Temporal selfie gesture gate. Camera/model access stays in Android."""


SMILE_ON = 0.66
SMILE_OFF = 0.48
EYE_OPEN = 0.68
EYE_CLOSED = 0.28
SMILE_HOLD_MS = 350
WINK_MIN_MS = 130
WINK_MAX_MS = 750
REMINDER_MS = 6000


class WinkGate:
    def __init__(self):
        self.reset()

    def reset(self):
        self.smile_since = None
        self.smiling = False
        self.armed = False
        self.wink_since = None
        self.last_reminder = None
        self.last_time = None
        self.wink_side = None

    def observe(self, face_count, framed, smile_score, left_eye, right_eye, now_ms):
        face_count = int(face_count)
        now_ms = int(now_ms)
        if self.last_time is not None and (now_ms <= self.last_time or now_ms - self.last_time > 300):
            self._clear_gesture()
        self.last_time = now_ms
        left_eye = None if left_eye is None or float(left_eye) < 0 else float(left_eye)
        right_eye = None if right_eye is None or float(right_eye) < 0 else float(right_eye)
        smile_score = None if smile_score is None or float(smile_score) < 0 else float(smile_score)

        if face_count != 1:
            self._clear_gesture()
            status = "NO_FACE" if face_count == 0 else "MULTIPLE_FACES"
            return self._result(status)

        if not framed:
            self._clear_gesture()
            return self._result("ADJUST_FRAME")

        if smile_score is None:
            self._clear_gesture()
            return self._result("CHECKING_FACE")

        if not self.smiling:
            if smile_score >= SMILE_ON:
                self.smiling = True
                self.smile_since = now_ms
        elif smile_score < SMILE_OFF:
            self._clear_gesture()
            return self._smile_prompt(now_ms)

        if not self.smiling:
            return self._smile_prompt(now_ms)

        if now_ms - self.smile_since < SMILE_HOLD_MS:
            return self._result("HOLD_SMILE")

        eyes_known = left_eye is not None and right_eye is not None
        both_open = eyes_known and left_eye >= EYE_OPEN and right_eye >= EYE_OPEN
        left_wink = eyes_known and left_eye <= EYE_CLOSED and right_eye >= EYE_OPEN
        right_wink = eyes_known and right_eye <= EYE_CLOSED and left_eye >= EYE_OPEN

        if not self.armed:
            if both_open:
                self.wink_side = None
                self.armed = True
                return self._result("READY")
            return self._result("READY_OPEN_EYES")

        if left_wink or right_wink:
            side = "left" if left_wink else "right"
            if self.wink_side is not None and self.wink_side != side:
                self.armed = False
                self.wink_since = None
                self.wink_side = None
                return self._result("READY_OPEN_EYES")
            self.wink_side = side
            if self.wink_since is None:
                self.wink_since = now_ms
            elapsed = now_ms - self.wink_since
            if WINK_MIN_MS <= elapsed <= WINK_MAX_MS:
                self.armed = False
                self.wink_since = None
                return self._result("CAPTURE")
            if elapsed > WINK_MAX_MS:
                self.wink_since = None
                self.armed = False
            return self._result("WINK_DETECTED")

        # Any bilateral blink, uncertain eye observation, or reopened eye cancels
        # the candidate. Both eyes must be open once again to re-arm.
        self.wink_since = None
        self.wink_side = None
        if both_open:
            return self._result("READY")
        self.armed = False
        return self._result("READY_OPEN_EYES")

    def _clear_gesture(self):
        self.wink_side = None
        self.smile_since = None
        self.smiling = False
        self.armed = False
        self.wink_since = None

    def _smile_prompt(self, now_ms):
        if self.last_reminder is None or now_ms - self.last_reminder >= REMINDER_MS:
            self.last_reminder = now_ms
            return self._result("NEED_SMILE_PROMPT")
        return self._result("NEED_SMILE")

    def _result(self, status):
        return status


_gate = WinkGate()


def process(face_count, framed, smile_score, left_eye, right_eye, now_ms):
    """Return the current UI/action state as a plain string."""
    return _gate.observe(face_count, framed, smile_score, left_eye, right_eye, now_ms)


def reset():
    """Invalidate gesture evidence while preserving the speech cooldown."""
    _gate._clear_gesture()
    _gate.last_time = None
