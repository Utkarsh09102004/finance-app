from django.contrib import admin
from django.urls import path, include
from FinSyncAuth.views import CustomConfirmEmailView, UserListAPIView
from dj_rest_auth.views import PasswordResetConfirmView

urlpatterns = [
    path('registration/account-confirm-email/<key>/', CustomConfirmEmailView.as_view(), name='account_confirm_email'),
    path('registration/', include('dj_rest_auth.registration.urls')),
    path('password/reset/confirm/<uidb64>/<token>/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),

    # Authentication (Login, Logout, Password Reset, User Details)
    path('', include('dj_rest_auth.urls')),
    
    # Users
    path('users/', UserListAPIView.as_view(), name='user-list'),

    # Registration (Email Signup)
    

 
    # path('accounts/', include('allauth.urls')),

]