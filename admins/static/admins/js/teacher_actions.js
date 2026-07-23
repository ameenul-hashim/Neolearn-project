// =====================================================
// TEACHER ACTIONS - BLOCK, UNBLOCK, DELETE
// =====================================================

let currentTeacherId = null;
let currentTeacherName = '';
let currentAction = ''; // 'block', 'unblock', 'delete'

// =====================================================
// BLOCK/UNBLOCK MODAL
// =====================================================

function openTeacherModal(teacherId, teacherName, action) {
    currentTeacherId = teacherId;
    currentTeacherName = teacherName;
    currentAction = action;

    const modal = document.getElementById('teacherActionModal');
    const title = document.getElementById('teacherActionTitle');
    const subtitle = document.getElementById('teacherActionSubtitle');
    const notice = document.getElementById('teacherActionNotice');
    const icon = document.getElementById('teacherActionIcon');
    const heading = document.getElementById('teacherActionHeading');
    const list = document.getElementById('teacherActionList');
    const avatar = document.getElementById('teacherAvatar');
    const nameDisplay = document.getElementById('teacherNameDisplay');
    const emailDisplay = document.getElementById('teacherEmailDisplay');
    const confirmInput = document.getElementById('teacherConfirmInput');
    const confirmLabel = document.getElementById('teacherConfirmLabel');
    const btnLabel = document.getElementById('teacherConfirmBtnLabel');
    const confirmBtn = document.getElementById('teacherActionConfirmBtn');
    const form = document.getElementById('teacherActionForm');
    const hiddenInput = document.getElementById('teacherActionInput');

    // Reset
    confirmInput.value = '';
    hiddenInput.value = '';
    confirmBtn.disabled = true;
    confirmBtn.classList.add('opacity-50');
    confirmBtn.classList.remove('opacity-100');

    // Set teacher info
    const initial = teacherName.charAt(0).toUpperCase();
    avatar.textContent = initial;
    nameDisplay.textContent = teacherName;
    emailDisplay.textContent = ''; // You can add email if available

    if (action === 'block') {
        // Block configuration
        title.textContent = 'Block Teacher';
        subtitle.textContent = 'This will restrict teacher access to the portal.';
        notice.className = 'rounded-2xl border border-orange-500/30 bg-orange-500/10 p-4';
        icon.textContent = '⚠️';
        heading.textContent = 'Blocking This Teacher Will:';
        heading.className = 'font-semibold text-orange-300 text-sm sm:text-base';
        list.innerHTML = `
            <li>Restrict all uploads by this teacher</li>
            <li>Students won't be able to access this teacher's content</li>
            <li>The teacher won't be able to login to the portal</li>
            <li>All existing content remains but becomes inaccessible to students</li>
        `;
        list.className = 'mt-2 space-y-1 text-xs sm:text-sm text-orange-100 list-disc list-inside';
        avatar.className = 'flex h-10 w-10 items-center justify-center rounded-full bg-orange-600 font-bold text-white text-sm';
        confirmLabel.textContent = 'Confirm Teacher Name';
        confirmLabel.className = 'mb-1 block text-[10px] font-semibold uppercase tracking-widest text-orange-400';
        btnLabel.textContent = 'Block';
        btnLabel.className = 'font-semibold text-orange-400';
        confirmBtn.textContent = 'Block Teacher';
        confirmBtn.className = 'flex h-10 min-w-[140px] items-center justify-center rounded-xl bg-orange-600 px-4 text-sm font-semibold text-white opacity-50 transition hover:bg-orange-700 disabled:cursor-not-allowed disabled:opacity-50';
        confirmInput.className = 'w-full rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2.5 text-white text-sm outline-none transition focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20 placeholder:text-slate-600';

        // Set form action
        form.action = `/admin-panel/teachers/${teacherId}/block/`;

    } else if (action === 'unblock') {
        // Unblock configuration
        title.textContent = 'Unblock Teacher';
        subtitle.textContent = 'This will restore teacher access to the portal.';
        notice.className = 'rounded-2xl border border-green-500/30 bg-green-500/10 p-4';
        icon.textContent = '✅';
        heading.textContent = 'Unblocking This Teacher Will:';
        heading.className = 'font-semibold text-green-300 text-sm sm:text-base';
        list.innerHTML = `
            <li>Restore all uploads by this teacher</li>
            <li>Students can access this teacher's content again</li>
            <li>The teacher can login to the portal</li>
            <li>All existing content becomes accessible to students</li>
        `;
        list.className = 'mt-2 space-y-1 text-xs sm:text-sm text-green-100 list-disc list-inside';
        avatar.className = 'flex h-10 w-10 items-center justify-center rounded-full bg-green-600 font-bold text-white text-sm';
        confirmLabel.textContent = 'Confirm Teacher Name';
        confirmLabel.className = 'mb-1 block text-[10px] font-semibold uppercase tracking-widest text-green-400';
        btnLabel.textContent = 'Unblock';
        btnLabel.className = 'font-semibold text-green-400';
        confirmBtn.textContent = 'Unblock Teacher';
        confirmBtn.className = 'flex h-10 min-w-[140px] items-center justify-center rounded-xl bg-green-600 px-4 text-sm font-semibold text-white opacity-50 transition hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-50';
        confirmInput.className = 'w-full rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2.5 text-white text-sm outline-none transition focus:border-green-500 focus:ring-2 focus:ring-green-500/20 placeholder:text-slate-600';

        // Set form action
        form.action = `/admin-panel/teachers/${teacherId}/unblock/`;
    }

    // Show modal
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    document.body.style.overflow = 'hidden';

    // Focus input after animation
    setTimeout(() => confirmInput.focus(), 100);

    // Setup input validation
    confirmInput.oninput = function() {
        const typedName = this.value.trim();
        if (typedName === teacherName) {
            confirmBtn.disabled = false;
            confirmBtn.classList.remove('opacity-50');
            confirmBtn.classList.add('opacity-100');
            hiddenInput.value = typedName;
        } else {
            confirmBtn.disabled = true;
            confirmBtn.classList.add('opacity-50');
            confirmBtn.classList.remove('opacity-100');
            hiddenInput.value = '';
        }
    };
}

