import React, { useState, useEffect, useMemo } from 'react';
import { 
  getMyOrganization, 
  getOrganizationMembers, 
  getOrganizationInvites,
  inviteMember,
  removeMember,
  leaveOrganization,
  createOrganization
} from '../api/organization';
import { getOrganizationIntegrations, disconnectIntegration, initiateZohoBooksOAuth } from '../api/integrations';
import { getCurrentUser } from '../api/auth';
import { 
  Building2, 
  Users, 
  UserPlus, 
  UserMinus, 
  LogOut, 
  AlertTriangle,
  Check,
  X,
  Calendar,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Menu,
  ChevronRight,
  User,
  ShieldCheck,
  Link2
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { Separator } from '../components/ui/separator';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ScrollArea } from '../components/ui/scroll-area';
import { Sidebar } from '../components/sidebar';
import { useWindowWidth } from "@react-hook/window-size";
import { cn } from "../lib/utils";
import { motion } from "framer-motion";
import IntegrationCard from '../components/IntegrationCard';

const Organizations = () => {
  const [organization, setOrganization] = useState(null);
  const [members, setMembers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [integrations, setIntegrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newEmail, setNewEmail] = useState('');
  const [newOrgName, setNewOrgName] = useState('');
  const [isInviteDialogOpen, setIsInviteDialogOpen] = useState(false);
  const [isCreateOrgDialogOpen, setIsCreateOrgDialogOpen] = useState(false);
  const [isLeaveConfirmOpen, setIsLeaveConfirmOpen] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [actionResult, setActionResult] = useState({ type: null, message: null });
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isDisconnectDialogOpen, setIsDisconnectDialogOpen] = useState(false);
  const [selectedIntegration, setSelectedIntegration] = useState(null);
  const onlyWidth = useWindowWidth();
  const mobileWidth = onlyWidth < 768;

  // Fetch organization data
  const fetchOrganizationData = async () => {
    setLoading(true);
    try {
      // Get current user from the API
      const user = await getCurrentUser();
      console.log("Current user data:", user);
      setCurrentUser(user);
      
      // Get organization details
      const orgData = await getMyOrganization();
      console.log("Organization data:", orgData);
      setOrganization(orgData);
      
      // Get organization members
      const membersData = await getOrganizationMembers(orgData);
      console.log("Members data:", membersData);
      setMembers(membersData);
      
      // Get pending invites - still need this for internal use
      const invitesData = await getOrganizationInvites(orgData);
      setInvites(invitesData);
      
      // Get integrations
      try {
        const integrationsData = await getOrganizationIntegrations();
        console.log("Integrations data:", integrationsData);
        setIntegrations(integrationsData);
      } catch (intErr) {
        console.error('Error fetching integrations:', intErr);
        // Don't fail the whole page load if integrations fail
        setIntegrations([]);
      }
      
      setError(null);
    } catch (err) {
      setError('Failed to load organization data. Please try again.');
      console.error('Error fetching organization data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrganizationData();
  }, []);

  useEffect(() => {
    if (mobileWidth) {
      setIsSidebarCollapsed(true);
    }
  }, [mobileWidth]);

  const handleSidebarToggle = (collapsedState) => {
    setIsSidebarCollapsed(collapsedState);
  };

  // Check if the current user is the organization owner - improved detection
  const isOwner = useMemo(() => {
    if (!organization || !currentUser) return false;
    
    // Log IDs for debugging
    console.log("Owner ID:", organization.owner?.id, typeof organization.owner?.id);
    console.log("Current user ID:", currentUser.id, typeof currentUser.id);
    
    // Compare IDs - convert to strings to ensure consistent comparison
    const ownerIdStr = String(organization.owner?.id || '');
    const userIdStr = String(currentUser.id || '');
    
    // Check if the current user is the owner
    const isMatch = ownerIdStr === userIdStr;
    console.log("Is owner match:", isMatch);
    
    return isMatch;
  }, [organization, currentUser]);

  // Fallback method to check if user is owner - in case the above fails
  const isOwnerByEmail = useMemo(() => {
    if (!organization?.owner?.email || !currentUser?.email) return false;
    return organization.owner.email.toLowerCase() === currentUser.email.toLowerCase();
  }, [organization, currentUser]);

  // Use either method to determine owner status
  const userIsOwner = isOwner || isOwnerByEmail;

  // For debugging - log owner status on changes
  useEffect(() => {
    console.log("User is owner:", userIsOwner);
    console.log("Is owner by ID match:", isOwner);
    console.log("Is owner by email match:", isOwnerByEmail);
  }, [userIsOwner, isOwner, isOwnerByEmail]);

  // Handle invite member
  const handleInviteMember = async (e) => {
    e.preventDefault();
    if (!newEmail) return;
    
    try {
      await inviteMember(newEmail, organization);
      await fetchOrganizationData(); // Refresh data
      setNewEmail('');
      setIsInviteDialogOpen(false);
      showActionResult('success', 'Invitation sent successfully');
    } catch (err) {
      showActionResult('error', `Failed to send invitation: ${err.detail || 'Unknown error'}`);
      console.error('Error inviting member:', err);
    }
  };

  // Handle remove member
  const handleRemoveMember = async (userId) => {
    try {
      await removeMember(userId, organization);
      await fetchOrganizationData(); // Refresh data
      showActionResult('success', 'Member removed successfully');
    } catch (err) {
      showActionResult('error', `Failed to remove member: ${err.detail || 'Unknown error'}`);
      console.error('Error removing member:', err);
    }
  };

  // Handle leave organization
  const handleLeaveOrganization = async () => {
    try {
      await leaveOrganization();
      showActionResult('success', 'You have left the organization');
      await fetchOrganizationData(); // Refresh data
      setIsLeaveConfirmOpen(false);
    } catch (err) {
      showActionResult('error', `Failed to leave organization: ${err.detail || 'Unknown error'}`);
      console.error('Error leaving organization:', err);
    }
  };

  // Handle create organization
  const handleCreateOrganization = async (e) => {
    e.preventDefault();
    if (!newOrgName) return;
    
    try {
      await createOrganization({ name: newOrgName });
      await fetchOrganizationData(); // Refresh data
      setNewOrgName('');
      setIsCreateOrgDialogOpen(false);
      showActionResult('success', 'Organization created successfully');
    } catch (err) {
      showActionResult('error', `Failed to create organization: ${err.detail || 'Unknown error'}`);
      console.error('Error creating organization:', err);
    }
  };

  // Show action result message
  const showActionResult = (type, message) => {
    setActionResult({ type, message });
    // Auto hide after 5 seconds
    setTimeout(() => {
      setActionResult({ type: null, message: null });
    }, 5000);
  };

  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString();
  };

  // Handle connect to integration
  const handleConnectIntegration = async (provider) => {
    try {
      if (provider === 'zohobooks') {
        const response = await initiateZohoBooksOAuth();
        // Redirect to OAuth URL
        if (response && response.authorization_url) {
          window.location.href = response.authorization_url;
        }
      }
      // Add other providers as needed
    } catch (err) {
      console.error(`Failed to connect to ${provider}:`, err);
      showActionResult('error', `Failed to connect to ${provider}. Please try again.`);
    }
  };

  // Handle disconnect integration
  const handleDisconnectIntegration = (integration) => {
    setSelectedIntegration(integration);
    setIsDisconnectDialogOpen(true);
  };

  // Confirm and execute integration disconnection
  const confirmDisconnectIntegration = async () => {
    if (!selectedIntegration) return;
    
    try {
      await disconnectIntegration(selectedIntegration.id);
      
      // Update local state by removing the disconnected integration
      setIntegrations(prev => prev.filter(item => item.id !== selectedIntegration.id));
      
      showActionResult('success', `Successfully disconnected from ${selectedIntegration.provider_display}.`);
    } catch (err) {
      console.error('Error disconnecting integration:', err);
      showActionResult('error', 'Failed to disconnect integration. Please try again.');
    } finally {
      setIsDisconnectDialogOpen(false);
      setSelectedIntegration(null);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen bg-background">
        <Sidebar isCollapsed={isSidebarCollapsed} onCollapseChange={handleSidebarToggle} />
        <main 
          className={cn(
            "flex-1 flex flex-col overflow-hidden transition-all duration-300 ease-in-out",
            mobileWidth ? "pt-0" : (isSidebarCollapsed ? "ml-[70px]" : "ml-64")
          )}
        >
          <div className="flex-1 flex justify-center items-center">
            <RefreshCw className="h-8 w-8 animate-spin text-primary mb-4" />
            <p className="text-lg ml-3">Loading organization data...</p>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-background">
      <Sidebar isCollapsed={isSidebarCollapsed} onCollapseChange={handleSidebarToggle} />
      <main 
        className={cn(
          "flex-1 overflow-auto transition-all duration-300 ease-in-out",
          mobileWidth ? "pt-0" : (isSidebarCollapsed ? "ml-[70px]" : "ml-64")
        )}
      >
        {/* Header for Mobile */}
        <header className={cn(
          "sticky top-0 z-30 flex items-center justify-between h-[60px] border-b bg-background px-4 sm:px-6",
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
              Organization
            </h1>
          )}
        </header>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Status message */}
          {actionResult.message && (
            <motion.div 
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className={`mb-6 flex items-center rounded-lg border p-4 shadow-sm ${
                actionResult.type === 'success' ? 'bg-green-50 border-green-200 text-green-700' : 'bg-red-50 border-red-200 text-red-700'
              }`}
            >
              {actionResult.type === 'success' ? 
                <Check className="h-5 w-5 mr-3" /> : 
                <AlertTriangle className="h-5 w-5 mr-3" />
              }
              <span className="font-medium">{actionResult.message}</span>
              <button 
                className="ml-auto text-gray-500 hover:text-gray-700 transition-colors rounded-full hover:bg-gray-100 p-1"
                onClick={() => setActionResult({ type: null, message: null })}
              >
                <X className="h-4 w-4" />
              </button>
            </motion.div>
          )}

          {/* Organization Header with Actions */}
          <div className="flex flex-col space-y-4 sm:flex-row sm:justify-between sm:items-center mb-8">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">
                <span className="flex items-center">
                  <Building2 className="inline-block h-8 w-8 text-primary mr-3" />
                  Organization
                </span>
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Manage your organization members and settings
              </p>
            </div>
            
            <div className="flex flex-wrap gap-3 mt-4 sm:mt-0">
              {userIsOwner && (
                <Dialog open={isInviteDialogOpen} onOpenChange={setIsInviteDialogOpen}>
                  <DialogTrigger asChild>
                    <Button className="flex items-center gap-2 shadow-sm">
                      <UserPlus className="h-4 w-4" />
                      <span>Invite Member</span>
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Invite New Member</DialogTitle>
                      <DialogDescription>
                        Send an invitation to join your organization.
                      </DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleInviteMember}>
                      <div className="grid gap-4 py-4">
                        <div className="grid gap-2">
                          <Label htmlFor="email">Email address</Label>
                          <Input
                            id="email"
                            type="email"
                            value={newEmail}
                            onChange={(e) => setNewEmail(e.target.value)}
                            placeholder="colleague@example.com"
                            required
                          />
                        </div>
                      </div>
                      <DialogFooter>
                        <Button type="button" variant="outline" onClick={() => setIsInviteDialogOpen(false)}>
                          Cancel
                        </Button>
                        <Button type="submit">Send Invitation</Button>
                      </DialogFooter>
                    </form>
                  </DialogContent>
                </Dialog>
              )}
              
              <Dialog open={isCreateOrgDialogOpen} onOpenChange={setIsCreateOrgDialogOpen}>
                <DialogTrigger asChild>
                  <Button variant="outline" className="flex items-center gap-2 shadow-sm">
                    <Plus className="h-4 w-4" />
                    <span>Create New Organization</span>
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Create New Organization</DialogTitle>
                    <DialogDescription>
                      Create a new organization. You will be set as the owner.
                    </DialogDescription>
                  </DialogHeader>
                  <form onSubmit={handleCreateOrganization}>
                    <div className="grid gap-4 py-4">
                      <div className="grid gap-2">
                        <Label htmlFor="orgName">Organization Name</Label>
                        <Input
                          id="orgName"
                          value={newOrgName}
                          onChange={(e) => setNewOrgName(e.target.value)}
                          placeholder="My New Organization"
                          required
                        />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button type="button" variant="outline" onClick={() => setIsCreateOrgDialogOpen(false)}>
                        Cancel
                      </Button>
                      <Button type="submit">Create</Button>
                    </DialogFooter>
                  </form>
                </DialogContent>
              </Dialog>
              
              <Dialog open={isLeaveConfirmOpen} onOpenChange={setIsLeaveConfirmOpen}>
                <DialogTrigger asChild>
                  <Button variant="destructive" className="flex items-center gap-2 shadow-sm">
                    <LogOut className="h-4 w-4" />
                    <span>Leave Organization</span>
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Leave Organization</DialogTitle>
                    <DialogDescription>
                      Are you sure you want to leave this organization? You will be moved to a new personal workspace.
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter className="mt-4">
                    <Button type="button" variant="outline" onClick={() => setIsLeaveConfirmOpen(false)}>
                      Cancel
                    </Button>
                    <Button variant="destructive" onClick={handleLeaveOrganization}>
                      Leave Organization
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </div>
          
          {/* Organization Details */}
          {organization ? (
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="grid gap-6 mb-10"
            >
              <div className="bg-card rounded-xl border shadow-sm overflow-hidden">
                <div className="flex items-center justify-between border-b p-6">
                  <div className="flex items-center">
                    <div className="rounded-lg bg-primary/10 p-3 mr-4">
                      <Building2 className="h-6 w-6 text-primary" />
                    </div>
                    <div>
                      <h2 className="text-xl font-semibold">{organization.name}</h2>
                      <p className="text-sm text-muted-foreground mt-1">
                        {organization.domain ? organization.domain : "Personal workspace"}
                      </p>
                    </div>
                  </div>
                  {userIsOwner && (
                    <span className="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-medium bg-primary/10 text-primary">
                      <ShieldCheck className="h-3.5 w-3.5 mr-1.5" />
                      Admin
                    </span>
                  )}
                </div>
                
                <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div>
                    <h3 className="text-sm font-medium text-muted-foreground mb-4 uppercase tracking-wider">Organization Details</h3>
                    <dl className="space-y-4">
                      <div className="flex justify-between">
                        <dt className="text-sm font-medium text-muted-foreground">Domain</dt>
                        <dd className="text-sm">{organization.domain || 'Not set'}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-sm font-medium text-muted-foreground">Created</dt>
                        <dd className="text-sm">{formatDate(organization.created_at)}</dd>
                      </div>
                      <div className="flex justify-between items-center">
                        <dt className="text-sm font-medium text-muted-foreground">Owner</dt>
                        <dd className="text-sm flex items-center">
                          <Avatar className="h-5 w-5 mr-2">
                            <AvatarFallback className="text-xs">{organization.owner.email.charAt(0).toUpperCase()}</AvatarFallback>
                          </Avatar>
                          {organization.owner.email}
                        </dd>
                      </div>
                    </dl>
                  </div>
                  
                  <div>
                    <h3 className="text-sm font-medium text-muted-foreground mb-4 uppercase tracking-wider">Subscription</h3>
                    <dl className="space-y-4">
                      <div className="flex justify-between items-center">
                        <dt className="text-sm font-medium text-muted-foreground">Plan</dt>
                        <dd>
                          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary">
                            {organization.subscription_plan?.display_name || 'Not set'}
                          </span>
                        </dd>
                      </div>
                      <div className="flex justify-between items-center">
                        <dt className="text-sm font-medium text-muted-foreground">Status</dt>
                        <dd>
                          <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                            organization.subscription_status === 'active' ? 'bg-green-100 text-green-800' :
                            organization.subscription_status === 'trialing' ? 'bg-blue-100 text-blue-800' :
                            'bg-amber-100 text-amber-800'
                          }`}>
                            {organization.subscription_status || 'Not set'}
                          </span>
                        </dd>
                      </div>
                      {organization.subscription_status === 'trialing' && (
                        <div className="flex justify-between items-center">
                          <dt className="text-sm font-medium text-muted-foreground">Trial ends</dt>
                          <dd className="text-sm flex items-center">
                            <Calendar className="h-3.5 w-3.5 mr-1.5 text-amber-500" />
                            {formatDate(organization.trial_ends_at)}
                          </dd>
                        </div>
                      )}
                    </dl>
                  </div>
                </div>
              </div>
              
              {/* New Integrations Section */}
              <div className="bg-card rounded-xl border shadow-sm overflow-hidden">
                <div className="flex items-center justify-between border-b p-6">
                  <div className="flex items-center">
                    <div className="rounded-lg bg-primary/10 p-3 mr-4">
                      <Link2 className="h-6 w-6 text-primary" />
                    </div>
                    <div>
                      <h2 className="text-xl font-semibold">Integrations</h2>
                      <p className="text-sm text-muted-foreground mt-1">
                        Connect to your financial services
                      </p>
                    </div>
                  </div>
                </div>
                
                <div className="p-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {/* Zoho Books Integration */}
                    {(() => {
                      const zohoIntegration = integrations.find(i => i.provider === 'zohobooks');
                      return (
                        <IntegrationCard
                          integration={zohoIntegration}
                          provider="zohobooks"
                          name="Zoho Books"
                          iconSrc="/icons/zohobooks.svg"
                          status="available"
                          onConnect={handleConnectIntegration}
                          onDisconnect={handleDisconnectIntegration}
                        />
                      );
                    })()}
                    
                    {/* QuickBooks Integration - Coming Soon */}
                    <IntegrationCard
                      provider="quickbooks"
                      name="QuickBooks"
                      iconSrc="/icons/quickbooks.svg"
                      status="coming-soon"
                    />
                    
                    {/* Xero Integration - Coming Soon */}
                    <IntegrationCard
                      provider="xero"
                      name="Xero"
                      iconSrc="/icons/xero.svg"
                      status="coming-soon"
                    />
                  </div>
                </div>
              </div>

              {/* Disconnect Integration Dialog */}
              <Dialog open={isDisconnectDialogOpen} onOpenChange={setIsDisconnectDialogOpen}>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Disconnect Integration</DialogTitle>
                    <DialogDescription>
                      Are you sure you want to disconnect from {selectedIntegration?.provider_display}? 
                      This will remove all associated data and settings.
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter className="mt-6">
                    <Button
                      variant="outline"
                      onClick={() => setIsDisconnectDialogOpen(false)}
                      className="mr-2"
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={confirmDisconnectIntegration}
                    >
                      Disconnect
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>

              {/* Members Section */}
              <div className="bg-card rounded-xl border shadow-sm overflow-hidden">
                <div className="p-6 border-b flex justify-between items-center">
                  <div className="flex items-center">
                    <div className="rounded-lg bg-primary/10 p-2 mr-3">
                      <Users className="h-5 w-5 text-primary" />
                    </div>
                    <h2 className="text-lg font-semibold">Members</h2>
                  </div>
                  <span className="text-sm px-2.5 py-1 bg-gray-100 rounded-full text-muted-foreground">
                    {members.length} {members.length === 1 ? 'member' : 'members'}
                  </span>
                </div>
                
                <ScrollArea className="h-[340px]">
                  <div>
                    {members.length > 0 ? (
                      members.map((member, index) => (
                        <motion.div 
                          key={member.id}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: index * 0.05, duration: 0.2 }}
                          className={`flex items-center justify-between py-4 px-6 hover:bg-muted/50 transition-colors ${
                            index !== members.length - 1 ? 'border-b' : ''
                          }`}
                        >
                          <div className="flex items-center">
                            <Avatar className="h-10 w-10 mr-4 border shadow-sm">
                              <AvatarFallback className="font-semibold">{member.email.charAt(0).toUpperCase()}</AvatarFallback>
                            </Avatar>
                            <div>
                              <p className="font-medium">
                                {member.first_name && member.last_name 
                                  ? `${member.first_name} ${member.last_name}` 
                                  : member.email}
                              </p>
                              <p className="text-sm text-muted-foreground">{member.email}</p>
                            </div>
                            {organization && organization.owner && member.id === organization.owner.id && (
                              <span className="ml-3 px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary flex items-center">
                                <ShieldCheck className="h-3 w-3 mr-1" />
                                Owner
                              </span>
                            )}
                          </div>
                          
                          {userIsOwner && member.id !== currentUser?.id && (
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full hover:bg-gray-100">
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-48">
                                <DropdownMenuItem 
                                  className="text-red-600 focus:text-red-600 cursor-pointer"
                                  onClick={() => handleRemoveMember(member.id)}
                                >
                                  <UserMinus className="h-4 w-4 mr-2" />
                                  <span>Remove member</span>
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          )}
                        </motion.div>
                      ))
                    ) : (
                      <div className="p-8 text-center">
                        <User className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
                        <p className="text-muted-foreground">No members found.</p>
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </div>
            </motion.div>
          ) : (
            <div className="bg-card rounded-xl border shadow-sm p-8 mb-6 text-center">
              <AlertTriangle className="h-12 w-12 text-amber-500 mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-2">Could not load organization details</h3>
              <p className="text-muted-foreground mb-4">There was a problem retrieving your organization information.</p>
              <Button 
                variant="outline" 
                onClick={fetchOrganizationData}
                className="mx-auto"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Retry
              </Button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default Organizations; 