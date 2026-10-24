// IncuBrix Dashboard Client Application

let allDestinations = [];
let allConnectors = [];

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  loadSystemData();
  setupPublishForm();
  setupRecommender();
  setupCatalogueSearch();
});

// Tab Navigation
function initTabs() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));

      tab.classList.add("active");
      const targetId = tab.getAttribute("data-tab");
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) targetPanel.classList.add("active");
    });
  });
}

// Initial Data Load
async function loadSystemData() {
  try {
    // 1. Fetch Connectors
    const connResp = await fetch("/connector/v1/manifests");
    if (connResp.ok) {
      const data = await connResp.json();
      allConnectors = data.manifests || [];
      renderConnectors(allConnectors);
      document.getElementById("stat-connectors-count").textContent = allConnectors.length;
    }

    // 2. Fetch Destinations
    const destResp = await fetch("/api/v1/destinations");
    if (destResp.ok) {
      allDestinations = await destResp.json();
      renderCatalogue(allDestinations);
      populateDestinationSelect(allDestinations);
      document.getElementById("stat-destinations-count").textContent = allDestinations.length;
    }
  } catch (err) {
    console.error("Failed loading initial data:", err);
  }
}

// Render Connectors Grid
function renderConnectors(connectors) {
  const container = document.getElementById("connectors-grid-container");
  if (!container) return;

  container.innerHTML = connectors.map(c => `
    <div class="connector-card">
      <div class="card-top">
        <span class="connector-title">${c.name || c.key}</span>
        <span class="tier-badge ${c.tier}">${c.tier}</span>
      </div>
      <div class="connector-meta">
        <div><strong>Key:</strong> <code>${c.key}</code> • v${c.version}</div>
        <div><strong>Auth:</strong> ${c.auth} • <strong>Limits:</strong> ${c.rate_limits?.per_connection?.requests || 60} req/min</div>
      </div>
      <div class="caps-list">
        ${(c.capabilities || []).map(cap => `<span class="cap-tag">${cap}</span>`).join("")}
      </div>
    </div>
  `).join("");
}

// Render Catalogue Table
function renderCatalogue(destinations) {
  const tbody = document.getElementById("catalogue-tbody");
  if (!tbody) return;

  tbody.innerHTML = destinations.map(d => `
    <tr>
      <td><strong>${d.name}</strong></td>
      <td><code>${d.platform_key}</code></td>
      <td><span class="badge badge-blue">${d.category.toUpperCase()}</span></td>
      <td><span class="badge badge-score">Score ${d.relevance_score}/5</span></td>
      <td><code>${d.frequency_cap}</code></td>
      <td>
        ${d.self_promo_allowed 
          ? '<span class="badge badge-green">Allowed</span>' 
          : '<span class="badge badge-red">Banned</span>'}
      </td>
      <td><span class="badge badge-blue">${d.level}</span></td>
      <td><a href="${d.url}" target="_blank" style="color: #38bdf8; text-decoration: none;">${d.url.replace(/^https?:\/\//, '').slice(0, 30)}...</a></td>
    </tr>
  `).join("");
}

function setupCatalogueSearch() {
  const searchInput = document.getElementById("catalogue-search-input");
  const catFilter = document.getElementById("catalogue-category-filter");

  function filterData() {
    const term = searchInput.value.toLowerCase();
    const cat = catFilter.value.toLowerCase();

    const filtered = allDestinations.filter(d => {
      const matchesSearch = d.name.toLowerCase().includes(term) || 
                            d.platform_key.toLowerCase().includes(term) ||
                            (d.audience_tags || []).some(t => t.toLowerCase().includes(term));
      const matchesCat = !cat || d.category.toLowerCase() === cat;
      return matchesSearch && matchesCat;
    });

    renderCatalogue(filtered);
  }

  if (searchInput) searchInput.addEventListener("input", filterData);
  if (catFilter) catFilter.addEventListener("change", filterData);
}

function populateDestinationSelect(destinations) {
  const select = document.getElementById("pub-destination-select");
  if (!select) return;

  select.innerHTML = destinations.slice(0, 40).map(d => `
    <option value="${d.url}">[${d.platform_key.toUpperCase()}] ${d.name} (${d.frequency_cap})</option>
  `).join("");
}

