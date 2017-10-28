#!/usr/bin/python3

import os
os.environ["DJANGO_SETTINGS_MODULE"] = "read.settings"

import django
django.setup()

from combine.models import Url, Request
import sys
import requests
import pprint

url = "http://hckrnews.com/data/20171022.js"
url = "http://localhost:8000/data/20171022.js"

try:
    req = Request.objects.filter(url=url).order_by("-time")[:1].get()
    print("cached")
except Request.DoesNotExist:
    headers = {
        'Host':
        'hckrnews.com',
        'User-Agent':
        'Mozilla/5.0 (X11; Linux x86_64; rv:57.0) Gecko/20100101 Firefox/57.0',
        'Accept':
        'application/json, text/javascript, */*; q=0.01',
        'Accept-Language':
        'en-US,en;q=0.5',
        'Referer':
        'http://hckrnews.com/',
        'X-Requested-With':
        'XMLHttpRequest',
        'Connection':
        'keep-alive',
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    req = Request(url=url, data=r.content)
    req.save()
    print("new")

pprint.pprint(req.url)
pprint.pprint(req.time)
pprint.pprint(len(req.data))
