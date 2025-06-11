from django.shortcuts import render
from allauth.account.views import ConfirmEmailView
from django.http import HttpResponseRedirect
from rest_framework import generics, permissions
from rest_framework.filters import SearchFilter
from django.db.models import Q

from .models import CustomUser
from .serializers import UserSerializer

# Create your views here.
from django.conf import settings
from django.shortcuts import redirect

class CustomConfirmEmailView(ConfirmEmailView):
    def get(self, request, *args, **kwargs):
        confirmation = self.get_object()
        confirmation.confirm(request)
        # Redirect to base URL
        return redirect('/')

    def post(self, request, *args, **kwargs):
        confirmation = self.get_object()
        confirmation.confirm(request)
        # Redirect to base URL
        return redirect('/')

    def dispatch(self, request, *args, **kwargs):
        confirmation = self.get_object()
        confirmation.confirm(request)
        # Redirect to base URL
        return redirect('/')

class UserListAPIView(generics.ListAPIView):
    """
    API endpoint that returns users in the same organization as the requesting user.
    Can be filtered by organization ID if provided in the query params.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ['email', 'first_name', 'last_name']
    
    def get_queryset(self):
        user = self.request.user
        queryset = CustomUser.objects.filter(is_active=True)
        
        # Check if organization filter is provided
        organization_id = self.request.query_params.get('organization')
        
        if organization_id:
            # Filter users by the specified organization
            queryset = queryset.filter(organization_id=organization_id)
        else:
            # If no organization specified, return users from the same organization as the requesting user
            queryset = queryset.filter(organization_id=user.organization_id)
            
        return queryset.order_by('email')



