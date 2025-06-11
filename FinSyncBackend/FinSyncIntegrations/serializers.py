from rest_framework import serializers
from .models import Integration

class IntegrationSerializer(serializers.ModelSerializer):
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    status_display = serializers.CharField(source='get_connection_status_display', read_only=True)

    class Meta:
        model = Integration
        fields = [
            'id',
            'organization',
            'provider',
            'provider_display',
            'external_id',
            'name',
            'connection_status',
            'status_display',
            'token_expiry',
            'added_by_user',
            'last_successful_sync',
            'last_sync_error',
            'created_at',
            'updated_at',
            # Do NOT include sensitive fields like access_token_encrypted or refresh_token_encrypted here
        ]
        read_only_fields = ['organization', 'added_by_user', 'token_expiry'] # Fields set by the system 