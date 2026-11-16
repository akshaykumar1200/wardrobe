// AURA Fashion AI — Client Application Logic

document.addEventListener("DOMContentLoaded", () => {
  let allItems = [];
  let currentCategory = "all";
  let extractedCandidates = [];

  // DOM Elements
  const navTabs = document.querySelectorAll(".nav-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");
  const garmentsGrid = document.getElementById("garmentsGrid");
  const closetEmptyState = document.getElementById("closetEmptyState");
  const categoryChips = document.querySelectorAll(".chip");
  const searchInput = document.getElementById("searchInput");
  const suggestionsContainer = document.getElementById("suggestionsContainer");
  const btnRefreshSuggestions = document.getElementById("btnRefreshSuggestions");
  const btnQuickUpload = document.getElementById("btnQuickUpload");
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const btnBrowse = document.getElementById("btnBrowse");
  const extractionStatus = document.getElementById("extractionStatus");
  const statusStep = document.getElementById("statusStep");
  const reviewModal = document.getElementById("reviewModal");
  const reviewGarmentsList = document.getElementById("reviewGarmentsList");
  const btnCloseReview = document.getElementById("btnCloseReview");
  const btnDiscardAll = document.getElementById("btnDiscardAll");
  const btnSaveAllToCloset = document.getElementById("btnSaveAllToCloset");
  const statsOverviewGrid = document.getElementById("statsOverviewGrid");

  // ----------------------------------------------------
  // Navigation Tabs
  // ----------------------------------------------------
  function switchTab(tabId) {
    navTabs.forEach(btn => {
      btn.classList.toggle("active", btn.dataset.tab === tabId);
    });
    tabPanes.forEach(pane => {
      pane.classList.toggle("active", pane.id === `pane${tabId.charAt(0).toUpperCase() + tabId.slice(1)}`);
    });

    if (tabId === "closet") loadClosetItems();
    if (tabId === "outfits") loadOutfitSuggestions();
    if (tabId === "analytics") loadAnalytics();
  }

  navTabs.forEach(btn => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  btnQuickUpload.addEventListener("click", () => switchTab("upload"));

  // ----------------------------------------------------
  // Toast Helper
  // ----------------------------------------------------
  function showToast(msg) {
    const toast = document.getElementById("toast");
    toast.textContent = msg;
    toast.classList.remove("hidden");
    setTimeout(() => {
      toast.classList.add("hidden");
    }, 3500);
  }

  // ----------------------------------------------------
  // 1. Digital Closet & Filtering
  // ----------------------------------------------------
  async function loadClosetItems() {
    try {
      const res = await fetch("/api/items");
      allItems = await res.json();
      updateCategoryCounts();
      renderGarmentsGrid();
    } catch (err) {
      console.error("Failed to load items:", err);
      showToast("Error loading closet items");
    }
  }

  function updateCategoryCounts() {
    document.getElementById("countAll").textContent = allItems.length;
    const cats = ["topwear", "bottomwear", "shoes", "accessories", "other"];
    cats.forEach(c => {
      const count = allItems.filter(i => i.category.toLowerCase() === c).length;
      const el = document.getElementById(`count${c.charAt(0).toUpperCase() + c.slice(1)}`);
      if (el) el.textContent = count;
    });
  }

  function renderGarmentsGrid() {
    const query = searchInput.value.toLowerCase().trim();
    const filtered = allItems.filter(item => {
      const matchesCat = currentCategory === "all" || item.category.toLowerCase() === currentCategory.toLowerCase();
      const matchesSearch = !query || 
        item.name.toLowerCase().includes(query) ||
        (item.color_name && item.color_name.toLowerCase().includes(query)) ||
        (item.pattern && item.pattern.toLowerCase().includes(query));
      return matchesCat && matchesSearch;
    });

    garmentsGrid.innerHTML = "";
    if (filtered.length === 0) {
      closetEmptyState.classList.remove("hidden");
      return;
    }
    closetEmptyState.classList.add("hidden");

    filtered.forEach(item => {
      const card = document.createElement("div");
      card.className = "garment-card";
      card.innerHTML = `
        <div class="card-image-box">
          <span class="category-tag">${item.category}</span>
          <img src="${item.image_path}" alt="${item.name}" loading="lazy">
        </div>
        <div class="card-body">
          <h3 class="card-title">${item.name}</h3>
          <div class="card-meta">
            <div class="color-swatch-pill">
              <span class="color-dot" style="background-color: ${item.color_hex};"></span>
              <span>${item.color_name || "Color"}</span>
            </div>
            <span class="pattern-badge">${item.pattern || "solid"}</span>
          </div>
        </div>
        <div class="card-footer">
          <span>Worn: ${item.wear_count || 0} times</span>
          <button class="btn-icon-del" data-id="${item.id}" title="Delete garment">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
          </button>
        </div>
      `;

      card.querySelector(".btn-icon-del").addEventListener("click", async (e) => {
        e.stopPropagation();
        if (confirm(`Remove "${item.name}" from your wardrobe?`)) {
          await deleteItem(item.id);
        }
      });

      garmentsGrid.appendChild(card);
    });
  }

  categoryChips.forEach(chip => {
    chip.addEventListener("click", () => {
      categoryChips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      currentCategory = chip.dataset.category;
      renderGarmentsGrid();
    });
  });

  searchInput.addEventListener("input", renderGarmentsGrid);

  async function deleteItem(id) {
    try {
      const res = await fetch(`/api/items/${id}`, { method: "DELETE" });
      if (res.ok) {
        showToast("Garment deleted");
        loadClosetItems();
      }
    } catch (err) {
      console.error(err);
    }
  }

  // ----------------------------------------------------
  // 2. AI Outfit Studio
  // ----------------------------------------------------
  async function loadOutfitSuggestions() {
    suggestionsContainer.innerHTML = `<div class="text-center" style="padding: 3rem; color: var(--text-muted);">Generating styling combinations via outfit_color.py engine...</div>`;
    try {
      const res = await fetch("/api/suggest");
      const data = await res.json();
      const suggestions = data.suggestions || [];

      if (suggestions.length === 0) {
        suggestionsContainer.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">✨</div>
            <h3>Not enough garments for outfit combinations</h3>
            <p>Upload at least one Topwear, Bottomwear, and Shoes to unlock AI styling recommendations.</p>
            <button class="btn btn-primary" style="margin-top: 1.5rem;" onclick="document.getElementById('tabUpload').click()">Upload First Garment</button>
          </div>
        `;
        return;
      }

      suggestionsContainer.innerHTML = "";
      suggestions.forEach((sug, idx) => {
        const outfitCard = document.createElement("div");
        outfitCard.className = "outfit-card";

        const verdictClass = `verdict-${sug.verdict.toLowerCase()}`;

        // Garments thumb row
        let itemsHtml = "";
        sug.items.forEach(it => {
          itemsHtml += `
            <div class="outfit-garment-thumb">
              <span class="thumb-cat">${it.category}</span>
              <img src="${it.image_path}" alt="${it.name}">
              <span class="thumb-title">${it.name}</span>
            </div>
          `;
        });

        // Palette ribbon
        let paletteHtml = "";
        if (sug.palette && sug.palette.palette) {
          sug.palette.palette.forEach(p => {
            paletteHtml += `<div class="palette-segment" style="width: ${p.share * 100}%; background-color: ${p.hex};" title="${p.name} (${Math.round(p.share*100)}%)"></div>`;
          });
        }

        // Stylist notes
        let notesHtml = "";
        (sug.notes || []).forEach(n => {
          notesHtml += `<li>${n}</li>`;
        });

        outfitCard.innerHTML = `
          <div class="outfit-left">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
              <h2 style="font-size: 1.4rem; color: #fff;">Option #${idx + 1} — ${sug.palette ? (sug.palette.temperature.toUpperCase() + ' ' + sug.palette.contrast.toUpperCase() + ' CONTRAST') : 'LOOK'}</h2>
            </div>
            <div class="outfit-items-row">
              ${itemsHtml}
            </div>
          </div>
          <div class="outfit-eval-sidebar">
            <div>
              <div class="score-badge-box">
                <div>
                  <div style="font-size: 0.75rem; color: var(--text-faint); font-weight: 700; text-transform: uppercase;">Harmony Score</div>
                  <div class="score-number">${sug.score}</div>
                </div>
                <div class="score-verdict ${verdictClass}">${sug.verdict}</div>
              </div>
              <div style="font-size: 0.75rem; color: var(--text-faint); margin-bottom: 0.4rem; font-weight: 700; text-transform: uppercase;">Combined Palette</div>
              <div class="palette-ribbon">
                ${paletteHtml}
              </div>
              <div style="font-size: 0.75rem; color: var(--text-faint); margin-bottom: 0.4rem; font-weight: 700; text-transform: uppercase;">Stylist Advice</div>
              <ul class="stylist-notes-list">
                ${notesHtml}
              </ul>
            </div>
            <button class="btn btn-primary btn-wear-today" style="width: 100%;">
              Wear This Today ✦
            </button>
          </div>
        `;

        outfitCard.querySelector(".btn-wear-today").addEventListener("click", async () => {
          await markOutfitWorn(sug.items.map(i => i.id), sug.score, sug.verdict, sug.palette, sug.notes);
        });

        suggestionsContainer.appendChild(outfitCard);
      });
    } catch (err) {
      console.error(err);
      suggestionsContainer.innerHTML = `<div class="text-center" style="padding: 2rem; color: #ef4444;">Error generating recommendations.</div>`;
    }
  }

  btnRefreshSuggestions.addEventListener("click", loadOutfitSuggestions);

  async function markOutfitWorn(itemIds, score, verdict, palette, notes) {
    try {
      const res = await fetch("/api/wear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: "Daily Outfit",
          item_ids: itemIds,
          score,
          verdict,
          palette,
          notes
        })
      });
      if (res.ok) {
        showToast("Logged outfit wear! Wear count updated.");
        loadOutfitSuggestions();
      }
    } catch (err) {
      console.error(err);
    }
  }

  // ----------------------------------------------------
  // 3. AI Upload & Dual-Model Extraction
  // ----------------------------------------------------
  dropZone.addEventListener("click", () => fileInput.click());
  btnBrowse.addEventListener("click", (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleUpload(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files.length > 0) {
      handleUpload(fileInput.files[0]);
    }
  });

  async function handleUpload(file) {
    extractionStatus.classList.remove("hidden");
    statusStep.textContent = "1. SegFormer Multi-Class Segmentation & BiRefNet Matting...";

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/extract", {
        method: "POST",
        body: formData
      });
      const data = await res.json();

      extractionStatus.classList.add("hidden");

      if (!data.success || !data.garments || data.garments.length === 0) {
        showToast(data.message || "No garments detected in photo.");
        return;
      }

      extractedCandidates = data.garments;
      openReviewModal(data.is_worn, data.garments);
    } catch (err) {
      extractionStatus.classList.add("hidden");
      console.error(err);
      showToast("Extraction error occurred.");
    }
  }

  // ----------------------------------------------------
  // 4. Review & Confirmation Modal
  // ----------------------------------------------------
  function openReviewModal(isWorn, garments) {
    document.getElementById("modalSubtitle").textContent = isWorn 
      ? `Detected ${garments.length} garments from worn outfit photo`
      : `Detected single flat-lay piece. Verify name and category.`;

    reviewGarmentsList.innerHTML = "";
    garments.forEach((g, idx) => {
      const row = document.createElement("div");
      row.className = "review-item-row";
      row.innerHTML = `
        <div class="review-item-thumb">
          <img src="${g.image_path}" alt="${g.name}">
        </div>
        <div class="review-form-fields">
          <div class="form-group">
            <label>Item Name</label>
            <input type="text" class="form-input" id="reviewName_${idx}" value="${g.name}">
          </div>
          <div class="form-group">
            <label>Category</label>
            <select class="form-select" id="reviewCat_${idx}">
              <option value="topwear" ${g.category === 'topwear' ? 'selected' : ''}>Topwear</option>
              <option value="bottomwear" ${g.category === 'bottomwear' ? 'selected' : ''}>Bottomwear</option>
              <option value="shoes" ${g.category === 'shoes' ? 'selected' : ''}>Shoes</option>
              <option value="accessories" ${g.category === 'accessories' ? 'selected' : ''}>Accessories</option>
              <option value="other" ${g.category === 'other' ? 'selected' : ''}>Other</option>
            </select>
          </div>
          <div class="form-group">
            <label>Primary Color</label>
            <input type="text" class="form-input" id="reviewColor_${idx}" value="${g.color_name} (${g.color_hex})">
          </div>
          <div class="form-group">
            <label>Pattern Texture</label>
            <input type="text" class="form-input" id="reviewPattern_${idx}" value="${g.pattern} (${g.pattern_scale})" readonly>
          </div>
        </div>
      `;
      reviewGarmentsList.appendChild(row);
    });

    reviewModal.classList.remove("hidden");
  }

  btnCloseReview.addEventListener("click", () => reviewModal.classList.add("hidden"));
  btnDiscardAll.addEventListener("click", () => reviewModal.classList.add("hidden"));

  btnSaveAllToCloset.addEventListener("click", async () => {
    for (let i = 0; i < extractedCandidates.length; i++) {
      const g = extractedCandidates[i];
      const nameInput = document.getElementById(`reviewName_${i}`);
      const catInput = document.getElementById(`reviewCat_${i}`);

      const payload = {
        name: nameInput ? nameInput.value : g.name,
        category: catInput ? catInput.value : g.category,
        image_path: g.image_path,
        color_hex: g.color_hex,
        color_name: g.color_name,
        colors: g.colors || [],
        pattern: g.pattern,
        pattern_scale: g.pattern_scale,
        area: g.area,
        confidence: g.confidence
      };

      await fetch("/api/items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    }

    reviewModal.classList.add("hidden");
    showToast(`Saved ${extractedCandidates.length} garments to your closet!`);
    switchTab("closet");
  });

  // ----------------------------------------------------
  // 5. Analytics
  // ----------------------------------------------------
  async function loadAnalytics() {
    try {
      const res = await fetch("/api/stats");
      const data = await res.json();

      statsOverviewGrid.innerHTML = `
        <div class="stat-card">
          <div class="stat-card-title">Total Wardrobe Pieces</div>
          <div class="stat-metric-large" style="color: var(--primary);">${data.total_items}</div>
          <p style="color: var(--text-muted); font-size: 0.85rem;">Across all categories</p>
        </div>

        <div class="stat-card">
          <div class="stat-card-title">Outfits Logged</div>
          <div class="stat-metric-large" style="color: var(--accent-emerald);">${data.total_outfits}</div>
          <p style="color: var(--text-muted); font-size: 0.85rem;">Worn and styled</p>
        </div>

        <div class="stat-card" style="grid-column: span 2;">
          <div class="stat-card-title">Top Wardrobe Colors</div>
          <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
            ${Object.entries(data.top_colors).map(([col, cnt]) => `
              <div class="color-swatch-pill" style="padding: 0.4rem 0.8rem;">
                <span class="color-dot" style="background: ${col === 'white' ? '#fff' : col === 'denim' ? '#29384d' : col === 'pine' ? '#2c524a' : '#888'};"></span>
                <span style="font-weight: 600; text-transform: capitalize;">${col} (${cnt})</span>
              </div>
            `).join("")}
          </div>
        </div>
      `;
    } catch (err) {
      console.error(err);
    }
  }

  // Initial Load
  loadClosetItems();
});
