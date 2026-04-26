from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import (
    Utilisateur, Article, Lot, Emplacement, Mouvement_Entree,
    Mouvement_Sortie, Mouvement_Sortie_externe, Inventaire,
    Comptage, Depreciation, Historique_Classification_ABC,
    HistoriqueAction, AlerteAutomatique,Fournisseur, CommandeFournisseur
)

class UtilisateurSerializer(serializers.ModelSerializer):
    """Serializer for user data"""
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = Utilisateur
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'role', 'role_display', 'telephone', 'is_active',
                  'date_joined', 'last_login']
        read_only_fields = ['id', 'date_joined', 'last_login']

class LoginSerializer(serializers.Serializer):
    """Serializer for login"""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data.get('username')
        password = data.get('password')

        if username and password:
            user = authenticate(username=username, password=password)

            if not user:
                raise serializers.ValidationError('Invalid username or password')

            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
        else:
            raise serializers.ValidationError('Must provide username and password')

        data['user'] = user
        return data

class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = Utilisateur
        fields = ['id', 'username', 'email', 'password', 'password_confirm',
                  'first_name', 'last_name', 'role', 'telephone']

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return data

    def validate_role(self, value):
        """Restrict role assignment during registration"""
        allowed_roles = ['magasinier']
        if value not in allowed_roles:
            raise serializers.ValidationError(f"Invalid role. Allowed roles: {allowed_roles}")
        return value

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')

        user = Utilisateur.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=password,
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=validated_data.get('role', 'magasinier'),
            telephone=validated_data.get('telephone', '')
        )
        return user

