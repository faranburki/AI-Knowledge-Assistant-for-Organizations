export function createStatusBadge(status, text) {
  const badge = document.createElement('span');
  badge.className = `badge badge-${status.toLowerCase()}`;
  badge.textContent = text;
  return badge;
}
