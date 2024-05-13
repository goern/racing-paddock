import logging
from typing import Dict, Union

import django.utils.timezone

from telemetry.models import Driver

from .session import Session
from .session_rbr import SessionRbr


class ActiveDrivers:
    def __init__(self, debug=False):
        self.debug = debug
        self.sessions: Dict[str, Union[Session, SessionRbr]] = {}
        self.do_clear_sessions = False

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

            try:
                db_driver, created = Driver.objects.get_or_create(name=driver)
                session.driver = db_driver
                session.session_id = session_id
                logging.debug(f"New session: {topic}")
                session.game_name = game
                session.track = track
                session.car = car
                session.car_class = payload.get("CarClass", "")
                session.session_type = session_type
                self.sessions[topic] = session
            except Exception as e:
                logging.error(f"Error creating driver {driver} - {e}")
                return

        session = self.sessions[topic]
        session.end = now
        if self.do_clear_sessions:
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

        delete_sessions = []
        for topic, session in self.sessions.items():
            # Delete session without updates for 10 minutes
            if (now - session.end).seconds > 600:
                delete_sessions.append(topic)

        # Delete all inactive sessions
        for topic in delete_sessions:
            del self.sessions[topic]
            logging.debug(f"{topic}\n\t deleting inactive session")
