import React from 'react';

const UserMessageBubble = ({ message }) => {
    return (
        <div className="flex justify-end">
            <div className="bg-gray-200 dark:bg-zinc-700 text-foreground dark:text-zinc-50 rounded-2xl rounded-tr-none p-4 px-5 max-w-[75%] sm:max-w-[70%] shadow-sm break-words">
                {message.text}
            </div>
        </div>
    );
};

export default UserMessageBubble; 