// Job Publisher
function setupPublishForm() {
  const form = document.getElementById("publish-job-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    
    const targetUrl = document.getElementById("pub-destination-select").value;
    const dest = allDestinations.find(d => d.url === targetUrl) || allDestinations[0];

    const title = document.getElementById("pub-title").value;
    const body = document.getElementById("pub-body").value;
    const rawTags = document.getElementById("pub-tags").value;
    const tags = rawTags.split(",").map(t => t.trim()).filter(Boolean);
    const isPromo = document.getElementById("pub-is-promo").checked;
    const aiGen = document.getElementById("pub-ai-generated").checked;

    const payload = {
      rendition: {
        title,
        body,
        tags,
        is_promotional: isPromo,
        ai_generated: aiGen
      },
      destination: dest,
      simulate_slow: false
    };

    // Show monitor UI
    document.getElementById("job-monitor-empty").style.display = "none";
    document.getElementById("job-monitor-active").style.display = "block";
    updateMonitorProgress(10, "RUNNING", "Validating rendition spec and headers...");

    try {
      const resp = await fetch("/api/v1/jobs/publish", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": `ui_job_${Date.now()}`
        },
        body: JSON.stringify(payload)
      });

      const data = await resp.json();
      const jobId = data.job_id;
      document.getElementById("monitor-job-id").textContent = jobId;

      pollJob(jobId);
    } catch (err) {
      console.error("Publish error:", err);
    }
  });
}

async function pollJob(jobId) {
  for (let i = 0; i < 40; i++) {
    await new Promise(r => setTimeout(r, 400));
    try {
      const resp = await fetch(`/api/v1/jobs/${jobId}`);
      if (resp.ok) {
        const job = await resp.json();
        updateMonitorProgress(job.progress, job.status.toUpperCase(), `Status: ${job.status}`);

        if (job.status === "succeeded" || job.status === "failed") {
          document.getElementById("monitor-json-output").textContent = JSON.stringify(job, null, 2);
          break;
        }
      }
    } catch (e) {
      console.error("Polling error:", e);
    }
  }
}

function updateMonitorProgress(pct, statusText, stepText) {
  const fill = document.getElementById("monitor-progress-fill");
  const pctLabel = document.getElementById("monitor-progress-percent");
  const stepLabel = document.getElementById("monitor-step-label");
  const statusBadge = document.getElementById("monitor-job-status");

  if (fill) fill.style.width = `${pct}%`;
  if (pctLabel) pctLabel.textContent = `${pct}%`;
  if (stepLabel) stepLabel.textContent = stepText;
  if (statusBadge) {
    statusBadge.textContent = statusText;
    statusBadge.style.color = statusText === "SUCCEEDED" ? "#10b981" : (statusText === "FAILED" ? "#f43f5e" : "#38bdf8");
  }
}

// Recommender
function setupRecommender() {
  const form = document.getElementById("recommender-form");
  const benchmarkBtn = document.getElementById("btn-eval-benchmark");

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const title = document.getElementById("rec-title").value;
      const body = document.getElementById("rec-body").value;
      const rawTags = document.getElementById("rec-tags").value;
      const tags = rawTags.split(",").map(t => t.trim()).filter(Boolean);

      const resp = await fetch("/api/v1/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rendition: { title, body, tags },
          top_k: 10
        })
      });

      if (resp.ok) {
        const results = await resp.json();
        renderRankedList(results);
      }
    });
  }

  if (benchmarkBtn) {
    benchmarkBtn.addEventListener("click", async () => {
      benchmarkBtn.textContent = "Running Benchmark...";
      const resp = await fetch("/api/v1/recommend/benchmark");
      if (resp.ok) {
        const data = await resp.json();
        document.getElementById("benchmark-score-badge").style.display = "block";
        document.getElementById("benchmark-val").textContent = data.percentage;
        benchmarkBtn.textContent = "📊 Run Benchmark (Precision@10)";
        alert(`Benchmark Complete!\nMean Precision@10: ${data.percentage}\nEvaluated on ${data.total_items_evaluated} creator content items.`);
      }
    });
  }
}