// =====================================================
// CLOSE BLOCK/UNBLOCK MODAL
// =====================================================

function closeTeacherModal() {
    const modal = document.getElementById('teacherActionModal');
    modal.classList.remove('flex');
    modal.classList.add('hidden');
    document.body.style.overflow = 'auto';

    const confirmInput = document.getElementById('teacherConfirmInput');
    const confirmBtn = document.getElementById('teacherActionConfirmBtn');
    const hiddenInput = document.getElementById('teacherActionInput');

    confirmInput.value = '';
    hiddenInput.value = '';
    confirmBtn.disabled = true;
    confirmBtn.classList.add('opacity-50');
    confirmBtn.classList.remove('opacity-100');
}

// =====================================================
// DELETE MODAL
// =====================================================

function openDeleteModal(teacherId, teacherName) {
    currentTeacherId = teacherId;
    currentTeacherName = teacherName;
    currentAction = 'delete';

    const modal = document.getElementById('deleteTeacherModal');
    const avatar = document.getElementById('deleteTeacherAvatar');
    const nameDisplay = document.getElementById('deleteTeacherNameDisplay');
    const confirmInput = document.getElementById('deleteConfirmInput');
    const confirmBtn = document.getElementById('deleteConfirmBtn');
    const form = document.getElementById('deleteTeacherForm');
    const hiddenInput = document.getElementById('deleteTeacherInput');

    // Reset
    confirmInput.value = '';
    hiddenInput.value = '';
    confirmBtn.disabled = true;
    confirmBtn.classList.add('opacity-50');
    confirmBtn.classList.remove('opacity-100');

    // Set teacher info
    const initial = teacherName.charAt(0).toUpperCase();
    avatar.textContent = initial;
    nameDisplay.textContent = teacherName;

    // Set form action
    form.action = `/admin-panel/teachers/${teacherId}/delete/`;

    // Show modal
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    document.body.style.overflow = 'hidden';

    // Focus input after animation
    setTimeout(() => confirmInput.focus(), 100);

    // Setup input validation
    confirmInput.oninput = function() {
        const typedName = this.value.trim();
        if (typedName === teacherName) {
            confirmBtn.disabled = false;
            confirmBtn.classList.remove('opacity-50');
            confirmBtn.classList.add('opacity-100');
            hiddenInput.value = typedName;
        } else {
            confirmBtn.disabled = true;
            confirmBtn.classList.add('opacity-50');
            confirmBtn.classList.remove('opacity-100');
            hiddenInput.value = '';
        }
    };
}

// =====================================================
// CLOSE DELETE MODAL
// =====================================================

function closeDeleteModal() {
    const modal = document.getElementById('deleteTeacherModal');
    modal.classList.remove('flex');
    modal.classList.add('hidden');
    document.body.style.overflow = 'auto';

    const confirmInput = document.getElementById('deleteConfirmInput');
    const confirmBtn = document.getElementById('deleteConfirmBtn');
    const hiddenInput = document.getElementById('deleteTeacherInput');

    confirmInput.value = '';
    hiddenInput.value = '';
    confirmBtn.disabled = true;
    confirmBtn.classList.add('opacity-50');
    confirmBtn.classList.remove('opacity-100');
}

// =====================================================
// CLOSE MODALS ON ESCAPE KEY
// =====================================================

document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const blockModal = document.getElementById('teacherActionModal');
        const deleteModal = document.getElementById('deleteTeacherModal');

        if (blockModal.classList.contains('flex')) {
            closeTeacherModal();
        }
        if (deleteModal.classList.contains('flex')) {
            closeDeleteModal();
        }
    }
});

// =====================================================
// CLOSE MODALS ON BACKDROP CLICK
// =====================================================

document.addEventListener('DOMContentLoaded', function() {
    const blockModal = document.getElementById('teacherActionModal');
    const deleteModal = document.getElementById('deleteTeacherModal');

    if (blockModal) {
        blockModal.addEventListener('click', function(event) {
            if (event.target === this) {
                closeTeacherModal();
            }
        });
    }

    if (deleteModal) {
        deleteModal.addEventListener('click', function(event) {
            if (event.target === this) {
                closeDeleteModal();
            }
        });
    }
});

// =====================================================
// PREVENT FORM SUBMISSION IF INPUT IS EMPTY
// =====================================================

document.addEventListener('DOMContentLoaded', function() {
    const blockForm = document.getElementById('teacherActionForm');
    const deleteForm = document.getElementById('deleteTeacherForm');

    if (blockForm) {
        blockForm.addEventListener('submit', function(e) {
            const hiddenInput = document.getElementById('teacherActionInput');
            if (!hiddenInput.value.trim()) {
                e.preventDefault();
                alert('Please confirm the teacher name before submitting.');
            }
        });
    }

    if (deleteForm) {
        deleteForm.addEventListener('submit', function(e) {
            const hiddenInput = document.getElementById('deleteTeacherInput');
            if (!hiddenInput.value.trim()) {
                e.preventDefault();
                alert('Please confirm the teacher name before submitting.');
            }
        });
    }
});