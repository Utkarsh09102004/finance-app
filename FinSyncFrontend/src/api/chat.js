import axiosClient from './axios';

export const chatAPI = {
  async sendMessage({ message, conversationId, title }) {
    const payload = {
      message,
    };

    if (conversationId) {
      payload.conversation_id = conversationId;
    }

    if (!conversationId && title) {
      payload.title = title;
    }

    const { data } = await axiosClient.post('/chat/send-message/', payload);
    return data;
  },

  async listConversations(params = {}) {
    const { data } = await axiosClient.get('/chat/conversations/list/', { params });
    return data?.conversations || [];
  },

  async getConversation(conversationId) {
    const { data } = await axiosClient.get(`/chat/conversations/${conversationId}/`);
    return data;
  },
};

export default chatAPI;
