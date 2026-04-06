import uuid
import json
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from FinSyncOrganizations.models import Organization

User = get_user_model()


class Conversation(models.Model):
    """
    Represents a chat conversation between a user and the AI assistant
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.CASCADE, 
        related_name='conversations'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='conversations'
    )
    title = models.CharField(
        max_length=255, 
        blank=True,
        help_text="Auto-generated or user-set conversation title"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this conversation is active or archived"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['organization', 'user', '-updated_at']),
            models.Index(fields=['is_active', '-updated_at']),
        ]

    def __str__(self):
        return f"Conversation {self.title or self.id} - {self.user.email}"

    def save(self, *args, **kwargs):
        # Auto-generate title from first user message if not set
        if not self.title and not self._state.adding:
            first_message = self.messages.filter(role='user').first()
            if first_message:
                # Take first 50 chars of content
                self.title = (first_message.content[:50] + '...') if len(first_message.content) > 50 else first_message.content
        super().save(*args, **kwargs)


class Message(models.Model):
    """
    Individual messages within a conversation
    """
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant' 
        SYSTEM = 'system', 'System'
        TOOL = 'tool', 'Tool'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField(help_text="The message content")
    
    # Tool-related fields
    tool_calls = models.JSONField(
        null=True, 
        blank=True,
        help_text="Tool calls made by the assistant (if role=assistant)"
    )
    tool_call_id = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        help_text="ID of the tool call this message responds to (if role=tool)"
    )
    name = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        help_text="Tool name (if role=tool)"
    )
    visualizations = models.JSONField(
        null=True,
        blank=True,
        help_text="Chart specifications associated with this assistant message"
    )
    sources = models.JSONField(
        null=True,
        blank=True,
        help_text="Tool output sources referenced in this assistant message"
    )
    
    # Message metadata
    sequence_number = models.PositiveIntegerField(
        help_text="Order of message in conversation"
    )
    token_count = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Estimated token count for this message"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sequence_number']
        unique_together = ['conversation', 'sequence_number']
        indexes = [
            models.Index(fields=['conversation', 'sequence_number']),
            models.Index(fields=['role', 'created_at']),
        ]

    def __str__(self):
        return f"Message {self.sequence_number} ({self.role}) - {self.conversation.title}"

    def save(self, *args, **kwargs):
        # Auto-set sequence number if not provided
        if self.sequence_number is None:
            last_message = Message.objects.filter(
                conversation=self.conversation
            ).order_by('-sequence_number').first()
            
            self.sequence_number = (last_message.sequence_number + 1) if last_message else 1
        
        super().save(*args, **kwargs)


class ToolExecution(models.Model):
    """
    Records of tool executions for analytics and debugging
    """
    class Status(models.TextChoices):
        SUCCESS = 'success', 'Success'
        ERROR = 'error', 'Error'
        TIMEOUT = 'timeout', 'Timeout'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        Message, 
        on_delete=models.CASCADE, 
        related_name='tool_executions'
    )
    tool_name = models.CharField(max_length=255)
    arguments = models.JSONField(help_text="Arguments passed to the tool")
    result = models.JSONField(
        null=True, 
        blank=True,
        help_text="Result returned by the tool"
    )
    execution_time = models.FloatField(
        help_text="Time taken to execute the tool in seconds"
    )
    status = models.CharField(max_length=20, choices=Status.choices)
    error_message = models.TextField(
        null=True, 
        blank=True,
        help_text="Error message if execution failed"
    )
    
    # MCP-specific fields
    mcp_server_url = models.URLField(
        null=True, 
        blank=True,
        help_text="URL of the MCP server that handled this tool call"
    )
    integration_id = models.UUIDField(
        null=True, 
        blank=True,
        help_text="ID of the integration used for this tool call"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tool_name', 'status', '-created_at']),
            models.Index(fields=['message', 'created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"Tool {self.tool_name} ({self.status}) - {self.execution_time:.2f}s"


class ConversationSummary(models.Model):
    """
    AI-generated summaries of conversations for quick reference
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.OneToOneField(
        Conversation, 
        on_delete=models.CASCADE, 
        related_name='summary'
    )
    summary_text = models.TextField(
        help_text="AI-generated summary of the conversation"
    )
    key_insights = models.JSONField(
        default=list,
        help_text="List of key insights from the conversation"
    )
    financial_metrics_discussed = models.JSONField(
        default=list,
        help_text="List of financial metrics discussed"
    )
    tools_used = models.JSONField(
        default=list,
        help_text="List of tools used in this conversation"
    )
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-last_updated']

    def __str__(self):
        return f"Summary for {self.conversation.title}"


class ChatSettings(models.Model):
    """
    User/Organization-specific chat settings
    """
    class ModelChoice(models.TextChoices):
        KIMI_K2 = 'openrouter/moonshotai/kimi-k2', 'Kimi K2 (OpenRouter)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(
        Organization, 
        on_delete=models.CASCADE, 
        related_name='chat_settings'
    )
    
    # Model settings
    preferred_model = models.CharField(
        max_length=50, 
        choices=ModelChoice.choices, 
        default=ModelChoice.KIMI_K2
    )
    temperature = models.FloatField(
        default=0.1,
        help_text="Temperature setting for the LLM (0.0-2.0)"
    )
    max_tokens = models.PositiveIntegerField(
        default=4096,
        help_text="Maximum tokens for LLM responses"
    )
    
    # Features
    enable_multi_tool_calls = models.BooleanField(
        default=True,
        help_text="Allow the AI to make multiple tool calls per response"
    )
    auto_generate_summaries = models.BooleanField(
        default=True,
        help_text="Automatically generate conversation summaries"
    )
    
    # Usage limits
    daily_message_limit = models.PositiveIntegerField(
        default=100,
        help_text="Daily message limit per organization"
    )
    daily_tool_call_limit = models.PositiveIntegerField(
        default=500,
        help_text="Daily tool call limit per organization"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Chat Settings"
        verbose_name_plural = "Chat Settings"

    def __str__(self):
        return f"Chat Settings for {self.organization.name}"


class UsageTracking(models.Model):
    """
    Track daily usage for billing and limits
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.CASCADE, 
        related_name='chat_usage'
    )
    date = models.DateField()
    
    # Counters
    messages_sent = models.PositiveIntegerField(default=0)
    tool_calls_made = models.PositiveIntegerField(default=0)
    tokens_used = models.PositiveIntegerField(default=0)
    
    # Cost tracking
    estimated_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        default=0,
        help_text="Estimated cost in USD"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['organization', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['organization', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"Usage {self.organization.name} - {self.date}"
