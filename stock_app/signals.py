# signals.py
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Emplacement, HistoriqueEmplacement
from django.utils import timezone
from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .models import HistoriqueAction


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    """Enregistre la connexion d'un utilisateur"""
    HistoriqueAction.objects.create(
        utilisateur=user.username,
        type_action='LOGIN',
        table_affectee='Utilisateur',
        id_entite_affectee=user.id,
        details_simplifies=f"🔐 Connexion de {user.username}",
        details_modifications=None
    )

@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    """Enregistre la déconnexion d'un utilisateur"""
    if user:  # Parfois user peut être None
        HistoriqueAction.objects.create(
            utilisateur=user.username,
            type_action='LOGOUT',
            table_affectee='Utilisateur',
            id_entite_affectee=user.id,
            details_simplifies=f"🚪 Déconnexion de {user.username}",
            details_modifications=None
        )

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