import os
import sys
import threading

from django.core.management.base import BaseCommand
from flask import Flask
from flask_healthz import healthz

from telemetry.models import Coach, Driver, FastLap
from telemetry.pitcrew.crew import Crew
from telemetry.pitcrew.kube_crew import KubeCrew


class Command(BaseCommand):
    help = "start pitcrew"

    def add_arguments(self, parser):
        parser.add_argument("-k", "--kube-crew", nargs="?", type=str, default=None)
        parser.add_argument("-c", "--coach", nargs="?", type=str, default=None)
        parser.add_argument("-r", "--replay", action="store_true")
        parser.add_argument("-s", "--session-saver", action="store_true")
        parser.add_argument("-n", "--no-save", action="store_true")
        parser.add_argument("-d", "--delete-driver-fastlaps", action="store_true")

    def handle(self, *args, **options):
        if options["delete_driver_fastlaps"]:
            # get all fastlaps where driver is not empty
            FastLap.objects.filter(driver__isnull=False).delete()
            return

        crew = Crew(save=(not options["no_save"]), replay=options["replay"])

        # Check if the B4MAD_RACING_COACH environment variable is set
        env_coach = os.getenv('B4MAD_RACING_COACH')

        # If the environment variable is set, it overrides the --coach option
        coach_name = options["coach"] if options["coach"] else env_coach

        if options["kube_crew"]:
            cmd = options["kube_crew"]
            kube_crew = KubeCrew()
            if cmd == "start":
                kube_crew.start_coach(coach_name)
            elif cmd == "stop":
                kube_crew.stop_coach(coach_name)

            sys.exit(0)

        if coach_name:
            driver, created = Driver.objects.get_or_create(name=coach_name)
            coach, created = Coach.objects.get_or_create(driver=driver)
            crew.coach_watcher.start_coach(driver.name, coach, debug=True)
        elif options["session_saver"]:
            t = threading.Thread(target=crew.firehose.run)
            t.name = "firehose"
            t.start()
            t = threading.Thread(target=crew.session_saver.run)
            t.name = "session_saver"
            t.start()
        else:
            if not crew.replay and not options["no_save"]:

                def start_flask():
                    app = Flask(__name__)
                    app.register_blueprint(healthz, url_prefix="/healthz")
                    app.config["HEALTHZ"] = {"live": crew.live, "ready": crew.ready}
                    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

                flask_thread = threading.Thread(target=start_flask)
                flask_thread.start()

            crew.run()
            # TODO: if we end up here, we should probably exit the flask thread
