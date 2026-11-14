from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from core import views
from core import role_views

router = DefaultRouter()
for prefix, view in [('users', views.UserViewSet), ('cars', views.CarViewSet), ('services', views.ServiceViewSet), ('parts', views.PartViewSet), ('orders', views.OrderViewSet), ('stock-movements', views.StockViewSet)]:
    router.register(prefix, view)
router.register('repair-requests', role_views.RepairRequestViewSet)
router.register('part-requests', role_views.PartRequestViewSet)
router.register('audit', role_views.AuditViewSet)
urlpatterns = [path('api/', include(router.urls)), path('api/auth/register/', views.register), path('api/auth/login/', TokenObtainPairView.as_view()), path('api/auth/refresh/', TokenRefreshView.as_view()), path('api/auth/me/', views.me), path('api/auth/change-password/', views.change_password), path('api/reports/<str:report_name>/', views.report), path('api/schema/', SpectacularAPIView.as_view(), name='schema'), path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'))]
urlpatterns += [path('', RedirectView.as_view(url='/api/docs/', permanent=False))]
urlpatterns += [path('api/dashboard/', role_views.dashboard)]
