// app.js - Shared logic for index.html and configure_zoho.html

// DOMContentLoaded ensures scripts run after the HTML is fully parsed.
// Specific page initializations will be called within this.

document.addEventListener('DOMContentLoaded', () => {
    if (!checkAuth()) return; // checkAuth from auth.js handles redirection if needed

    // Page-specific initializations
    if (document.getElementById('zohoIntegrationSection')) {
        initIndexPage();
    }
    if (document.getElementById('zohoOrgConfigurationSection')) {
        initConfigureZohoPage();
    }

    const logoutBtn = document.getElementById('logoutButton');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logoutUser);
    }
});

function displayStatusMessage(elementId, message, isSuccess) {
    const el = document.getElementById(elementId);
    if (el) {
        el.textContent = message;
        el.className = 'status-message';
        if (message) {
            el.classList.add(isSuccess ? 'success' : 'error');
        } else {
            el.textContent = '';
        }
    }
}

// --- Index Page Specific Logic (index.html) ---
async function initIndexPage() {
    handleOAuthRedirectMessages();
    await loadZohoIntegrationStatus();

    const connectZohoButton = document.getElementById('connectZohoButton');
    if (connectZohoButton) {
        connectZohoButton.addEventListener('click', initiateZohoOAuth);
    }
}

function handleOAuthRedirectMessages() {
    const urlParams = new URLSearchParams(window.location.search);
    const status = urlParams.get('status');
    const error = urlParams.get('error');
    const provider = urlParams.get('provider');

    if (status === 'success' && provider === 'zohobooks') {
        displayStatusMessage('pageStatus', 'Zoho Books connection process initiated successfully!', true);
    } else if (status === 'failure') {
        displayStatusMessage('pageStatus', `Zoho Books connection failed. Error: ${error || 'Unknown error'}`, false);
    }

    if (status || error) {
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

async function loadZohoIntegrationStatus() {
    const statusEl = document.getElementById('zohoStatus');
    const actionButton = document.getElementById('connectZohoButton');
    const configInfoEl = document.getElementById('zohoConfigInfo');

    if (!statusEl || !actionButton || !configInfoEl) return;

    statusEl.textContent = 'Loading status...';
    actionButton.classList.add('hidden');
    configInfoEl.classList.add('hidden');
    configInfoEl.innerHTML = '';

    try {
        const response = await authorizedFetch(`${BACKEND_URL}/api/integrations/`);

        if (!response.ok) {
            if (response.status === 401) {
                statusEl.textContent = 'Session expired or unauthorized.';
                actionButton.textContent = 'Login Required';
                actionButton.onclick = () => window.location.href = 'login.html';
                actionButton.classList.remove('hidden');
            } else {
                const errorData = await response.json().catch(() => ({ detail: "Failed to load integrations." }));
                throw new Error(errorData.detail || `Server error: ${response.status}`);
            }
            return;
        }

        const integrations = await response.json();
        const zohoIntegration = integrations.find(int => int.provider === 'zohobooks');

        if (zohoIntegration) {
            statusEl.className = 'integration-status';
            switch (zohoIntegration.connection_status) {
                case 'Connected':
                    statusEl.innerHTML = `Status: <span class="connected">Connected</span> (ID: ${zohoIntegration.external_id || 'N/A'})`;
                    actionButton.textContent = 'Disconnect Zoho (Not Implemented)';
                    actionButton.classList.remove('hidden');
                    actionButton.disabled = true;
                    break;
                case 'PendingExternalID':
                    statusEl.innerHTML = 'Status: <span class="pending-config">Pending Configuration</span>';
                    actionButton.textContent = 'Configure Zoho Organization';
                    actionButton.onclick = () => window.location.href = `configure_zoho.html?integration_id=${zohoIntegration.id}`;
                    actionButton.classList.remove('hidden');
                    actionButton.disabled = false;
                    break;
                case 'NeedsReauth':
                    statusEl.innerHTML = 'Status: <span class="needs-reauth">Needs Reauthorization</span>';
                    actionButton.textContent = 'Reauthorize Zoho Books';
                    actionButton.onclick = initiateZohoOAuth;
                    actionButton.classList.remove('hidden');
                    actionButton.disabled = false;
                    configInfoEl.textContent = zohoIntegration.last_sync_error || "Your connection needs to be refreshed.";
                    configInfoEl.classList.remove('hidden');
                    break;
                default:
                    statusEl.textContent = `Status: ${zohoIntegration.connection_status}`;
                    actionButton.textContent = 'Connect to Zoho Books';
                    actionButton.onclick = initiateZohoOAuth;
                    actionButton.classList.remove('hidden');
                    actionButton.disabled = false;
                    if (zohoIntegration.last_sync_error) {
                        configInfoEl.textContent = `Error: ${zohoIntegration.last_sync_error}`;
                        configInfoEl.classList.remove('hidden');
                    }
            }
        } else {
            statusEl.textContent = 'Status: Not Connected';
            actionButton.textContent = 'Connect to Zoho Books';
            actionButton.onclick = initiateZohoOAuth;
            actionButton.classList.remove('hidden');
            actionButton.disabled = false;
        }
    } catch (error) {
        console.error('Error loading Zoho integration status:', error);
        statusEl.textContent = 'Error loading status: ' + error.message;
        actionButton.textContent = 'Retry Connection';
        actionButton.onclick = initiateZohoOAuth;
        actionButton.classList.remove('hidden');
        actionButton.disabled = false;
    }
}

async function initiateZohoOAuth() {
    displayStatusMessage('pageStatus', 'Initiating Zoho Books connection...', true);
    const actionButton = document.getElementById('connectZohoButton');
    actionButton.disabled = true;

    try {
        const response = await authorizedFetch(`${BACKEND_URL}/api/integrations/zohobooks/initiate/`);
        const data = await response.json();

        if (!response.ok) {
            if (response.status === 401 && data.error === 'reauthorization_required') {
                displayStatusMessage('pageStatus', data.detail || 'Reauthorization required. Please click again.', false);
                document.getElementById('zohoStatus').innerHTML = 'Status: <span class="needs-reauth">Needs Reauthorization</span>';
                actionButton.textContent = 'Reauthorize Zoho Books';
                actionButton.disabled = false;
            } else if (response.status === 403) {
                displayStatusMessage('pageStatus', data.error || 'Cannot add more integrations.', false);
                actionButton.disabled = true;
            } else {
                throw new Error(data.error || data.detail || 'Failed to initiate OAuth flow');
            }
        } else if (data.authorization_url) {
            window.location.href = data.authorization_url;
        } else {
            throw new Error('Authorization URL not received from backend.');
        }
    } catch (error) {
        console.error('OAuth initiation error:', error);
        displayStatusMessage('pageStatus', 'Error: ' + error.message, false);
        actionButton.disabled = false;
    }
}

// --- Configure Zoho Page Specific Logic (configure_zoho.html) ---
let currentIntegrationId = null;

async function initConfigureZohoPage() {
    const urlParams = new URLSearchParams(window.location.search);
    currentIntegrationId = urlParams.get('integration_id');
    const provider = urlParams.get('provider');

    if (!currentIntegrationId || provider !== 'zohobooks') {
        displayStatusMessage('configStatus', 'Error: Missing integration ID or invalid provider for configuration.', false);
        document.getElementById('zohoOrgForm').classList.add('hidden');
        return;
    }

    document.getElementById('integrationIdDisplay').textContent = currentIntegrationId;
    await fetchZohoOrganizations();

    document.getElementById('zohoOrgForm').addEventListener('submit', setZohoOrganization);
}

async function fetchZohoOrganizations() {
    const orgSelect = document.getElementById('zohoOrgSelect');
    const loadingEl = document.getElementById('loadingOrgsMessage');
    orgSelect.innerHTML = '';
    orgSelect.disabled = true;
    loadingEl.classList.remove('hidden');

    try {
        const response = await authorizedFetch(`${BACKEND_URL}/api/integrations/zohobooks/${currentIntegrationId}/fetch-external-organizations/`);
        const data = await response.json();

        if (!response.ok) {
            if (response.status === 401 && data.error === 'reauthorization_required') {
                displayStatusMessage('configStatus',
                    `Your session with Zoho needs reauthorization. <a href="#" onclick="reauthFromConfigPage('${currentIntegrationId}')">Reauthorize Zoho</a> and then return to this page.`,
                    false);
                document.getElementById('zohoOrgForm').classList.add('hidden');
            } else {
                throw new Error(data.error || data.detail || 'Failed to fetch Zoho organizations');
            }
            loadingEl.classList.add('hidden');
            return;
        }

        if (data.length === 0) {
            displayStatusMessage('configStatus', 'No organizations found in your Zoho Books account, or you might not have permission to access them.', false);
            orgSelect.innerHTML = '<option value="">No organizations found</option>';
        } else {
            data.forEach(org => {
                const option = document.createElement('option');
                option.value = org.id;
                option.textContent = `${org.name} (ID: ${org.id})`;
                orgSelect.appendChild(option);
            });
            orgSelect.disabled = false;
            displayStatusMessage('configStatus', '', true);
        }
    } catch (error) {
        console.error('Fetch Zoho Orgs Error:', error);
        displayStatusMessage('configStatus', 'Error fetching organizations: ' + error.message, false);
    } finally {
        loadingEl.classList.add('hidden');
    }
}

async function setZohoOrganization(event) {
    event.preventDefault();
    const orgSelect = document.getElementById('zohoOrgSelect');
    const selectedOrgId = orgSelect.value;
    const selectedOrgName = orgSelect.selectedOptions[0]?.textContent.split(' (ID:')[0];

    if (!selectedOrgId) {
        displayStatusMessage('configStatus', 'Please select a Zoho organization.', false);
        return;
    }

    displayStatusMessage('configStatus', 'Saving configuration...', true);

    try {
        const response = await authorizedFetch(`${BACKEND_URL}/api/integrations/zohobooks/${currentIntegrationId}/set-external-organization/`, {
            method: 'POST',
            body: JSON.stringify({
                external_organization_id: selectedOrgId,
                external_organization_name: selectedOrgName
            }),
        });
        const data = await response.json();

        if (!response.ok) {
            if (response.status === 401 && data.error === 'reauthorization_required') {
                displayStatusMessage('configStatus',
                    `Configuration failed. Your session with Zoho needs reauthorization. <a href="#" onclick="reauthFromConfigPage('${currentIntegrationId}')">Reauthorize Zoho</a> and try again.`,
                    false);
            } else if (response.status === 409) {
                displayStatusMessage('configStatus', data.error || 'This Zoho Organization is already configured elsewhere.', false);
            } else {
                throw new Error(data.error || data.detail || 'Failed to save configuration');
            }
        } else {
            displayStatusMessage('configStatus', 'Zoho organization configured successfully!', true);
        }
    } catch (error) {
        console.error('Set Zoho Org Error:', error);
        displayStatusMessage('configStatus', 'Error: ' + error.message, false);
    }
}