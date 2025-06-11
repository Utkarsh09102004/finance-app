from rest_framework.generics import ListAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from .models import Integration
from .serializers import IntegrationSerializer
import logging

logger = logging.getLogger(__name__)

class CommonIntegrationListView(ListAPIView):
    """
    Provides a list of all integrations for the authenticated user's organization.
    """
    serializer_class = IntegrationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Ensure the user has an organization linked.
        # The IsAuthenticated permission already ensures request.user exists.
        if not hasattr(self.request.user, 'organization') or not self.request.user.organization:
            logger.warning(f"User {self.request.user.email} attempted to list integrations but has no organization.")
            return Integration.objects.none() # Return an empty queryset
        
        queryset = Integration.objects.filter(organization=self.request.user.organization)
        logger.info(f"User {self.request.user.email} from org {self.request.user.organization.name} listing integrations. Found: {queryset.count()}")
        return queryset

class CommonIntegrationDetailView(RetrieveUpdateDestroyAPIView):
    """
    Provides retrieve, update (partial), and delete for a specific integration
    belonging to the authenticated user's organization.
    Note: Direct updates to integrations might be limited; most changes happen via OAuth flows.
    This view is more for potential name changes or manual disconnections.
    """
    serializer_class = IntegrationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id' # Assuming 'id' is the UUID primary key

    def get_queryset(self):
        if not hasattr(self.request.user, 'organization') or not self.request.user.organization:
            logger.warning(f"User {self.request.user.email} attempted to access integration detail but has no organization.")
            return Integration.objects.none()
        return Integration.objects.filter(organization=self.request.user.organization)

    def perform_destroy(self, instance):
        # Add any specific logic needed on deletion, e.g., trying to revoke tokens with the provider.
        # For now, just log and delete.
        logger.info(
            f"User {self.request.user.email} from org {instance.organization.name} is deleting integration ID: {instance.id}, Provider: {instance.provider}"
        )
        # Example: Potentially call a method on the instance if it exists
        # if hasattr(instance, 'cleanup_on_delete'):
        #     instance.cleanup_on_delete()
        instance.delete() 