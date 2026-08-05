export function showSpinner(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = `
    <div class="spinner-overlay" style="display:flex; justify-content:center; align-items:center; width:100%; height:100%;">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
        <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
        <path d="M12 2a10 10 0 0 1 10 10"></path>
      </svg>
    </div>
  `;
}

export function hideSpinner(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const spinner = container.querySelector('.spinner-overlay');
  if (spinner) spinner.remove();
}
