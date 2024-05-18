import logging
from typing import Dict, Union

import django.utils.timezone

from .session import Session
from .session_rbr import SessionRbr
from .session_saver import SessionSaver


class Persister:
    def __init__(self, debug=False):
        self.debug = debug
        self.sessions: Dict[str, Union[Session, SessionRbr]] = {}
        self.clear_ticks = 0
        self.clear_interval = 60 * 60 * 5  # ticks. telemetry is sent at 60hz, so 60*60*5 = 5 minutes
        self.save_ticks = 0
        self.save_interval = 60 * 60 * 1  # ticks. telemetry is sent at 60hz, so 60*60*1 = 1 minute
        self.session_saver = SessionSaver(self)

    def notify(self, topic, payload, now=None):
        now = now or django.utils.timezone.now()
        if topic not in self.sessions:
            try:
                (
                    prefix,
                    driver,
                    session_id,
                    game,
                    track,
                    car,
                    session_type,
                ) = topic.split("/")
            except ValueError:
                # ignore invalid session
                return

            if game == "Richard Burns Rally":
                session = SessionRbr(topic, start=now)
            else:
                session = Session(topic, start=now)

            session.driver = driver
            session.session_id = session_id
            session.game_name = game
            session.track = track
            session.car = car
            session.car_class = payload.get("CarClass", "")
            session.session_type = session_type
            self.sessions[topic] = session
            logging.debug(f"New session: {topic}")

        session = self.sessions[topic]
        session.signal(payload, now)
        self.save_sessions(now)

    def save_sessions(self, now):
        if self.save_ticks < self.save_interval:
            self.save_ticks += 1
            return
        self.save_ticks = 0

        self.session_saver.save_sessions()
        self.clear_sessions(now)

    # TODO: clear sessions every now and then
    def clear_sessions(self, now):
        """Clear inactive telemetry sessions.

        Loops through all sessions and deletes:
        - Any session inactive for more than 10 minutes
        - Any lap marked for deletion

        Args:
            now (datetime): The current datetime

        """

        max_session_age = 60 * 60  # 1 hour
        delete_sessions = []
        for topic, session in self.sessions.items():
            if (now - session.end).seconds > max_session_age:
                delete_sessions.append(topic)

            # # Delete any lap marked for deletion
            # for i in range(len(session.laps) - 1, -1, -1):
            #     lap = session.laps[i]
            #     if lap.get("delete", False):
            #         logging.debug(f"{topic}\n\t deleting lap {lap['number']}")
            #         del session.laps[i]

        if len(delete_sessions) > 0:
            logging.debug(f"Inactive sessions: {len(delete_sessions)}")
            logging.debug(f"Active sessions: {len(self.sessions)}")

        # Delete all inactive sessions
        for topic in delete_sessions:
            del self.sessions[topic]
            logging.debug(f"{topic}\n\t deleting inactive session")
