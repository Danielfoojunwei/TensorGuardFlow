// TensorGuard Platform Client

const API_BASE = '/api/v1';
let token = localStorage.getItem('tg_token');

// --- Auth ---

async function login(username, password) {
    try {
        const res = await fetch(`${API_BASE}/auth/token`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        if (!res.ok) throw new Error("Login failed");
        const data = await res.json();
        token = data.access_token;
        localStorage.setItem('tg_token', token);
        showMain();
        loadFleets();
    } catch (e) {
        alert(e.message);
    }
}

async function initTenant(name, email, password) {
    try {
        const res = await fetch(`${API_BASE}/onboarding/init?name=${name}&admin_email=${email}&admin_pass=${password}`, {
            method: 'POST'
        });
        if (!res.ok) throw new Error("Init failed: " + await res.text());
        alert("Tenant created! Please login.");
        toggleInitView();
    } catch (e) {
        alert(e.message);
    }
}

function logout() {
    token = null;
    localStorage.removeItem('tg_token');
    location.reload();
}

// --- Data Fetching ---

async function api(path, method = 'GET', body = null) {
    const opts = {
        method,
        headers: {
            'Authorization': `Bearer ${token}`
        }
    };
    if (body) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
    }
    const res = await fetch(`${API_BASE}${path}`, opts);
    if (res.status === 401) { logout(); return; }
    return res.json();
}

async function loadFleets() {
    const fleets = await api('/fleets');
    const container = document.getElementById('fleet-list');
    container.innerHTML = '';

    if (fleets.length === 0) {
        container.innerHTML = '<div class="list-item">No fleets found. Create one.</div>';
        return;
    }

    fleets.forEach(f => {
        const div = document.createElement('div');
        div.className = 'list-item';
        div.innerHTML = `<strong>${f.name}</strong> <span class="badge ${f.is_active ? 'success' : 'warn'}">${f.is_active ? 'Active' : 'Offline'}</span>`;
        container.appendChild(div);
    });
}

async function createJob() {
    // Mock Job Creation
    const fleets = await api('/fleets');
    if (!fleets.length) return alert("Create a fleet first!");

    const job = await api('/jobs', 'POST', {
        fleet_id: fleets[0].id,
        type: 'FED_PEFT_ROUND',
        config: JSON.stringify({ rounds: 10, epsilon: 1.0 })
    });

    alert(`Job ${job.id} started!`);
    loadJobs();
}

async function loadJobs() {
    const jobs = await api('/jobs');
    const container = document.getElementById('job-list');
    container.innerHTML = '';

    jobs.forEach(j => {
        const div = document.createElement('div');
        div.className = 'list-item';
        div.innerHTML = `
            <div class="flex-col">
                <span><strong>${j.type}</strong> (${j.status})</span>
                <small>${new Date(j.created_at).toLocaleString()}</small>
            </div>
        `;
        container.appendChild(div);
    });
}

// --- UI Logic ---

function showMain() {
    document.getElementById('auth-overlay').classList.add('hidden');
    document.getElementById('main-content').classList.remove('hidden');
}

function toggleInitView() {
    document.getElementById('auth-overlay').querySelector('.auth-card:not(.hidden)').classList.add('hidden');
    const target = document.getElementById('init-card').classList.contains('hidden') ? 'init-card' : null;
    if (target) document.getElementById(target).classList.remove('hidden');
    else document.querySelector('.auth-card').classList.remove('hidden');
}

// Navigation
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        // Toggle active
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');

        // Switch View
        const view = e.target.dataset.view;
        document.querySelectorAll('.view-section').forEach(v => v.classList.add('hidden'));
        document.getElementById(`view-${view}`).classList.remove('hidden');

        if (view === 'fleets') {
            loadFleets();
            loadJobs();
        }
    });
});

// Forms
document.getElementById('login-form').addEventListener('submit', e => {
    e.preventDefault();
    login(document.getElementById('email').value, document.getElementById('password').value);
});

document.getElementById('init-form').addEventListener('submit', e => {
    e.preventDefault();
    initTenant(
        document.getElementById('init-org').value,
        document.getElementById('init-email').value,
        document.getElementById('init-pass').value
    );
});

document.getElementById('link-init').onclick = toggleInitView;
document.getElementById('link-login').onclick = toggleInitView;
document.getElementById('btn-logout').onclick = logout;
document.getElementById('btn-add-fleet').onclick = async () => {
    const name = prompt("Fleet Name:");
    if (name) {
        await api('/fleets?name=' + name, 'POST');
        loadFleets();
    }
};
document.getElementById('btn-new-job').onclick = createJob;

// Init
if (token) {
    showMain();
}
