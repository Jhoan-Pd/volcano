"""supervisord event listener: stop the whole container when a service cannot be kept running.

supervisord restarts a crashed program a few times and then marks it FATAL and gives up — leaving a
container that looks alive while, say, nothing listens on the public port. The platform would only
find out by timing out a deploy fifteen minutes later, with no hint of the cause. Exiting instead
makes the failure immediate and visible: the platform reports the crash next to the service's own
error message and restarts the container.

Protocol: http://supervisord.org/events.html#event-listeners-and-event-notifications
"""
import os
import signal
import sys


def main() -> None:
    while True:
        sys.stdout.write("READY\n")
        sys.stdout.flush()
        header = dict(token.split(":", 1) for token in sys.stdin.readline().split())
        payload = dict(token.split(":", 1) for token in sys.stdin.read(int(header["len"])).split())
        if header.get("eventname") == "PROCESS_STATE_FATAL":
            sys.stderr.write(f"fail-fast: '{payload.get('processname')}' could not start; stopping the container\n")
            sys.stderr.flush()
            os.kill(os.getppid(), signal.SIGTERM)  # supervisord, which then stops every program
        sys.stdout.write("RESULT 2\nOK")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
