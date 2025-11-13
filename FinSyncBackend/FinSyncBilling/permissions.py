from rest_framework import permissions
from FinSyncOrganizations.models import Organization


class CanManageBilling(permissions.BasePermission):
    """
    Permission to check if user can manage billing for their organization.
    Only organization owners can manage billing.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        try:
            # Check if user has organization and is the owner
            if hasattr(request.user, 'organization') and request.user.organization:
                return request.user.organization.owner == request.user
            return False
        except Exception:
            return False


class CanViewBilling(permissions.BasePermission):
    """
    Permission to check if user can view billing information.
    All organization members can view billing info.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        try:
            # Check if user has organization attribute and it's not None
            if hasattr(request.user, 'organization') and request.user.organization:
                return True
            return False
        except Exception:
            return False