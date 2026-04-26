# signals.py
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Emplacement, HistoriqueEmplacement
from django.utils import timezone

@receiver(pre_save, sender=Emplacement)
def track_emplacement_change(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Emplacement.objects.get(pk=instance.pk)
            if old_instance.id_article != instance.id_article:
                # Fermer l'ancien historique
                HistoriqueEmplacement.objects.filter(
                    emplacement=instance,
                    est_actif=True
                ).update(date_fin=timezone.now(), est_actif=False)
        except Emplacement.DoesNotExist:
            pass

@receiver(post_save, sender=Emplacement)
def create_emplacement_history(sender, instance, created, **kwargs):
    if instance.id_article:
        HistoriqueEmplacement.objects.create(
            emplacement=instance,
            article=instance.id_article,
            est_actif=True
        )