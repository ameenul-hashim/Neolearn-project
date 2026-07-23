// =====================================================
// ASSIGNED BATCHES - PROFESSIONAL PURPLE THEME
// =====================================================

function openBatchesModal(teacherId, teacherName) {
    const modal = document.getElementById('batchesModal');
    const teacherNameSpan = document.getElementById('modalTeacherName');
    const contentDiv = document.getElementById('batchesContent');
    
    // Set teacher name
    teacherNameSpan.innerHTML = '<span class="text-purple-400 font-semibold">' + teacherName + '</span>';
    
    // Show loading
    contentDiv.innerHTML = `
        <div class="text-center py-8">
            <div class="inline-block animate-spin rounded-full h-10 w-10 border-4 border-purple-500 border-t-transparent"></div>
            <p class="mt-3 text-slate-400">Loading assigned batches...</p>
        </div>
    `;
    
    // Show modal
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    
    // Fetch data
    const url = '/admin-panel/teachers/' + teacherId + '/batches-data/';
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.batches && data.batches.length > 0) {
                let html = '';
                data.batches.forEach((batch, index) => {
                    // Purple theme gradients
                    const gradients = [
                        'from-purple-500/10 to-indigo-500/10',
                        'from-purple-500/10 to-violet-500/10',
                        'from-purple-500/10 to-fuchsia-500/10',
                        'from-purple-500/10 to-pink-500/10',
                        'from-purple-500/10 to-indigo-500/10',
                        'from-purple-500/10 to-violet-500/10'
                    ];
                    const borderColors = [
                        'border-purple-500/30',
                        'border-purple-500/30',
                        'border-purple-500/30',
                        'border-purple-500/30',
                        'border-purple-500/30',
                        'border-purple-500/30'
                    ];
                    const subjectGradients = [
                        'from-purple-600/20 to-indigo-600/20',
                        'from-purple-600/20 to-violet-600/20',
                        'from-purple-600/20 to-fuchsia-600/20',
                        'from-purple-600/20 to-pink-600/20',
                        'from-purple-600/20 to-indigo-600/20',
                        'from-purple-600/20 to-violet-600/20'
                    ];
                    const subjectBorders = [
                        'border-purple-500/20',
                        'border-purple-500/20',
                        'border-purple-500/20',
                        'border-purple-500/20',
                        'border-purple-500/20',
                        'border-purple-500/20'
                    ];
                    
                    const gradIndex = index % gradients.length;
                    
                    html += `
                        <div class="rounded-xl border ${borderColors[gradIndex]} bg-gradient-to-br ${gradients[gradIndex]} p-5 mb-4 transition hover:scale-[1.01] hover:shadow-lg hover:shadow-purple-500/10">
                            <!-- Batch Header -->
                            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                                <div class="flex items-center gap-3">
                                    <span class="text-2xl text-purple-400">📋</span>
                                    <span class="text-lg sm:text-xl font-bold text-white">${batch.batch_name}</span>
                                </div>
                                <div class="flex flex-wrap items-center gap-2">
                                    <span class="inline-flex items-center gap-1.5 rounded-full bg-slate-800/60 px-3 py-1 text-xs text-slate-300 border border-slate-700/50">
                                        <span class="text-purple-400">👥</span>
                                        ${batch.student_count || 0} students
                                    </span>
                                    <span class="inline-flex items-center gap-1.5 rounded-full bg-slate-800/60 px-3 py-1 text-xs text-slate-300 border border-slate-700/50">
                                        <span class="text-purple-400">📖</span>
                                        ${batch.subject_count || 0} subjects
                                    </span>
                                </div>
                            </div>
                            
                            <!-- Subjects -->
                            ${batch.subjects && batch.subjects.length > 0 ? `
                                <div class="mt-4 flex flex-wrap gap-2">
                                    ${batch.subjects.map(subject => 
                                        `<span class="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r ${subjectGradients[gradIndex]} px-3 py-1.5 text-xs sm:text-sm font-medium text-white border ${subjectBorders[gradIndex]} hover:scale-105 transition duration-200">
                                            <span class="text-purple-300">📖</span>
                                            ${subject}
                                        </span>`
                                    ).join('')}
                                </div>
                            ` : `
                                <div class="mt-3 rounded-lg bg-slate-800/40 border border-slate-700/50 p-3 text-center">
                                    <span class="text-sm text-slate-400">No subjects assigned to this batch</span>
                                </div>
                            `}
                            
                            <!-- Decorative divider -->
                            <div class="mt-3 h-px w-full bg-gradient-to-r from-transparent via-purple-500/20 to-transparent"></div>
                        </div>
                    `;
                });
                contentDiv.innerHTML = html;
            } else {
                contentDiv.innerHTML = `
                    <div class="text-center py-12">
                        <div class="text-6xl mb-4 opacity-50">📚</div>
                        <h3 class="text-xl font-semibold text-white">No Batches Assigned</h3>
                        <p class="mt-2 text-slate-400">This teacher hasn't been assigned to any batches yet.</p>
                        <div class="mt-4 inline-flex items-center gap-2 rounded-lg bg-purple-500/10 px-4 py-2 text-sm text-purple-400 border border-purple-500/20">
                            <span>💡</span>
                            Go to "Assign Batch" to add one
                        </div>
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            contentDiv.innerHTML = `
                <div class="text-center py-8">
                    <div class="text-4xl mb-3">❌</div>
                    <p class="text-red-400">Failed to load data</p>
                    <p class="text-sm text-slate-500 mt-1">Please try again later</p>
                </div>
            `;
        });
}

function closeBatchesModal() {
    const modal = document.getElementById('batchesModal');
    modal.classList.add('hidden');
    document.body.style.overflow = 'auto';
}

// Close on escape
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        const modal = document.getElementById('batchesModal');
        if (modal && !modal.classList.contains('hidden')) {
            closeBatchesModal();
        }
    }
});

// Close on backdrop click
document.addEventListener('click', function(e) {
    const modal = document.getElementById('batchesModal');
    if (modal && !modal.classList.contains('hidden')) {
        const modalContent = modal.querySelector('.relative');
        if (modalContent && !modalContent.contains(e.target)) {
            if (e.target === modal || e.target.closest('.fixed.inset-0.bg-black\\/70')) {
                closeBatchesModal();
            }
        }
    }
});