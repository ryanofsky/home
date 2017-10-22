from django.db import models

class Url(models.Model):
    source = models.CharField(max_length=20)
    url = models.CharField(max_length=1000)
    title = models.CharField(max_length=1000)
    site = models.CharField(max_length=1000)
    score = models.IntegerField()
    comments = models.IntegerField()

class Event(models.Model):
    url = models.ForeignKey(Url, on_delete=models.PROTECT)
    date = models.DateTimeField()
    rating = models.IntegerField()
