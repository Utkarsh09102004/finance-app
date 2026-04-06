from django.contrib import admin
from .models import (
    Conversation, Message, ToolExecution, ChatSettings, 
    ConversationSummary, UsageTracking
)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'organization', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'organization', 'created_at']
    search_fields = ['title', 'user__email', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user', 'organization']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'role', 'content_preview', 'sequence_number', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['content', 'conversation__title']
    readonly_fields = ['created_at', 'token_count']
    raw_id_fields = ['conversation']
    ordering = ['conversation', 'sequence_number']
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'


@admin.register(ToolExecution)
class ToolExecutionAdmin(admin.ModelAdmin):
    list_display = ['tool_name', 'status', 'execution_time', 'message', 'created_at']
    list_filter = ['status', 'tool_name', 'created_at']
    search_fields = ['tool_name', 'error_message']
    readonly_fields = ['created_at']
    raw_id_fields = ['message']


@admin.register(ChatSettings)
class ChatSettingsAdmin(admin.ModelAdmin):
    list_display = ['organization', 'preferred_model', 'temperature', 'enable_multi_tool_calls', 'created_at']
    list_filter = ['preferred_model', 'enable_multi_tool_calls']
    search_fields = ['organization__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['organization']


@admin.register(ConversationSummary)
class ConversationSummaryAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'summary_preview', 'last_updated']
    search_fields = ['summary_text', 'conversation__title']
    readonly_fields = ['created_at', 'last_updated']
    raw_id_fields = ['conversation']
    
    def summary_preview(self, obj):
        return obj.summary_text[:100] + '...' if len(obj.summary_text) > 100 else obj.summary_text
    summary_preview.short_description = 'Summary'


@admin.register(UsageTracking)
class UsageTrackingAdmin(admin.ModelAdmin):
    list_display = ['organization', 'date', 'messages_sent', 'tool_calls_made', 'tokens_used', 'estimated_cost']
    list_filter = ['date', 'organization']
    search_fields = ['organization__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['organization']
    date_hierarchy = 'date'
