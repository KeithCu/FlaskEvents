// Set default times when the page loads
document.addEventListener('DOMContentLoaded', function() {
    if (!document.getElementById('start').value) {
        setDateOffset(0);
    }
    
    // Add validation styling to venue select
    const venueSelect = document.getElementById('venue_id');
    venueSelect.addEventListener('change', function() {
        if (this.value === '') {
            this.classList.add('is-invalid');
        } else {
            this.classList.remove('is-invalid');
        }
    });
    
    // Handle recurring event options visibility
    const rruleInput = document.getElementById('rrule');
    const recurringOptions = document.getElementById('recurring-options');
    const recurringUntilInput = document.getElementById('recurring_until');
    
    function toggleRecurringOptions() {
        if (rruleInput.value.trim()) {
            recurringOptions.classList.add('show');
            
            // Set a default end date if none is set (2 years from start date)
            if (!recurringUntilInput.value) {
                const startInput = document.getElementById('start');
                if (startInput.value) {
                    const startDate = new Date(startInput.value);
                    const endDate = new Date(startDate);
                    endDate.setFullYear(startDate.getFullYear() + 2);
                    
                    // Format as YYYY-MM-DD
                    const year = endDate.getFullYear();
                    const month = String(endDate.getMonth() + 1).padStart(2, '0');
                    const day = String(endDate.getDate()).padStart(2, '0');
                    recurringUntilInput.value = `${year}-${month}-${day}`;
                }
            }
        } else {
            recurringOptions.classList.remove('show');
            // Clear the recurring until date when RRULE is cleared
            recurringUntilInput.value = '';
        }
    }
    
    rruleInput.addEventListener('input', toggleRecurringOptions);
    toggleRecurringOptions(); // Initial state
    
    // Update recurring until date when start date changes
    const startInput = document.getElementById('start');
    startInput.addEventListener('change', function() {
        if (rruleInput.value.trim() && !recurringUntilInput.value) {
            // Only update if there's an RRULE and no recurring until date set
            const startDate = new Date(this.value);
            const endDate = new Date(startDate);
            endDate.setFullYear(startDate.getFullYear() + 2);
            
            // Format as YYYY-MM-DD
            const year = endDate.getFullYear();
            const month = String(endDate.getMonth() + 1).padStart(2, '0');
            const day = String(endDate.getDate()).padStart(2, '0');
            recurringUntilInput.value = `${year}-${month}-${day}`;
        }
    });
    
    // Handle virtual event options visibility
    const isVirtualCheckbox = document.getElementById('is_virtual');
    const isHybridCheckbox = document.getElementById('is_hybrid');
    const urlSection = document.getElementById('url-section');
    
    function toggleVirtualOptions() {
        const isVirtual = isVirtualCheckbox.checked;
        const isHybrid = isHybridCheckbox.checked;
        
        if (isVirtual || isHybrid) {
            urlSection.classList.add('show');
        } else {
            urlSection.classList.remove('show');
        }
    }
    
    isVirtualCheckbox.addEventListener('change', toggleVirtualOptions);
    isHybridCheckbox.addEventListener('change', toggleVirtualOptions);
    toggleVirtualOptions(); // Initial state
});

function validateForm() {
    const venueSelect = document.getElementById('venue_id');
    if (venueSelect.value === '') {
        venueSelect.classList.add('is-invalid');
        return false;
    }
    return true;
}

function setDateOffset(days) {
    const now = new Date();
    const targetDate = new Date(now);
    targetDate.setDate(now.getDate() + days);
    
    // Format date as YYYY-MM-DD
    const year = targetDate.getFullYear();
    const month = String(targetDate.getMonth() + 1).padStart(2, '0');
    const day = String(targetDate.getDate()).padStart(2, '0');
    
    // Set start time to 7 PM
    const startDate = `${year}-${month}-${day}T19:00`;
    document.getElementById('start').value = startDate;
    
    // Set end time to 10 PM
    const endDate = `${year}-${month}-${day}T22:00`;
    document.getElementById('end').value = endDate;
}
