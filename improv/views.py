from django.shortcuts import render


def home(request):
    return render(request, "improv/home.html")


def spike(request):
    return render(request, "improv/spike.html")
