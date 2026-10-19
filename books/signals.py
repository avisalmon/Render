"""Books' signals. Kept to one: a new offer tells the people who wished for
that book (BK5 wishlist alerts). Run after the transaction so a rolled-back
offer never alerts anyone."""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Offer


@receiver(post_save, sender=Offer)
def offer_saved(sender, instance, created, **kwargs):
    if not created or not instance.is_active:
        return
    from . import hub

    transaction.on_commit(lambda: hub.alert_wishers(instance))
