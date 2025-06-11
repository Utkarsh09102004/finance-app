const BACKEND_URL = 'http://localhost:8000'; // ADJUST IF YOUR BACKEND IS ELSEWHERE

function storeToken(token) {
    localStorage.setItem('authToken', token);
}

function getToken() {
    return localStorage.getItem('authToken');
}

function removeToken() {
    localStorage.removeItem('authToken');
}

async function loginUser(email, password) {
    try {
        console.log(`${BACKEND_URL}/api/auth/login/`);
        const response = await fetch(`${BACKEND_URL}/api/auth/login/`, {
            
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password }),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Login failed');
        }
        // Assuming token is in data.access (for SimpleJWT) or data.token
        const token = data.access || data.token;
        if (token) {
            storeToken(token);
            return true;
        } else {
            throw new Error('Token not found in login response');
        }
    } catch (error) {

        console.error('Login error:', error);
        alert('Login failed: ' + error.message);
        return false;
    }
}

async function logoutUser() {
    const token = getToken();
    if (token) {
        try {
            // Optional: Call backend logout if it invalidates tokens
            await fetch(`${BACKEND_URL}/api/auth/logout/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}` // Or just 'Token ${token}' depending on auth type
                },
            });
        } catch (error) {
            console.warn('Backend logout call failed, proceeding with client-side logout:', error);
        }
    }
    removeToken();
    // Redirect to login page
    if (window.location.pathname.includes('login.html') === false) {
      window.location.href = 'login.html';
    }
}

function checkAuth() {
    const token = getToken();
    const isLoginPage = window.location.pathname.includes('login.html');

    if (!token && !isLoginPage) {
        window.location.href = 'login.html';
        return false;
    }
    if (token && isLoginPage) {
        window.location.href = 'index.html';
        return false;
    }
    return true;
}

// Global API fetch wrapper
async function authorizedFetch(url, options = {}) {
    const token = getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`; // Adjust if using 'Token ${token}'
    }

    const response = await fetch(url, { ...options, headers, credentials: 'include' });

    if (response.status === 401) {
        // Potentially an expired token or other auth issue
        console.warn('Received 401 Unauthorized from API');
        const responseData = await response.clone().json().catch(() => null);
        if (responseData && responseData.error === 'reauthorization_required') {
            // Specific reauth signal handled by the calling function
            // Do not logout globally here, let specific handlers decide
        } else if (window.location.pathname.includes('login.html') === false) {
            // Generic 401, not a specific reauth signal, and not on login page
            alert('Your session may have expired or access was denied. Please log in again.');
            logoutUser(); // Perform a full logout
        }
        // Propagate the original response for further handling
        return response; 
    }
    return response;
} 