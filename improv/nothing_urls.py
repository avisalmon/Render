"""A urlconf with no routes. The gate points a refused request at it so that
CommonMiddleware, which asks "would this path plus a slash resolve?", finds
that nothing does and does not answer /improv with a redirect."""

urlpatterns = []
