"""Sign in, sign up and sign out, all in SensorLab's own chrome (Rule 3).

The accounts underneath are the site's shared `User`, and Google sign-in is
the site's shared allauth flow — that is infrastructure every app here uses,
not a navigation leak back to babook.
"""

from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import SensorLabLoginForm, SensorLabSignupForm
from .profiles import profile_for


class LoginView(auth.LoginView):
    template_name = "sensorlab/auth/login.html"
    authentication_form = SensorLabLoginForm
    redirect_authenticated_user = True
    next_page = reverse_lazy("sensorlab:lab")

    def form_valid(self, response):
        result = super().form_valid(response)
        profile_for(self.request.user)
        return result


class LogoutView(auth.LogoutView):
    next_page = reverse_lazy("sensorlab:home")


def signup(request):
    if request.user.is_authenticated:
        return redirect("sensorlab:lab")
    if request.method == "POST":
        form = SensorLabSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            profile_for(user)
            return redirect("sensorlab:lab")
    else:
        form = SensorLabSignupForm()
    return render(request, "sensorlab/auth/signup.html", {"form": form})
