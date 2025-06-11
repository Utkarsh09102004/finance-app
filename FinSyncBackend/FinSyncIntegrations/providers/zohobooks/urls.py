from django.urls import path
from .views import (
    ZohoBooksInitiateView, 
    ZohoBooksCallbackView,
    ZohoBooksFetchExternalOrganizationsView,
    ZohoBooksSetExternalOrganizationView
)

app_name = 'zohobooks_integration'

urlpatterns = [
    path('initiate/', ZohoBooksInitiateView.as_view(), name='initiate'),
    path('callback/', ZohoBooksCallbackView.as_view(), name='callback'),
    path('<uuid:integration_id>/fetch-external-organizations/', ZohoBooksFetchExternalOrganizationsView.as_view(), name='fetch_external_orgs'),
    path('<uuid:integration_id>/set-external-organization/', ZohoBooksSetExternalOrganizationView.as_view(), name='set_external_org'),
] 