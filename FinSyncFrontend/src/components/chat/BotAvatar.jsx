import React from 'react';
import { Sparkles } from 'lucide-react';

const BotAvatar = () => (
    <div className="flex-shrink-0 h-8 w-8 rounded-full overflow-hidden bg-blue-100 dark:bg-blue-500/20 flex items-center justify-center">
        <Sparkles className="h-5 w-5 text-blue-500 dark:text-blue-400" />
    </div>
);

export default BotAvatar; 