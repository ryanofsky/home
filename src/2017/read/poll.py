import os
os.environ["DJANGO_SETTINGS_MODULE"] = "read.settings"

import django
django.setup()

from combine.models import Url

print(Url.objects.all())
