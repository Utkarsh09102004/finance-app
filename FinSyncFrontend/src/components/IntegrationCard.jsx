import React from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, RefreshCw, X } from 'lucide-react';
import { Button } from './ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import { motion } from 'framer-motion';
import { cn } from '../lib/utils';

export const IntegrationCard = ({ 
  integration = null, 
  provider, 
  name, 
  iconSrc, 
  status = 'coming-soon',
  onDisconnect = () => {},
  onConnect = () => {} 
}) => {
  const isConnected = integration && integration.connection_status === 'Connected';
  const needsReauth = integration && integration.connection_status === 'NeedsReauth';
  const isComingSoon = status === 'coming-soon';
  const isAvailable = status === 'available';
  
  const getStatusColor = () => {
    if (isConnected) return 'bg-green-100 text-green-800';
    if (needsReauth) return 'bg-amber-100 text-amber-800';
    if (isComingSoon) return 'bg-blue-100 text-blue-800';
    return 'bg-gray-100 text-gray-800';
  };
  
  const getStatusText = () => {
    if (isConnected) return 'Connected';
    if (needsReauth) return 'Needs Reauthorization';
    if (isComingSoon) return 'Coming Soon';
    return 'Available';
  };
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="bg-card border rounded-lg shadow-sm p-5 relative overflow-hidden"
    >
      {/* Badge in corner */}
      <div className={cn("absolute top-0 right-0 px-2 py-1 text-xs font-medium rounded-bl", getStatusColor())}>
        {getStatusText()}
      </div>
      
      <div className="flex items-start mb-4">
        <div className="w-14 h-14 rounded-md flex items-center justify-center border shadow-sm mr-4">
          {iconSrc ? (
            <img src={iconSrc} alt={`${name} logo`} className="w-10 h-10 object-contain" />
          ) : (
            <div className="w-10 h-10 bg-primary/10 rounded-md flex items-center justify-center">
              <span className="font-bold text-primary text-lg">{name.charAt(0)}</span>
            </div>
          )}
        </div>
        
        <div className="flex-1">
          <h3 className="text-lg font-medium">{name}</h3>
          <p className="text-sm text-muted-foreground mt-1">
            {integration ? (
              <>
                {integration.name || 'Default Connection'}
                {integration.external_id && (
                  <span className="block text-xs text-muted-foreground mt-1">
                    ID: {integration.external_id.substring(0, 12)}...
                  </span>
                )}
              </>
            ) : (
              isComingSoon ?
                'This integration will be available soon.' :
                'Connect to sync your financial data.'
            )}
          </p>
        </div>
      </div>
      
      <div className="flex flex-wrap gap-2 mt-4">
        {isConnected && (
          <>
            <Button 
              variant="outline" 
              size="sm" 
              className="text-xs"
              asChild
            >
              <Link to={`/integrations/${provider}`} className="flex items-center gap-1">
                <ExternalLink className="h-3 w-3" />
                Manage
              </Link>
            </Button>
            
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="text-xs"
                    onClick={() => onDisconnect(integration)}
                  >
                    <X className="h-3 w-3 mr-1" />
                    Disconnect
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Disconnect this integration</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </>
        )}
        
        {needsReauth && (
          <Button 
            variant="outline" 
            size="sm" 
            className="text-xs text-amber-600 border-amber-200 bg-amber-50 hover:bg-amber-100"
            onClick={() => onConnect(provider)}
          >
            <RefreshCw className="h-3 w-3 mr-1" />
            Reauthorize
          </Button>
        )}
        
        {!integration && !isComingSoon && isAvailable && (
          <Button 
            variant="default" 
            size="sm" 
            className="text-xs w-full"
            onClick={() => onConnect(provider)}
          >
            Connect
          </Button>
        )}
        
        {isComingSoon && (
          <Button 
            variant="outline" 
            size="sm" 
            className="text-xs w-full"
            disabled
          >
            Coming Soon
          </Button>
        )}
      </div>
    </motion.div>
  );
};

export default IntegrationCard; 