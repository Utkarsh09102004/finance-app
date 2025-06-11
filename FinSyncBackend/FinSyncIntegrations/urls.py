from django.urls import path, include
# Import the new common views
from .common_views import CommonIntegrationListView, CommonIntegrationDetailView

app_name = 'integrations'

urlpatterns = [
    # Provider-specific integration flows
    path('zohobooks/', include('FinSyncIntegrations.providers.zohobooks.urls', namespace='zohobooks')),
    # path('quickbooks/', include('FinSyncIntegrations.providers.quickbooks.urls', namespace='quickbooks')), # Example for future

    # Common integration management APIs
    path('', CommonIntegrationListView.as_view(), name='list-integrations'),
    path('<uuid:id>/', CommonIntegrationDetailView.as_view(), name='detail-integration'),

] 