class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change"""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=6)
    confirm_password = serializers.CharField(required=True, min_length=6)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match"})
        return data

class ArticleSerializer(serializers.ModelSerializer):
    quantite_stock = serializers.SerializerMethodField()
    valeur_stock = serializers.SerializerMethodField()
    statut_stock = serializers.SerializerMethodField()
    consommation_annuelle_quantite = serializers.SerializerMethodField()
    consommation_annuelle_valeur = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = '__all__'

    def get_quantite_stock(self, obj):
        return obj.quantite_stock_actuel()

    def get_valeur_stock(self, obj):
        return obj.valeur_stock_actuel()

    def get_statut_stock(self, obj):
        return obj.get_statut_stock()

    def get_consommation_annuelle_quantite(self, obj):
        return obj.get_consommation_annuelle_quantite()

    def get_consommation_annuelle_valeur(self, obj):
        return obj.get_consommation_annuelle_valeur()

# ========== LOT SERIALIZERS ==========
class LotSerializer(serializers.ModelSerializer):
    article_nom = serializers.CharField(source='id_article.nom_article', read_only=True)
    article_famille = serializers.CharField(source='id_article.famille', read_only=True)
    capacite_correspondante = serializers.SerializerMethodField()

    class Meta:
        model = Lot
        fields = '__all__'

    def get_capacite_correspondante(self, obj):
        return obj.get_capacite_correspondante()

# ========== EMPLACEMENT SERIALIZERS ==========
class EmplacementSerializer(serializers.ModelSerializer):
    article_nom = serializers.CharField(source='id_article.nom_article', read_only=True, allow_null=True)
    pourcentage_occupation = serializers.SerializerMethodField()

    class Meta:
        model = Emplacement
        fields = '__all__'  # This will include latitude and longitude automatically

    def get_pourcentage_occupation(self, obj):
        return obj.pourcentage_occupation()

# ========== MOVEMENT SERIALIZERS ==========
class MouvementEntreeSerializer(serializers.ModelSerializer):
    article_nom = serializers.CharField(source='id_article.nom_article', read_only=True)
    lot_info = serializers.CharField(source='id_lot.id_lot', read_only=True)

    class Meta:
        model = Mouvement_Entree
        fields = '__all__'

class MouvementSortieSerializer(serializers.ModelSerializer):
    article_nom = serializers.CharField(source='id_article.nom_article', read_only=True)
    lot_info = serializers.CharField(source='id_lot.id_lot', read_only=True)
    type_sortie_display = serializers.CharField(source='get_type_sortie_display', read_only=True)

    class Meta:
        model = Mouvement_Sortie
        fields = '__all__'

class MouvementSortieExterneSerializer(serializers.ModelSerializer):
    article_nom = serializers.CharField(source='id_article.nom_article', read_only=True)
    lot_info = serializers.CharField(source='id_lot.id_lot', read_only=True)

    class Meta:
        model = Mouvement_Sortie_externe
        fields = '__all__'

# ========== INVENTORY SERIALIZERS ==========
class InventaireSerializer(serializers.ModelSerializer):
    article_nom = serializers.CharField(source='article.nom_article', read_only=True)
    article_famille = serializers.CharField(source='article.famille', read_only=True)
    unite_mesure = serializers.CharField(source='article.unite_mesure', read_only=True)
    responsable_nom = serializers.CharField(source='responsable.username', read_only=True)

    # Accepte l'ID du responsable directement
    responsable = serializers.PrimaryKeyRelatedField(
        queryset=Utilisateur.objects.all(),
        required=False,
        write_only=True
    )

    class Meta:
        model = Inventaire
        fields = '__all__'
        read_only_fields = ['id_inventaire', 'ecart', 'date_inventaire', 'quantite_theorique']


class ComptageSerializer(serializers.ModelSerializer):
    article_nom = serializers.CharField(source='id_article.nom_article', read_only=True)
    quantite_theorique = serializers.SerializerMethodField()
    pourcentage_ecart = serializers.SerializerMethodField()
    statut_ecart = serializers.SerializerMethodField()

    class Meta:
        model = Comptage
        fields = '__all__'

    def get_quantite_theorique(self, obj):
        return obj.get_quantite_theorique()

    def get_pourcentage_ecart(self, obj):
        return obj.get_pourcentage_ecart()

    def get_statut_ecart(self, obj):
        return obj.get_statut_ecart()

# ========== DEPRECIATION SERIALIZERS ==========
class DepreciationSerializer(serializers.ModelSerializer):
    article_nom = serializers.CharField(source='id_article.nom_article', read_only=True)

    class Meta:
        model = Depreciation
        fields = '__all__'

# ========== ALERT SERIALIZERS ==========
class AlerteAutomatiqueSerializer(serializers.ModelSerializer):
    quantite_stock = serializers.SerializerMethodField()
    jours_restants = serializers.SerializerMethodField()
    type_alerte_stock = serializers.SerializerMethodField()
    priorite_alerte = serializers.SerializerMethodField()
    icone_priorite = serializers.SerializerMethodField()
    criticite_alerte = serializers.SerializerMethodField()
    details_alerte = serializers.SerializerMethodField()

    class Meta:
        model = AlerteAutomatique
        fields = ['id_article', 'nom_article', 'famille', 'seuil_securite',
                  'date_peremption', 'quantite_stock', 'jours_restants',
                  'type_alerte_stock', 'priorite_alerte', 'icone_priorite',
                  'criticite_alerte', 'details_alerte']

    def get_quantite_stock(self, obj):
        return obj.quantite_stock_actuel()

    def get_jours_restants(self, obj):
        return obj.get_jours_restants()

    def get_type_alerte_stock(self, obj):
        return obj.get_type_alerte_stock()

    def get_priorite_alerte(self, obj):
        return obj.get_priorite_alerte()

    def get_icone_priorite(self, obj):
        return obj.get_icone_priorite()

    def get_criticite_alerte(self, obj):
        return obj.get_criticite_alerte()

    def get_details_alerte(self, obj):
        return obj.get_details_alerte()

# ========== HISTORY SERIALIZERS ==========
class HistoriqueActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoriqueAction
        fields = '__all__'

class HistoriqueClassificationABCSerializer(serializers.ModelSerializer):
    article_nom = serializers.CharField(source='id_article.nom_article', read_only=True)

    class Meta:
        model = Historique_Classification_ABC
        fields = '__all__'

class FournisseurSerializer(serializers.ModelSerializer):
    categorie_display = serializers.CharField(source='get_categorie_display', read_only=True)

    class Meta:
        model = Fournisseur
        fields = '__all__'

class CommandeFournisseurSerializer(serializers.ModelSerializer):
    fournisseur_nom = serializers.CharField(source='fournisseur.nom', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)

    class Meta:
        model = CommandeFournisseur
        fields = '__all__'