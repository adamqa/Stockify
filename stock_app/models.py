import json
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from datetime import date, timedelta
from django.core.exceptions import ValidationError

class Utilisateur(AbstractUser):
    ROLE_CHOICES = [
        ('Responsable_magasin', 'Responsable Magasin'),
        ('magasinier', 'Magasinier'),
        ('Responsable_Audit', 'Responsable_Audit'),
    ]

    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='magasinier')
    telephone = models.CharField(max_length=15, blank=True)

    class Meta:
        db_table = 'utilisateur'

    def __str__(self):
        return f"{self.username} ({self.role})"

class Article(models.Model):
    FAMILLE_CHOICES = [
        ('MP', 'MP'),
        ('PF', 'PF'),
        ('SPF', 'SPF'),
        ('P.RECH', 'P.RECH'),
        ('consommable', 'consommable'),
    ]

    STATUT_CHOICES = [
        ('disponible', 'disponible'),
        ('bloqué', 'bloqué'),
        ('en contrôle', 'en contrôle'),
        ('réservé', 'réservé'),
    ]

    id_article = models.AutoField(primary_key=True)
    nom_article = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True, null=True)
    famille = models.CharField(max_length=50, choices=FAMILLE_CHOICES)
    sous_famille = models.CharField(max_length=100, blank=True, null=True)
    categorie = models.CharField(max_length=100, blank=True, null=True)
    unite_mesure = models.CharField(max_length=20)
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    date_peremption = models.DateField(blank=True, null=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='disponible')
    seuil_securite = models.IntegerField()
    classe_abc = models.CharField(max_length=1, choices=[('A','A'),('B','B'),('C','C')], default='C', blank=True)
    methode_valorisation = models.CharField(
        max_length=10,
        choices=[('FIFO','FIFO'), ('LIFO','LIFO'), ('CMP','CMP')],
        default='FIFO'
    )

    def quantite_stock_actuel(self):
        """Retourne la quantité totale en stock pour cet article"""
        return Lot.objects.filter(
            id_article=self,
            quantite_restante__gt=0
        ).aggregate(total=Sum('quantite_restante'))['total'] or 0

    def valeur_stock_actuel(self):
        """Retourne la valeur totale du stock pour cet article"""
        lots = Lot.objects.filter(id_article=self, quantite_restante__gt=0)
        return sum(lot.quantite_restante * lot.cout_unitaire for lot in lots)

    def get_consommation_annuelle_quantite(self):
        """Calcule la consommation annuelle en QUANTITÉ - VERSION CORRIGÉE"""
        from datetime import datetime, timedelta
        date_debut = datetime.now() - timedelta(days=365)

        # Consommation externe
        conso_externe = Mouvement_Sortie_externe.objects.filter(
            id_article=self,
            date_sortie__gte=date_debut
        ).aggregate(total=Sum('quantite_sortie'))['total'] or 0

        # Consommation interne
        conso_interne = Mouvement_Sortie.objects.filter(
            id_article=self,
            date_sortie__gte=date_debut
        ).aggregate(total=Sum('quantite_sortie'))['total'] or 0

        total = conso_externe + conso_interne
        return total

    def get_consommation_annuelle_valeur(self):
        """Calcule la consommation annuelle en VALEUR - VERSION CORRIGÉE"""
        from datetime import datetime, timedelta
        date_debut = datetime.now() - timedelta(days=365)

        # Utiliser les champs valeur_sortie qui sont déjà calculés
        conso_externe = Mouvement_Sortie_externe.objects.filter(
            id_article=self,
            date_sortie__gte=date_debut
        ).aggregate(total=Sum('valeur_sortie'))['total'] or 0

        conso_interne = Mouvement_Sortie.objects.filter(
            id_article=self,
            date_sortie__gte=date_debut
        ).aggregate(total=Sum('valeur_sortie'))['total'] or 0

        return conso_externe + conso_interne

    def get_statut_stock(self):
        """Retourne le statut du stock par rapport au seuil de sécurité"""
        quantite_totale = self.quantite_stock_actuel()
        if quantite_totale <= 0:
            return "❌ Rupture"
        elif quantite_totale <= self.seuil_securite:
            return "⚠️ Critique"
        else:
            return "✅ Sécurisé"

    class Meta:
        pass

    def __str__(self):
        return f"{self.id_article} - {self.nom_article} ({self.classe_abc})"

