import React from 'react';
import BotAvatar from './BotAvatar';
import { ThumbsUp, ThumbsDown, Share, MoreVertical } from 'lucide-react';

const AIMessageBubble = ({ message }) => {
    return (
        <div className="space-y-2">
            <div className="flex items-start gap-3">
                <BotAvatar />
                <div className="bg-background dark:bg-zinc-800/60 text-foreground rounded-2xl rounded-tl-none p-4 px-5 max-w-[80%] shadow-sm border border-border dark:border-zinc-700/80 break-words">
                    {message.text}
                </div>
            </div>
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
        </div>
    );
};

export default AIMessageBubble; 