function renderRankedList(items) {
  const container = document.getElementById("recommender-results-list");
  if (!container) return;

  container.innerHTML = items.map(item => `
    <div class="ranked-item-card">
      <div class="rank-pill">#${item.rank}</div>
      <div class="ranked-item-body">
        <div class="ranked-item-header">
          <span class="ranked-name">${item.name}</span>
          <span class="fit-score">${Math.round(item.fit_score * 100)}% Fit</span>
        </div>
        <div class="fit-reason">${item.fit_reason}</div>
      </div>
    </div>
  `).join("");
}

// Certification Cycle
const certBtn = document.getElementById("btn-run-full-certification");
if (certBtn) {
  certBtn.addEventListener("click", async () => {
    certBtn.textContent = "Executing Probe Pack...";
    const container = document.getElementById("cert-results-container");
    container.innerHTML = "<p>Running full lifecycle probes across connectors (Publish -> Confirm Live -> Read Status -> Auto-Delete)...</p>";

    const connectorsToTest = ["discourse", "lemmy", "devto", "ghost", "webhook_hmac", "assisted"];
    const results = [];

    for (const key of connectorsToTest) {
      const resp = await fetch("/api/v1/certification/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          platform_key: key,
          destination_url: `https://probe.${key}.org`
        })
      });
      if (resp.ok) {
        results.push(await resp.json());
      }
    }

    certBtn.textContent = "🛡️ Run Full Certification Cycle";
    container.innerHTML = results.map(r => `
      <div class="cert-card">
        <div class="cert-card-header">
          <strong>${r.connector_key.toUpperCase()}</strong>
          <span class="badge ${r.verdict === 'PASSED' ? 'badge-green' : 'badge-red'}">${r.verdict}</span>
        </div>
        <div style="font-size: 0.75rem; color: #94a3b8; margin-bottom: 0.5rem;">
          <div>Post ID: <code>${r.publish_response.platform_post_id}</code></div>
          <div>Live URL: <a href="${r.publish_response.live_url}" target="_blank" style="color:#38bdf8">${r.publish_response.live_url}</a></div>
          <div>Status Confirmed: <code>${r.status_response.status}</code></div>
          <div>Deleted Confirmation: <code>${r.delete_response.deleted}</code> (${r.duration_seconds}s)</div>
        </div>
      </div>
    `).join("");
  });
}

// Edge Cases Trigger
async function triggerHardCase(caseType) {
  const box = document.getElementById("hardcase-response-box");
  const output = document.getElementById("hardcase-json-output");
  box.style.display = "block";
  output.textContent = "Triggering test case...";

  let endpoint = "";
  let payload = {};

  if (caseType === "promo_violation") {
    endpoint = "/api/v1/rules/check";
    payload = {
      rendition: {
        title: "Buy our discount coupon now",
        body: "Huge 50% discount on all subscriptions",
        is_promotional: true
      },
      destination: {
        name: "Strict Anti-Promo Forum",
        url: "https://strict.test.org",
        platform_key: "discourse",
        connector_key: "discourse",
        self_promo_allowed: false
      }
    };
  } else if (caseType === "freq_cap") {
    endpoint = "/api/v1/rules/check";
    // Check twice on same destination
    payload = {
      rendition: { title: "Second Post In Cap", body: "Testing cooldown period" },
      destination: {
        name: "Weekly Digest Community",
        url: "https://weekly.test.org",
        platform_key: "discourse",
        connector_key: "discourse",
        frequency_cap: "1/7d"
      }
    };
  } else {
    // Other cases via test probe
    endpoint = "/api/v1/jobs/publish";
    payload = {
      rendition: { title: `Probe ${caseType}`, body: "Testing resilience against simulated failures" },
      destination: allDestinations[0] || {
        name: "Test Community",
        url: "https://test.discourse.org",
        platform_key: "discourse",
        connector_key: "discourse"
      }
    };
  }

  try {
    const resp = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await resp.json();
    output.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    output.textContent = `Error: ${err.message}`;
  }
}
