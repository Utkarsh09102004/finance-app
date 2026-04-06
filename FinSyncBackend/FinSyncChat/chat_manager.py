import json
import time
import asyncio
import logging
import os
import uuid
from typing import Dict, List, Any, Optional, Callable, Awaitable
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import litellm
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from asgiref.sync import sync_to_async

from .models import (
    Conversation, Message, ToolExecution, ChatSettings,
    UsageTracking, ConversationSummary
)
from .mcp_client import get_mcp_client_for_organization
from .prompts import PROMPT_V1

logger = logging.getLogger(__name__)

DEFAULT_LLM_MODEL = ChatSettings.ModelChoice.KIMI_K2


class ChatManager:
    """
    Manages chat conversations with multi-tool call support
    """
    
    def __init__(self, conversation: Conversation):
        self.conversation = conversation
        self.organization = conversation.organization
        self.user = conversation.user
        self.settings = self._get_or_create_settings()
        self._configure_openrouter()
        self.tool_outputs: List[Dict[str, Any]] = []
        
    def _get_or_create_settings(self) -> ChatSettings:
        """Get or create chat settings for organization"""
        # This is called during __init__, so it needs to be sync
        # It's safe because __init__ is called from a sync context
        settings, created = ChatSettings.objects.get_or_create(
            organization=self.organization
        )
        if created:
            logger.info(f"Created default chat settings for {self.organization.name}")
        if settings.preferred_model != DEFAULT_LLM_MODEL:
            settings.preferred_model = DEFAULT_LLM_MODEL
            settings.save(update_fields=['preferred_model'])
        return settings
    
    def _configure_openrouter(self):
        """Configure OpenRouter environment variables for LiteLLM"""
        # Get OpenRouter API key from environment
        openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
        
        if openrouter_api_key:
            # Set environment variables for LiteLLM OpenRouter integration
            os.environ["OPENROUTER_API_KEY"] = openrouter_api_key
            os.environ["OPENROUTER_API_BASE"] = "https://openrouter.ai/api/v1"
            
            # Optional: Set site URL and app name for OpenRouter tracking
            os.environ["OR_SITE_URL"] = "https://finsync.app"
            os.environ["OR_APP_NAME"] = "FinSync AI Assistant"
            
            logger.debug("OpenRouter configured for LiteLLM")
        else:
            logger.warning("OPENROUTER_API_KEY not found in environment variables")
    
    async def process_user_message(self, user_message: str, stream_callback: Optional[Callable[[str], Awaitable[None]]] = None) -> Dict[str, Any]:
        """
        Process a user message and return the complete response
        """
        start_time = time.time()
        
        try:
            # Check usage limits
            await self._check_usage_limits()
            self.tool_outputs = []
            
            # Get conversation history
            messages = await self._get_conversation_history()
            
            # Add system message if this is the start of conversation
            if not messages:
                messages.append({
                    "role": "system",
                    "content": PROMPT_V1
                })
            
            # Add user message
            messages.append({"role": "user", "content": user_message})
            
            # Save user message to database
            user_msg = await self._save_message(
                role='user',
                content=user_message
            )
            
            # Process with LLM and tools until complete
            final_response = await self._process_with_tools(messages, stream_callback=stream_callback)
            assistant_text = final_response.get('content', '')
            chart_specs = await self._generate_chart_specs_with_llm(assistant_text)
            if chart_specs and final_response.get('message_id'):
                await self._store_visualizations(final_response['message_id'], chart_specs)
            sources_payload = self._format_sources()
            if sources_payload and final_response.get('message_id'):
                await self._store_sources(final_response['message_id'], sources_payload)
            
            # Update usage tracking
            await self._update_usage_tracking(
                messages_sent=1,
                tool_calls_made=await self._count_tool_executions(user_msg),
                tokens_used=self._estimate_tokens(user_message + assistant_text)
            )
            
            # Generate summary if enabled and conversation is long enough
            if self.settings.auto_generate_summaries:
                await self._maybe_generate_summary()
            
            execution_time = time.time() - start_time
            
            return {
                "success": True,
                "response": assistant_text,
                "conversation_id": str(self.conversation.id),
                "message_id": str(final_response.get('message_id')),
                "tool_calls_made": await self._count_tool_executions(user_msg),
                "execution_time": execution_time,
                "charts": chart_specs,
                "sources": sources_payload,
            }
            
        except Exception as e:
            logger.error(f"Error processing user message: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "conversation_id": str(self.conversation.id),
                "charts": [],
                "sources": [],
            }
    
    async def _get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Get conversation history in OpenAI format
        """
        @sync_to_async
        def get_messages():
            db_messages = Message.objects.filter(
                conversation=self.conversation
            ).order_by('sequence_number')
            
            messages = []
            for msg in db_messages:
                message_dict = {
                    "role": msg.role,
                    "content": msg.content
                }
                
                # Add tool-specific fields
                if msg.tool_calls:
                    message_dict["tool_calls"] = msg.tool_calls
                
                if msg.tool_call_id:
                    message_dict["tool_call_id"] = msg.tool_call_id
                    
                if msg.name:
                    message_dict["name"] = msg.name
                
                messages.append(message_dict)
            
            return messages
        
        return await get_messages()
    
    async def _process_with_tools(self, messages: List[Dict[str, Any]], stream_callback: Optional[Callable[[str], Awaitable[None]]] = None) -> Dict[str, Any]:
        """
        Process messages with LLM and handle tool calls until complete
        """
        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        
        # Get MCP client and keep it open for the entire process
        mcp_client = await get_mcp_client_for_organization(self.organization)
        async with mcp_client:
            while iteration < max_iterations:
                iteration += 1
                
                # Get LLM response with tools from MCP
                response = await self._call_llm_with_tools(messages, mcp_client, stream_callback=stream_callback)
                assistant_message = response.choices[0].message
                
                # Convert tool_calls to JSON-serializable format if present
                tool_calls_json = None
                if hasattr(assistant_message, 'tool_calls') and assistant_message.tool_calls:
                    tool_calls_json = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in assistant_message.tool_calls
                    ]
                
                # Save assistant message
                saved_message = await self._save_message(
                    role='assistant',
                    content=assistant_message.content or "",
                    tool_calls=tool_calls_json
                )
                
                # Check if there are tool calls to execute
                if not hasattr(assistant_message, 'tool_calls') or not assistant_message.tool_calls:
                    # No tool calls, this is the final response
                    return {
                        "content": assistant_message.content,
                        "message_id": str(saved_message.id),
                        "iterations": iteration
                    }
                
                # Execute tool calls with the MCP client
                tool_results = await self._execute_tool_calls_with_client(
                    saved_message, assistant_message.tool_calls, mcp_client
                )
                
                # Add assistant message and tool results to conversation
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in assistant_message.tool_calls
                    ]
                })
                
                # Add tool result messages
                for result in tool_results:
                    messages.append(result)
        
        # If we reach here, we've hit max iterations
        logger.warning(f"Max iterations ({max_iterations}) reached for conversation {self.conversation.id}")
        return {
            "content": "I apologize, but I've reached the maximum number of tool calls for this request. Please try breaking down your question into smaller parts.",
            "message_id": None,
            "iterations": iteration
        }
    
    async def _call_llm_with_tools(self, messages: List[Dict[str, Any]], mcp_client, stream_callback: Optional[Callable[[str], Awaitable[None]]] = None) -> Any:
        """
        Call LLM with tools using provided MCP client
        """
        try:
            # Get available tools from MCP server
            tools = await mcp_client.load_tools()
            logger.info(f"Loaded {len(tools) if tools else 0} tools from MCP server")
            if tools:
                tool_names = [tool.get('function', {}).get('name', 'unknown') for tool in tools]
                logger.info(f"Available tools: {tool_names}")
            
            # Call LiteLLM with tools
            if stream_callback:
                response = await self._streaming_completion(
                    messages=messages,
                    tools=tools,
                    temperature=self.settings.temperature,
                    max_tokens=self.settings.max_tokens,
                    token_callback=stream_callback
                )
            else:
                response = await litellm.acompletion(
                    model=self.settings.preferred_model,
                    messages=messages,
                    tools=tools if tools else None,
                    temperature=self.settings.temperature,
                    max_tokens=self.settings.max_tokens,
                    tool_choice="auto" if tools else None,
                )
            
            # Log the response for debugging
            logger.info("=" * 80)
            logger.info("LiteLLM Response:")
            logger.info(f"Model: {response.model}")
            logger.info(f"Usage: {response.usage}")
            
            # Log the message content
            if response.choices:
                choice = response.choices[0]
                logger.info(f"Message role: {choice.message.role}")
                logger.info(f"Message content: {choice.message.content}")
                
                # Log tool calls if any
                if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                    logger.info(f"Tool calls count: {len(choice.message.tool_calls)}")
                    for i, tool_call in enumerate(choice.message.tool_calls):
                        logger.info(f"Tool call {i}: {tool_call.function.name}")
                        logger.info(f"Tool call {i} args: {tool_call.function.arguments}")
            
            logger.info("=" * 80)
            
            return response
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    async def _streaming_completion(self, messages, tools, temperature, max_tokens, token_callback):
        stream = await litellm.acompletion(
            model=self.settings.preferred_model,
            messages=messages,
            tools=tools if tools else None,
            temperature=temperature,
            max_tokens=max_tokens,
            tool_choice="auto" if tools else None,
            stream=True,
        )

        content_parts: List[str] = []
        tool_calls: Dict[int, Dict[str, Any]] = {}

        async for chunk in stream:
            choice = chunk.choices[0]
            delta = getattr(choice, 'delta', getattr(choice, 'message', None))
            if delta is None:
                continue

            text = getattr(delta, 'content', None) or (delta.get('content') if isinstance(delta, dict) else None)
            if text:
                content_parts.append(text)
                await token_callback(text)

            tool_delta = getattr(delta, 'tool_calls', None) or (delta.get('tool_calls') if isinstance(delta, dict) else None)
            if tool_delta:
                for call in tool_delta:
                    index = call.get('index', 0)
                    entry = tool_calls.setdefault(index, {
                        'id': call.get('id'),
                        'type': 'function',
                        'function': {'name': '', 'arguments': ''}
                    })
                    if call.get('id'):
                        entry['id'] = call['id']
                    function = call.get('function') or {}
                    if function.get('name'):
                        entry['function']['name'] = function['name']
                    if function.get('arguments'):
                        entry['function']['arguments'] += function['arguments']

        message = SimpleNamespace(
            role='assistant',
            content=''.join(content_parts) if content_parts else None,
            tool_calls=[SimpleNamespace(
                id=tc.get('id'),
                type='function',
                function=SimpleNamespace(
                    name=tc['function'].get('name'),
                    arguments=tc['function'].get('arguments', '')
                )
            ) for tc in tool_calls.values()] if tool_calls else None
        )

        return SimpleNamespace(
            model=self.settings.preferred_model,
            usage=None,
            choices=[SimpleNamespace(message=message)]
        )
    
    async def _execute_tool_calls_with_client(self, message: Message, tool_calls: List[Any], mcp_client) -> List[Dict[str, Any]]:
        """
        Execute tool calls using the provided MCP client and return results
        """
        results = []
        
        for tool_call in tool_calls:
            start_time = time.time()
            
            try:
                # Parse arguments
                arguments = json.loads(tool_call.function.arguments)
                
                # Execute tool via MCP
                logger.info(f"Executing tool: {tool_call.function.name}")
                logger.info(f"Tool arguments: {json.dumps(arguments, indent=2)}")
                
                result = await mcp_client.call_tool(
                    tool_name=tool_call.function.name,
                    arguments=arguments
                )
                self.tool_outputs.append({
                    'id': f"{tool_call.function.name}-{uuid.uuid4().hex}",
                    'tool_name': tool_call.function.name,
                    'arguments': arguments,
                    'result': result,
                })
                
                # Log the tool execution result
                logger.info("=" * 80)
                logger.info(f"Tool execution result for {tool_call.function.name}:")
                logger.info(json.dumps(result, indent=2))
                logger.info("=" * 80)
                
                execution_time = time.time() - start_time
                
                # Save tool execution record
                tool_execution = await self._save_tool_execution(
                    message=message,
                    tool_name=tool_call.function.name,
                    arguments=arguments,
                    result=result,
                    execution_time=execution_time,
                    status='success',
                    mcp_server_url=mcp_client.server_url,
                    integration_id=mcp_client.credentials.get('integration_id')
                )
                
                # Save tool result message
                await self._save_message(
                    role='tool',
                    content=json.dumps(result),
                    tool_call_id=tool_call.id,
                    name=tool_call.function.name
                )
                
                # Add to results
                results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": json.dumps(result)
                })
                
            except Exception as e:
                execution_time = time.time() - start_time
                error_msg = str(e)
                
                # Log the error
                logger.error("=" * 80)
                logger.error(f"Tool execution FAILED for {tool_call.function.name}")
                logger.error(f"Error: {error_msg}")
                logger.error("=" * 80)
                
                # Save failed execution
                await self._save_tool_execution(
                    message=message,
                    tool_name=tool_call.function.name,
                    arguments=json.loads(tool_call.function.arguments) if tool_call.function.arguments else {},
                    result=None,
                    execution_time=execution_time,
                    status='error',
                    error_message=error_msg,
                    mcp_server_url=mcp_client.server_url
                )
                
                # Save error message
                await self._save_message(
                    role='tool',
                    content=f"Error executing {tool_call.function.name}: {error_msg}",
                    tool_call_id=tool_call.id,
                    name=tool_call.function.name
                )
                
                # Add error to results
                results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": f"Error: {error_msg}"
                })
                
                logger.error(f"Tool execution failed: {tool_call.function.name} - {error_msg}")
        
        return results
    
    async def _save_message(self, role: str, content: str, tool_calls=None, 
                           tool_call_id=None, name=None) -> Message:
        """
        Save message to database
        """
        @sync_to_async
        def create_message():
            return Message.objects.create(
                conversation=self.conversation,
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
                name=name,
                token_count=self._estimate_tokens(content)
            )
        
        return await create_message()
    
    async def _save_tool_execution(self, message: Message, tool_name: str, 
                                  arguments: Dict, result: Any, execution_time: float,
                                  status: str, error_message: str = None,
                                  mcp_server_url: str = None, 
                                  integration_id: str = None) -> ToolExecution:
        """
        Save tool execution record
        """
        @sync_to_async
        def create_tool_execution():
            return ToolExecution.objects.create(
                message=message,
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                execution_time=execution_time,
                status=status,
                error_message=error_message,
                mcp_server_url=mcp_server_url,
                integration_id=integration_id
            )
        
        return await create_tool_execution()
    
    async def _check_usage_limits(self):
        """
        Check if organization has exceeded usage limits
        """
        @sync_to_async
        def check_limits():
            today = date.today()
            usage, _ = UsageTracking.objects.get_or_create(
                organization=self.organization,
                date=today
            )
            
            if usage.messages_sent >= self.settings.daily_message_limit:
                raise Exception(f"Daily message limit ({self.settings.daily_message_limit}) exceeded")
            
            if usage.tool_calls_made >= self.settings.daily_tool_call_limit:
                raise Exception(f"Daily tool call limit ({self.settings.daily_tool_call_limit}) exceeded")
        
        await check_limits()
    
    async def _update_usage_tracking(self, messages_sent: int = 0, 
                                   tool_calls_made: int = 0, tokens_used: int = 0):
        """
        Update usage tracking
        """
        @sync_to_async
        def update_usage():
            today = date.today()
            usage, _ = UsageTracking.objects.get_or_create(
                organization=self.organization,
                date=today
            )
            
            usage.messages_sent += messages_sent
            usage.tool_calls_made += tool_calls_made
            usage.tokens_used += tokens_used
            
            # Estimate cost (rough calculation)
            # GPT-4o: ~$5/1M tokens, Claude: ~$3/1M tokens
            cost_per_token = 0.000005  # $5 per 1M tokens
            usage.estimated_cost += Decimal(str(tokens_used * cost_per_token))
            
            usage.save()
        
        await update_usage()
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Rough token estimation (1 token ≈ 4 characters)
        """
        return len(text) // 4
    
    async def _count_tool_executions(self, message: Message) -> int:
        """
        Count tool executions for a message
        """
        @sync_to_async
        def count_executions():
            return ToolExecution.objects.filter(message=message).count()
        
        return await count_executions()
    
    async def _maybe_generate_summary(self):
        """
        Generate conversation summary if conversation is long enough
        """
        @sync_to_async
        def get_message_count():
            return Message.objects.filter(conversation=self.conversation).count()
        
        @sync_to_async
        def has_summary():
            return hasattr(self.conversation, 'summary')
        
        @sync_to_async
        def get_conversation_messages():
            messages = Message.objects.filter(
                conversation=self.conversation,
                role__in=['user', 'assistant']
            ).order_by('sequence_number')[:20]
            
            return "\n\n".join([
                f"{msg.role.title()}: {msg.content}" 
                for msg in messages
            ])
        
        message_count = await get_message_count()
        
        if message_count >= 10 and not await has_summary():
            # Generate summary using LLM
            try:
                # Get conversation text
                conversation_text = await get_conversation_messages()
                
                summary_prompt = f"""
                Please provide a concise summary of this financial conversation, including:
                1. Main topics discussed
                2. Key financial insights or findings
                3. Tools/reports that were used
                4. Important metrics mentioned
                
                Conversation:
                {conversation_text}
                """
                
                response = await litellm.acompletion(
                    model=self.settings.preferred_model,
                    messages=[{"role": "user", "content": summary_prompt}],
                    temperature=0.1,
                    max_tokens=500
                )
                
                summary_text = response.choices[0].message.content
                
                # Save summary
                @sync_to_async
                def save_summary():
                    tools_used = list(ToolExecution.objects.filter(
                        message__conversation=self.conversation
                    ).values_list('tool_name', flat=True).distinct())
                    
                    ConversationSummary.objects.create(
                        conversation=self.conversation,
                        summary_text=summary_text,
                        key_insights=[],  # Could parse this from LLM response
                        financial_metrics_discussed=[],  # Could parse this
                        tools_used=tools_used
                    )
                
                await save_summary()
                
                logger.info(f"Generated summary for conversation {self.conversation.id}")
                
            except Exception as e:
                logger.error(f"Failed to generate summary: {e}")

    async def _generate_chart_specs_with_llm(self, assistant_text: str) -> List[Dict[str, Any]]:
        """Ask the LLM to propose chart specs based on tool outputs."""
        if not self.tool_outputs:
            return []

        # Build context from tool outputs (truncate large payloads)
        context_sections = []
        for entry in self.tool_outputs:
            try:
                result_json = json.dumps(entry['result'], default=str)
            except TypeError:
                result_json = str(entry['result'])

            if len(result_json) > 4000:
                result_json = result_json[:4000] + '...'

            context_sections.append(
                f"Tool: {entry['tool_name']}\nArguments: {json.dumps(entry['arguments'], default=str)}\nResult: {result_json}"
            )

        chart_prompt = (
            "You are FinSync Chart Builder. Given the assistant's narrative and the raw tool results, "
            "propose up to two charts that would help a finance user understand the data. "
            "Use existing numeric values from the tool results—do not fabricate numbers. "
            "Return JSON ONLY with the shape {\"charts\": [...]} where each chart matches this schema:"
            " {id, title, description, type (bar|stackedBar|line|area|pie), x_axis:{field,label}, "
            "y_axis:{field,label}, series:[{field,label}], data:[{...}], metadata:{timeframe?,unit?}}."
        )

        user_payload = (
            f"Assistant narrative:\n{assistant_text}\n\n"
            f"Tool data:\n" + "\n\n".join(context_sections)
        )

        try:
            response = await litellm.acompletion(
                model=self.settings.preferred_model,
                messages=[
                    {"role": "system", "content": chart_prompt},
                    {"role": "user", "content": user_payload}
                ],
                temperature=0.1,
                max_tokens=800
            )
            content = response.choices[0].message.content if response.choices else None
            if not content:
                return []
            charts_payload = json.loads(content)
            charts = charts_payload.get('charts') if isinstance(charts_payload, dict) else None
            if isinstance(charts, list):
                return [chart for chart in charts if isinstance(chart, dict)]
        except Exception as exc:
            logger.warning("Chart generation LLM call failed: %s", exc)

        return []

    async def _store_visualizations(self, message_id: str, charts: List[Dict[str, Any]]):
        @sync_to_async
        def persist():
            Message.objects.filter(id=message_id).update(visualizations=charts)
        await persist()

    def _format_sources(self) -> List[Dict[str, Any]]:
        sources: List[Dict[str, Any]] = []
        for entry in self.tool_outputs:
            tool_name = entry.get('tool_name')
            arguments = entry.get('arguments') or {}
            result = self._normalize_tool_result(entry.get('result'))
            if result is None:
                continue

            items = result if isinstance(result, list) else [result]
            for idx, item in enumerate(items):
                if item is None:
                    continue
                sources.append({
                    'id': entry.get('id') or f"{tool_name}-{uuid.uuid4().hex}-{idx}",
                    'tool': tool_name,
                    'label': self._build_source_label(tool_name, arguments, item, idx),
                    'arguments': arguments,
                    'data': item,
                })
        return sources

    def _normalize_tool_result(self, result):
        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return result
        return result

    def _build_source_label(self, tool_name: str, arguments: Dict[str, Any], item: Any, index: int) -> str:
        base = (tool_name or 'Data Source').replace('_', ' ').title()
        timeframe = self._extract_timeframe(item) or self._extract_timeframe(arguments)
        if timeframe:
            return f"{base} ({timeframe})"
        if index:
            return f"{base} #{index + 1}"
        return base

    def _extract_timeframe(self, data: Any) -> str:
        if not isinstance(data, dict):
            return ''
        start = data.get('from_date') or data.get('start_date')
        end = data.get('to_date') or data.get('end_date')
        if start and end:
            if start == end:
                return start
            return f"{start} to {end}"
        if start:
            return f"from {start}"
        if end:
            return f"through {end}"
        return ''

    async def _store_sources(self, message_id: str, sources: List[Dict[str, Any]]):
        @sync_to_async
        def persist():
            Message.objects.filter(id=message_id).update(sources=sources)
        await persist()


# Utility functions
async def create_conversation(organization, user, title: str = None) -> Conversation:
    """
    Create a new conversation
    """
    return Conversation.objects.create(
        organization=organization,
        user=user,
        title=title
    )


async def get_conversation_manager(conversation_id: str, user) -> ChatManager:
    """
    Get chat manager for conversation
    """
    try:
        conversation = Conversation.objects.get(
            id=conversation_id,
            user=user,
            is_active=True
        )
        return ChatManager(conversation)
    except Conversation.DoesNotExist:
        raise ValueError(f"Conversation {conversation_id} not found or not accessible")


def list_user_conversations(user, limit: int = 20) -> List[Dict[str, Any]]:
    """List user's conversations (synchronous)."""
    conversations = Conversation.objects.filter(
        user=user,
        is_active=True
    ).order_by('-updated_at')[:limit]

    return [
        {
            "id": str(conv.id),
            "title": conv.title or "New Conversation",
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "message_count": conv.messages.count(),
        }
        for conv in conversations
    ]