class Lot(models.Model):
    STATUT_CHOICES = [
        ('disponible', 'disponible'),
        ('bloqué', 'bloqué'),
        ('réservé', 'réservé'),
        ('en contrôle', 'en contrôle'),
    ]

    id_lot = models.AutoField(primary_key=True)
    id_article = models.ForeignKey(Article, on_delete=models.CASCADE, db_column='id_article')
    date_peremption = models.DateField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='disponible')

    proche = models.IntegerField(choices=[(1, '1'), (20, '20'), (100, '100')], verbose_name="Type de Proche", default=1)

    quantite_lot = models.IntegerField(verbose_name="Quantité du Lot", default=0)

    cout_unitaire = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date_entree = models.DateField(default=date.today)
    quantite_restante = models.IntegerField(default=0)

    def clean(self):
        """Validation pour s'assurer que la quantité restante est cohérente"""
        if self.quantite_restante > self.quantite_lot:
            raise ValidationError("La quantité restante ne peut pas dépasser la quantité du lot")
        if self.quantite_restante < 0:
            raise ValidationError("La quantité restante ne peut pas être négative")

    def save(self, *args, **kwargs):
        # Initialiser quantite_restante si c'est un nouveau lot
        if not self.pk:
            self.quantite_restante = self.quantite_lot

        # S'assurer que quantite_restante est valide
        if self.quantite_restante > self.quantite_lot:
            self.quantite_restante = self.quantite_lot
        if self.quantite_restante < 0:
            self.quantite_restante = 0

        super().save(*args, **kwargs)

    def get_capacite_correspondante(self):
        """Retourne la capacité maximale correspondante au PROCHE"""
        capacites = {
            1: 5,
            20: 50,
            100: 300
        }
        return capacites.get(self.proche, 0)

    class Meta:
        pass

    def __str__(self):
        return f"{self.id_lot} - {self.id_article.nom_article} (Proche: {self.proche}, Restant: {self.quantite_restante})"

class Emplacement(models.Model):
    ZONE_CHOICES = [
        ('préparation', 'préparation'),
        ('stockage', 'stockage'),
        ('retours', 'retours'),
    ]

    id_emplacement = models.AutoField(primary_key=True)
    zone_physique = models.CharField(max_length=50, choices=ZONE_CHOICES)
    rack = models.IntegerField()
    etagere = models.CharField(max_length=50)
    capacite_max = models.IntegerField(default=0)
    capacite_actuelle = models.IntegerField(default=0)
    id_article = models.ForeignKey(Article, on_delete=models.CASCADE, db_column='id_article', null=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, help_text="Latitude for map positioning")
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, help_text="Longitude for map positioning")
    def get_capacite_auto_selon_lot(self):
        """Calcule la capacité max automatique basée sur le PROCHE de l'article"""
        if self.id_article:
            lot = Lot.objects.filter(id_article=self.id_article).first()
            if lot and lot.proche:
                capacites = {
                    1: 5,
                    20: 50,
                    100: 300
                }
                return capacites.get(lot.proche, 0)
        return 0

    def pourcentage_occupation(self):
        if self.capacite_max > 0:
            return (self.capacite_actuelle / self.capacite_max) * 100
        return 0

    def clean(self):
        if self.capacite_actuelle > self.capacite_max:
            raise ValidationError(
                f"La capacité actuelle ({self.capacite_actuelle}) ne peut pas dépasser la capacité maximale ({self.capacite_max})"
            )

    def save(self, *args, **kwargs):
        if self.id_article:
            capacite_auto = self.get_capacite_auto_selon_lot()
            if capacite_auto > 0:
                self.capacite_max = capacite_auto

        if self.capacite_actuelle > self.capacite_max:
            self.capacite_actuelle = self.capacite_max

        super().save(*args, **kwargs)

    class Meta:
        pass

    def __str__(self):
        article_nom = self.id_article.nom_article if self.id_article else "Non affecté"
        return f"{self.id_emplacement} - {article_nom} - {self.zone_physique}"

class Mouvement_Entree(models.Model):
    TYPE_ENTREE_CHOICES = [
        ('achat', 'achat'),
        ('transfert', 'transfert'),
        ('retour', 'retour'),
    ]

    id_entree = models.AutoField(primary_key=True)
    id_article = models.ForeignKey(Article, on_delete=models.CASCADE, db_column='id_article')
    id_lot = models.ForeignKey(Lot, on_delete=models.CASCADE, db_column='id_lot')
    date_entree = models.DateField()
    type_entree = models.CharField(max_length=50, choices=TYPE_ENTREE_CHOICES)
    documents_reglementaires = models.CharField(max_length=100, blank=True, null=True)
    id_responsable = models.ForeignKey(
        Utilisateur, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='entrees_effectuees'
    )
    reference_facture = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    class Meta:
        pass

    def __str__(self):
        return f"Entrée {self.id_entree} - {self.id_article.nom_article}"

