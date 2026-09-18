"""SensorLab's views.

SL-A1 is the shell only: one page, rendered from SensorLab's own base
template, proving the app is mounted and sealed. The real screens start in
SL-B4.
"""

from django.shortcuts import render


def home(request):
    return render(request, "sensorlab/home.html")
