export function createEmptyState(title, description, iconSvg) {
  const container = document.createElement('div');
  container.className = 'empty-state';
  container.style.marginTop = '100px';
  container.innerHTML = `
    <div style="width:48px;height:48px;color:var(--text-tertiary);margin-bottom:16px;margin:0 auto;">
      ${iconSvg}
    </div>
    <h3>${title}</h3>
    <p>${description}</p>
  `;
  return container;
}
