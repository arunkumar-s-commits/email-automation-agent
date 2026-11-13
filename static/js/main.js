document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');
    const statusIndicator = document.getElementById('scheduler-status-indicator');
    const statusText = document.getElementById('scheduler-status-text');
    
    const btnExecute = document.getElementById('btn-execute');
    const btnSave = document.getElementById('btn-save');
    const btnClear = document.getElementById('btn-clear-textarea');
    const btnAddRow = document.getElementById('btn-add-row');
    const btnRefresh = document.getElementById('btn-refresh');
    const btnUploadExcel = document.getElementById('btn-upload-excel');
    const excelFileInput = document.getElementById('excel-file-input');
    const btnDeleteAll = document.getElementById('btn-delete-all');
    const btnRetryFailed = document.getElementById('btn-retry-failed');

    // Drag and Drop Zone elements
    const dropZone = document.getElementById('drop-zone');
    const dropZoneContent = document.getElementById('drop-zone-content');
    const dropZoneFileInfo = document.getElementById('drop-zone-file-info');
    const dropZoneFileName = document.getElementById('drop-zone-file-name');
    const dropZoneFileSize = document.getElementById('drop-zone-file-size');
    const btnRemoveDroppedFile = document.getElementById('btn-remove-dropped-file');

    // Modal elements
    const retryModal = document.getElementById('retry-modal');
    const closeBtn = document.querySelector('.close-modal');
    const cancelRetryBtn = document.getElementById('btn-cancel-retry');
    const confirmRetryBtn = document.getElementById('btn-confirm-retry');
    const retryTimeInput = document.getElementById('retry-time-input');
    const retryTaskId = document.getElementById('retry-task-id');

    const tbody = document.getElementById('tasks-tbody');

    // Stats Elements
    const statTotal = document.getElementById('stat-total');
    const statPending = document.getElementById('stat-pending');
    const statSent = document.getElementById('stat-sent');
    const statFailed = document.getElementById('stat-failed');

    let pollingInterval;

    // Toast Notification System
    const showToast = (message, type = 'success') => {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <span>${message}</span>
            <i class="fas fa-times close-toast"></i>
        `;
        container.appendChild(toast);
        
        toast.querySelector('.close-toast').addEventListener('click', () => {
            toast.remove();
        });
        
        setTimeout(() => {
            if (toast.parentElement) toast.remove();
        }, 5000);
    };

    // Initialize
    fetchStatus();
    fetchStats();
    fetchTasks();

    // Initialize Jspreadsheet
    let spreadsheet = jspreadsheet(document.getElementById('spreadsheet'), {
        data: [
            ['', '', '']
        ],
        columns: [
            { type: 'text', title: 'Email Address', width: 250 },
            { type: 'text', title: 'Subject', width: 200 },
            { type: 'text', title: 'Message Content', width: 350 }
        ],
        minDimensions: [4, 5],
        contextMenu: true,
        allowInsertRow: true,
        allowManualInsertRow: true,
        allowInsertColumn: false,
        allowDeleteRow: true,
        allowDeleteColumn: false,
        wordWrap: true,
        onbeforepaste: function(instance, data, x, y) {
            // Check if the pasted data looks like CSV (contains commas but no tabs)
            if (typeof data === 'string' && data.indexOf(',') !== -1 && data.indexOf('\t') === -1) {
                const rows = data.split(/\r?\n/);
                const parsedData = [];
                for (let i = 0; i < rows.length; i++) {
                    if (rows[i].trim()) {
                        parsedData.push(rows[i].split(','));
                    }
                }
                return parsedData;
            }
            return data;
        }
    });

    // Start polling for live updates
    pollingInterval = setInterval(() => {
        fetchStatus();
        fetchStats();
        fetchTasks();
    }, 5000);

    // Event Listeners
    btnStart.addEventListener('click', async () => {
        try {
            const res = await fetch('/api/scheduler/control', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'start' })
            });
            if (res.ok) {
                fetchStatus();
            }
        } catch (e) { console.error('Error starting scheduler', e); }
    });

    btnStop.addEventListener('click', async () => {
        try {
            const res = await fetch('/api/scheduler/control', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'stop' })
            });
            if (res.ok) {
                fetchStatus();
            }
        } catch (e) { console.error('Error stopping scheduler', e); }
    });

    btnRefresh.addEventListener('click', () => {
        fetchTasks();
        fetchStats();
    });

    btnClear.addEventListener('click', () => {
        spreadsheet.setData([['', '', '']]);
        resetDropZone();
    });

    btnAddRow.addEventListener('click', () => {
        spreadsheet.insertRow();
    });

    btnUploadExcel.addEventListener('click', () => {
        excelFileInput.click();
    });

    if (btnDeleteAll) {
        btnDeleteAll.addEventListener('click', async () => {
            if(!confirm('Are you absolutely sure you want to delete ALL emails from the queue?')) return;
            try {
                const res = await fetch(`/api/tasks/all`, { method: 'DELETE' });
                if(res.ok) {
                    showToast('All tasks deleted successfully');
                    fetchTasks();
                    fetchStats();
                }
            } catch (e) {
                console.error('Delete all error', e);
                showToast('Failed to delete all tasks', 'danger');
            }
        });
    }

    if (btnRetryFailed) {
        btnRetryFailed.addEventListener('click', async () => {
            try {
                btnRetryFailed.disabled = true;
                btnRetryFailed.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Retrying...';
                const res = await fetch('/api/tasks/retry-failed', { method: 'POST' });
                const data = await res.json();
                if (res.ok) {
                    showToast(data.message || 'Rescheduled failed emails for retry', 'success');
                    fetchTasks();
                    fetchStats();
                } else {
                    showToast(data.error || 'Failed to retry emails', 'danger');
                }
            } catch (e) {
                console.error('Retry all error', e);
                showToast('Error retrying failed emails', 'danger');
            } finally {
                btnRetryFailed.disabled = false;
                btnRetryFailed.innerHTML = '<i class="fas fa-redo-alt"></i> Retry Failed';
            }
        });
    }

    // Modal logic
    const closeModal = () => { retryModal.style.display = 'none'; };
    if(closeBtn) closeBtn.addEventListener('click', closeModal);
    if(cancelRetryBtn) cancelRetryBtn.addEventListener('click', closeModal);
    
    if(confirmRetryBtn) {
        confirmRetryBtn.addEventListener('click', async () => {
            const id = retryTaskId.value;
            const newTime = retryTimeInput.value;
            
            if (!newTime) {
                alert('Please select a new time');
                return;
            }

            confirmRetryBtn.disabled = true;
            confirmRetryBtn.innerHTML = 'Rescheduling...';

            try {
                const res = await fetch(`/api/tasks/retry/${id}`, { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ new_time: newTime })
                });
                
                if (res.ok) {
                    showToast('Task rescheduled and marked for retry', 'success');
                    fetchTasks();
                    fetchStats();
                    closeModal();
                } else {
                    showToast('Failed to reschedule task', 'danger');
                }
            } catch (e) {
                console.error('Retry error', e);
                showToast('Failed to retry task', 'danger');
            } finally {
                confirmRetryBtn.disabled = false;
                confirmRetryBtn.innerHTML = 'Reschedule & Retry';
            }
        });
    }

    // Drop Zone Utilities
    const formatBytes = (bytes) => {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    };

    const showDroppedFileInfo = (file, rowCount) => {
        if (!dropZoneFileInfo || !dropZoneContent) return;
        if (dropZoneFileName) dropZoneFileName.textContent = file.name;
        if (dropZoneFileSize) dropZoneFileSize.textContent = `${formatBytes(file.size)} (${rowCount} contact${rowCount > 1 ? 's' : ''})`;
        dropZoneContent.style.display = 'none';
        dropZoneFileInfo.style.display = 'flex';
    };

    const resetDropZone = () => {
        if (!dropZoneFileInfo || !dropZoneContent) return;
        dropZoneContent.style.display = 'flex';
        dropZoneFileInfo.style.display = 'none';
        if (dropZoneFileName) dropZoneFileName.textContent = '';
        if (dropZoneFileSize) dropZoneFileSize.textContent = '';
        if (excelFileInput) excelFileInput.value = '';
    };

    const uploadFile = async (file) => {
        if (!file) return;

        const validExtensions = ['.csv', '.xlsx', '.xls'];
        const fileName = file.name.toLowerCase();
        const isValid = validExtensions.some(ext => fileName.endsWith(ext));

        if (!isValid) {
            showToast('Unsupported file type. Please upload a .xlsx, .xls, or .csv file.', 'warning');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            if (dropZone) dropZone.classList.add('uploading');
            showToast(`Importing ${file.name}...`, 'info');

            const response = await fetch('/api/import', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (response.ok) {
                let parsedData = data.records || [];
                
                if (parsedData.length > 0) {
                    // Check if the first row looks like a header and remove it
                    const firstRow = (parsedData[0] || []).join('').toLowerCase();
                    if (firstRow.includes('email') || firstRow.includes('subject') || firstRow.includes('time') || firstRow.includes('date') || firstRow.includes('message')) {
                        parsedData.shift(); 
                    }
                }
                
                // Format any Date objects or fix date strings before passing to Jspreadsheet
                const mappedData = parsedData.map(row => {
                    return [
                        row[0] ? row[0].toString().trim() : '',
                        row[1] ? row[1].toString().trim() : '',
                        row[2] ? row[2].toString().trim() : ''
                    ];
                }).filter(row => row[0] || row[1] || row[2]);
                
                if (mappedData.length === 0) {
                    showToast('No valid data rows found in file.', 'warning');
                    resetDropZone();
                } else {
                    spreadsheet.setData(mappedData);
                    showToast(`Successfully imported ${mappedData.length} contact${mappedData.length > 1 ? 's' : ''} from ${file.name}!`, 'success');
                    showDroppedFileInfo(file, mappedData.length);
                }
            } else {
                showToast(data.error || 'Failed to import file', 'danger');
                resetDropZone();
            }
        } catch (error) {
            console.error('File import error:', error);
            showToast('Error importing file', 'danger');
            resetDropZone();
        } finally {
            if (dropZone) dropZone.classList.remove('uploading');
            if (excelFileInput) excelFileInput.value = '';
        }
    };

    excelFileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            uploadFile(file);
        }
    });

    if (btnRemoveDroppedFile) {
        btnRemoveDroppedFile.addEventListener('click', (e) => {
            e.stopPropagation();
            resetDropZone();
            spreadsheet.setData([['', '', '']]);
            showToast('Imported file cleared', 'info');
        });
    }

    // Drag and Drop Event Handlers
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        window.addEventListener(eventName, (e) => {
            e.preventDefault();
        }, false);
    });

    if (dropZone) {
        let dragCounter = 0;

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        dropZone.addEventListener('dragenter', (e) => {
            dragCounter++;
            dropZone.classList.add('drag-over');
        });

        dropZone.addEventListener('dragleave', (e) => {
            dragCounter--;
            if (dragCounter <= 0) {
                dragCounter = 0;
                dropZone.classList.remove('drag-over');
            }
        });

        dropZone.addEventListener('dragover', (e) => {
            if (!dropZone.classList.contains('drag-over')) {
                dropZone.classList.add('drag-over');
            }
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dragCounter = 0;
            dropZone.classList.remove('drag-over');

            const dt = e.dataTransfer;
            if (dt && dt.files && dt.files.length > 0) {
                uploadFile(dt.files[0]);
            }
        });

        dropZone.addEventListener('click', (e) => {
            if (e.target.closest('#btn-remove-dropped-file')) return;
            excelFileInput.click();
        });
    }

    const getCleanData = () => {
        const data = spreadsheet.getData();
        const records = [];

        for (let i = 0; i < data.length; i++) {
            const row = data[i];
            const email = row[0] ? row[0].trim() : '';
            const subject = row[1] ? row[1].trim() : '';
            const content = row[2] ? row[2].trim() : '';

            // Skip empty rows
            if (!email && !subject && !content) continue;

            if (email) {
                records.push({
                    email_address: email,
                    subject: subject,
                    message_content: content
                });
            } else {
                console.warn(`Row ${i+1} is incomplete`);
            }
        }
        return records;
    };

    btnSave.addEventListener('click', async () => {
        const records = getCleanData();
        if (records.length === 0) {
            alert('No valid data found. Ensure Email is filled.');
            return;
        }

        btnSave.disabled = true;
        btnSave.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

        try {
            const res = await fetch('/api/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(records)
            });

            if (res.ok) {
                spreadsheet.setData([['', '', '']]);
                resetDropZone();
                showToast(`Successfully saved draft for ${records.length} emails.`, 'success');
                fetchTasks();
                fetchStats();
            } else {
                const data = await res.json();
                alert(`Error saving: ${data.error || 'Unknown error'}`);
            }
        } catch (e) {
            console.error('Save error', e);
            alert('Failed to connect to server.');
        } finally {
            btnSave.disabled = false;
            btnSave.innerHTML = '<i class="fas fa-save"></i> Save Draft';
        }
    });

    btnExecute.addEventListener('click', async () => {
        const records = getCleanData();
        if (records.length === 0) {
            alert('No valid data found. Ensure Email is filled.');
            return;
        }

        btnExecute.disabled = true;
        btnExecute.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Executing...';

        try {
            const res = await fetch('/api/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(records)
            });

            if (res.ok) {
                spreadsheet.setData([['', '', '']]);
                resetDropZone();
                showToast(`Successfully scheduled ${records.length} emails.`, 'success');
                fetchTasks();
                fetchStats();
            } else {
                const data = await res.json();
                alert(`Error scheduling: ${data.error || 'Unknown error'}`);
            }
        } catch (e) {
            console.error('Execute error', e);
            alert('Failed to connect to server.');
        } finally {
            btnExecute.disabled = false;
            btnExecute.innerHTML = '<i class="fas fa-paper-plane"></i> Execute Scheduler';
        }
    });

    // API Calls
    async function fetchStatus() {
        try {
            const res = await fetch('/api/scheduler/status');
            const data = await res.json();
            if (data.running) {
                statusIndicator.className = 'status-indicator online';
                statusText.innerText = 'Scheduler Online';
                btnStart.disabled = true;
                btnStop.disabled = false;
            } else {
                statusIndicator.className = 'status-indicator offline';
                statusText.innerText = 'Scheduler Offline';
                btnStart.disabled = false;
                btnStop.disabled = true;
            }
        } catch (e) {
            console.error('Status fetch error', e);
        }
    }

    async function fetchStats() {
        try {
            const res = await fetch('/api/stats');
            const data = await res.json();
            
            // Animate number changes
            animateValue(statTotal, parseInt(statTotal.innerText), data.total, 500);
            animateValue(statPending, parseInt(statPending.innerText), data.pending, 500);
            animateValue(statSent, parseInt(statSent.innerText), data.sent, 500);
            animateValue(statFailed, parseInt(statFailed.innerText), data.failed, 500);
        } catch (e) {
            console.error('Stats fetch error', e);
        }
    }

    async function fetchTasks() {
        try {
            const res = await fetch('/api/tasks');
            const data = await res.json();
            
            tbody.innerHTML = '';
            
            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No emails queued. Import some data to get started.</td></tr>';
                return;
            }

            data.forEach(task => {
                const tr = document.createElement('tr');
                
                const schedDate = task.scheduled_time ? task.scheduled_time : '-';
                const sentDate = task.actual_send_time ? task.actual_send_time : '-';
                
                let statusClass = '';
                switch(task.status.toLowerCase()) {
                    case 'pending': statusClass = 'status-pending'; break;
                    case 'scheduled': statusClass = 'status-scheduled'; break;
                    case 'sending': statusClass = 'status-sending'; break;
                    case 'sent': statusClass = 'status-sent'; break;
                    case 'failed': statusClass = 'status-failed'; break;
                }

                let statusBadgeText = task.status;
                if (task.status === 'Failed' && task.retry_count && task.retry_count > 0) {
                    statusBadgeText = task.retry_count >= 3 ? 'Failed (Max Retries)' : `Failed (Retry ${task.retry_count}/3)`;
                } else if (task.status === 'Sending' && task.retry_count && task.retry_count > 0) {
                    statusBadgeText = `Retrying (${task.retry_count}/3)`;
                }

                let actionsHTML = `
                    <button class="btn-icon" onclick="deleteTask(${task.id})" title="Delete"><i class="fas fa-trash"></i></button>
                `;
                
                if (task.status === 'Failed') {
                    actionsHTML = `
                        <button class="btn-icon" onclick="retryTask(${task.id}, '${schedDate}')" title="Retry / Reschedule"><i class="fas fa-redo"></i></button>
                        ${actionsHTML}
                    `;
                }

                let errorHTML = task.error_message ? `<span class="error-text" title="${task.error_message}">${task.error_message}</span>` : '';

                tr.innerHTML = `
                    <td>#${task.id}</td>
                    <td>${task.email_address}</td>
                    <td>${task.subject}</td>
                    <td>${sentDate}</td>
                    <td>
                        <span class="status-badge ${statusClass}">${statusBadgeText}</span>
                        ${errorHTML}
                    </td>
                    <td>${actionsHTML}</td>
                `;
                
                tbody.appendChild(tr);
            });
        } catch (e) {
            console.error('Tasks fetch error', e);
        }
    }

    // Global Functions for inline onclick
    window.deleteTask = async (id) => {
        if(!confirm('Are you sure you want to delete this email task?')) return;
        try {
            await fetch(`/api/tasks/${id}`, { method: 'DELETE' });
            fetchTasks();
            fetchStats();
            showToast('Task deleted successfully');
        } catch (e) {
            console.error('Delete error', e);
            showToast('Failed to delete task', 'danger');
        }
    };

    window.retryTask = (id, currentScheduledTime) => {
        retryTaskId.value = id;
        
        // Populate the datetime-local input
        if (currentScheduledTime && currentScheduledTime !== '-') {
            // Convert 'YYYY-MM-DD HH:MM:SS' to 'YYYY-MM-DDTHH:MM'
            try {
                const dt = currentScheduledTime.split(' ');
                if(dt.length === 2) {
                    const timeParts = dt[1].split(':');
                    retryTimeInput.value = `${dt[0]}T${timeParts[0]}:${timeParts[1]}`;
                }
            } catch(e) { console.error(e); }
        }
        
        retryModal.style.display = 'flex';
    };

    // Number animation helper
    function animateValue(obj, start, end, duration) {
        if (start === end || isNaN(start) || isNaN(end)) {
            obj.innerHTML = end;
            return;
        }
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            obj.innerHTML = Math.floor(progress * (end - start) + start);
            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        };
        window.requestAnimationFrame(step);
    }
});
