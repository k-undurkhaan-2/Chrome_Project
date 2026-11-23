"""Independent offline watchdog model. It owns no process/pipe/OS capability."""
from .native_probe_protocol import ProbeError, require


class Limits:
    """Conservative 60 s/case, 15 min/session model, in one injected clock."""
    def __init__(self, clock_ms):
        self.clock, self.last, self.case_started = clock_ms, -1, None
        self.failed = False
        self.started = self._now()

    def _now(self):
        value = self.clock()
        require(type(value) is int and value >= 0 and value >= self.last, "LIMIT_CLOCK")
        self.last = value
        return value

    def check(self):
        try:
            require(not self.failed, "LIMITS_CLOSED")
            now = self._now()
            require(now - self.started < 900000, "SESSION_TIMEOUT")
            require(self.case_started is None or now - self.case_started < 60000, "CASE_TIMEOUT")
            return now
        except Exception:
            self.failed = True
            raise

    def start_case(self):
        require(self.case_started is None, "CASE_OVERLAP")
        self.case_started = self.check()

    def finish_case(self):
        self.check()
        self.case_started = None


class Watchdog:
    def __init__(self, clock_ms, emit, *, enabled=False):
        require(enabled is True, "WATCHDOG_DISABLED")
        self.clock, self.emit = clock_ms, emit
        self.state, self.started, self.last = "IDLE", None, -1
        self.request_id = ""

    def _now(self):
        value = self.clock()
        if type(value) is not int or value < 0 or value < self.last:
            self.state = "INDETERMINATE"
            raise ProbeError("WATCHDOG_CLOCK")
        self.last = value
        return value

    def arm(self, request_id):
        require(self.state == "IDLE", "WATCHDOG_ACTIVE")
        self.started, self.request_id = self._now(), request_id
        self.state = "ARMED"
        self.emit("WATCHDOG_ARM", {"request_id": request_id, "deadline_ms": 250, "cutoff_ms": 2000})

    def cancel(self):
        if self.state in ("ARMED", "DEADLINE"):
            self.state = "CANCEL_REQUESTED"
            self.emit("CANCEL_REQUEST", {"request_id": self.request_id})

    def poll(self):
        now = self._now()
        if self.started is None or self.state in ("COMPLETE", "COMPLETE_IO", "INDETERMINATE"):
            return self.state
        elapsed = now - self.started
        if elapsed >= 2000:
            self.state = "INDETERMINATE"
            self.emit("HARD_CUTOFF_MODEL", {"request_id": self.request_id, "elapsed_ms": elapsed})
        elif elapsed >= 250 and self.state == "ARMED":
            self.state = "DEADLINE"
            self.emit("DEADLINE", {"request_id": self.request_id, "elapsed_ms": elapsed})
        return self.state

    def observe_reply(self):
        """Operation completion is distinct from closing the session's resources."""
        require(self.poll() == "ARMED", "WATCHDOG_REPLY_LATE")
        self.state = "COMPLETE_IO"
        self.emit("REPLY_OBSERVED", {"request_id": self.request_id, "resources_closed": False})
        return self.state

    def observe_completion(self, *, io_completed, resources_closed):
        # A cancellation *request* is deliberately insufficient evidence.
        self.poll()
        require(self.state in ("ARMED", "DEADLINE", "CANCEL_REQUESTED", "INDETERMINATE"), "WATCHDOG_NOT_ARMED")
        if io_completed is True and resources_closed is True and self.state != "INDETERMINATE":
            self.state = "COMPLETE"
        else:
            self.state = "INDETERMINATE"
        self.emit("CLEANUP_OBSERVED", {"request_id": self.request_id, "io_completed": io_completed is True,
                                     "resources_closed": resources_closed is True, "state": self.state})
        return self.state
