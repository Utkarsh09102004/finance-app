import { useState, useCallback } from 'react';

export const useChat = () => {
    const [messages, setMessages] = useState([]);
    const [currentInputValue, setCurrentInputValue] = useState("");
    const [chatStarted, setChatStarted] = useState(false);

    const addMessage = useCallback((text, sender) => {
        setMessages(prevMessages => [...prevMessages, { text, sender, id: Date.now() }]);
    }, []);

    // Placeholder for actual API call
    const getAIResponse = async (userText) => {
        // Simulate API delay
        await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 1000));
        // In a real app, you would make an API call here:
        // const response = await fetch('/api/chat', { method: 'POST', body: JSON.stringify({ prompt: userText }) });
        // const data = await response.json();
        // return data.reply;
        return `FinSync AI processing: "${userText}". Actual AI response logic needs to be implemented.`;
    };

    const sendMessage = useCallback(async (text) => {
        if (text.trim() === "") return;

        if (!chatStarted) {
            setChatStarted(true);
        }

        addMessage(text, 'user');
        setCurrentInputValue(""); // Clear input after sending user message

        const aiText = await getAIResponse(text);
        addMessage(aiText, 'ai');
    }, [addMessage, chatStarted]);
    
    const handleInputChange = useCallback((e) => {
        setCurrentInputValue(e.target.value);
    }, []);

    const handleSubmit = useCallback((e) => {
        if (e) e.preventDefault();
        sendMessage(currentInputValue);
    }, [sendMessage, currentInputValue]);

    const handlePromptClick = useCallback((promptText) => {
        if (!chatStarted) {
            setChatStarted(true);
        }
        // Set input value briefly so it can be picked up by sendMessage if needed,
        // or directly call sendMessage with promptText after ensuring input is cleared.
        setCurrentInputValue(promptText); // This might be optional depending on how PlaceholdersAndVanishInput behaves
        sendMessage(promptText);
        // setCurrentInputValue(""); // Ensure input is cleared after prompt click if not handled by sendMessage
    }, [sendMessage, chatStarted]);

    return {
        messages,
        currentInputValue,
        chatStarted,
        setChatStarted, // Exposing this if direct control is needed, e.g., for resetting chat
        handleInputChange,
        handleSubmit,
        handlePromptClick,
        // addMessage, // Expose if needed for direct message injection outside of sendFlow
    };
}; 