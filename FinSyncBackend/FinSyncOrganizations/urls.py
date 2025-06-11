from django.urls import path
from .views import (
    OrganizationInviteListCreateAPIView,
    OrganizationInviteAcceptAPIView,
    LeaveOrganizationAPIView,
    OrganizationChangeOwnerAPIView,
    OrganizationRemoveMemberAPIView,
    CreateOrganizationAPIView,
    MyOrganizationDetailView
)

app_name = 'FinSyncOrganizations'

urlpatterns = [
    path(
        'create/',
        CreateOrganizationAPIView.as_view(),
        name='organization-create-list'
    ),
    path(
        'my-organization/',
        MyOrganizationDetailView.as_view(),
        name='my-organization-detail'
    ),
    path(
        '<int:organization_id>/invites/',
        OrganizationInviteListCreateAPIView.as_view(),
        name='organization-invite-list-create'
    ),
    path(
        'invites/accept/',
        OrganizationInviteAcceptAPIView.as_view(),
        name='organization-invite-accept'
    ),
    path(
        'leave/',
        LeaveOrganizationAPIView.as_view(),
        name='organization-leave'
    ),
    path(
        '<int:organization_id>/change-owner/',
        OrganizationChangeOwnerAPIView.as_view(),
        name='organization-change-owner'
    ),
    path(
        '<int:organization_id>/members/<int:user_id_to_remove>/remove/',
        OrganizationRemoveMemberAPIView.as_view(),
        name='organization-remove-member'
    ),
] 