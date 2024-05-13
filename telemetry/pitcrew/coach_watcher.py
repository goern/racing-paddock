import logging
import threading
import time

from telemetry.models import Driver

from .active_drivers import ActiveDrivers

# from .coach import Coach as PitCrewCoach
# from .coach_app import CoachApp
from .coach_copilots import CoachCopilots
from .history import History
from .kube_crew import KubeCrew
from .mqtt import Mqtt


class CoachWatcher:
    def __init__(self, firehose: ActiveDrivers, replay=False):
        self.firehose = firehose
        self.sleep_time = 10
        self.active_coaches = {}
        self.replay = replay
        self.ready = False
        self._stop_event = threading.Event()
        self.kube_crew = KubeCrew()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

    def drivers(self):
        drivers = set()
        for session in self.firehose.sessions.values():
            # check if session.driver is a Driver object
            if isinstance(session.driver, Driver):
                drivers.add(session.driver)
        return drivers

    def watch_coaches(self):
        self.ready = True
        while True and not self.stopped():
            # sleep longer than save_sessions, to make sure all DB objects are initialized
            time.sleep(self.sleep_time)
            drivers = self.drivers()
            self.kube_crew.drivers.clear()
            for driver in drivers:
                self.kube_crew.drivers.add(driver.name)
            self.kube_crew.sync_deployments()
            self.firehose.do_clear_sessions = True

    def start_coach(self, driver_name, coach_model, debug=False):
        history = History()
        # if coach_model.mode == Coach.MODE_TRACK_GUIDE_APP or coach_model.mode == Coach.MODE_DEBUG_APP:
        #     coach = CoachApp(history, coach_model, debug=debug)
        # if coach_model.mode == Coach.MODE_COPILOTS:
        #     coach = CoachCopilots(history, coach_model, debug=debug)
        # else:
        #     coach = PitCrewCoach(history, coach_model, debug=debug)
        coach = CoachCopilots(history, coach_model, debug=debug)

        topic = f"crewchief/{driver_name}/#"
        mqtt = Mqtt(coach, topic, replay=self.replay, debug=debug)

        def history_thread():
            logging.info(f"History thread starting for {driver_name}")
            history.run()
            logging.info(f"History thread stopped for {driver_name}")

        h = threading.Thread(target=history_thread)
        h.name = f"history-{driver_name}"

        def mqtt_thread():
            logging.info(f"MQTT thread starting for {driver_name}")
            mqtt.run()
            logging.info(f"MQTT thread stopped for {driver_name}")

        c = threading.Thread(target=mqtt_thread)
        c.name = f"mqtt-{driver_name}"

        threads = list()
        threads.append(h)
        threads.append(c)
        c.start()
        h.start()

    def run(self):
        try:
            self.watch_coaches()
        except Exception as e:
            logging.exception(f"Exception in CoachWatcher: {e}")
            raise e
