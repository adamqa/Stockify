# methodes_valorisation.py
from django.db.models import Sum
from .models import Lot

class GestionnaireValorisation:
    @staticmethod
    def calculer_cout_sortie(article, quantite):
        """Calculate cost of outgoing movement using article's valuation method"""
        lots = Lot.objects.filter(
            id_article=article,
            quantite_restante__gt=0
        ).order_by('date_entree')  # FIFO by default
        
        if article.methode_valorisation == 'FIFO':
            return GestionnaireValorisation._fifo_cost(lots, quantite)
        elif article.methode_valorisation == 'LIFO':
            return GestionnaireValorisation._lifo_cost(lots, quantite)
        else:  # CMP
            return GestionnaireValorisation._cmp_cost(article, quantite)
    
    @staticmethod
    def _fifo_cost(lots, quantite):
        """Calculate cost using FIFO method"""
        remaining = quantite
        total_cost = 0
        
        for lot in lots:
            if remaining <= 0:
                break
            qty_to_take = min(remaining, lot.quantite_restante)
            total_cost += qty_to_take * lot.cout_unitaire
            remaining -= qty_to_take
        
        return total_cost
    
    @staticmethod
    def _lifo_cost(lots, quantite):
        """Calculate cost using LIFO method"""
        lots = list(lots)[::-1]  # Reverse order
        remaining = quantite
        total_cost = 0
        
        for lot in lots:
            if remaining <= 0:
                break
            qty_to_take = min(remaining, lot.quantite_restante)
            total_cost += qty_to_take * lot.cout_unitaire
            remaining -= qty_to_take
        
        return total_cost
    
    @staticmethod
    def _cmp_cost(article, quantite):
        """Calculate cost using CMP (Weighted Average) method"""
        lots = Lot.objects.filter(
            id_article=article,
            quantite_restante__gt=0
        )
        
        total_value = sum(lot.quantite_restante * lot.cout_unitaire for lot in lots)
        total_quantity = sum(lot.quantite_restante for lot in lots)
        
        if total_quantity > 0:
            avg_cost = total_value / total_quantity
            return quantite * avg_cost
        
        return quantite * article.prix_unitaire