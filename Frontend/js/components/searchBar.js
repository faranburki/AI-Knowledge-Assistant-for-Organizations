export function initSearchBar(inputId, onSearch) {
  const input = document.getElementById(inputId);
  if (!input) return;
  
  let debounceTimeout;
  input.addEventListener('input', (e) => {
    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(() => {
      onSearch(e.target.value);
    }, 300);
  });
}
