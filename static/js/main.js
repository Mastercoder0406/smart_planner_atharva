/* ════════════════════════════════════════════════════════════
   SmartPlanner — main.js
   ════════════════════════════════════════════════════════════ */

// ── Map init ──────────────────────────────────────────────────
const map = L.map('map', { zoomControl: false }).setView([19.0330, 73.0297], 13);
let markerLayer = L.layerGroup().addTo(map);
let routeLayer = L.layerGroup().addTo(map);

L.control.zoom({ position: 'bottomright' }).addTo(map);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

map.whenReady(() => setTimeout(() => map.invalidateSize(), 100));
map.getContainer().style.pointerEvents = 'auto';

// ── State ─────────────────────────────────────────────────────
let currentStart = null;
let currentEnd = null;
let startMarker = null;
let endMarker = null;
let routeLayers = { fastest: null, comfortable: null, accessible: null };
let routeDataByType = {};
let visibleRoutes = new Set(['fastest', 'comfortable', 'accessible']);
let activeRouteType = 'fastest';
let latestRouteStats = [];

// ── Info control ──────────────────────────────────────────────
const info = L.control({ position: 'bottomleft' });
info.onAdd = function () {
    this._div = L.DomUtil.create('div', 'info');
    this.update();
    return this._div;
};
info.update = function (text = 'Click map or search to set start point.') {
    this._div.innerHTML = text;
};
info.addTo(map);

// ── Helpers ───────────────────────────────────────────────────
function formatDistanceMeters(m) { return `${(m / 1000).toFixed(2)} km`; }
function formatMinutes(min) { return `${Math.round(min)} min`; }

function updateHint() {
    const t = document.getElementById('hint-target');
    if (!t) return;
    if (!startMarker) t.textContent = 'start';
    else if (!endMarker) t.textContent = 'end';
    else t.textContent = 'start (reset)';
}

// ── Markers ───────────────────────────────────────────────────
function setStartPoint(latlng, label = 'Start') {
    if (startMarker) markerLayer.removeLayer(startMarker);
    startMarker = L.marker([latlng.lat, latlng.lng], { draggable: true })
        .addTo(markerLayer).bindPopup(label);
    startMarker.on('dragend', () => {
        const p = startMarker.getLatLng();
        currentStart = { lat: p.lat, lng: p.lng };
    });
    currentStart = { lat: latlng.lat, lng: latlng.lng };
    info.update('Start set. Now select destination.');
    updateHint();
    markCardFilled('start-card', !!label && label !== 'Start');
}

function setEndPoint(latlng, label = 'End') {
    if (endMarker) markerLayer.removeLayer(endMarker);
    endMarker = L.marker([latlng.lat, latlng.lng], { draggable: true })
        .addTo(markerLayer).bindPopup(label);
    endMarker.on('dragend', () => {
        const p = endMarker.getLatLng();
        currentEnd = { lat: p.lat, lng: p.lng };
    });
    currentEnd = { lat: latlng.lat, lng: latlng.lng };
    info.update('Both points set. Click "Calculate Routes".');
    updateHint();
    markCardFilled('end-card', !!label && label !== 'End');
}

function markCardFilled(cardId, filled) {
    const card = document.getElementById(cardId);
    if (card) card.classList.toggle('has-value', filled);
}

