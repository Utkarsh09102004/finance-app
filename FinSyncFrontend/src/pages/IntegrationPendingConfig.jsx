import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Building2, CheckCircle2, RefreshCw, AlertCircle, ArrowLeft } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../components/ui/card';
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group';
import { Label } from '../components/ui/label';
import { Sidebar } from '../components/sidebar';
import { cn } from '../lib/utils';
import { useWindowWidth } from '@react-hook/window-size';
import { motion } from 'framer-motion';
import { 
  getIntegration, 
  updateIntegration, 
  fetchExternalOrganizations, 
  setExternalOrganization 
} from '../api/integrations';

const IntegrationPendingConfig = () => {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [integration, setIntegration] = useState(null);
  const [externalOrgs, setExternalOrgs] = useState([]);
  const [selectedOrgId, setSelectedOrgId] = useState('');
  const [configuring, setConfiguring] = useState(false);
  const [configSuccess, setConfigSuccess] = useState(false);
  
  const navigate = useNavigate();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const integrationId = searchParams.get('integration_id');
  const provider = searchParams.get('provider');
  
  const onlyWidth = useWindowWidth();
  const mobileWidth = onlyWidth < 768;

  const handleSidebarToggle = (collapsedState) => {
    setIsSidebarCollapsed(collapsedState);
  };

  useEffect(() => {
    if (mobileWidth) {
      setIsSidebarCollapsed(true);
    }
  }, [mobileWidth]);

  useEffect(() => {
    const loadIntegration = async () => {
      setLoading(true);
      try {
        if (!integrationId || !provider) {
          throw new Error('Missing integration ID or provider');
        }

        // 1. Load the integration details
        const integrationData = await getIntegration(integrationId);
        setIntegration(integrationData);


        // 2. Fetch external organizations based on provider
        const orgsData = await fetchExternalOrganizations(integrationId, provider);
        setExternalOrgs(orgsData || []);



        // If there's only one org, pre-select it
        if (orgsData.length === 1) {
          setSelectedOrgId(orgsData[0].id);
        }
        
        setError(null);
      } catch (err) {
        console.error('Error loading integration data:', err);
        setError(err.message || 'Failed to load integration details');
      } finally {
        setLoading(false);
      }
    };

    loadIntegration();
  }, [integrationId, provider]);

  const handleConfirmSelection = async () => {
    if (!selectedOrgId) return;
    
    setConfiguring(true);
    try {
      // Update the integration with the selected external organization ID
      await setExternalOrganization(integrationId, provider, selectedOrgId);
      
      // Update the name to the selected organization's name
      const selectedOrg = externalOrgs.find(org => org.id === selectedOrgId);
      if (selectedOrg) {
        await updateIntegration(integrationId, {
          name: selectedOrg.name,
          external_id: selectedOrgId
        });
      }
      
      setConfigSuccess(true);
      
      // Redirect after 2 seconds
      setTimeout(() => {
        navigate('/organizations');
      }, 2000);
    } catch (err) {
      console.error('Error configuring integration:', err);
      setError(err.message || 'Failed to configure integration');
    } finally {
      setConfiguring(false);
    }
  };

  const handleCancel = () => {
    navigate('/organizations');
  };

  const getProviderDisplayName = () => {
    switch (provider) {
      case 'zohobooks':
        return 'Zoho Books';
      case 'quickbooks':
        return 'QuickBooks';
      default:
        return 'External Service';
    }
  };

  return (
    <div className="flex h-screen bg-background">
      <Sidebar isCollapsed={isSidebarCollapsed} onCollapseChange={handleSidebarToggle} />
      <main 
        className={cn(
          "flex-1 overflow-auto transition-all duration-300 ease-in-out",
          mobileWidth ? "pt-0" : (isSidebarCollapsed ? "ml-[70px]" : "ml-64")
        )}
      >
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
          <Button 
            variant="ghost" 
            className="mb-6 -ml-2 flex items-center text-muted-foreground hover:text-foreground"
            onClick={handleCancel}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Organization
          </Button>
          
          <Card className="shadow-md">
            <CardHeader>
              <div className="flex items-center mb-4">
                <div className="rounded-lg bg-primary/10 p-3 mr-4">
                  <Building2 className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <CardTitle>Complete Your {getProviderDisplayName()} Integration</CardTitle>
                  <CardDescription>
                    {provider === 'zohobooks' 
                      ? 'Select the Zoho Books organization you want to connect with'
                      : 'Configure your integration'
                    }
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            
            <CardContent>
              {loading ? (
                <div className="flex justify-center py-8">
                  <RefreshCw className="h-6 w-6 animate-spin text-primary" />
                  <span className="ml-3">Loading integration details...</span>
                </div>
              ) : error ? (
                <div className="bg-red-50 text-red-700 p-4 rounded-lg flex items-start">
                  <AlertCircle className="h-5 w-5 mr-3 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="font-medium">Configuration Error</p>
                    <p className="mt-1 text-sm">{error}</p>
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="mt-3" 
                      onClick={handleCancel}
                    >
                      Return to Organization
                    </Button>
                  </div>
                </div>
              ) : configSuccess ? (
                <motion.div 
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="py-8 text-center"
                >
                  <CheckCircle2 className="h-12 w-12 text-green-500 mx-auto mb-4" />
                  <h3 className="text-lg font-medium mb-2">Integration Configured Successfully!</h3>
                  <p className="text-muted-foreground">Redirecting you back to your organization...</p>
                </motion.div>
              ) : (
                <div>
                  {provider === 'zohobooks' && (
                    <>
                      <p className="mb-4">
                        Your Zoho Books account has been connected. Please select which Zoho Books organization 
                        you want to sync with FinSync:
                      </p>
                      
                      {externalOrgs.length > 0 ? (
                        <RadioGroup value={selectedOrgId} onValueChange={setSelectedOrgId} className="mt-5">
                          {externalOrgs.map(org => (
                            <div key={org.id} className="flex items-center space-x-2 my-3 border rounded-md p-3 hover:bg-muted transition-colors cursor-pointer">
                              <RadioGroupItem value={org.id} id={org.id} />
                              <Label htmlFor={org.id} className="flex-1 cursor-pointer">
                                <span className="font-medium">{org.name}</span>
                                {org.additional_info && (
                                  <span className="text-sm text-muted-foreground block mt-0.5">
                                    {org.additional_info}
                                  </span>
                                )}
                              </Label>
                            </div>
                          ))}
                        </RadioGroup>
                      ) : (
                        <div className="bg-yellow-50 text-yellow-700 p-4 rounded-lg text-sm">
                          No organizations found in your Zoho Books account. Please ensure you have at least one organization 
                          created in Zoho Books before connecting.
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </CardContent>
            
            <CardFooter className="flex justify-end gap-3 pt-6 border-t">
              <Button 
                variant="outline" 
                onClick={handleCancel}
                disabled={configuring || configSuccess}
              >
                Cancel
              </Button>
              <Button 
                onClick={handleConfirmSelection}
                disabled={!selectedOrgId || configuring || configSuccess || externalOrgs.length === 0}
                className="ml-3"
              >
                {configuring ? (
                  <>
                    <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                    Configuring...
                  </>
                ) : 'Confirm Selection'}
              </Button>
            </CardFooter>
          </Card>
        </div>
      </main>
    </div>
  );
};

export default IntegrationPendingConfig; 