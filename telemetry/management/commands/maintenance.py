import datetime
import logging

from django.core.management.base import BaseCommand

from telemetry.influx import Influx
from telemetry.models import FastLap, Lap, Session


class Command(BaseCommand):
    help = "clean stuff"

    def add_arguments(self, parser):
        # add argument for list of lap ids as integers separated by commas
        parser.add_argument(
            "-d",
            "--delete-influx",
            help="delete old influx data",
            action="store_true",
        )

        parser.add_argument(
            "--delete-sessions",
            help="delete sessions",
            action="store_true",
        )

        parser.add_argument(
            "-s",
            "--start",
            help="start date for deletion",
            type=str,
            default=None,
        )
        parser.add_argument(
            "-e",
            "--end",
            help="end date for deletion",
            type=str,
            default=None,
        )

        parser.add_argument(
            "--fix-rbr-sessions",
            help="fix data",
            action="store_true",
        )

        parser.add_argument(
            "--fix-fastlaps",
            help="fix data",
            action="store_true",
        )

        parser.add_argument(
            "--fix-fastlaps-data",
            help="fix fastlaps data",
            action="store_true",
        )

    def handle(self, *args, **options):
        self.influx = Influx()
        if options["delete_influx"]:
            self.delete_influx(options["start"], options["end"])
        elif options["delete_sessions"]:
            self.delete_sessions(options["start"], options["end"])
        elif options["fix_rbr_sessions"]:
            self.fix_rbr_sessions()
        elif options["fix_fastlaps_data"]:
            self.fix_fastlaps_data()
        elif options["fix_fastlaps"]:
            self.fix_fastlaps()

    def fix_fastlaps(self):
        """
        Deletes fastlaps that have no associated laps.

        This method retrieves all primary keys for fastlaps and all ids for laps.
        It then removes the lap ids from the fastlap ids and deletes the fastlaps
        that have no associated laps.

        Returns:
            None
        """
        # get all primary keys for fastlaps
        fastlap_ids = list(FastLap.objects.all().values_list("id", flat=True))
        print(f"found {len(fastlap_ids)} fastlaps")

        # get all ids for laps
        lap_fast_laps_ids = list(Lap.objects.all().values_list("fast_lap", flat=True))

        # remove all lap_fast_laps_ids from fastlap_ids
        rm_fastlap_ids = list(set(fastlap_ids) - set(lap_fast_laps_ids))

        print(f"deleting {len(rm_fastlap_ids)} fastlaps")

        # delete all fastlaps that have no laps
        FastLap.objects.filter(id__in=rm_fastlap_ids).delete()

    def fix_fastlaps_data(self):
        """
        Checks the data attribute of each fastlap. The data attribute should be a dict with a key called 'segment' 
        that contains a list of instances of type `Segment`.

        Returns:
            None
        """
        from telemetry.models import Segment

        fastlaps = FastLap.objects.all()
        for fastlap in fastlaps:
            data = fastlap.data
            if not isinstance(data, dict):
                logging.warning(f"FastLap {fastlap.id} has invalid data format.")
                continue

            segments = data.get("segment", [])
            if not isinstance(segments, list):
                logging.warning(f"FastLap {fastlap.id} has invalid segments format.")
                continue

            for segment in segments:
                if not isinstance(segment, Segment):
                    logging.warning(f"FastLap {fastlap.id} has invalid segment instance.")
                    break

    def fix_rbr_sessions(self):
        # get all sessions for Richard Burns Rally
        sessions = Session.objects.filter(game__name="Richard Burns Rally")
        for session in sessions:
            # get all laps for this session
            laps = session.laps.all()
            # iterate over all laps
            for lap in laps:
                print(f"fixing lap {lap.id} end: {lap.end}")
                # set the end time of the lap to the start + the lap time
                lap.end = lap.start + datetime.timedelta(seconds=lap.time + 60)
                print(f"--> {lap.end}")
                lap.number = 0
                # save the lap
                lap.save()

    def delete_sessions(self, start, end):
        Session.objects.all().delete()

    def delete_influx(self, start, end):
        if start:
            start = datetime.datetime.strptime(start, "%Y-%m-%d")
        else:
            start = datetime.datetime.now() - datetime.timedelta(days=30)

        if end:
            end = datetime.datetime.strptime(end, "%Y-%m-%d")
        else:
            end = start + datetime.timedelta(days=1)

        # delete in on hour chunks
        while start < end:
            end_delta = start + datetime.timedelta(hours=4)
            logging.debug(f"Deleting data from {start} to {end_delta}")
            now = datetime.datetime.now()
            self.influx.delete_data(start=start, end=end_delta)
            # log how long it took
            logging.debug(f"... {datetime.datetime.now() - now}")
            start = end_delta
