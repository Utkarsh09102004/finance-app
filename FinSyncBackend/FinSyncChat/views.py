import asyncio
import json
import logging
import queue
import threading
from typing import Dict, Any

from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from asgiref.sync import sync_to_async

from .models import Conversation, Message, ChatSettings, UsageTracking
from .serializers import (
    ConversationSerializer, ConversationDetailSerializer, MessageSerializer,
    ChatSettingsSerializer, SendMessageSerializer, ChatResponseSerializer,
    MCPStatusSerializer, ConversationCreateSerializer
)
from .chat_manager import ChatManager, create_conversation, get_conversation_manager, list_user_conversations
from .mcp_client import test_mcp_connection
# from FinSyncOrganizations.views import IsOrganizationMember

logger = logging.getLogger(__name__)


class ConversationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing conversations
    """
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Conversation.objects.filter(
            organization=self.request.user.organization,
            user=self.request.user,
            is_active=True
        ).order_by('-updated_at')
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ConversationDetailSerializer
        elif self.action == 'create':
            return ConversationCreateSerializer
        return ConversationSerializer
    
    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.user.organization,
            user=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive a conversation"""
        conversation = self.get_object()
        conversation.is_active = False
        conversation.save()
        return Response({'status': 'conversation archived'})
    
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore an archived conversation"""
        conversation = get_object_or_404(
            Conversation,
            pk=pk,
            organization=request.user.organization,
            user=request.user,
            is_active=False
        )
        conversation.is_active = True
        conversation.save()
        return Response({'status': 'conversation restored'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message(request):
    """
    Send a message and get AI response
    """
    serializer = SendMessageSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    message_content = data['message']
    conversation_id = data.get('conversation_id')
    title = data.get('title')
    
    try:
        # Get user's organization
        organization = getattr(request.user, 'organization', None)
        if organization is None:
            return Response(
                {'error': 'You are not associated with an organization'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create conversation
        if conversation_id:
            try:
                conversation = Conversation.objects.get(
                    id=conversation_id,
                    organization=organization,
                    user=request.user,
                    is_active=True
                )
            except Conversation.DoesNotExist:
                return Response(
                    {'error': 'Conversation not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Create new conversation with user's question as title
            conversation_title = title or (message_content[:50] + "..." if len(message_content) > 50 else message_content)
            conversation = Conversation.objects.create(
                organization=organization,
                user=request.user,
                title=conversation_title
            )
        
        # Save user message
        user_message = Message.objects.create(
            conversation=conversation,
            role='user',
            content=message_content,
            token_count=len(message_content) // 4  # rough estimate
        )
        
        # Process message with ChatManager in thread
        import threading
        import queue
        
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def run_chat_manager_in_thread():
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Import here to avoid circular imports
                chat_manager = ChatManager(conversation)
                result = loop.run_until_complete(chat_manager.process_user_message(message_content))
                result_queue.put(result)
            except Exception as e:
                exception_queue.put(e)
            finally:
                loop.close()
        
        thread = threading.Thread(target=run_chat_manager_in_thread)
        thread.start()
        thread.join()
        
        if not exception_queue.empty():
            # If ChatManager fails, provide fallback response
            error = exception_queue.get()
            logger.error(f"ChatManager failed: {error}")
            
            assistant_response = f"I apologize, but I'm having trouble connecting to the financial data services. Error: {str(error)[:100]}..."
            assistant_message = Message.objects.create(
                conversation=conversation,
                role='assistant', 
                content=assistant_response,
                token_count=len(assistant_response) // 4
            )
            
            result = {
                "success": False,
                "response": assistant_response,
                "conversation_id": str(conversation.id),
                "message_id": str(assistant_message.id),
                "tool_calls_made": 0,
                "execution_time": 0.1,
                "error": str(error),
                "charts": [],
                "sources": []
            }
        else:
            result = result_queue.get()
        
        # Serialize response
        response_serializer = ChatResponseSerializer(result)
        return Response(response_serializer.data)
        
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message_stream(request):
    serializer = SendMessageSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    message_content = data['message']
    conversation_id = data.get('conversation_id')
    title = data.get('title')

    organization = getattr(request.user, 'organization', None)
    if organization is None:
        return Response(
            {'error': 'You are not associated with an organization'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        if conversation_id:
            conversation = Conversation.objects.get(
                id=conversation_id,
                organization=organization,
                user=request.user,
                is_active=True
            )
        else:
            conversation_title = title or (message_content[:50] + "..." if len(message_content) > 50 else message_content)
            conversation = Conversation.objects.create(
                organization=organization,
                user=request.user,
                title=conversation_title
            )
    except Conversation.DoesNotExist:
        return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)

    user_message = Message.objects.create(
        conversation=conversation,
        role='user',
        content=message_content,
        token_count=len(message_content) // 4
    )

    event_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()

    async def token_callback(text: str):
        event_queue.put({'type': 'token', 'text': text})

    def run_chat_manager():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            chat_manager = ChatManager(conversation)
            result = loop.run_until_complete(chat_manager.process_user_message(
                message_content,
                stream_callback=token_callback
            ))
            loop.close()
            event_queue.put({'type': 'result', 'payload': result})
        except Exception as exc:
            logger.error(f"Streaming chat error: {exc}", exc_info=True)
            event_queue.put({'type': 'error', 'error': str(exc)})

    thread = threading.Thread(target=run_chat_manager)
    thread.start()

    def event_stream():
        try:
            while True:
                event = event_queue.get()
                yield f"data: {json.dumps(event)}\n\n"
                if event['type'] in ('result', 'error'):
                    break
        finally:
            thread.join()

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_conversations(request):
    """
    List user's conversations
    """
    try:
        limit = int(request.query_params.get('limit', 20))
        conversations = list_user_conversations(request.user, limit)
        return Response({'conversations': conversations})
    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        return Response(
            {'error': 'Failed to list conversations'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def conversation_detail(request, conversation_id):
    """
    Get detailed conversation with messages
    """
    try:
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            organization=request.user.organization,
            user=request.user,
            is_active=True
        )
        
        serializer = ConversationDetailSerializer(conversation)
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(f"Error getting conversation detail: {e}")
        return Response(
            {'error': 'Failed to get conversation'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class ChatSettingsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing chat settings
    """
    serializer_class = ChatSettingsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        settings, created = ChatSettings.objects.get_or_create(
            organization=self.request.user.organization
        )
        return settings
    
    def list(self, request):
        """Get chat settings"""
        settings = self.get_object()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)
    
    def update(self, request, pk=None):
        """Update chat settings"""
        settings = self.get_object()
        serializer = self.get_serializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mcp_status(request):
    """
    Check MCP server connection status
    """
    try:
        # Get user's organization
        organization = getattr(request.user, 'organization', None)
        if organization is None:
            return Response({
                'status': 'error',
                'error': 'No organization found',
                'tools_available': 0,
                'tool_names': []
            })
        
        # Use thread to run async function
        import threading
        import queue
        
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def run_async_in_thread():
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(test_mcp_connection(organization))
                result_queue.put(result)
            except Exception as e:
                exception_queue.put(e)
            finally:
                loop.close()
        
        thread = threading.Thread(target=run_async_in_thread)
        thread.start()
        thread.join()
        
        if not exception_queue.empty():
            raise exception_queue.get()
        
        result = result_queue.get()
        serializer = MCPStatusSerializer(result)
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"Error checking MCP status: {e}")
        return Response(
            {
                'status': 'error',
                'error': str(e),
                'tools_available': 0,
                'tool_names': []
            }
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def usage_stats(request):
    """
    Get usage statistics for organization
    """
    try:
        from datetime import date, timedelta
        
        # Get last 30 days of usage
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        usage_records = UsageTracking.objects.filter(
            organization=request.user.organization,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        # Aggregate statistics
        total_messages = sum(record.messages_sent for record in usage_records)
        total_tool_calls = sum(record.tool_calls_made for record in usage_records)
        total_tokens = sum(record.tokens_used for record in usage_records)
        total_cost = sum(record.estimated_cost for record in usage_records)
        
        # Daily breakdown
        daily_stats = [
            {
                'date': record.date.isoformat(),
                'messages_sent': record.messages_sent,
                'tool_calls_made': record.tool_calls_made,
                'tokens_used': record.tokens_used,
                'estimated_cost': float(record.estimated_cost)
            }
            for record in usage_records
        ]
        
        # Current limits
        settings = ChatSettings.objects.filter(
            organization=request.user.organization
        ).first()
        
        limits = {
            'daily_message_limit': settings.daily_message_limit if settings else 100,
            'daily_tool_call_limit': settings.daily_tool_call_limit if settings else 500,
        }
        
        # Today's usage
        today_usage = usage_records.filter(date=end_date).first()
        today_stats = {
            'messages_sent': today_usage.messages_sent if today_usage else 0,
            'tool_calls_made': today_usage.tool_calls_made if today_usage else 0,
            'tokens_used': today_usage.tokens_used if today_usage else 0,
            'estimated_cost': float(today_usage.estimated_cost) if today_usage else 0,
        }
        
        return Response({
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
            },
            'totals': {
                'messages_sent': total_messages,
                'tool_calls_made': total_tool_calls,
                'tokens_used': total_tokens,
                'estimated_cost': float(total_cost),
            },
            'today': today_stats,
            'limits': limits,
            'daily_breakdown': daily_stats,
        })
        
    except Exception as e:
        logger.error(f"Error getting usage stats: {e}")
        return Response(
            {'error': 'Failed to get usage statistics'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def available_models(request):
    """
    Get list of available LLM models
    """
    return Response({
        'models': [
            {
                'id': 'openrouter/moonshotai/kimi-k2',
                'name': 'Kimi K2',
                'provider': 'Moonshot AI (via OpenRouter)',
                'description': 'Advanced MoE model optimized for agentic capabilities and tool use',
                'cost_per_1k_tokens': 0.002,
                'context_length': 128000,
                'parameters': '1T total / 32B active'
            }
        ]
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_conversation(request, conversation_id):
    """
    Clear all messages from a conversation (keep conversation but remove messages)
    """
    try:
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            organization=request.user.organization,
            user=request.user,
            is_active=True
        )
        
        # Delete all messages
        Message.objects.filter(conversation=conversation).delete()
        
        # Reset conversation title
        conversation.title = ""
        conversation.save()
        
        return Response({'status': 'conversation cleared'})
        
    except Exception as e:
        logger.error(f"Error clearing conversation: {e}")
        return Response(
            {'error': 'Failed to clear conversation'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
