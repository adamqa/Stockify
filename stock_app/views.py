from rest_framework import status, viewsets, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action  
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from django.db.models import Sum, Count, Avg, Q, F
from datetime import datetime, timedelta, date
from calendar import month_name
from .models import (
    Utilisateur, Article, Lot, Emplacement, Mouvement_Entree,
    Mouvement_Sortie, Mouvement_Sortie_externe, Inventaire,
    Comptage, Depreciation, HistoriqueAction, AlerteAutomatique,
    Fournisseur, CommandeFournisseur, HistoriqueEmplacement
)
from .serializers import (
    UtilisateurSerializer, LoginSerializer, RegisterSerializer,
    ChangePasswordSerializer, ArticleSerializer, LotSerializer,
    EmplacementSerializer, MouvementEntreeSerializer,
    MouvementSortieSerializer, MouvementSortieExterneSerializer,
    InventaireSerializer, ComptageSerializer, DepreciationSerializer,
    HistoriqueActionSerializer, AlerteAutomatiqueSerializer,
    FournisseurSerializer, CommandeFournisseurSerializer,
    HistoriqueEmplacementSerializer
)
from .permissions import IsResponsableMagasin
from .mixins import AuditTrailMixin



class HistoriqueActionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HistoriqueAction.objects.all().order_by('-date_action')
    serializer_class = HistoriqueActionSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques des actions"""
        from datetime import datetime, timedelta
        from django.db.models import Count
        
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        
        stats = {
            'total_actions': HistoriqueAction.objects.count(),
            'actions_semaine': HistoriqueAction.objects.filter(date_action__date__gte=week_ago).count(),
            'par_type': list(HistoriqueAction.objects.values('type_action').annotate(count=Count('id'))),
            'par_table': list(HistoriqueAction.objects.values('table_affectee').annotate(count=Count('id'))),
            'par_utilisateur': list(HistoriqueAction.objects.values('utilisateur').annotate(count=Count('id'))[:10]),
        }
        return Response(stats)

# ========== AUTHENTICATION VIEWS ==========
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['role'] = self.user.role
        data['user_id'] = self.user.id
        data['username'] = self.user.username
        return data

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class LoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            
            # Enregistrer la connexion dans l'historique
            HistoriqueAction.objects.create(
                utilisateur=user.username,
                type_action='LOGIN',
                table_affectee='Utilisateur',
                id_entite_affectee=user.id,
                details_simplifies=f"🔐 Connexion de {user.username}"
            )
            
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UtilisateurSerializer(user).data,
                'role': user.role,
                'message': 'Login successful'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RegisterView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UtilisateurSerializer(user).data,
                'message': 'Registration successful'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            # Enregistrer la déconnexion
            HistoriqueAction.objects.create(
                utilisateur=request.user.username,
                type_action='LOGOUT',
                table_affectee='Utilisateur',
                id_entite_affectee=request.user.id,
                details_simplifies=f"🚪 Déconnexion de {request.user.username}"
            )
            
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'message': 'Logged out successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = UtilisateurSerializer(request.user)
        return Response(serializer.data)
    
    def put(self, request):
        serializer = UtilisateurSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            if not user.check_password(serializer.validated_data['old_password']):
                return Response({'old_password': 'Wrong password'}, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({'message': 'Password changed successfully'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class HomeView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        return Response({
            'message': f'Welcome {user.get_full_name() or user.username}!',
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
            'role_display': user.get_role_display(),
            'permissions': {
                'can_view_stock': True,
                'can_edit_article': user.role == 'Responsable_magasin',
                'can_edit_lot': user.role == 'Responsable_magasin',
                'can_create_movement': user.role in ['Responsable_magasin', 'magasinier'],
                'can_view_reports': user.role in ['Responsable_magasin', 'Responsable_Audit'],
                'can_manage_users': user.role == 'Responsable_magasin',
                'can_validate_inventory': user.role == 'Responsable_Audit',
            }
        })

class UserListView(APIView):
    permission_classes = [IsAuthenticated, IsResponsableMagasin]
    
    def get(self, request):
        users = Utilisateur.objects.all().order_by('-date_joined')
        serializer = UtilisateurSerializer(users, many=True)
        return Response(serializer.data)

class UserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsResponsableMagasin]
    
    def get(self, request, user_id):
        try:
            user = Utilisateur.objects.get(id=user_id)
            serializer = UtilisateurSerializer(user)
            return Response(serializer.data)
        except Utilisateur.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    
    def put(self, request, user_id):
        try:
            user = Utilisateur.objects.get(id=user_id)
            serializer = UtilisateurSerializer(user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Utilisateur.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    
    def delete(self, request, user_id):
        try:
            user = Utilisateur.objects.get(id=user_id)
            user.delete()
            return Response({'message': 'User deleted successfully'}, status=status.HTTP_200_OK)
        except Utilisateur.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

# ========== ARTICLE VIEWS ==========
class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.all().order_by('nom_article')
    serializer_class = ArticleSerializer
    permission_classes = [IsAuthenticated]
    

    def perform_create(self, serializer):
        instance = serializer.save()
        HistoriqueAction.objects.create(
            utilisateur=self.request.user.username,
            type_action='CREATE',
            table_affectee='Article',
            id_entite_affectee=instance.id_article,
            details_simplifies=f"➕ Création de l'article {instance.nom_article}"
        )
    
    def perform_update(self, serializer):
        instance = serializer.save()
        HistoriqueAction.objects.create(
            utilisateur=self.request.user.username,
            type_action='UPDATE',
            table_affectee='Article',
            id_entite_affectee=instance.id_article,
            details_simplifies=f"✏️ Modification de l'article {instance.nom_article}"
        )
    
    def perform_destroy(self, instance):
        HistoriqueAction.objects.create(
            utilisateur=self.request.user.username,
            type_action='DELETE',
            table_affectee='Article',
            id_entite_affectee=instance.id_article,
            details_simplifies=f"🗑️ Suppression de l'article {instance.nom_article}"
        )
        instance.delete()
        
    def get_create_details(self, instance):
        return {
            'nom_article': instance.nom_article,
            'famille': instance.famille,
            'prix_unitaire': str(instance.prix_unitaire)
        }
    
    def get_delete_details(self, instance):
        return {
            'nom_article': instance.nom_article,
            'id_article': instance.id_article
        }

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        articles = []
        for article in Article.objects.all():
            if article.quantite_stock_actuel() <= article.seuil_securite:
                articles.append(article)
        serializer = self.get_serializer(articles, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_famille(self, request):
        famille = request.query_params.get('famille')
        articles = Article.objects.filter(famille=famille)
        serializer = self.get_serializer(articles, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def alerts(self, request):
        alerts = AlerteAutomatique.objects.all()
        serializer = AlerteAutomatiqueSerializer(alerts, many=True)
        return Response(serializer.data)

# ========== LOT VIEWS ==========
class LotViewSet(viewsets.ModelViewSet):
    queryset = Lot.objects.all().order_by('-date_entree')
    serializer_class = LotSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        instance = serializer.save()
        HistoriqueAction.objects.create(
            utilisateur=self.request.user.username,
            type_action='CREATE',
            table_affectee='Lot',
            id_entite_affectee=instance.id_lot,
            details_simplifies=f"➕ Création du lot #{instance.id_lot} - {instance.quantite_lot} unités"
        )
    
    def perform_update(self, serializer):
        instance = serializer.save()
        HistoriqueAction.objects.create(
            utilisateur=self.request.user.username,
            type_action='UPDATE',
            table_affectee='Lot',
            id_entite_affectee=instance.id_lot,
            details_simplifies=f"✏️ Modification du lot #{instance.id_lot}"
        )
    
    def perform_destroy(self, instance):
        HistoriqueAction.objects.create(
            utilisateur=self.request.user.username,
            type_action='DELETE',
            table_affectee='Lot',
            id_entite_affectee=instance.id_lot,
            details_simplifies=f"🗑️ Suppression du lot #{instance.id_lot}"
        )
        instance.delete()

    def get_create_details(self, instance):
        return {
            'article': instance.id_article.nom_article,
            'quantite': instance.quantite_lot,
            'cout_unitaire': str(instance.cout_unitaire)
        }
    
    def get_delete_details(self, instance):
        return {
            'article': instance.id_article.nom_article,
            'quantite': instance.quantite_lot
        }

    
    def get_queryset(self):
        queryset = Lot.objects.all()
        article_id = self.request.query_params.get('article')
        if article_id:
            queryset = queryset.filter(id_article_id=article_id)
        return queryset

# ========== EMPLACEMENT VIEWS ==========
class EmplacementViewSet(viewsets.ModelViewSet):
    queryset = Emplacement.objects.all()
    serializer_class = EmplacementSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        instance = serializer.save()
        HistoriqueAction.objects.create(
            utilisateur=self.request.user.username,
            type_action='CREATE',
            table_affectee='Emplacement',
            id_entite_affectee=instance.id_emplacement,
            details_simplifies=f"➕ Création de l'emplacement Rack {instance.rack}"
        )

    def get_create_details(self, instance):
        return {
            'zone': instance.zone_physique,
            'rack': instance.rack,
            'etagere': instance.etagere
        }

# ========== MOVEMENT VIEWS ==========
class MouvementEntreeViewSet(viewsets.ModelViewSet):
    queryset = Mouvement_Entree.objects.all().order_by('-date_entree')
    serializer_class = MouvementEntreeSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        try:
            instance = serializer.save(id_responsable=self.request.user)
            HistoriqueAction.objects.create(
                utilisateur=self.request.user.username,
                type_action='CREATE',
                table_affectee='Mouvement_Entree',
                id_entite_affectee=instance.id_entree,
                details_simplifies=f"📥 Entrée de stock - Article #{instance.id_article.id_article} - Type: {instance.type_entree}"
            )
        except Exception as e:
            print(f"Erreur dans MouvementEntreeViewSet: {str(e)}")
            raise

class MouvementSortieViewSet(viewsets.ModelViewSet):
    queryset = Mouvement_Sortie.objects.all().order_by('-date_sortie')
    serializer_class = MouvementSortieSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        try:
            quantite_sortie = serializer.validated_data.get('quantite_sortie', 0)
            id_lot = serializer.validated_data.get('id_lot')
            
            if id_lot and quantite_sortie > id_lot.quantite_restante:
                raise serializers.ValidationError({
                    'quantite_sortie': f'Quantité insuffisante. Disponible: {id_lot.quantite_restante}'
                })
            
            instance = serializer.save(id_responsable=self.request.user)
            HistoriqueAction.objects.create(
                utilisateur=self.request.user.username,
                type_action='CREATE',
                table_affectee='Mouvement_Sortie',
                id_entite_affectee=instance.id_sortie,
                details_simplifies=f"📤 Sortie interne - {instance.quantite_sortie} unités - Type: {instance.type_sortie}"
            )
        except Exception as e:
            print(f"Erreur dans MouvementSortieViewSet: {str(e)}")
            raise

class MouvementSortieExterneViewSet(viewsets.ModelViewSet):
    queryset = Mouvement_Sortie_externe.objects.all().order_by('-date_sortie')
    serializer_class = MouvementSortieExterneSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        try:
            quantite_sortie = serializer.validated_data.get('quantite_sortie', 0)
            id_lot = serializer.validated_data.get('id_lot')
            
            if id_lot and quantite_sortie > id_lot.quantite_restante:
                raise serializers.ValidationError({
                    'quantite_sortie': f'Quantité insuffisante. Disponible: {id_lot.quantite_restante}'
                })
            
            instance = serializer.save(id_responsable=self.request.user)
            HistoriqueAction.objects.create(
                utilisateur=self.request.user.username,
                type_action='CREATE',
                table_affectee='Mouvement_Sortie_externe',
                id_entite_affectee=instance.id_sortie_externe,
                details_simplifies=f"💰 Vente/Sortie externe - {instance.quantite_sortie} unités - Type: {instance.type_sortie}"
            )
        except Exception as e:
            print(f"Erreur dans MouvementSortieExterneViewSet: {str(e)}")
            raise

# ========== INVENTORY VIEWS ==========
class InventaireViewSet(viewsets.ModelViewSet):
    queryset = Inventaire.objects.all()
    serializer_class = InventaireSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        try:
            article = serializer.validated_data.get('article')
            quantite_reelle = serializer.validated_data.get('quantite_reelle', 0)
            
            if not article:
                raise serializers.ValidationError({"article": "L'article est requis"})
            
            quantite_theorique = article.quantite_stock_actuel()
            ecart = quantite_reelle - quantite_theorique
            
            instance = serializer.save(
                responsable=self.request.user,
                quantite_theorique=quantite_theorique,
                ecart=ecart
            )
            
            HistoriqueAction.objects.create(
                utilisateur=self.request.user.username,
                type_action='CREATE',
                table_affectee='Inventaire',
                id_entite_affectee=instance.id_inventaire,
                details_simplifies=f"Inventaire - Article: {article.nom_article} - Écart: {ecart}"
            )
        except Exception as e:
            print(f"Erreur dans InventaireViewSet: {str(e)}")
            raise


class ComptageViewSet(viewsets.ModelViewSet):
    queryset = Comptage.objects.all()
    serializer_class = ComptageSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        # Récupérer ou créer un inventaire pour ce comptage
        today = date.today()
        inventory, created = Inventaire.objects.get_or_create(
            date_inventaire=today,
            type_inventaire='tournant',
            statut_inventaire='en_cours',
            defaults={
                'id_responsable': self.request.user,
                'documents_reglementaires': f"INV_{today.strftime('%Y%m%d')}"
            }
        )
        
        # Ajouter l'article à l'inventaire si pas déjà présent
        if not inventory.articles_a_inventorier.filter(id_article=serializer.validated_data['id_article'].id_article).exists():
            inventory.articles_a_inventorier.add(serializer.validated_data['id_article'])
        
        serializer.save(id_inventaire=inventory)

# ========== DEPRECIATION VIEWS ==========
class DepreciationViewSet(viewsets.ModelViewSet):
    queryset = Depreciation.objects.all().order_by('-date_depreciation')
    serializer_class = DepreciationSerializer
    permission_classes = [IsAuthenticated]

# ========== DASHBOARD STATISTICS VIEWS ==========
class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]
    
     def get(self, request):
        total_articles = Article.objects.count()
        low_stock = 0
        total_value = 0
        
        for article in Article.objects.all():
            qty = article.quantite_stock_actuel()
            if qty <= article.seuil_securite:
                low_stock += 1
            total_value += article.valeur_stock_actuel()
        
        today = datetime.now()
        month_start = today.replace(day=1)
        
        monthly_internal = Mouvement_Sortie.objects.filter(
            date_sortie__gte=month_start
        ).aggregate(total=Sum('quantite_sortie'))['total'] or 0
        
        monthly_external = Mouvement_Sortie_externe.objects.filter(
            date_sortie__gte=month_start
        ).aggregate(total=Sum('quantite_sortie'))['total'] or 0
        
        print(f"DEBUG - Total stock value: {total_value}")  # Debug
        print(f"DEBUG - Monthly internal: {monthly_internal}")  # Debug
        print(f"DEBUG - Monthly external: {monthly_external}")  # Debug
        
        return Response({
            'total_articles': total_articles,
            'low_stock_articles': low_stock,
            'total_stock_value': float(total_value),
            'monthly_movements': monthly_internal + monthly_external,
            'monthly_internal': monthly_internal,
            'monthly_external': monthly_external
        })
    
class TopArticlesView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        articles = []
        for article in Article.objects.all():
            articles.append({
                'id': article.id_article,
                'name': article.nom_article,
                'value': float(article.valeur_stock_actuel()),
                'quantity': article.quantite_stock_actuel(),
                'famille': article.famille
            })
        articles.sort(key=lambda x: x['value'], reverse=True)
        return Response(articles[:10])

class RecentMovementsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        internal = Mouvement_Sortie.objects.all().order_by('-date_sortie')[:5]
        external = Mouvement_Sortie_externe.objects.all().order_by('-date_sortie')[:5]
        
        internal_serializer = MouvementSortieSerializer(internal, many=True)
        external_serializer = MouvementSortieExterneSerializer(external, many=True)
        
        return Response({
            'internal': internal_serializer.data,
            'external': external_serializer.data
        })

class HistoriqueActionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HistoriqueAction.objects.all().order_by('-date_action')
    serializer_class = HistoriqueActionSerializer
    permission_classes = [IsAuthenticated]


class ChartDataView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get last 12 months of data
        today = datetime.now()
        months_data = []
        
        for i in range(11, -1, -1):
            month_date = today - timedelta(days=30*i)
            month_start = month_date.replace(day=1)
            
            # Calculate next month start
            if month_date.month == 12:
                month_end = month_date.replace(year=month_date.year + 1, month=1, day=1)
            else:
                month_end = month_date.replace(month=month_date.month + 1, day=1)
            
            # Get entrees for this month
            entrees = Mouvement_Entree.objects.filter(
                date_entree__gte=month_start,
                date_entree__lt=month_end
            ).aggregate(total=Sum('id_lot__quantite_lot'))['total'] or 0
            
            # Get sorties for this month
            sorties = Mouvement_Sortie.objects.filter(
                date_sortie__gte=month_start,
                date_sortie__lt=month_end
            ).aggregate(total=Sum('quantite_sortie'))['total'] or 0
            
            months_data.append({
                'month': month_name[month_date.month][:3],
                'entrees': float(entrees),
                'sorties': float(sorties)
            })
        
        return Response(months_data)

class StockValueTrendView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get stock value trend for last 6 months
        today = datetime.now()
        trend_data = []
        
        for i in range(5, -1, -1):
            month_date = today - timedelta(days=30*i)
            month_start = month_date.replace(day=1)
            
            # Calculate stock value at end of month (simplified)
            # For real implementation, you'd need historical stock values
            total_value = 0
            for article in Article.objects.all():
                total_value += article.valeur_stock_actuel()
            
            trend_data.append({
                'month': month_name[month_date.month][:3],
                'value': float(total_value)
            })
        
        return Response(trend_data)

class StorageCapacityView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get storage capacity by zone
        zones = ['préparation', 'stockage', 'retours']
        capacity_data = []
        
        for zone in zones:
            emplacements = Emplacement.objects.filter(zone_physique=zone)
            total_capacity = emplacements.aggregate(total=Sum('capacite_max'))['total'] or 0
            used_capacity = emplacements.aggregate(used=Sum('capacite_actuelle'))['used'] or 0
            
            capacity_data.append({
                'zone': zone,
                'used': used_capacity,
                'available': total_capacity - used_capacity,
                'total': total_capacity
            })
        
        return Response(capacity_data)

class TopArticlesByMovementView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get top 5 articles by number of movements
        from django.db.models import Count, Q
        
        top_articles = Article.objects.annotate(
            movement_count=Count('mouvement_sortie') + Count('mouvement_sortie_externe')
        ).order_by('-movement_count')[:5]
        
        data = []
        for article in top_articles:
            data.append({
                'name': article.nom_article,
                'count': article.movement_count,
                'famille': article.famille
            })
        
        return Response(data)

class RecentActivityView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get recent activities for the dashboard
        recent_entrees = Mouvement_Entree.objects.all().order_by('-date_entree')[:5]
        recent_sorties = Mouvement_Sortie.objects.all().order_by('-date_sortie')[:5]
        
        entrees_data = []
        for entree in recent_entrees:
            entrees_data.append({
                'id': entree.id_entree,
                'article': entree.id_article.nom_article,
                'date': entree.date_entree.strftime('%Y-%m-%d'),
                'type': entree.type_entree
            })
        
        sorties_data = []
        for sortie in recent_sorties:
            sorties_data.append({
                'id': sortie.id_sortie,
                'article': sortie.id_article.nom_article,
                'date': sortie.date_sortie.strftime('%Y-%m-%d'),
                'quantity': sortie.quantite_sortie,
                'type': sortie.type_sortie
            })
        
        return Response({
            'entrees': entrees_data,
            'sorties': sorties_data
        })

class StockValueHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get stock value for each month of the current year
        from datetime import datetime, timedelta
        today = datetime.now()
        months_data = []
        
        for i in range(11, -1, -1):
            date = today - timedelta(days=30*i)
            month_name = date.strftime('%b')
            
            # Calculate stock value at that time (you'd need historical data)
            # For now, use current value with variation
            total_value = sum(a.valeur_stock_actuel() for a in Article.objects.all())
            
            months_data.append({
                'month': month_name,
                'valeur': float(total_value),
                'croissance': 0
            })
        
        return Response(months_data)

class MonthlyMovementsStatsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from datetime import datetime
        months = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
        
        entrees_by_month = [0] * 12
        sorties_by_month = [0] * 12
        
        # Count entrees by month
        for entry in Mouvement_Entree.objects.all():
            if entry.date_entree:
                month = entry.date_entree.month - 1
                entrees_by_month[month] += entry.id_lot.quantite_lot if entry.id_lot else 0
        
        # Count sorties by month
        for sortie in Mouvement_Sortie.objects.all():
            if sortie.date_sortie:
                month = sortie.date_sortie.month - 1
                sorties_by_month[month] += sortie.quantite_sortie
        
        return Response({
            'months': months,
            'entrees': entrees_by_month,
            'sorties': sorties_by_month
        })

from django.db.models import Sum

class FournisseurViewSet(viewsets.ModelViewSet):
    queryset = Fournisseur.objects.all()
    serializer_class = FournisseurSerializer
    permission_classes = [IsAuthenticated]
    
    def get_create_details(self, instance):
        return {
            'nom': instance.nom,
            'code': instance.code,
            'categorie': instance.categorie
        }

    @action(detail=False, methods=['get'])
    def stats(self, request):
        total = Fournisseur.objects.count()
        actifs = Fournisseur.objects.filter(est_actif=True).count()
        by_categorie = list(Fournisseur.objects.values('categorie').annotate(count=Count('id_fournisseur')))
        avg_qualite = Fournisseur.objects.aggregate(avg=Avg('taux_qualite'))['avg'] or 0
        avg_delai = Fournisseur.objects.aggregate(avg=Avg('delai_livraison_moyen'))['avg'] or 0
        return Response({
            'total': total,
            'actifs': actifs,
            'inactifs': total - actifs,
            'by_categorie': by_categorie,
            'avg_qualite': float(avg_qualite),
            'avg_delai': float(avg_delai)
        })
    
    @action(detail=False, methods=['get'])
    def spending_stats(self, request):
        """Get spending statistics per supplier"""
        spending_data = []
        for fournisseur in Fournisseur.objects.filter(est_actif=True):
            total_spent = CommandeFournisseur.objects.filter(
                fournisseur=fournisseur,
                statut='recue'
            ).aggregate(total=Sum('montant_total'))['total'] or 0
            
            spending_data.append({
                'id_fournisseur': fournisseur.id_fournisseur,
                'nom': fournisseur.nom,
                'depenses': float(total_spent),
                'commandes': CommandeFournisseur.objects.filter(fournisseur=fournisseur).count()
            })
        
        # Sort by spending descending
        spending_data.sort(key=lambda x: x['depenses'], reverse=True)
        
        return Response(spending_data)
        
class CommandeFournisseurViewSet(viewsets.ModelViewSet):
    queryset = CommandeFournisseur.objects.all()
    serializer_class = CommandeFournisseurSerializer
    permission_classes = [IsAuthenticated]
    
    def get_create_details(self, instance):
        return {
            'fournisseur': instance.fournisseur.nom,
            'montant': str(instance.montant_total),
            'statut': instance.statut
        }

    @action(detail=False, methods=['get'])
    def by_fournisseur(self, request):
        fournisseur_id = request.query_params.get('fournisseur_id')
        if fournisseur_id:
            commandes = CommandeFournisseur.objects.filter(fournisseur_id=fournisseur_id)
        else:
            commandes = CommandeFournisseur.objects.all()
        serializer = self.get_serializer(commandes, many=True)
        return Response(serializer.data)

class HistoriqueActionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HistoriqueAction.objects.all().order_by('-date_action')
    serializer_class = HistoriqueActionSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def par_utilisateur(self, request):
        utilisateur = request.query_params.get('utilisateur')
        if utilisateur:
            logs = HistoriqueAction.objects.filter(utilisateur=utilisateur)
            serializer = self.get_serializer(logs, many=True)
            return Response(serializer.data)
        return Response([])
    
    @action(detail=False, methods=['get'])
    def par_table(self, request):
        table = request.query_params.get('table')
        if table:
            logs = HistoriqueAction.objects.filter(table_affectee=table)
            serializer = self.get_serializer(logs, many=True)
            return Response(serializer.data)
        return Response([])
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques des actions"""
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        
        stats = {
            'total_actions': HistoriqueAction.objects.count(),
            'actions_semaine': HistoriqueAction.objects.filter(date_action__date__gte=week_ago).count(),
            'par_type': list(HistoriqueAction.objects.values('type_action').annotate(count=Count('id'))),
            'par_table': list(HistoriqueAction.objects.values('table_affectee').annotate(count=Count('id'))),
            'par_utilisateur': list(HistoriqueAction.objects.values('utilisateur').annotate(count=Count('id'))[:10]),
        }
        return Response(stats)

class HistoriqueEmplacementViewSet(viewsets.ModelViewSet):
    queryset = HistoriqueEmplacement.objects.all()
    serializer_class = HistoriqueEmplacementSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def par_article(self, request):
        article_id = request.query_params.get('article_id')
        if article_id:
            historique = HistoriqueEmplacement.objects.filter(article_id=article_id)
            serializer = self.get_serializer(historique, many=True)
            return Response(serializer.data)
        return Response([])


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = UtilisateurSerializer(request.user)
        return Response(serializer.data)

