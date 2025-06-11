from dj_rest_auth.registration.serializers import RegisterSerializer
from rest_framework import serializers

class CustomRegisterSerializer(RegisterSerializer):
    username = None  # Disable the username field
    first_name = serializers.CharField(max_length=30, required=True)
    last_name = serializers.CharField(max_length=150, required=True)
    organization_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    organization_invite_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    # def save(self, request):
    #     print("-" * 40)
    #     print("CustomRegisterSerializer save method called")
        
    #     # Access organization_name and organization_invite_id from validated_data
    #     org_name = self.validated_data.get('organization_name')
    #     print(f"Organization Name from serializer: {org_name}")

    #     org_invite_id = self.validated_data.get('organization_invite_id')
    #     print(f"Organization Invite ID from serializer: {org_invite_id}")
        
    #     # Calling the parent save method, which will save the user
    #     user = super().save(request)

    #     # Additional logic to save organization data if necessary
    #     # If you're saving the `organization_name` or `organization_invite_id` to the user model, do it here:
    #     if org_name:
    #         user.organization_name = org_name  # assuming `organization_name` exists on the User model
    #     if org_invite_id:
    #         user.organization_invite_id = org_invite_id  # assuming `organization_invite_id` exists on the User model
        
    #     user.save()

    #     print("-" * 40)
    #     return user


    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data['first_name'] = self.validated_data.get('first_name', '')
        data['last_name'] = self.validated_data.get('last_name', '')
        data['organization_name'] = self.validated_data.get('organization_name')
        data['organization_invite_id'] = self.validated_data.get('organization_invite_id')
        return data


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the custom user model that includes organization details.
    """
    organization_name = serializers.SerializerMethodField()
    role = serializers.CharField(read_only=True)
    
    class Meta:
        from django.contrib.auth import get_user_model
        model = get_user_model()
        fields = ['id', 'email', 'first_name', 'last_name', 'organization_name', 'role']
        read_only_fields = ['id', 'email', 'organization_name', 'role']
    
    def get_organization_name(self, obj):
        if hasattr(obj, 'organization') and obj.organization:
            return obj.organization.name
        return None
