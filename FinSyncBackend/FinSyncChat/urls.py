from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for ViewSets
router = DefaultRouter()
router.register(r'conversations', views.ConversationViewSet, basename='conversation')
router.register(r'settings', views.ChatSettingsViewSet, basename='chat-settings')

urlpatterns = [
    # Chat functionality
    path('send-message/', views.send_message, name='send-message'),
    path('send-message/stream/', views.send_message_stream, name='send-message-stream'),
    path('conversations/list/', views.list_conversations, name='list-conversations'),
    path('conversations/<uuid:conversation_id>/detail/', views.conversation_detail, name='conversation-detail'),
    path('conversations/<uuid:conversation_id>/clear/', views.clear_conversation, name='clear-conversation'),
    
    # MCP and system status
    path('mcp/status/', views.mcp_status, name='mcp-status'),
    path('usage/stats/', views.usage_stats, name='usage-stats'),
    path('models/', views.available_models, name='available-models'),

    # Include router URLs last so custom paths take precedence
    path('', include(router.urls)),
]
