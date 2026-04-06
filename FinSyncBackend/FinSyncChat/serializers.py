from rest_framework import serializers
from .models import Conversation, Message, ToolExecution, ChatSettings, ConversationSummary


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for chat messages"""
    
    class Meta:
        model = Message
        fields = [
            'id', 'role', 'content', 'tool_calls', 'tool_call_id', 
            'name', 'sequence_number', 'token_count', 'created_at', 'visualizations', 'sources'
        ]
        read_only_fields = ['id', 'sequence_number', 'token_count', 'created_at']


class ToolExecutionSerializer(serializers.ModelSerializer):
    """Serializer for tool execution records"""
    
    class Meta:
        model = ToolExecution
        fields = [
            'id', 'tool_name', 'arguments', 'result', 'execution_time',
            'status', 'error_message', 'mcp_server_url', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ConversationSummarySerializer(serializers.ModelSerializer):
    """Serializer for conversation summaries"""
    
    class Meta:
        model = ConversationSummary
        fields = [
            'id', 'summary_text', 'key_insights', 'financial_metrics_discussed',
            'tools_used', 'last_updated', 'created_at'
        ]
        read_only_fields = ['id', 'last_updated', 'created_at']


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer for conversations"""
    
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    summary = ConversationSummarySerializer(read_only=True)
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'title', 'is_active', 'created_at', 'updated_at',
            'message_count', 'last_message', 'summary'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_message_count(self, obj):
        return obj.messages.count()
    
    def get_last_message(self, obj):
        last_msg = obj.messages.filter(role__in=['user', 'assistant']).last()
        if last_msg:
            return {
                'content': last_msg.content[:100] + '...' if len(last_msg.content) > 100 else last_msg.content,
                'role': last_msg.role,
                'created_at': last_msg.created_at
            }
        return None


class ConversationDetailSerializer(ConversationSerializer):
    """Detailed serializer for conversations with messages"""
    
    messages = serializers.SerializerMethodField()
    
    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ['messages']

    def get_messages(self, obj):
        qs = obj.messages.filter(role__in=['user', 'assistant']).order_by('sequence_number')
        return MessageSerializer(qs, many=True).data


class ChatSettingsSerializer(serializers.ModelSerializer):
    """Serializer for chat settings"""
    
    class Meta:
        model = ChatSettings
        fields = [
            'id', 'preferred_model', 'temperature', 'max_tokens',
            'enable_multi_tool_calls', 'auto_generate_summaries',
            'daily_message_limit', 'daily_tool_call_limit',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'preferred_model']
    
    def validate_temperature(self, value):
        if not 0.0 <= value <= 2.0:
            raise serializers.ValidationError("Temperature must be between 0.0 and 2.0")
        return value
    
    def validate_max_tokens(self, value):
        if not 100 <= value <= 32000:
            raise serializers.ValidationError("Max tokens must be between 100 and 32000")
        return value


class SendMessageSerializer(serializers.Serializer):
    """Serializer for sending chat messages"""
    
    message = serializers.CharField(min_length=1, max_length=10000)
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    title = serializers.CharField(max_length=255, required=False, allow_null=True)
    
    def validate_message(self, value):
        # Basic validation for message content
        if len(value.strip()) == 0:
            raise serializers.ValidationError("Message cannot be empty")
        return value.strip()


class ChatResponseSerializer(serializers.Serializer):
    """Serializer for chat responses"""
    
    success = serializers.BooleanField()
    response = serializers.CharField(required=False, allow_null=True)
    conversation_id = serializers.UUIDField()
    message_id = serializers.UUIDField(required=False, allow_null=True)
    tool_calls_made = serializers.IntegerField(default=0)
    execution_time = serializers.FloatField(required=False)
    error = serializers.CharField(required=False, allow_null=True)
    charts = serializers.ListField(child=serializers.DictField(), required=False)
    sources = serializers.ListField(child=serializers.DictField(), required=False)


class MCPStatusSerializer(serializers.Serializer):
    """Serializer for MCP server status"""
    
    status = serializers.CharField()
    tools_available = serializers.IntegerField()
    tool_names = serializers.ListField(child=serializers.CharField())
    server_url = serializers.URLField(required=False)
    organization_id = serializers.CharField(required=False)
    error = serializers.CharField(required=False, allow_null=True)


class ConversationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating conversations"""
    
    class Meta:
        model = Conversation
        fields = ['title']
    
    def create(self, validated_data):
        # Organization and user will be set in the view
        return Conversation.objects.create(**validated_data)


class MessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating messages manually (admin use)"""
    
    class Meta:
        model = Message
        fields = ['role', 'content', 'tool_calls', 'tool_call_id', 'name']
        
    def create(self, validated_data):
        # Conversation will be set in the view
        return Message.objects.create(**validated_data)
