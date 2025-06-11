// FinSync UI - Main JavaScript

document.addEventListener('DOMContentLoaded', () => {
  // Initialize mobile menu toggle
  const menuToggle = document.querySelector('.menu-toggle');
  const sidebarNav = document.querySelector('.sidebar');
  
  if (menuToggle && sidebarNav) {
    menuToggle.addEventListener('click', () => {
      sidebarNav.classList.toggle('open');
      menuToggle.classList.toggle('active');
    });
  }
  
  // Password visibility toggle
  const passwordToggles = document.querySelectorAll('.password-toggle');
  
  passwordToggles.forEach(toggle => {
    toggle.addEventListener('click', () => {
      const input = toggle.closest('.form-group').querySelector('input');
      
      if (input.type === 'password') {
        input.type = 'text';
        toggle.innerHTML = '<i class="fas fa-eye-slash"></i>';
      } else {
        input.type = 'password';
        toggle.innerHTML = '<i class="fas fa-eye"></i>';
      }
    });
  });
  
  // Chat UI - message submission
  const chatForm = document.querySelector('.chat-form');
  const chatInput = document.querySelector('.chat-input-field');
  const chatMessages = document.querySelector('.chat-messages');
  
  if (chatForm && chatInput && chatMessages) {
    chatForm.addEventListener('submit', (e) => {
      e.preventDefault();
      
      const message = chatInput.value.trim();
      
      if (message) {
        // Add user message
        addMessage(message, 'user');
        
        // Clear input
        chatInput.value = '';
        
        // Simulate AI thinking
        setTimeout(() => {
          // Simulate AI response (in a real app, this would come from an API)
          const responses = [
            "Based on your current cash flow, you have approximately $42,500 available for operations.",
            "Your Q3 revenue was $125,000, which is 15% higher than the previous quarter.",
            "Your top expense category is marketing at $15,200 for this month.",
            "Your runway is approximately 8 months based on current burn rate.",
            "Your accounts receivable currently stands at $32,750 with 3 outstanding invoices."
          ];
          
          const randomResponse = responses[Math.floor(Math.random() * responses.length)];
          addMessage(randomResponse, 'ai');
          
          // Scroll to bottom
          chatMessages.scrollTop = chatMessages.scrollHeight;
        }, 1000);
      }
    });
  }
  
  // Function to add a message to the chat UI
  function addMessage(text, sender) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message');
    messageElement.classList.add(`message-${sender}`);
    messageElement.textContent = text;
    
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
  
  // Form validation (simple example)
  const forms = document.querySelectorAll('.needs-validation');
  
  forms.forEach(form => {
    form.addEventListener('submit', (event) => {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      
      form.classList.add('was-validated');
    });
  });
});

// Example function for integration connection (simulation)
function connectZohoBooks() {
  const connectButton = document.querySelector('.connect-zoho-btn');
  
  if (connectButton) {
    connectButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Connecting...';
    
    // Simulate connection process
    setTimeout(() => {
      connectButton.innerHTML = 'Connected ✓';
      connectButton.classList.remove('btn-primary');
      connectButton.classList.add('btn-success');
      connectButton.disabled = true;
      
      // Show success message
      const successAlert = document.createElement('div');
      successAlert.classList.add('alert', 'alert-success', 'mt-3');
      successAlert.textContent = 'Successfully connected to Zoho Books!';
      connectButton.parentNode.appendChild(successAlert);
    }, 2000);
  }
}

// Example function for organization name saving (simulation)
function saveOrgName() {
  const saveButton = document.querySelector('.save-org-btn');
  const orgNameInput = document.querySelector('#organizationName');
  
  if (saveButton && orgNameInput) {
    const orgName = orgNameInput.value.trim();
    
    if (orgName) {
      saveButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...';
      
      // Simulate saving process
      setTimeout(() => {
        saveButton.innerHTML = 'Saved';
        
        // Show success message
        const successAlert = document.createElement('div');
        successAlert.classList.add('alert', 'alert-success', 'mt-3');
        successAlert.textContent = `Organization name "${orgName}" saved successfully!`;
        saveButton.parentNode.appendChild(successAlert);
        
        // Redirect after a delay (simulation)
        setTimeout(() => {
          window.location.href = 'integrations.html';
        }, 1500);
      }, 1000);
    }
  }
} 