class Mouvement_Sortie(models.Model):
    TYPE_SORTIE_CHOICES = [
        ('transfert_interne', 'Transfert Interne'),
        ('consommation_interne', 'Consommation Interne'),
        ('ajustement', 'Ajustement'),
        ('destruction', 'Destruction'),
        ('échantillon', 'Échantillon'),
    ]

    id_sortie = models.AutoField(primary_key=True)
    id_article = models.ForeignKey(Article, on_delete=models.CASCADE, db_column='id_article')
    id_lot = models.ForeignKey(Lot, on_delete=models.CASCADE, db_column='id_lot')
    date_sortie = models.DateField()
    quantite_sortie = models.IntegerField()
    type_sortie = models.CharField(max_length=50, choices=TYPE_SORTIE_CHOICES)
    valeur_sortie = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    id_responsable = models.ForeignKey(
        Utilisateur, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='sorties_effectuees'
    )
    motif = models.CharField(max_length=200, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def clean(self):
        """Validation de la quantité disponible"""
        if self.pk:  # Si modification
            ancien_mouvement = Mouvement_Sortie.objects.get(pk=self.pk)
            quantite_disponible = self.id_lot.quantite_restante + ancien_mouvement.quantite_sortie
        else:  # Si création
            quantite_disponible = self.id_lot.quantite_restante

        if self.quantite_sortie > quantite_disponible:
            raise ValidationError(f"Quantité insuffisante dans le lot. Disponible: {quantite_disponible}")

    def save(self, *args, **kwargs):
        # 🔥 CORRECTION : Gérer la modification
        if self.pk:  # Si l'objet existe déjà (modification)
            print(f"🔄 Modification détectée - ID: {self.pk}")
            # Récupérer l'ancienne valeur depuis la base
            ancien_mouvement = Mouvement_Sortie.objects.get(pk=self.pk)
            ancienne_quantite = ancien_mouvement.quantite_sortie
            print(f"📊 Ancienne quantité: {ancienne_quantite}, Nouvelle quantité: {self.quantite_sortie}")

            # RESTAURER l'ancienne quantité
            self.id_lot.quantite_restante += ancienne_quantite
            print(f"🔄 Quantité restaurée: {self.id_lot.quantite_restante}")

        # CALCULER LA VALEUR DE SORTIE
        if not self.valeur_sortie and self.quantite_sortie > 0:
            from .methodes_valorisation import GestionnaireValorisation
            try:
                self.valeur_sortie = GestionnaireValorisation.calculer_cout_sortie(
                    self.id_article, self.quantite_sortie
                )
            except:
                # Fallback si la valorisation échoue
                self.valeur_sortie = self.quantite_sortie * self.id_article.prix_unitaire

        # SOUSTRAIRE la nouvelle quantité
        self.id_lot.quantite_restante -= self.quantite_sortie
        self.id_lot.save()
        print(f"✅ Nouvelle quantité soustraite: {self.id_lot.quantite_restante}")

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Restaurer la quantité restante si suppression
        self.id_lot.quantite_restante += self.quantite_sortie
        self.id_lot.save()
        super().delete(*args, **kwargs)

    class Meta:
        pass

    def __str__(self):
        return f"Sortie Interne {self.id_sortie} - {self.id_article.nom_article}"

class Mouvement_Sortie_externe(models.Model):
    TYPE_SORTIE_CHOICES = [
        ('vente', 'vente'),
        ('consommation', 'consommation'),
    ]

    id_sortie_externe = models.AutoField(primary_key=True)
    id_article = models.ForeignKey(Article, on_delete=models.CASCADE, db_column='id_article')
    id_lot = models.ForeignKey(Lot, on_delete=models.CASCADE, db_column='id_lot')
    date_sortie = models.DateField()
    quantite_sortie = models.IntegerField()
    type_sortie = models.CharField(max_length=50, choices=TYPE_SORTIE_CHOICES)
    documents_reglementaires = models.CharField(max_length=100, blank=True, null=True)
    valeur_sortie = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    id_responsable = models.ForeignKey(
        Utilisateur, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='sorties_externes_effectuees'
    )
    client_nom = models.CharField(max_length=200, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
class HistoriqueEmplacement(models.Model):
    id_historique = models.AutoField(primary_key=True)
    emplacement = models.ForeignKey(Emplacement, on_delete=models.CASCADE, related_name='historique')
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    date_debut = models.DateTimeField(auto_now_add=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    est_actif = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'historique_emplacement'
        ordering = ['-date_debut']
    
    def __str__(self):
        return f"{self.article.nom_article} -> {self.emplacement.zone_physique} (début: {self.date_debut})"

class Inventaire(models.Model):
    id_inventaire = models.AutoField(primary_key=True)
    article = models.ForeignKey(Article, on_delete=models.CASCADE, db_column='id_article', verbose_name="Article inventorié",default=1)
    quantite_theorique = models.IntegerField(default=0, verbose_name="Quantité théorique (système)")
    quantite_reelle = models.IntegerField(default=0, verbose_name="Quantité réelle (comptée)")
    ecart = models.IntegerField(default=0, verbose_name="Écart")
    date_inventaire = models.DateField(auto_now_add=True, verbose_name="Date de l'inventaire")
    responsable = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        null=True,      # ← Ajoutez ceci
        blank=True      # ← Ajoutez ceci
    )
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    statut = models.CharField(max_length=20, choices=[
        ('brouillon', 'Brouillon'),
        ('valide', 'Validé'),
        ('corrige', 'Corrigé')
    ], default='brouillon')

    class Meta:
        db_table = 'inventaire'
        ordering = ['-date_inventaire']
        # unique_together = ['article', 'date_inventaire']  # Un seul inventaire par article par jour

    def save(self, *args, **kwargs):
        # Calcul automatique de l'écart
        self.ecart = self.quantite_reelle - self.quantite_theorique
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.article.nom_article} - {self.date_inventaire} (Écart: {self.ecart})"



class Depreciation(models.Model):
    id_depreciation = models.AutoField(primary_key=True)
    id_article = models.ForeignKey(Article, on_delete=models.CASCADE, db_column='id_article')
    id_lot = models.ForeignKey(Lot, on_delete=models.CASCADE, db_column='id_lot')
    date_depreciation = models.DateField()
    montant_depreciation = models.DecimalField(max_digits=12, decimal_places=2)
    cout = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        # 1. Enregistrer la dépréciation
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # 2. Mettre à jour le Lot lié si c'est une nouvelle dépréciation
        if is_new:
            # Récupérer le lot
            lot = self.id_lot

            # La quantité restante est utilisée pour répartir le montant de la dépréciation
            # Dépréciation unitaire = Montant Total Déprécié / Quantité Restante
            if lot.quantite_restante > 0:
                # Calculer la dépréciation unitaire
                depreciation_unitaire = self.montant_depreciation / lot.quantite_restante

                # Mettre à jour le coût unitaire du lot
                # Le coût unitaire est REDUIT par la dépréciation
                lot.cout_unitaire = lot.cout_unitaire - depreciation_unitaire

                # S'assurer que le coût unitaire ne devient pas négatif
                if lot.cout_unitaire < 0:
                    lot.cout_unitaire = 0

                lot.save(update_fields=['cout_unitaire'])

                # OPTIONNEL: Enregistrer une action d'historique (similaire à la suppression)
                from .models import HistoriqueAction
                HistoriqueAction.objects.create(
                    utilisateur="SYSTEME_DEPRECIATION",
                    type_action="DEPRECIATION",
                    table_affectee="Lot",
                    id_entite_affectee=lot.id_lot,
                    details_simplifies=f"Dépréciation de {self.montant_depreciation} € appliquée au Lot #{lot.id_lot}. Nouveau coût unitaire: {lot.cout_unitaire:.2f} €."
                )
            else:
                 # Gérer le cas où la quantité est nulle (le coût unitaire n'est pas modifié)
                 pass

    class Meta:
        pass

    def __str__(self):
        return f"Dépréciation {self.id_depreciation} - {self.id_article.nom_article}"



class Historique_Classification_ABC(models.Model):
    id_historique = models.AutoField(primary_key=True)
    id_article = models.ForeignKey(Article, on_delete=models.CASCADE, db_column='id_article')
    ancienne_classe = models.CharField(max_length=1, choices=[('A','A'),('B','B'),('C','C')])
    nouvelle_classe = models.CharField(max_length=1, choices=[('A','A'),('B','B'),('C','C')])
    date_changement = models.DateField()

    class Meta:
        pass

    def __str__(self):
        return f"Changement ABC {self.id_article.nom_article}"

class HistoriqueAction(models.Model):
    date_action = models.DateTimeField(auto_now_add=True)
    utilisateur = models.CharField(max_length=100, default="Système")
    type_action = models.CharField(max_length=50)
    table_affectee = models.CharField(max_length=100)
    id_entite_affectee = models.IntegerField(null=True, blank=True)
    details_modifications = models.TextField(null=True, blank=True)
    details_simplifies = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        # FIX: Check if utilisateur is a User object
        if hasattr(self, 'utilisateur') and hasattr(self.utilisateur, 'username'):
            self.utilisateur = self.utilisateur.username
        elif not self.utilisateur or self.utilisateur == "Système":
            self.utilisateur = "Système"

        # Generate simplified details if not provided
        if not self.details_simplifies:
            self.details_simplifies = self.generer_details_simplifies()

        super().save(*args, **kwargs)

    def generer_details_simplifies(self):
        # Cette méthode est cruciale pour l'affichage côté React
        try:
            details = {}
            if self.details_modifications:
                if isinstance(self.details_modifications, str):
                    details = json.loads(self.details_modifications)
                else:
                    details = self.details_modifications

            # Logique pour les Articles
            if self.table_affectee == "Article":
                nom = details.get('nom_article', f"Article #{self.id_entite_affectee}")
                return f"📋 Article : {nom}"

            # Logique pour les Lots
            elif self.table_affectee == "Lot":
                qty = details.get('quantite_lot', 'N/A')
                article_id = details.get('id_article', 'N/A')
                return f"📦 Lot #{self.id_entite_affectee} - Qty: {qty} (Article ID: {article_id})"

            # Logique pour les Emplacements
            elif self.table_affectee == "Emplacement":
                nom = details.get('code_emplacement', f"Emplacement #{self.id_entite_affectee}")
                return f"📍 Emplacement : {nom}"

            # Logique par défaut
            return f"{self.type_action} sur {self.table_affectee} #{self.id_entite_affectee}"

        except Exception as e:
            # En cas d'erreur de parsing JSON
            return f"{self.type_action} {self.table_affectee} (Erreur de détail: {e})"

    class Meta:
        verbose_name = "Historique d'Action"

    def __str__(self):
        return f"{self.type_action} - {self.table_affectee} - {self.date_action}"


class ArticleStock(Article):
    """Modèle proxy pour l'affichage du stock calculé dans l'admin"""

    class Meta:
        proxy = True
        verbose_name = "Stock Calculé"
        verbose_name_plural = "Stocks Calculés"
        app_label = 'gestion_stock'

    def __str__(self):
        return f"Stock - {self.nom_article}"

class AlerteAutomatique(Article):
    """Modèle proxy pour l'affichage des alertes automatiques"""

    class Meta:
        proxy = True
        verbose_name = "Alerte Automatique"
        verbose_name_plural = "Alertes Automatiques"
        app_label = 'gestion_stock'

    def __str__(self):
        return f"Alerte - {self.nom_article}"

    def get_jours_restants(self):
        """Calcule les jours restants avant péremption"""
        if not self.date_peremption:
            return "N/A"

        aujourdhui = date.today()
        jours_restants = (self.date_peremption - aujourdhui).days

        if jours_restants < 0:
            return f"❌ Périmé depuis {abs(jours_restants)} jours"
        elif jours_restants == 0:
            return "⚠️ Expire aujourd'hui"
        elif jours_restants <= 20:
            return f"🔴 {jours_restants} jours"
        elif jours_restants <= 60:
            return f"🟠 {jours_restants} jours"
        else:
            return f"🟡 {jours_restants} jours"

    def get_type_alerte_stock(self):
        """Retourne le type d'alerte stock selon la nouvelle logique"""
        quantite_totale = self.quantite_stock_actuel()

        if quantite_totale <= 0:
            return "🔴 RUPTURE TOTALE"
        elif quantite_totale < self.seuil_securite:  # < au lieu de <=
            return "🔴 CRITIQUE URGENTE"
        else:
            return "🟢 STOCK SUFFISANT"

    def get_priorite_alerte(self):
        """Calcule la priorité de l'alerte selon la nouvelle logique"""
        quantite_totale = self.quantite_stock_actuel()

        # 🔴 URGENT : Stock < Sécurité OU Péremption < 20j
        if quantite_totale < self.seuil_securite:
            return 1  # 🔴 URGENT

        if self.date_peremption:
            jours_restants = (self.date_peremption - date.today()).days
            if jours_restants < 20:
                return 1  # 🔴 URGENT

        # 🟠 MOYEN : Stock ≥ Sécurité ET Péremption 20-60j
        if self.date_peremption:
            jours_restants = (self.date_peremption - date.today()).days
            if 20 <= jours_restants <= 60:
                return 2  # 🟠 MOYEN

        # ✅ NORMAL : Stock ≥ Sécurité ET Péremption > 60j
        return 4  # ✅ NORMAL

    def get_icone_priorite(self):
        """Retourne l'icône de priorité selon la nouvelle logique"""
        priorite = self.get_priorite_alerte()
        if priorite == 1:
            return "🔴"
        elif priorite == 2:
            return "🟠"
        elif priorite == 3:
            return "🟡"
        else:
            return "✅"

    def get_criticite_alerte(self):
        """Retourne le texte de criticité selon la nouvelle logique"""
        priorite = self.get_priorite_alerte()
        if priorite == 1:
            return "🔴 CRITIQUE URGENTE"
        elif priorite == 2:
            return "🟠 MOYENNE"
        elif priorite == 3:
            return "🟡 FAIBLE"
        else:
            return "✅ NORMALE"

    def get_details_alerte(self):
        """Retourne les détails de l'alerte selon la nouvelle logique"""
        quantite_totale = self.quantite_stock_actuel()
        details = []

        # Logique stock
        if quantite_totale <= 0:
            details.append("🔴 Rupture totale de stock")
        elif quantite_totale < self.seuil_securite:  # < au lieu de <=
            details.append("🔴 Stock inférieur au seuil de sécurité")
        else:
            details.append("🟢 Stock suffisant")

        # Logique péremption
        if self.date_peremption:
            jours_restants = (self.date_peremption - date.today()).days
            if jours_restants < 0:
                details.append("❌ Article périmé")
            elif jours_restants <= 20:
                details.append(f"🔴 Péremption dans {jours_restants} jours")
            elif jours_restants <= 60:
                details.append(f"🟠 Péremption dans {jours_restants} jours")
            else:
                details.append(f"🟡 Péremption dans {jours_restants} jours")

        return " | ".join(details)

class Fournisseur(models.Model):
    id_fournisseur = models.AutoField(primary_key=True)
    nom = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    email = models.EmailField()
    telephone = models.CharField(max_length=20)
    adresse = models.TextField()
    ville = models.CharField(max_length=100)
    pays = models.CharField(max_length=100, default='Maroc')
    ice = models.CharField(max_length=20, blank=True, null=True, verbose_name="ICE")
    rib = models.CharField(max_length=50, blank=True, null=True)
    categorie = models.CharField(max_length=50, choices=[
        ('matieres_premieres', 'Matières Premières'),
        ('emballages', 'Emballages'),
        ('equipements', 'Équipements'),
        ('services', 'Services'),
        ('autres', 'Autres')
    ], default='matieres_premieres')
    note = models.IntegerField(default=3, choices=[(1, '★'), (2, '★★'), (3, '★★★'), (4, '★★★★'), (5, '★★★★★')])
    delai_livraison_moyen = models.IntegerField(default=7, help_text="Délai moyen en jours")
    taux_qualite = models.DecimalField(max_digits=5, decimal_places=2, default=95.00, help_text="Taux de qualité (%)")
    est_actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    derniere_commande = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'fournisseur'
        ordering = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.code})"

class CommandeFournisseur(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En Attente'),
        ('confirmee', 'Confirmée'),
        ('en_livraison', 'En Livraison'),
        ('recue', 'Reçue'),
        ('annulee', 'Annulée')
    ]

    id_commande = models.AutoField(primary_key=True)
    fournisseur = models.ForeignKey(Fournisseur, on_delete=models.CASCADE, related_name='commandes')
    date_commande = models.DateField(auto_now_add=True)
    date_livraison_prevue = models.DateField()
    date_livraison_reelle = models.DateField(null=True, blank=True)
    montant_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'commande_fournisseur'

    def __str__(self):
        return f"Commande #{self.id_commande} - {self.fournisseur.nom}"

class Comptage(models.Model):
    id_comptage = models.AutoField(primary_key=True)

    class Meta:
        pass

    def __str__(self):
        return f"Comptage {self.id_comptage}"


