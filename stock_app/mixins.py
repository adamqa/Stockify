# mixins.py
import json
from django.contrib.auth.models import AnonymousUser

class AuditTrailMixin:
    """Mixin pour enregistrer automatiquement les actions CRUD"""
    
    def log_action(self, request, instance, action, details=None):
        """Enregistre une action dans l'historique"""
        from .models import HistoriqueAction
        
        # Déterminer le nom de l'utilisateur
        username = "Système"
        if request and hasattr(request, 'user') and request.user and not isinstance(request.user, AnonymousUser):
            username = request.user.username
        
        # Générer les détails
        if details is None:
            details = {}
        
        # Ajouter l'instance à l'historique
        HistoriqueAction.objects.create(
            utilisateur=username,
            type_action=action,
            table_affectee=instance.__class__.__name__,
            id_entite_affectee=instance.pk,
            details_modifications=json.dumps(details, default=str),
            details_simplifies=self.generate_simple_details(instance, action, details)
        )
    
    def generate_simple_details(self, instance, action, details):
        """Génère une description lisible"""
        class_name = instance.__class__.__name__
        
        if action == 'CREATE':
            return f"➕ Création {class_name} #{instance.pk}"
        elif action == 'UPDATE':
            changed = details.get('changed_fields', [])
            return f"✏️ Modification {class_name} #{instance.pk} - Champs: {', '.join(changed)}"
        elif action == 'DELETE':
            return f"🗑️ Suppression {class_name} #{instance.pk}"
        elif action == 'LOGIN':
            return f"🔐 Connexion utilisateur: {instance}"
        elif action == 'LOGOUT':
            return f"🚪 Déconnexion utilisateur: {instance}"
        else:
            return f"📝 {action} sur {class_name} #{instance.pk}"