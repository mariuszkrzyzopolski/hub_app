import time
import socket
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Wait for PostgreSQL database to be available'

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=30)

    def handle(self, *args, **options):
        timeout = options['timeout']
        db_settings = settings.DATABASES['default']
        host = db_settings['HOST']
        port = int(db_settings['PORT'])

        self.stdout.write(f"Waiting for PostgreSQL at {host}:{port}...")

        for i in range(timeout):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                sock.close()
                if result == 0:
                    self.stdout.write(self.style.SUCCESS("PostgreSQL is ready!"))
                    return
            except Exception:
                pass
            time.sleep(1)

        self.stderr.write(self.style.ERROR(
            f"Timeout: PostgreSQL did not become ready within {timeout}s"
        ))
        exit(1)