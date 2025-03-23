/**
 * Main JavaScript for Creative Closets Payroll
 */

document.addEventListener('DOMContentLoaded', function() {
  // Initialize all alert dismiss buttons
  initAlertDismiss();
  
  // Initialize dynamic form fields
  initDynamicForms();
  
  // Initialize timesheet functionality if on timesheet page
  if (document.querySelector('.timesheet-container')) {
    initTimesheet();
  }
});

/**
 * Initialize alert dismissal functionality
 */
function initAlertDismiss() {
  document.querySelectorAll('.alert').forEach(alert => {
    // Add close button if it doesn't exist
    if (!alert.querySelector('.close')) {
      const closeBtn = document.createElement('button');
      closeBtn.className = 'close';
      closeBtn.innerHTML = '&times;';
      closeBtn.style.float = 'right';
      closeBtn.style.border = 'none';
      closeBtn.style.background = 'none';
      closeBtn.style.fontSize = '1.25rem';
      closeBtn.style.fontWeight = 'bold';
      closeBtn.style.lineHeight = '1';
      closeBtn.style.cursor = 'pointer';
      
      closeBtn.addEventListener('click', function() {
        alert.style.display = 'none';
      });
      
      alert.insertBefore(closeBtn, alert.firstChild);
    }
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
      alert.style.display = 'none';
    }, 5000);
  });
}

/**
 * Initialize dynamic form fields based on selection
 */
function initDynamicForms() {
  // Handle employee pay type selection to show/hide relevant fields
  const payTypeSelect = document.getElementById('pay_type');
  if (payTypeSelect) {
    const rateField = document.querySelector('.rate-field');
    const salaryField = document.querySelector('.salary-field');
    const commissionField = document.querySelector('.commission-field');
    
    function updateFields() {
      const payType = payTypeSelect.value;
      
      if (rateField) rateField.style.display = (payType === 'hourly' || payType === 'salary_plus_hourly') ? 'block' : 'none';
      if (salaryField) salaryField.style.display = (payType === 'salary' || payType === 'salary_plus_hourly') ? 'block' : 'none';
      if (commissionField) commissionField.style.display = (payType === 'commission') ? 'block' : 'none';
    }
    
    // Initial update
    updateFields();
    
    // Update on change
    payTypeSelect.addEventListener('change', updateFields);
  }
}

/**
 * Initialize timesheet entry functionality
 */
function initTimesheet() {
  const timesheet = document.querySelector('.timesheet-container');
  const periodId = timesheet.dataset.periodId;
  const employeeId = timesheet.dataset.employeeId;
  
  // Add event listeners to all hour input fields
  document.querySelectorAll('.hours-input').forEach(input => {
    input.addEventListener('change', function() {
      const date = this.dataset.date;
      const type = this.dataset.type; // 'regular' or 'overtime'
      const value = parseFloat(this.value) || 0;
      
      // Get the other type of hours for this date
      const otherType = type === 'regular' ? 'overtime' : 'regular';
      const otherInput = document.querySelector(`.hours-input[data-date="${date}"][data-type="${otherType}"]`);
      const otherValue = parseFloat(otherInput.value) || 0;
      
      // Get job name and notes
      const jobInput = document.querySelector(`.job-input[data-date="${date}"]`);
      const notesInput = document.querySelector(`.notes-input[data-date="${date}"]`);
      
      // Prepare data for saving
      const entryData = {
        period_id: periodId,
        employee_id: employeeId,
        date: date,
        regular_hours: type === 'regular' ? value : otherValue,
        overtime_hours: type === 'overtime' ? value : otherValue,
        job_name: jobInput ? jobInput.value : '',
        notes: notesInput ? notesInput.value : ''
      };
      
      // Save timesheet entry
      saveTimesheetEntry(entryData);
    });
  });
  
  // Add event listeners to job and notes inputs
  document.querySelectorAll('.job-input, .notes-input').forEach(input => {
    input.addEventListener('change', function() {
      const date = this.dataset.date;
      const fieldType = this.classList.contains('job-input') ? 'job' : 'notes';
      
      // Get hours inputs for this date
      const regularInput = document.querySelector(`.hours-input[data-date="${date}"][data-type="regular"]`);
      const overtimeInput = document.querySelector(`.hours-input[data-date="${date}"][data-type="overtime"]`);
      
      // Get the other field
      const jobInput = fieldType === 'job' ? this : document.querySelector(`.job-input[data-date="${date}"]`);
      const notesInput = fieldType === 'notes' ? this : document.querySelector(`.notes-input[data-date="${date}"]`);
      
      // Prepare data for saving
      const entryData = {
        period_id: periodId,
        employee_id: employeeId,
        date: date,
        regular_hours: parseFloat(regularInput.value) || 0,
        overtime_hours: parseFloat(overtimeInput.value) || 0,
        job_name: jobInput ? jobInput.value : '',
        notes: notesInput ? notesInput.value : ''
      };
      
      // Save timesheet entry
      saveTimesheetEntry(entryData);
    });
  });
}

/**
 * Save a timesheet entry via API
 * @param {Object} entryData - The timesheet entry data to save
 */
function saveTimesheetEntry(entryData) {
  const saveIndicator = document.getElementById('save-indicator');
  if (saveIndicator) {
    saveIndicator.textContent = 'Saving...';
    saveIndicator.style.display = 'inline';
  }
  
  fetch('/timesheet/save', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(entryData),
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      // Update totals if available
      if (data.regular_total !== undefined) {
        const regularTotal = document.getElementById('regular-total');
        if (regularTotal) regularTotal.textContent = data.regular_total.toFixed(1);
      }
      
      if (data.overtime_total !== undefined) {
        const overtimeTotal = document.getElementById('overtime-total');
        if (overtimeTotal) overtimeTotal.textContent = data.overtime_total.toFixed(1);
      }
      
      // Show success indicator
      if (saveIndicator) {
        saveIndicator.textContent = 'Saved';
        setTimeout(() => {
          saveIndicator.style.display = 'none';
        }, 2000);
      }
    } else {
      console.error('Error saving timesheet entry:', data.error);
      if (saveIndicator) {
        saveIndicator.textContent = 'Error saving';
        saveIndicator.style.color = 'red';
      }
    }
  })
  .catch(error => {
    console.error('Network error:', error);
    if (saveIndicator) {
      saveIndicator.textContent = 'Network error';
      saveIndicator.style.color = 'red';
    }
  });
} 