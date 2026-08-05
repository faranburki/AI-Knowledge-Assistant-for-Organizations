export const Router = {
  currentPage: 'dashboard',
  routes: {
    dashboard: { id: 'page-chat', label: 'Overview' },
    agents: { id: 'page-agents', label: 'Agents' },
    knowledge: { id: 'page-documents', label: 'Knowledge Sources' },
    conversations: { id: 'page-history', label: 'Conversations' },
    voice: { id: 'page-voice', label: 'Voice' },
    analytics: { id: 'page-analytics', label: 'Analytics' },
    settings: { id: 'page-admin', label: 'Settings' }
  },

  navigate(pageId) {
    if (!this.routes[pageId]) pageId = 'dashboard';
    this.currentPage = pageId;
    
    // Hide all pages
    document.querySelectorAll('.page, .page-content').forEach(p => p.classList.add('hidden'));
    
    // Show target page
    const routeInfo = this.routes[pageId];
    const targetEl = document.getElementById(routeInfo.id);
    if (targetEl) targetEl.classList.remove('hidden');
    
    // Update active nav items
    document.querySelectorAll('.nav-item').forEach(n => {
      n.classList.toggle('active', n.dataset.page === pageId);
    });
    
    // Update breadcrumb
    const breadcrumb = document.getElementById('breadcrumbPage');
    if (breadcrumb) breadcrumb.textContent = routeInfo.label;

    // Trigger page-specific initializers if needed
    // (In a full framework this would emit an event or call a lifecycle hook)
  }
};
