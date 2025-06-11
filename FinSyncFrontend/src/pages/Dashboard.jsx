import React, { useState, useEffect, useRef } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/sidebar';
import { Button } from "../components/ui/button";
import { Menu } from 'lucide-react';
import { useWindowWidth } from "@react-hook/window-size";
import { cn } from "../lib/utils";
import { PlaceholdersAndVanishInput } from "../components/ui/placeholders-and-vanish-input";
import { motion, AnimatePresence } from "framer-motion";
import UserMessageBubble from '../components/chat/UserMessageBubble';
import AIMessageBubble from '../components/chat/AIMessageBubble';
import { useChat } from '../hooks/useChat';

const initialPlaceholders = [
    "What are my upcoming bills?",
    "Show my spending in groceries last month.",
    "How can I save more money?",
    "Explain compound interest.",
    "What's my current investment portfolio value?",
];

const chatPlaceholders = [
    "Type your message..."
];

const ExamplePromptBox = ({ text, onClick }) => (
    <motion.button
        whileHover={{ scale: 1.03, backgroundColor: 'hsl(var(--muted-hover))'}}
        whileTap={{ scale: 0.98 }}
        onClick={onClick}
        className="p-4 bg-muted/70 dark:bg-muted/40 rounded-lg text-left text-sm hover:bg-muted dark:hover:bg-muted/60 transition-colors shadow-sm"
    >
        <p className="text-foreground/90 dark:text-foreground/80">{text}</p>
    </motion.button>
);

const Dashboard = () => {
    const navigate = useNavigate();
    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
    const onlyWidth = useWindowWidth();
    const mobileWidth = onlyWidth < 768;

    const {
        messages,
        chatStarted,
        handleInputChange,
        handleSubmit,
        handlePromptClick,
    } = useChat();

    const messagesEndRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(scrollToBottom, [messages]);

    useEffect(() => {
        const token = localStorage.getItem('accessToken');
        if (!token) {
            navigate('/login');
        }
    }, [navigate]);

    useEffect(() => {
        if (mobileWidth) {
            setIsSidebarCollapsed(true);
        }
    }, [mobileWidth]);

    const handleSidebarToggle = (collapsedState) => {
        setIsSidebarCollapsed(collapsedState);
    };

    return (
        <div className="flex h-screen bg-background">
            <Sidebar isCollapsed={isSidebarCollapsed} onCollapseChange={handleSidebarToggle} bgColor="#f9f9f9" />
            <main 
                className={cn(
                    "flex-1 flex flex-col overflow-hidden transition-all duration-300 ease-in-out",
                    mobileWidth ? "pt-0" : (isSidebarCollapsed ? "ml-[70px]" : "ml-64")
                )}
            >
                {/* Combined Header for Mobile and Desktop */}
                {/* <header className={cn(
                    "sticky top-0 z-30 flex items-center h-[60px] border-b bg-background px-4 sm:px-6",
                    mobileWidth && !isSidebarCollapsed && "hidden"
                )}>
                    {mobileWidth && isSidebarCollapsed && (
                        <>
                            <div className="flex items-center gap-2">
                                <img src="/logo.svg" alt="FinSync Logo" className="h-7 w-7" />
                                <span className="font-semibold text-lg">FinSync</span>
                            </div>
                            <Button variant="ghost" size="icon" onClick={() => handleSidebarToggle(false)}>
                                <Menu className="h-6 w-6" />
                            </Button>
                        </>
                    )}
                    {!mobileWidth && (
                        <h1 className="text-xl font-semibold text-foreground">
                            {chatStarted ? "AI Chat" : "Dashboard Overview"}
                        </h1>
                    )}
                </header> */}

                {/* Chat Interface Area */}
                <div className="flex flex-col flex-grow items-center w-full h-full relative overflow-hidden bg-white">
                    {/* Pre-chat / Initial View */}
                    <AnimatePresence>
                        {!chatStarted && (
                            <motion.div
                                key="pre-chat-view"
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeInOut" } }}
                                exit={{ opacity: 0, y: -20, transition: { duration: 0.3, ease: "easeInOut" } }}
                                className="flex flex-col justify-center items-center w-full max-w-3xl mx-auto px-4 flex-grow"
                            >
                                <h2 className="mb-8 sm:mb-10 text-2xl text-center sm:text-4xl dark:text-white text-black font-semibold">
                                    Ask FinSync Anything
                                </h2>
                                <div className='w-full max-w-xl'>
                                    <PlaceholdersAndVanishInput
                                        placeholders={initialPlaceholders}
                                        onChange={handleInputChange}
                                        onSubmit={handleSubmit}
                                    />
                                </div>
                                <div className="mt-10 sm:mt-12 grid grid-cols-1 md:grid-cols-2 gap-3.5 w-full max-w-xl">
                                    <ExamplePromptBox text="What was my total spending last week?" onClick={() => handlePromptClick("What was my total spending last week?")} />
                                    <ExamplePromptBox text="Create a budget for my upcoming vacation." onClick={() => handlePromptClick("Create a budget for my upcoming vacation.")} />
                                    <ExamplePromptBox text="Show transactions over $100 in January." onClick={() => handlePromptClick("Show transactions over $100 in January.")} />
                                    <ExamplePromptBox text="Tips for reducing subscription costs?" onClick={() => handlePromptClick("Tips for reducing subscription costs?")} />
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Active Chat View - Appears after first message */}
                    <div className={`flex flex-col w-full h-full ${chatStarted ? 'opacity-100 visible' : 'opacity-0 invisible hidden'}`}> 
                        {/* Message Log Area */}
                        <motion.div
                            layout
                            className="flex-grow overflow-y-auto py-4 px-10 sm:py-6 sm:px-8 lg:px-24 space-y-6 bg-white"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: chatStarted ? 1 : 0 }}
                            transition={{ delay: chatStarted ? 0.3 : 0, duration: 0.5 }}
                        >
                            {messages.map((msg) => (
                                <motion.div
                                    key={msg.id}
                                    layout
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity:0, y: -5}}
                                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                                >
                                    {msg.sender === 'user' ? (
                                        <UserMessageBubble message={msg} />
                                    ) : (
                                        <AIMessageBubble message={msg} />
                                    )}
                                </motion.div>
                            ))}
                            <div ref={messagesEndRef} />
                        </motion.div>

                        {/* Chat Input Area - Fixed at the bottom */}
                        <motion.div
                            className="bg-white p-3 sm:p-8 w-full mt-auto"
                            initial={{ y: 100, opacity: 0 }}
                            animate={{ y: chatStarted ? 0 : 100, opacity: chatStarted ? 1 : 0 }}
                            transition={{ type: "spring", stiffness: 260, damping: 25, delay: chatStarted ? 0.2 : 0 }}
                        >
                             <div className='w-full max-w-3xl mx-auto'>
                                <PlaceholdersAndVanishInput
                                    placeholders={chatPlaceholders}
                                    onChange={handleInputChange}
                                    onSubmit={handleSubmit}
                                />
                            </div>
                        </motion.div>
                    </div>
                </div>
            </main>
        </div>
    );
};

export default Dashboard; 