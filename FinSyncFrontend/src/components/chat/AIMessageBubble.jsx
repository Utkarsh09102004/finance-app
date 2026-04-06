import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import BotAvatar from './BotAvatar';
import { ThumbsUp, ThumbsDown, Share, MoreVertical } from 'lucide-react';

const markdownComponents = {
    h1: ({ children }) => <h1 className="text-xl font-semibold mb-2">{children}</h1>,
    h2: ({ children }) => <h2 className="text-lg font-semibold mt-4 mb-2">{children}</h2>,
    h3: ({ children }) => <h3 className="text-base font-semibold mt-3 mb-1">{children}</h3>,
    p: ({ children }) => <p className="text-sm leading-relaxed mb-2 last:mb-0">{children}</p>,
    ul: ({ children }) => <ul className="list-disc pl-5 space-y-1 mb-2">{children}</ul>,
    ol: ({ children }) => <ol className="list-decimal pl-5 space-y-1 mb-2">{children}</ol>,
    li: ({ children }) => <li className="text-sm leading-relaxed">{children}</li>,
    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
    em: ({ children }) => <em className="italic">{children}</em>,
    blockquote: ({ children }) => (
        <blockquote className="border-l-4 border-muted pl-3 italic text-sm text-muted-foreground">{children}</blockquote>
    ),
    code: ({ children }) => (
        <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{children}</code>
    ),
};

const AIMessageBubble = ({ message }) => {
    const bubbleClasses = message.isError
        ? 'bg-red-50 text-red-900 border-red-200 dark:bg-red-950/50 dark:text-red-100 dark:border-red-900'
        : 'bg-background dark:bg-zinc-800/60 text-foreground border border-border dark:border-zinc-700/80';

    return (
        <div className="space-y-2">
            <div className="flex items-start gap-3">
                <BotAvatar />
                <div className={`rounded-2xl rounded-tl-none p-4 px-5 max-w-[80%] shadow-sm break-words ${bubbleClasses}`}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                        {message.text || ''}
                    </ReactMarkdown>
                </div>
            </div>
            {!message.isError && (
                <div className="flex items-center gap-2 pl-11 text-muted-foreground">
                    <button className="p-1.5 hover:bg-muted dark:hover:bg-zinc-700/50 rounded-full transition-colors">
                        <ThumbsUp className="h-4 w-4" />
                    </button>
                    <button className="p-1.5 hover:bg-muted dark:hover:bg-zinc-700/50 rounded-full transition-colors">
                        <ThumbsDown className="h-4 w-4" />
                    </button>
                    <button className="p-1.5 hover:bg-muted dark:hover:bg-zinc-700/50 rounded-full transition-colors">
                        <Share className="h-4 w-4" />
                    </button>
                    <button className="p-1.5 hover:bg-muted dark:hover:bg-zinc-700/50 rounded-full transition-colors">
                        <MoreVertical className="h-4 w-4" />
                    </button>
                </div>
            )}
        </div>
    );
};

export default AIMessageBubble; 