// ── Search ────────────────────────────────────────────────────
async function searchPlaces(query) {
    if (!query || query.trim().length < 3) return [];
    const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&q=${encodeURIComponent(query)}&limit=6`;
    try {
        const res = await fetch(url, { headers: { Accept: 'application/json' } });
        if (!res.ok) return [];
        return await res.json();
    } catch { return []; }
}

function renderSuggestions(containerId, results, kind) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!results.length) {
        container.classList.remove('open');
        container.innerHTML = '';
        return;
    }

    container.innerHTML = results.map(place => `
    <div class="suggestion-item"
      data-kind="${kind}"
      data-lat="${place.lat}"
      data-lon="${place.lon}"
      data-name="${place.display_name}">
      ${place.display_name}
    </div>
  `).join('');
    container.classList.add('open');

    container.querySelectorAll('.suggestion-item').forEach(item => {
        item.addEventListener('click', () => {
            const latlng = { lat: parseFloat(item.dataset.lat), lng: parseFloat(item.dataset.lon) };
            const name = item.dataset.name;
            if (kind === 'start') {
                setStartPoint(latlng, `Start: ${name}`);
                const inp = document.getElementById('start-search');
                if (inp) { inp.value = name; inp.closest('.search-card')?.classList.add('has-value'); }
                container.classList.remove('open');
            } else {
                setEndPoint(latlng, `End: ${name}`);
                const inp = document.getElementById('end-search');
                if (inp) { inp.value = name; inp.closest('.search-card')?.classList.add('has-value'); }
                container.classList.remove('open');
            }
            map.setView([latlng.lat, latlng.lng], 16);
        });
    });
}

function setupSearchBox(inputId, buttonId, suggestionsId, kind) {
    const input = document.getElementById(inputId);
    const suggestions = document.getElementById(suggestionsId);
    let debounce = null;

    input?.addEventListener('input', () => {
        clearTimeout(debounce);
        input.closest('.search-card')?.classList.toggle('has-value', input.value.length > 0);
        debounce = setTimeout(async () => {
            const q = input.value.trim();
            if (q.length < 3) { suggestions.classList.remove('open'); suggestions.innerHTML = ''; return; }
            renderSuggestions(suggestionsId, await searchPlaces(q), kind);
        }, 300);
    });

    // Button id may be null in new HTML (no explicit set-btn), so guard
    const button = buttonId ? document.getElementById(buttonId) : null;
    button?.addEventListener('click', async () => {
        const q = input.value.trim();
        const results = await searchPlaces(q);
        if (!results.length) { alert('No location found.'); return; }
        const first = results[0];
        const latlng = { lat: parseFloat(first.lat), lng: parseFloat(first.lon) };
        kind === 'start' ? setStartPoint(latlng, `Start: ${first.display_name}`)
            : setEndPoint(latlng, `End: ${first.display_name}`);
        map.setView([latlng.lat, latlng.lng], 16);
        suggestions.classList.remove('open');
    });

    input?.addEventListener('focus', () => {
        if (suggestions.children.length > 0) suggestions.classList.add('open');
    });

    document.addEventListener('click', (e) => {
        if (!input?.contains(e.target) && !suggestions.contains(e.target)) {
            suggestions.classList.remove('open');
        }
    });
}

// ── Clear buttons ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('clear-start')?.addEventListener('click', () => {
        const inp = document.getElementById('start-search');
        if (inp) { inp.value = ''; }
        document.getElementById('start-card')?.classList.remove('has-value');
        document.getElementById('start-suggestions')?.classList.remove('open');
        if (startMarker) { markerLayer.removeLayer(startMarker); startMarker = null; }
        currentStart = null;
        updateHint();
        info.update('Start cleared. Click map or search to set start.');
    });

    document.getElementById('clear-end')?.addEventListener('click', () => {
        const inp = document.getElementById('end-search');
        if (inp) { inp.value = ''; }
        document.getElementById('end-card')?.classList.remove('has-value');
        document.getElementById('end-suggestions')?.classList.remove('open');
        if (endMarker) { markerLayer.removeLayer(endMarker); endMarker = null; }
        currentEnd = null;
        updateHint();
        info.update('Destination cleared.');
    });

    // Swap button
    document.getElementById('swap-btn')?.addEventListener('click', () => {
        const si = document.getElementById('start-search');
        const ei = document.getElementById('end-search');
        const sv = si?.value || '';
        const ev = ei?.value || '';
        if (si) si.value = ev;
        if (ei) ei.value = sv;

        const tmpPt = currentStart;
        currentStart = currentEnd;
        currentEnd = tmpPt;

        if (currentStart && startMarker) {
            startMarker.setLatLng([currentStart.lat, currentStart.lng]);
        }
        if (currentEnd && endMarker) {
            endMarker.setLatLng([currentEnd.lat, currentEnd.lng]);
        }
        updateHint();
    });

    // Sidebar toggle
    document.getElementById('sidebar-toggle')?.addEventListener('click', () => {
        document.getElementById('sidebar')?.classList.toggle('collapsed');
        setTimeout(() => map.invalidateSize(), 320);
    });

    setupSearchBox('start-search', null, 'start-suggestions', 'start');
    setupSearchBox('end-search', null, 'end-suggestions', 'end');
    updateHint();
});

// ── Preference sliders ─────────────────────────────────────────
const slopeSlider = document.getElementById('slope');
const comfortSlider = document.getElementById('comfort');
const slopeValue = document.getElementById('slopeValue');
const comfortValue = document.getElementById('comfortValue');

slopeSlider?.addEventListener('input', () => { if (slopeValue) slopeValue.textContent = slopeSlider.value; });
comfortSlider?.addEventListener('input', () => { if (comfortValue) comfortValue.textContent = comfortSlider.value; });

// ── Button wiring ─────────────────────────────────────────────
document.getElementById('calculate-routes')?.addEventListener('click', calculateAllRoutes);
document.getElementById('save-profile')?.addEventListener('click', saveCurrentProfile);
document.getElementById('show-fastest')?.addEventListener('click', () => toggleRouteVisibility('fastest'));
document.getElementById('show-comfortable')?.addEventListener('click', () => toggleRouteVisibility('comfortable'));
document.getElementById('show-accessible')?.addEventListener('click', () => toggleRouteVisibility('accessible'));
document.getElementById('show-all')?.addEventListener('click', showAllRoutes);
document.getElementById('zoom-all-btn')?.addEventListener('click', zoomAllRoutes);
document.getElementById('focus-fastest-btn')?.addEventListener('click', () => focusRoute('fastest'));
document.getElementById('focus-comfortable-btn')?.addEventListener('click', () => focusRoute('comfortable'));
document.getElementById('focus-accessible-btn')?.addEventListener('click', () => focusRoute('accessible'));

// ── Load user profile on page load ───────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const res = await fetch('/api/me');
        if (!res.ok) return;
        const me = await res.json();
        if (slopeSlider) { slopeSlider.value = me.max_slope; if (slopeValue) slopeValue.textContent = me.max_slope; }
        if (comfortSlider) { comfortSlider.value = me.comfort_weight; if (comfortValue) comfortValue.textContent = me.comfort_weight; }
        const gravel = document.getElementById('gravel');
        if (gravel) gravel.checked = me.disliked_surfaces.includes('gravel');
        const userNameEl = document.getElementById('user-name');
        if (userNameEl) userNameEl.textContent = me.name;
    } catch { /* silent */ }

    if (typeof loadProfiles === 'function') loadProfiles();
});

// ── Map click ─────────────────────────────────────────────────
map.on('click', function (e) {
    if (!startMarker) setStartPoint(e.latlng, 'Start');
    else if (!endMarker) setEndPoint(e.latlng, 'End');
    else { clearSelectionOnly(); setStartPoint(e.latlng, 'Start'); }
});

// ── Right-click obstacle report ───────────────────────────────
map.on('contextmenu', async function (e) {
    const description = prompt('Describe the obstacle:');
    if (!description) return;
    try {
        const response = await fetch('/report_obstacle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat: e.latlng.lat, lng: e.latlng.lng, description })
        });
        const result = await response.json();
        if (result.success) {
            alert('Obstacle reported successfully.');
            L.marker(e.latlng).addTo(map).bindPopup(description);
        } else {
            alert(result.error || 'Failed to report obstacle.');
        }
    } catch (err) { alert('Failed to report obstacle.'); }
});

// ── Route calculation ─────────────────────────────────────────
function setActiveRouteCard(routeType) {
    document.querySelectorAll('.route-card-btn').forEach(btn =>
        btn.classList.toggle('active', btn.dataset.route === routeType));
}

function clearSelectionOnly() {
    if (startMarker) { map.removeLayer(startMarker); startMarker = null; }
    if (endMarker) { map.removeLayer(endMarker); endMarker = null; }
}

function clearAllRoutes() {
    Object.values(routeLayers).forEach(layer => {
        if (layer && map.hasLayer(layer)) map.removeLayer(layer);
    });
    routeLayers = { fastest: null, comfortable: null, accessible: null };
    routeDataByType = {};
    visibleRoutes = new Set(['fastest', 'comfortable', 'accessible']);
    const rcp = document.getElementById('route-details-panel');
    if (rcp) rcp.style.display = 'none';
}

async function calculateAllRoutes() {
    if (!startMarker || !endMarker) {
        alert('Please select both start and end points first.');
        return;
    }

    const startPoint = currentStart || startMarker?.getLatLng();
    const endPoint = currentEnd || endMarker?.getLatLng();

    const dislikedSurfaces = [];
    if (document.getElementById('gravel')?.checked) dislikedSurfaces.push('gravel');

    const userProfile = {
        max_slope: parseFloat(document.getElementById('slope')?.value || 4),
        disliked_surfaces: dislikedSurfaces,
        comfort_weight: parseFloat(document.getElementById('comfort')?.value || 0.5)
    };

    const routeTypes = ['fastest', 'comfortable', 'accessible'];
    const routeColors = { fastest: '#ef4444', comfortable: '#22c55e', accessible: '#3b82f6' };
    const routeNames = { fastest: 'Fastest', comfortable: 'Most Comfortable', accessible: 'Most Accessible' };
    const routeStats = [];

    clearAllRoutes();

    const btn = document.getElementById('calculate-routes');
    if (btn) { btn.disabled = true; btn.textContent = 'Calculating…'; }

    for (const routeType of routeTypes) {
        try {
            const response = await fetch('/get_route', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    start: { lat: startPoint.lat, lng: startPoint.lng },
                    end: { lat: endPoint.lat, lng: endPoint.lng },
                    profile: userProfile,
                    route_type: routeType
                })
            });
            const data = await response.json();
            if (!response.ok || !data.route || data.route.length < 2) continue;

            const polyline = L.polyline(data.route, {
                color: routeColors[routeType], weight: 5, opacity: 0.9
            }).addTo(map);

            polyline.on('click', () => {
                activeRouteType = routeType;
                setActiveRouteCard(routeType);
                showRouteDetails(routeType);
                focusRoute(routeType);
            });

            routeLayers[routeType] = polyline;
            routeDataByType[routeType] = data;

            routeStats.push({
                type: routeType, name: routeNames[routeType],
                color: routeColors[routeType],
                stats: data.stats, segments: data.segments || [], bounds: data.bounds
            });
        } catch (err) { console.error(`Route error (${routeType}):`, err); }
    }

    if (btn) { btn.disabled = false; btn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><polygon points="5 3 19 12 5 21 5 3"/></svg> Calculate Routes'; }

    displayRouteComparison(routeStats);
    activeRouteType = routeStats[0]?.type || 'fastest';
    setActiveRouteCard(activeRouteType);
    showRouteDetails(activeRouteType);
    zoomAllRoutes();
    info.update('Routes calculated. Click a route to inspect it.');
}

function displayRouteComparison(routeStats) {
    latestRouteStats = routeStats;
    const statsDiv = document.getElementById('route-stats');
    const panel = document.getElementById('route-details-panel');

    if (!routeStats.length) {
        if (statsDiv) statsDiv.innerHTML = '<div style="color:var(--text-2);font-size:13px">No routes found.</div>';
        return;
    }

    if (statsDiv) statsDiv.innerHTML = `
    <div class="route-grid">
      ${routeStats.map(route => {
        const s = route.stats;
        return `<button class="route-card-btn" data-route="${route.type}">
          <h3 style="color:${route.color}">${route.name}</h3>
          <div>📏 ${formatDistanceMeters(s.length)}</div>
          <div>⏱ ${formatMinutes(s.estimated_time)}</div>
          <div>📈 Avg slope ${s.avg_slope.toFixed(1)}%</div>
          <div>⭐ Accessibility ${s.accessibility_score}/100</div>
        </button>`;
    }).join('')}
    </div>`;

    if (panel) panel.style.display = '';

    statsDiv?.querySelectorAll('.route-card-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            activeRouteType = btn.dataset.route;
            setActiveRouteCard(activeRouteType);
            showRouteDetails(activeRouteType);
            focusRoute(activeRouteType);
        });
    });

    setActiveRouteCard(routeStats[0].type);
    showRouteDetails(routeStats[0].type);
}

function showRouteDetails(routeType) {
    const segmentList = document.getElementById('segment-list');
    const route = latestRouteStats.find(r => r.type === routeType);
    if (!route || !segmentList) return;

    const s = route.stats;
    const segments = route.segments || [];

    segmentList.innerHTML = `
    <h2 style="margin-top:14px">${route.name} — Segments</h2>
    <div class="details-grid">
      <div>♿ Accessibility<br><strong>${s.accessibility_score}/100</strong></div>
      <div>📈 Avg slope<br><strong>${s.avg_slope.toFixed(1)}%</strong></div>
      <div>⛰ Max slope<br><strong>${s.max_slope.toFixed(1)}%</strong></div>
      <div>⚠️ Obstacles<br><strong>${s.obstacle_count}</strong></div>
    </div>
    <div style="margin-top:8px">
      ${segments.slice(0, 10).map(seg => `
        <div class="segment-row">
          <b>#${seg.index} · ${seg.highway_type}</b><br>
          ${seg.length.toFixed(1)} m · ${seg.slope.toFixed(1)}% slope · ${seg.surface}
        </div>`).join('')}
    </div>`;
}

// ── Route visibility ──────────────────────────────────────────
function zoomAllRoutes() {
    const layers = Object.values(routeLayers).filter(Boolean);
    if (!layers.length) return;
    map.fitBounds(L.featureGroup(layers).getBounds(), { padding: [40, 40], maxZoom: 18, animate: true });
}

function focusRoute(routeType) {
    const layer = routeLayers[routeType];
    if (!layer) return;
    Object.entries(routeLayers).forEach(([type, line]) => {
        if (!line) return;
        line.setStyle({ opacity: type === routeType ? 1 : 0.2, weight: type === routeType ? 7 : 4 });
    });
    map.fitBounds(layer.getBounds(), { padding: [40, 40], maxZoom: 19, animate: true });
}

function toggleRouteVisibility(routeType) {
    visibleRoutes.has(routeType) ? visibleRoutes.delete(routeType) : visibleRoutes.add(routeType);
    updateRouteVisibility();
}

function showAllRoutes() {
    visibleRoutes = new Set(['fastest', 'comfortable', 'accessible']);
    updateRouteVisibility();
    zoomAllRoutes();
}

function updateRouteVisibility() {
    Object.keys(routeLayers).forEach(routeType => {
        const layer = routeLayers[routeType];
        if (!layer) return;
        visibleRoutes.has(routeType) ? (!map.hasLayer(layer) && layer.addTo(map))
            : (map.hasLayer(layer) && map.removeLayer(layer));
    });
    document.querySelectorAll('.route-btn').forEach(btn => {
        const rt = btn.dataset.route;
        if (!rt || rt === 'all') return;
        btn.classList.toggle('active', visibleRoutes.has(rt));
    });
}

// ── Profile management ────────────────────────────────────────
async function saveCurrentProfile() {
    const profileName = prompt('Enter a name for this profile:');
    if (!profileName?.trim()) return;

    const dislikedSurfaces = [];
    if (document.getElementById('gravel')?.checked) dislikedSurfaces.push('gravel');

    try {
        const response = await fetch('/create_profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile_name: profileName.trim(),
                max_slope: parseFloat(document.getElementById('slope')?.value || 4),
                disliked_surfaces: dislikedSurfaces,
                comfort_weight: parseFloat(document.getElementById('comfort')?.value || 0.5)
            })
        });
        const result = await response.json();
        if (result.success) { alert('Profile saved!'); if (typeof loadProfiles === 'function') loadProfiles(); }
        else alert('Error: ' + result.error);
    } catch { alert('Failed to save profile.'); }
}

async function handleRouteCalculation() { /* auto-recalculate hook */ }
