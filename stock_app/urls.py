from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    # Auth views
    LoginView, RegisterView, LogoutView, UserProfileView,
    ChangePasswordView, HomeView, UserListView, UserDetailView,
    CustomTokenObtainPairView,
    # Model ViewSets
    ArticleViewSet, LotViewSet, EmplacementViewSet,
    MouvementEntreeViewSet, MouvementSortieViewSet,
    MouvementSortieExterneViewSet, InventaireViewSet,
    ComptageViewSet, DepreciationViewSet, HistoriqueActionViewSet,
    # Dashboard views
    DashboardStatsView, TopArticlesView, RecentMovementsView,
    ChartDataView, StockValueTrendView, StorageCapacityView,
    TopArticlesByMovementView, RecentActivityView,
    FournisseurViewSet, CommandeFournisseurViewSet,
    HistoriqueEmplacementViewSet
)

router = DefaultRouter()
router.register('articles', ArticleViewSet)
router.register('lots', LotViewSet)
router.register('emplacements', EmplacementViewSet)
router.register('entrees', MouvementEntreeViewSet)
router.register('sorties', MouvementSortieViewSet)
router.register('sorties-externes', MouvementSortieExterneViewSet)
router.register('comptages', ComptageViewSet)
router.register('inventaires', InventaireViewSet)
router.register('depreciations', DepreciationViewSet)
router.register('historique', HistoriqueActionViewSet)
router.register('fournisseurs', FournisseurViewSet)
router.register('commandes-fournisseur', CommandeFournisseurViewSet)
router.register('historique-emplacements', HistoriqueEmplacementViewSet)

urlpatterns = [
    # Authentication
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/profile/', UserProfileView.as_view(), name='profile'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change_password'),
    
    # User management
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/<int:user_id>/', UserDetailView.as_view(), name='user_detail'),
    
    # Home/Dashboard
    path('home/', HomeView.as_view(), name='home'),
    
    # Dashboard statistics
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard_stats'),
    path('dashboard/top-articles/', TopArticlesView.as_view(), name='top_articles'),
    path('dashboard/recent-movements/', RecentMovementsView.as_view(), name='recent_movements'),

    path('charts/monthly-movements/', ChartDataView.as_view(), name='monthly_movements'),
    path('charts/stock-trend/', StockValueTrendView.as_view(), name='stock_trend'),
    path('charts/storage-capacity/', StorageCapacityView.as_view(), name='storage_capacity'),
    path('charts/top-articles/', TopArticlesByMovementView.as_view(), name='top_articles_movements'),
    path('charts/recent-activity/', RecentActivityView.as_view(), name='recent_activity'),

    # API routes
    path('', include(router.urls)),

]