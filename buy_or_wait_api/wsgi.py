from __future__ import annotations

import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "buy_or_wait_api.settings")

application = get_wsgi_application()
