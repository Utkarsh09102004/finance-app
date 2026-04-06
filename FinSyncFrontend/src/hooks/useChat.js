import { useState, useCallback, useEffect } from 'react';
import { chatAPI } from '../api/chat';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const mapServerMessage = (message) => ({
  id: message.id || `message-${Date.now()}`,
  sender: message.role === 'user' ? 'user' : 'ai',
  text: message.content || '',
  createdAt: message.created_at || new Date().toISOString(),
  role: message.role,
  type: 'text',
});

export const useChat = () => {
  const [messages, setMessages] = useState([]);
  const [currentInputValue, setCurrentInputValue] = useState('');
  const [chatStarted, setChatStarted] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [conversationTitle, setConversationTitle] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isMessagesLoading, setIsMessagesLoading] = useState(false);
  const [error, setError] = useState(null);
  const [conversationHistory, setConversationHistory] = useState([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [hasHydratedInitialConversation, setHasHydratedInitialConversation] = useState(false);
  const [conversationSources, setConversationSources] = useState([]);

  const buildChartMessages = useCallback((charts, baseId = `chart-${Date.now()}`) => {
    if (!Array.isArray(charts) || charts.length === 0) return [];
    const grouped = [];
    for (let i = 0; i < charts.length; i += 3) {
      grouped.push(charts.slice(i, i + 3));
    }
    return grouped.map((group, idx) => ({
      id: `${baseId}-${idx}`,
      sender: 'chart',
      type: 'chart_group',
      charts: group,
      createdAt: new Date().toISOString(),
    }));
  }, []);

  const parseSourceData = useCallback((raw) => {
    if (typeof raw === 'string') {
      try {
        return JSON.parse(raw);
      } catch {
        return raw;
      }
    }
    return raw;
  }, []);

  const normalizeSources = useCallback((sources, baseId = `source-${Date.now()}` , createdAt) => {
    if (!Array.isArray(sources) || sources.length === 0) return [];
    return sources.map((source, idx) => ({
      id: source.id || `${baseId}-${idx}`,
      tool: source.tool || 'Data Source',
      label: source.label || source.tool || 'Data Source',
      arguments: source.arguments || {},
      data: parseSourceData(source.data),
      createdAt: createdAt || new Date().toISOString(),
    }));
  }, [parseSourceData]);

  const refreshConversationHistory = useCallback(async () => {
    setIsHistoryLoading(true);
    try {
      const conversations = await chatAPI.listConversations({ limit: 25 });
      setConversationHistory(conversations);
    } catch (historyError) {
      console.error('Failed to fetch chat history', historyError);
    } finally {
      setIsHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshConversationHistory();
  }, [refreshConversationHistory]);

  const applyConversationDetail = useCallback((detail) => {
    if (!detail) return;

    setConversationId(detail.id);
    setConversationTitle(detail.title || 'Conversation');
    const baseMessages = [];
    const aggregatedSources = [];

    (detail.messages || []).forEach((msg) => {
      if (msg?.content) {
        baseMessages.push(mapServerMessage(msg));
      }

      const visuals = Array.isArray(msg?.visualizations) ? msg.visualizations : [];
      if (visuals.length) {
        const chartMessages = buildChartMessages(visuals, msg.id);
        chartMessages.forEach((chartMsg) => {
          chartMsg.createdAt = msg.created_at || new Date().toISOString();
        });
        baseMessages.push(...chartMessages);
      }

      const sourceEntries = normalizeSources(msg?.sources, msg.id, msg.created_at);
      if (sourceEntries.length) {
        aggregatedSources.push(...sourceEntries);
      }
    });

    setMessages(baseMessages);
    setChatStarted(baseMessages.length > 0);
    setConversationSources(aggregatedSources);
  }, [buildChartMessages, normalizeSources]);

  const loadConversation = useCallback(
    async (id, { silent = false } = {}) => {
      if (!id) return;
      if (!silent) {
        setIsMessagesLoading(true);
      }
      setError(null);

      try {
        const detail = await chatAPI.getConversation(id);
        applyConversationDetail(detail);
      } catch (err) {
        console.error('Failed to load conversation', err);
        setError('Failed to load conversation.');
      } finally {
        if (!silent) {
          setIsMessagesLoading(false);
        }
      }
    },
    [applyConversationDetail]
  );

  useEffect(() => {
    if (
      !hasHydratedInitialConversation &&
      conversationHistory.length > 0
    ) {
      loadConversation(conversationHistory[0]?.id);
      setHasHydratedInitialConversation(true);
    }
  }, [conversationHistory, hasHydratedInitialConversation, loadConversation]);

  const startNewConversation = useCallback(() => {
    setConversationId(null);
    setConversationTitle('');
    setMessages([]);
    setChatStarted(false);
    setCurrentInputValue('');
    setError(null);
    setConversationSources([]);
  }, []);

  const finalizeStreamingResult = useCallback(
    (result, assistantId) => {
      setConversationId(result.conversation_id);
      setConversationTitle((prevTitle) => prevTitle || 'Conversation');
      setError(result?.error || null);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantId
            ? { ...msg, text: result.response || '', isStreaming: false }
            : msg
        )
      );

      const chartMessages = buildChartMessages(result.charts);
      if (chartMessages.length) {
        setMessages((prev) => [...prev, ...chartMessages]);
      }

      const sourceEntries = normalizeSources(result.sources, assistantId);
      if (sourceEntries.length) {
        setConversationSources((prev) => [...prev, ...sourceEntries]);
      }
    },
    [buildChartMessages, normalizeSources]
  );

  const streamMessageRequest = useCallback(
    async (content, assistantId) => {
      const payload = {
        message: content,
        title: content.slice(0, 60),
      };
      if (conversationId) {
        payload.conversation_id = conversationId;
      }

      const headers = {
        'Content-Type': 'application/json',
      };
      const token = localStorage.getItem('accessToken');
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${API_BASE_URL}/chat/send-message/stream/`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      if (!response.ok || !response.body) {
        throw new Error('Failed to initiate streaming response');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop();

        for (const event of events) {
          const line = event.trim();
          if (!line.startsWith('data:')) continue;

          const payload = JSON.parse(line.slice(5).trim());
          if (payload.type === 'token') {
            const text = payload.text || '';
            if (!text) continue;
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId
                  ? { ...msg, text: (msg.text || '') + text }
                  : msg
              )
            );
          } else if (payload.type === 'result') {
            finalizeStreamingResult(payload.payload, assistantId);
            refreshConversationHistory();
            return;
          } else if (payload.type === 'error') {
            throw new Error(payload.error || 'Streaming error');
          }
        }
      }

      throw new Error('Stream ended unexpectedly');
    },
    [conversationId, finalizeStreamingResult, refreshConversationHistory]
  );

  const sendMessage = useCallback(
    async (textValue) => {
      const content = (textValue ?? currentInputValue).trim();
      if (!content || isSending) return;

      const optimisticMessage = {
        id: `local-${Date.now()}`,
        sender: 'user',
        text: content,
        createdAt: new Date().toISOString(),
        pending: true,
        type: 'text',
      };
      const streamingMessageId = `ai-${Date.now()}`;
      const streamingMessage = {
        id: streamingMessageId,
        sender: 'ai',
        text: '',
        createdAt: new Date().toISOString(),
        type: 'text',
        isStreaming: true,
      };

      setMessages((prev) => [...prev, optimisticMessage, streamingMessage]);
      setChatStarted(true);
      setIsSending(true);
      setError(null);

      try {
        await streamMessageRequest(content, streamingMessageId);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === optimisticMessage.id ? { ...msg, pending: false } : msg
          )
        );
      } catch (err) {
        console.error('Failed to stream message', err);
        setMessages((prev) =>
          prev
            .filter((msg) => msg.id !== streamingMessageId)
            .map((msg) =>
              msg.id === optimisticMessage.id ? { ...msg, pending: false } : msg
            )
        );

        try {
          const response = await chatAPI.sendMessage({
            message: content,
            conversationId,
            title: content.slice(0, 60),
          });

          setConversationId(response.conversation_id);
          setConversationTitle((prevTitle) => prevTitle || content.slice(0, 60));
          setError(response?.error || null);
          const assistantText = response?.response || 'I was unable to generate a response just now.';
          setMessages((prev) => [...prev, { id: response.message_id || `ai-${Date.now()}`, sender: 'ai', text: assistantText, createdAt: new Date().toISOString(), type: 'text' }]);
          const chartMessages = buildChartMessages(response.charts);
          if (chartMessages.length) {
            setMessages((prev) => [...prev, ...chartMessages]);
          }
          const sourceEntries = normalizeSources(response.sources, response.message_id || `ai-${Date.now()}`);
          if (sourceEntries.length) {
            setConversationSources((prev) => [...prev, ...sourceEntries]);
          }
          refreshConversationHistory();
        } catch (fallbackErr) {
          console.error('Fallback message send failed', fallbackErr);
          const fallbackError =
            fallbackErr?.response?.data?.error ||
            fallbackErr?.response?.data?.detail ||
            fallbackErr?.message ||
            'Failed to send message.';
          setError(fallbackError);
          setMessages((prev) => [
            ...prev,
            {
              id: `error-${Date.now()}`,
              sender: 'ai',
              text: `⚠️ ${fallbackError}`,
              isError: true,
              createdAt: new Date().toISOString(),
              type: 'text',
            },
          ]);
        }
      } finally {
        setIsSending(false);
        setCurrentInputValue('');
      }
    },
    [conversationId, currentInputValue, isSending, streamMessageRequest, buildChartMessages, normalizeSources, refreshConversationHistory]
  );

  const handleInputChange = useCallback((e) => {
    setCurrentInputValue(e.target.value);
  }, []);

  const handleSubmit = useCallback(
    (e) => {
      if (e) {
        e.preventDefault();
      }
      if (!currentInputValue.trim()) return;
      sendMessage(currentInputValue);
    },
    [currentInputValue, sendMessage]
  );

  const handlePromptClick = useCallback(
    (promptText) => {
      if (!promptText) return;
      setCurrentInputValue(promptText);
      sendMessage(promptText);
    },
    [sendMessage]
  );

  return {
    messages,
    currentInputValue,
    chatStarted,
    conversationId,
    conversationTitle,
    isSending,
    isMessagesLoading,
    error,
    conversationHistory,
    isHistoryLoading,
    conversationSources,
    handleInputChange,
    handleSubmit,
    handlePromptClick,
    startNewConversation,
    loadConversation,
  };
};
