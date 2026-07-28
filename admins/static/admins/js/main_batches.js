function toggleDetails(id) {
    const details = document.getElementById('details-' + id);
    const btn = document.getElementById('toggle-btn-' + id);
    
    if (details.classList.contains('hidden')) {
        details.classList.remove('hidden');
        btn.innerHTML = '<span>▲</span> Hide Details';
    } else {
        details.classList.add('hidden');
        btn.innerHTML = '<span>▼</span> Details';
    }
}