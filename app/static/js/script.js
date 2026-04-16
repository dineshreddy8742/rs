window.CareerStorage = {
    trackerKey: 'myresumo-tracker-v1',

    getApplications() {
        try {
            const raw = localStorage.getItem(this.trackerKey);
            return raw ? JSON.parse(raw) : [];
        } catch (error) {
            console.error('Failed to read tracker applications:', error);
            return [];
        }
    },

    saveApplications(applications) {
        localStorage.setItem(this.trackerKey, JSON.stringify(applications));
        return applications;
    },

    upsertApplication(application) {
        const applications = this.getApplications();
        const index = applications.findIndex((item) => item.id === application.id);

        if (index >= 0) {
            applications[index] = { ...applications[index], ...application };
        } else {
            applications.unshift(application);
        }

        this.saveApplications(applications);
        return applications;
    },

    removeApplication(applicationId) {
        const nextApplications = this.getApplications().filter(
            (item) => item.id !== applicationId
        );
        this.saveApplications(nextApplications);
        return nextApplications;
    },
};

// Toast notification system
document.addEventListener('DOMContentLoaded', function() {
    window.showToast = function(message, type = 'info', duration = 5000) {
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container fixed bottom-4 right-4 z-50';
            document.body.appendChild(toastContainer);
        }
        
        const toast = document.createElement('div');
        toast.setAttribute('x-data', '{ show: true }');
        toast.setAttribute('x-show', 'show');
        toast.setAttribute('x-init', `setTimeout(() => show = false, ${duration})`);
        
        let bgColor, textColor, borderColor, iconSvg;
        switch(type) {
            case 'success':
                bgColor = 'bg-green-50'; textColor = 'text-green-800'; borderColor = 'border-green-100';
                iconSvg = '<svg class="h-5 w-5 text-green-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" /></svg>';
                break;
            case 'error':
                bgColor = 'bg-red-50'; textColor = 'text-red-800'; borderColor = 'border-red-100';
                iconSvg = '<svg class="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" /></svg>';
                break;
            case 'warning':
                bgColor = 'bg-yellow-50'; textColor = 'text-yellow-800'; borderColor = 'border-yellow-100';
                iconSvg = '<svg class="h-5 w-5 text-yellow-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" /></svg>';
                break;
            default:
                bgColor = 'bg-blue-50'; textColor = 'text-blue-800'; borderColor = 'border-blue-100';
                iconSvg = '<svg class="h-5 w-5 text-blue-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2h-1V9a1 1 0 00-1-1z" clip-rule="evenodd" /></svg>';
        }
        
        toast.className = `mb-2 p-4 rounded-md shadow-md ${bgColor} ${textColor} border ${borderColor} transform transition-all duration-300 ease-in-out`;
        toast.innerHTML = `
            <div class="flex">
                <div class="flex-shrink-0">${iconSvg}</div>
                <div class="ml-3"><p class="text-sm">${message}</p></div>
                <div class="ml-auto pl-3">
                    <button @click="show = false" class="inline-flex rounded-md p-1.5 ${textColor} hover:${bgColor} focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                        <span class="sr-only">Dismiss</span>
                        <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
                    </button>
                </div>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        if (window.Alpine) window.Alpine.initTree(toast);
        setTimeout(() => { if (toast.parentNode) toast.remove(); }, duration);
    };

    window.showSuccessToast = (message, duration = 5000) => window.showToast(message, 'success', duration);
    window.showErrorToast = (message, duration = 5000) => window.showToast(message, 'error', duration);
    window.showWarningToast = (message, duration = 5000) => window.showToast(message, 'warning', duration);
    window.showInfoToast = (message, duration = 5000) => window.showToast(message, 'info', duration);

    const checkToastHeaders = () => {
        const message = document.head.querySelector('meta[name="x-toast-message"]')?.getAttribute('content');
        const type = document.head.querySelector('meta[name="x-toast-type"]')?.getAttribute('content') || 'info';
        if (message) window.showToast(message, type);
    };

    const initAjaxToastHandler = () => {
        const originalFetch = window.fetch;
        window.fetch = async function(...args) {
            const response = await originalFetch(...args);
            const toastMessage = response.headers.get('X-Toast-Message');
            if (toastMessage) {
                window.showToast(toastMessage, response.headers.get('X-Toast-Type') || 'info');
            }
            return response;
        };
    };

    checkToastHeaders();
    initAjaxToastHandler();
});

// Score & Optimization Functions
function scoreResume(resumeId) { window.currentResumeId = resumeId; Alpine.store('app').showScoreModal = true; }
function cancelScoreModal() { Alpine.store('app').showScoreModal = false; }
async function submitScoreResume() {
    const jd = document.getElementById('job-description').value.trim();
    if (!jd) return window.showWarningToast('Enter job description.');
    try {
        Alpine.store('app').isScoring = true;
        const res = await fetch(`/api/resume/${window.currentResumeId}/score`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_description: jd })
        });
        const result = await res.json();
        Alpine.store('app').scoreResults = result;
        Alpine.store('app').showScoreModal = false;
        Alpine.store('app').showScoreResultsModal = true;
    } catch (e) { window.showErrorToast('Scoring failed.'); }
    finally { Alpine.store('app').isScoring = false; }
}

document.addEventListener('alpine:init', () => {
    Alpine.store('app', {
        showScoreModal: false, isScoring: false, showScoreResultsModal: false,
        scoreResults: { ats_score: 0, matching_skills: [], missing_skills: [], recommendation: '' }
    });
});

// Neural Synthesizer for the AuraRise Era
window.AudioCore = {
    ctx: null,
    init() { 
        if (!this.ctx) {
            this.ctx = new (window.AudioContext || window.webkitAudioContext)();
        }
    },
    play(type) {
        this.init();
        if (this.ctx.state === 'suspended') this.ctx.resume();
        const now = this.ctx.currentTime;
        const createTone = (freq, duration, oscType = 'sine', gainVal = 0.1) => {
            const o = this.ctx.createOscillator();
            const g = this.ctx.createGain();
            o.type = oscType; o.frequency.setValueAtTime(freq, now);
            o.connect(g); g.connect(this.ctx.destination);
            g.gain.setValueAtTime(gainVal, now);
            g.gain.exponentialRampToValueAtTime(0.01, now + duration);
            o.start(now); o.stop(now + duration);
        };
        switch(type) {
            case 'login': createTone(440, 0.3); setTimeout(() => { this.init(); createTone(880, 0.3); }, 100); break;
            case 'logout': createTone(880, 0.4, 'sine', 0.1); setTimeout(() => { this.init(); createTone(440, 0.4, 'sine', 0.05); }, 100); break; 
            case 'optimize': createTone(330, 0.2, 'square', 0.05); break;
            case 'success': createTone(523.25, 0.6); createTone(659.25, 0.6); createTone(783.99, 0.6); break;
            case 'download': createTone(880, 0.4, 'triangle'); break;
        }
    }
};

// Auto-authorize Audio on first user gesture
document.addEventListener('mousedown', () => window.AudioCore.init(), { once: true });
document.addEventListener('touchstart', () => window.AudioCore.init(), { once: true });
