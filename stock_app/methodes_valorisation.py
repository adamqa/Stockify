# stock_app/methodes_valorisation.py

class GestionnaireValorisation:
    """
    Gestionnaire de valorisation des stocks - Version simplifiée
    """
    
    @classmethod
    def calculer_cout_sortie(cls, article, quantite_sortie):
        """
        Calcule le coût d'une sortie utilisant le coût unitaire de l'article
        
        Args:
            article: L'article concerné
            quantite_sortie: La quantité à sortir
        
        Returns:
            decimal: La valeur totale de la sortie
        """
        try:
            # Utiliser le prix unitaire de l'article
            prix_unitaire = getattr(article, 'prix_unitaire', 0)
            if not prix_unitaire:
                # Fallback : chercher dans les lots
                from .models import Lot
                premier_lot = Lot.objects.filter(
                    id_article=article,
                    quantite_restante__gt=0
                ).first()
                if premier_lot:
                    prix_unitaire = premier_lot.cout_unitaire
            
            valeur = quantite_sortie * prix_unitaire
            return valeur
        except Exception as e:
            print(f"Erreur lors du calcul de valorisation: {e}")
            return 0
    
    @classmethod
    def calculer_cout_entree(cls, lot):
        """Calcule le coût d'une entrée"""
        if lot and lot.cout_unitaire and lot.quantite_lot:
            return lot.quantite_lot * lot.cout_unitaire
        return 0