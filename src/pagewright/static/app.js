/* Pagewright Editor — token-driven, paged.js-aware, production polish.
 *
 * Visual-only refit on top of the v3 functional base.
 * - Inline SVG icons (icons.js) hydrated at boot
 * - Theme controller: light / dark / auto, persisted, system-aware
 * - Branded tooltips with keyboard-shortcut chips (replaces native title)
 * - Skeleton tree shown while /api/tree resolves
 * - Status pill is now an icon + label state machine
 * - Outline highlights the heading the cursor is inside
 * - Relative-time "Saved 3m ago" stamp updates every 30s
 *
 * Functionality (file ops, palette, resizer, etc.) is unchanged from v3.
 */

(() => {
  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // ─── State ──────────────────────────────────────────────────────────
  let editor = null;
  let tree = [];
  let currentPath = null;
  let currentEtag = null;          // server's last-known etag for currentPath
  let lastSavedContent = "";
  let lastSavedAt = null;
  let dirty = false;
  let saveTimer = null;
  let saveInFlight = false;
  let previewTimer = null;
  let editorWidthPct = parseFloat(localStorage.getItem("editor.split") || "50");
  let modalCloseHandler = null;    // bound when modal opens, unbound on close

  // Preview state machine (no infinite-spinner bug)
  let previewLoadingTimer = null;
  let previewSafetyTimer = null;
  let pendingPreviewURL = null;

  // Heading-aware preview navigation. Each heading in the rendered preview
  // carries id="h-N" (1-based, h1+h2+h3 in document order); the same N
  // matches outlineItems[N-1]. Used by outline clicks and (via the
  // restorePreviewPosition machinery) to keep the iframe scrolled to
  // the same heading across re-renders.
  let pendingScrollHeading = null;   // queue when iframe isn't ready yet

  // Preview zoom. 0 = fit-to-width (auto-recalculates on resize).
  // Any positive number is an explicit factor, e.g. 1.0 = 100 %.
  // Persisted across reloads so the user's preferred zoom sticks.
  const ZOOM_KEY = "editor.previewZoom";
  const ZOOM_STEP = 0.1;
  const ZOOM_MIN = 0.4;
  const ZOOM_MAX = 2.0;
  const A4_PX = 794;  // 210 mm at 96 dpi — the rendered page width
  let previewZoom = parseFloat(localStorage.getItem(ZOOM_KEY) || "0");
  if (!isFinite(previewZoom) || previewZoom < 0) previewZoom = 0;

  const STATUS_RESET_MS = 2400;
  const SPINNER_DELAY_MS = 280;
  const SPINNER_MAX_MS = 12000; // longer to accommodate paged.js renders

  const THEME_KEY = "editor.theme";
  const THEME_CYCLE = ["auto", "light", "dark"];
  const THEME_LABEL = { auto: "Auto", light: "Light", dark: "Dark" };

  const MODE_KEY = "editor.previewMode";
  const MODES = ["continuous", "paged"];
  let previewMode = MODES.includes(localStorage.getItem(MODE_KEY))
    ? localStorage.getItem(MODE_KEY)
    : "continuous";

  // ─── Boot ───────────────────────────────────────────────────────────
  function init() {
    // 1. Hydrate icons before anything else paints
    if (window.renderIcons) window.renderIcons();

    // 2. Theme first (no flash of unthemed content)
    setupTheme();

    // 3. Editor + interactions
    setupEditor();
    setupResizer();
    setupSidebarToggle();
    setupSearch();
    setupToolbar();
    setupShortcuts();
    setupPalette();
    setupTooltips();
    setupModeToggle();
    setupPagedListener();
    setupPreviewActions();
    setupBeforeUnload();
    setupResponsiveLayout();
    applySplit(editorWidthPct);
    applyModeUI();

    if (localStorage.getItem("editor.sidebar") === "collapsed") {
      toggleSidebar(true);
    }

    // 4. Periodic relative-time refresh on the "Saved Xm ago" label
    setInterval(refreshLastSaved, 30 * 1000);

    // 5. Load content
    loadTree().catch((err) => {
      console.error(err);
      setStatus("error", "Failed to load");
    });
  }

  // ─── Theme controller ──────────────────────────────────────────────
  function setupTheme() {
    const stored = localStorage.getItem(THEME_KEY);
    const theme = THEME_CYCLE.includes(stored) ? stored : "auto";
    applyTheme(theme);

    $("#theme-toggle").addEventListener("click", cycleTheme);

    // Watch system preference for the auto branch — when it flips, the
    // CSS does the work, but we re-render the preview iframe so its
    // injected dark-mode override stays in sync.
    if (window.matchMedia) {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      mq.addEventListener("change", () => {
        if (currentTheme() === "auto") {
          requestPreviewRefresh(120);
        }
      });
    }
  }

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") || "auto";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_KEY, theme);

    const btn = $("#theme-toggle");
    btn.classList.remove("is-light", "is-dark", "is-auto");
    btn.classList.add(`is-${theme}`);
    btn.setAttribute("data-tooltip", `Theme · ${THEME_LABEL[theme]}`);

    // Re-render preview so the iframe's dark-mode override switches.
    if (currentPath) requestPreviewRefresh(60);
  }

  function cycleTheme() {
    const cur = currentTheme();
    const idx = THEME_CYCLE.indexOf(cur);
    const next = THEME_CYCLE[(idx + 1) % THEME_CYCLE.length];
    applyTheme(next);
  }

  function effectiveTheme() {
    const t = currentTheme();
    if (t !== "auto") return t;
    if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) return "dark";
    return "light";
  }

  // ─── Editor (CodeMirror) ───────────────────────────────────────────
  function setupEditor() {
    editor = CodeMirror.fromTextArea($("#editor"), {
      mode: "markdown",
      lineNumbers: true,
      lineWrapping: true,
      autoCloseBrackets: true,
      styleActiveLine: { nonEmpty: false },
      indentUnit: 2,
      tabSize: 2,
      extraKeys: {
        "Cmd-S": save,
        "Ctrl-S": save,
        "Cmd-B": () => wrapInline("**"),
        "Ctrl-B": () => wrapInline("**"),
        "Cmd-I": () => wrapInline("_"),
        "Ctrl-I": () => wrapInline("_"),
        "Cmd-F": "findPersistent",
        "Ctrl-F": "findPersistent",
      },
    });
    // Force CodeMirror's internal viewport math to use 100% of the host.
    // The CSS rule alone isn't sufficient: the library captures a
    // dimension at construction time from the textarea's offsetHeight,
    // and only setSize updates the line-renderer's viewport so the
    // lower half of the buffer paints.
    editor.setSize("100%", "100%");
    editor.on("change", onEdit);
    editor.on("cursorActivity", () => {
      updatePosition();
      updateOutlineActive();
    });
  }

  // ─── Tree (sidebar) ────────────────────────────────────────────────
  async function loadTree() {
    setStatus("ready", "Loading…");
    const res = await fetch("/api/tree");
    if (!res.ok) throw new Error(`tree HTTP ${res.status}`);
    tree = await res.json();
    renderTree();
    const initial = restoreLastFile() || firstPath();
    if (initial) await loadFile(initial);
    setStatus("ready", "Ready");
  }

  function firstPath() {
    for (const book of tree) {
      for (const part of book.parts) {
        if (part.chapters[0]) return part.chapters[0].path;
      }
    }
    return null;
  }

  function restoreLastFile() {
    const last = localStorage.getItem("editor.lastFile");
    if (!last) return null;
    const all = tree.flatMap((b) => b.parts.flatMap((p) => p.chapters.map((c) => c.path)));
    return all.includes(last) ? last : null;
  }

  function renderTree() {
    const treeEl = $("#tree");
    treeEl.innerHTML = "";
    if (!tree.length) {
      treeEl.innerHTML = `<div class="tree-empty"><strong>No books found</strong><br>Add a config.yaml under <code>content/</code></div>`;
      return;
    }
    for (const book of tree) treeEl.appendChild(renderBook(book));
  }

  function renderBook(book) {
    const bookEl = document.createElement("div");
    bookEl.className = "book";
    bookEl.dataset.slug = book.slug;

    const header = document.createElement("div");
    header.className = "book-header";
    const title = document.createElement("div");
    title.className = "book-title";
    title.textContent = book.title;
    header.appendChild(title);

    const meta = document.createElement("div");
    meta.className = "book-meta";
    const bits = [];
    if (book.edition) bits.push(`Ed. ${book.edition}`);
    bits.push(`${book.total_chapters} chapters`);
    meta.append(bits.join(" · "));
    if (book.audience_form) {
      const pill = document.createElement("span");
      pill.className = "form-pill";
      pill.textContent = book.audience_form;
      meta.appendChild(pill);
    }
    header.appendChild(meta);
    bookEl.appendChild(header);

    for (const part of book.parts) {
      const partEl = document.createElement("div");
      partEl.className = "part";
      const partTitle = document.createElement("div");
      partTitle.className = "part-title";
      partTitle.textContent = part.title || "—";
      partEl.appendChild(partTitle);
      bookEl.appendChild(partEl);

      for (const ch of part.chapters) bookEl.appendChild(renderChapter(book, ch));
    }
    return bookEl;
  }

  function renderChapter(book, ch) {
    const el = document.createElement("div");
    el.className = "chapter";
    el.dataset.path = ch.path;
    el.dataset.bookSlug = book.slug;
    el.tabIndex = 0;

    const num = document.createElement("span");
    num.className = "chapter-num";
    num.textContent = String(ch.number || 0).padStart(2, "0");
    el.appendChild(num);

    const body = document.createElement("div");
    body.className = "chapter-body";
    const t = document.createElement("div");
    t.className = "chapter-title";
    t.textContent = ch.title || ch.filename;
    body.appendChild(t);
    if (ch.description) {
      const d = document.createElement("div");
      d.className = "chapter-desc";
      d.textContent = ch.description;
      body.appendChild(d);
    }
    el.appendChild(body);

    el.addEventListener("click", () => loadFile(ch.path));
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        loadFile(ch.path);
      }
    });
    return el;
  }

  function highlightActive() {
    $$(".chapter").forEach((el) => {
      const isActive = el.dataset.path === currentPath;
      el.classList.toggle("active", isActive);
      if (isActive) el.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  }

  function markDirty() {
    $$(".chapter").forEach((el) => {
      el.classList.toggle("dirty", el.dataset.path === currentPath && dirty);
    });
  }

  // ─── Search / filter ───────────────────────────────────────────────
  function setupSearch() {
    const inp = $("#search");
    inp.addEventListener("input", () => filterTree(inp.value.trim().toLowerCase()));
    inp.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        inp.value = "";
        filterTree("");
        inp.blur();
      }
    });
  }

  function filterTree(q) {
    if (!q) {
      $$("#tree .chapter, #tree .book, #tree .part, #tree .tree-empty").forEach((el) => (el.style.display = ""));
      return;
    }
    let anyMatch = false;
    $$("#tree .book").forEach((bookEl) => {
      let match = false;
      bookEl.querySelectorAll(".chapter").forEach((chEl) => {
        const text = chEl.textContent.toLowerCase();
        const slug = bookEl.dataset.slug.toLowerCase();
        const m = text.includes(q) || slug.includes(q);
        chEl.style.display = m ? "" : "none";
        if (m) match = true;
      });
      bookEl.querySelectorAll(".part").forEach((p) => (p.style.display = match ? "" : "none"));
      bookEl.style.display = match ? "" : "none";
      if (match) anyMatch = true;
    });
    let emptyEl = $("#tree-search-empty");
    if (!anyMatch) {
      if (!emptyEl) {
        emptyEl = document.createElement("div");
        emptyEl.id = "tree-search-empty";
        emptyEl.className = "tree-empty";
        $("#tree").appendChild(emptyEl);
      }
      emptyEl.innerHTML = `Nothing matches <strong>"${escapeHtml(q)}"</strong><br>Try a different query.`;
      emptyEl.style.display = "";
    } else if (emptyEl) {
      emptyEl.style.display = "none";
    }
  }

  // ─── File ops ──────────────────────────────────────────────────────
  async function loadFile(path) {
    if (dirty && path !== currentPath) {
      const ok = await confirmDialog({
        title: "Discard unsaved changes?",
        message: "You have unsaved edits in the current file. Switching chapters will discard them.",
        confirmLabel: "Discard & switch",
        cancelLabel: "Stay here",
        danger: true,
      });
      if (!ok) return;
    }
    setStatus("ready", "Loading…");
    try {
      const res = await fetch(`/api/file?path=${encodeURIComponent(path)}`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error?.message || `HTTP ${res.status}`);
      }
      const text = await res.text();
      currentEtag = res.headers.get("ETag");
      const switching = path !== currentPath;
      currentPath = path;
      lastSavedContent = text;
      dirty = false;
      // A new chapter file means heading-id "h-N" no longer maps to the
      // previous chapter's outline — drop any queued/last-synced heading
      // so the preview lands at the top of the new chapter.
      if (switching) {
        pendingScrollHeading = null;
      }
      editor.setValue(text);
      editor.clearHistory();
      editor.focus();
      // setValue resets the visible viewport but the gutter/measure
      // cache can lag — refresh on the next frame so the lower half
      // of the buffer doesn't render blank.
      requestAnimationFrame(() => { try { editor.refresh(); } catch (_) {} });
      localStorage.setItem("editor.lastFile", path);
      updateBreadcrumb();
      updateFilepath();
      updateWordCount();
      renderOutline();
      updateOutlineActive();
      highlightActive();
      markDirty();
      refreshPreview();
      setStatus("ready", "Ready");
    } catch (err) {
      console.error(err);
      setStatus("error", "Load failed");
      showToast({
        kind: "error",
        title: "Could not load chapter",
        message: err?.message || "Unknown error",
      });
    }
  }

  // Up to 3 attempts: immediate, +400 ms, +1200 ms. Conflict (HTTP 409)
  // is handled separately — the user picks "overwrite" or "reload".
  const SAVE_RETRY_DELAYS = [0, 400, 1200];

  async function save() {
    if (!currentPath || !dirty) return;
    if (saveInFlight) return;  // a previous save is still pending
    if (saveTimer) {
      clearTimeout(saveTimer);
      saveTimer = null;
    }
    setStatus("saving", "Saving");
    saveInFlight = true;
    const content = editor.getValue();
    const path = currentPath;
    const etag = currentEtag;

    let lastErr = null;
    for (let attempt = 0; attempt < SAVE_RETRY_DELAYS.length; attempt++) {
      if (attempt > 0) await new Promise((r) => setTimeout(r, SAVE_RETRY_DELAYS[attempt]));
      try {
        const res = await fetch("/api/file", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path, content, ifMatch: etag }),
        });

        if (res.status === 409) {
          // Conflict — file changed externally. Don't retry; ask the
          // user. Keep `dirty` true so their work isn't lost.
          const data = await res.json().catch(() => ({}));
          saveInFlight = false;
          setStatus("modified", "Modified");
          await handleSaveConflict(path, content, data?.error?.currentEtag || null);
          return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        // Only commit success if the user is still on the same file
        // and hasn't typed something newer mid-flight. If they have,
        // dirty is true again — leave it; the next autosave covers it.
        if (path === currentPath) {
          if (editor.getValue() === content) {
            lastSavedContent = content;
            dirty = false;
            markDirty();
          }
          currentEtag = data.etag || currentEtag;
        }
        lastSavedAt = new Date();
        setStatus("saved", `Saved · ${formatBytes(data.bytes)}`);
        refreshLastSaved();
        // Save is the natural sync point: always refresh the preview
        // (paged mode included) so the user sees their saved edits.
        requestPreviewRefresh(120);
        setTimeout(() => {
          if (!dirty) setStatus("ready", "Ready");
        }, STATUS_RESET_MS);
        saveInFlight = false;
        return;
      } catch (err) {
        lastErr = err;
        // Network errors or 5xx → retry. Other 4xx → break.
        if (err.message && /^HTTP 4/.test(err.message) && !/HTTP 408|HTTP 429/.test(err.message)) {
          break;
        }
      }
    }

    // All retries exhausted.
    saveInFlight = false;
    setStatus("error", "Save failed");
    console.error("save failed", lastErr);
    showToast({
      kind: "error",
      title: "Save failed",
      message: lastErr?.message || "Unable to reach the server. Your changes are still in the editor.",
      duration: 0,
      actions: [
        { label: "Retry", primary: true, onClick: () => save() },
      ],
    });
  }

  async function handleSaveConflict(path, localContent, serverEtag) {
    showToast({
      kind: "warn",
      title: "File changed externally",
      message: "Another process modified this file since you opened it.",
      duration: 4500,
    });
    const choice = await openModal({
      title: "Save conflict",
      body: `<p>The file <code>${escapeHtml(path)}</code> was changed on disk after you opened it.</p>
             <p>Pick how to resolve:</p>
             <ul style="margin:10px 0 0 18px; line-height:1.6;">
               <li><strong>Reload</strong>: discard your edits and load the disk version.</li>
               <li><strong>Overwrite</strong>: keep your edits and write them out, replacing the disk version.</li>
             </ul>`,
      actions: [
        { label: "Cancel", value: "cancel" },
        { label: "Reload from disk", value: "reload" },
        { label: "Overwrite disk", danger: true, value: "overwrite" },
      ],
      dismissValue: "cancel",
    });
    if (choice === "reload") {
      // Reload the current file fresh; user explicitly chose this so
      // we bypass the dirty-check confirm.
      dirty = false;
      currentEtag = null;
      await loadFile(path);
    } else if (choice === "overwrite") {
      currentEtag = serverEtag;  // pretend we're up to date with server
      // Re-trigger save with fresh etag.
      await save();
    }
    // cancel: do nothing; user keeps editing with dirty=true.
  }

  // Word-count + outline rebuild are O(file-size); they don't need to
  // run on every keystroke. Debounce so long files stay snappy on
  // burst typing — at 200 ms idle the UI feels live, at 50 KB the
  // outline parser is still ~1 ms but we skip 95 %+ of redundant work.
  let editSideEffectsTimer = null;
  function scheduleEditSideEffects() {
    if (editSideEffectsTimer) clearTimeout(editSideEffectsTimer);
    editSideEffectsTimer = setTimeout(() => {
      editSideEffectsTimer = null;
      updateWordCount();
      renderOutline();
    }, 200);
  }

  function onEdit() {
    const content = editor.getValue();
    dirty = content !== lastSavedContent;
    markDirty();
    if (dirty) setStatus("modified", "Modified");
    scheduleEditSideEffects();
    if (saveTimer) clearTimeout(saveTimer);
    // Single source of preview refresh: autosave at 1500 ms triggers
    // requestPreviewRefresh(120) → refreshPreview. An additional
    // edit-driven refresh would only re-render the on-disk content
    // (which hasn't received the edit yet), and worse, would race the
    // save-driven refresh — the first navigation resets iframe.scrollY
    // to 0, so the second refresh captures "top" as the user's
    // position and jumps the page back to the start of the chapter.
    if (dirty) saveTimer = setTimeout(save, 1500);
  }

  // ─── Preview ───────────────────────────────────────────────────────

  // Edit-driven debounce: skipped in paged mode because paged.js takes
  // 1-3 s to repaginate and re-running it on every keystroke is noisy.
  // For paged mode, the natural sync point is save → refreshPreview()
  // (see `save` and `requestPreviewRefresh`).
  function schedulePreview(delay) {
    if (previewMode === "paged") return;
    if (previewTimer) clearTimeout(previewTimer);
    previewTimer = setTimeout(refreshPreview, delay);
  }

  // Non-edit refresh trigger (theme change, system dark-mode flip, mode
  // toggle, save). Always runs — paged mode included — because these
  // events are user-intentional and infrequent enough that the
  // re-pagination cost is acceptable.
  function requestPreviewRefresh(delay) {
    if (previewTimer) clearTimeout(previewTimer);
    previewTimer = setTimeout(refreshPreview, delay);
  }

  // Snapshot of the user's vertical reading position in the iframe,
  // captured immediately before a refresh and replayed after the new
  // content settles. Two channels because each survives different
  // failure modes:
  //   • headingId — robust against content-height changes above the
  //     visible area; jumps to the same logical place even if the
  //     line that used to be at y=420 is now at y=430.
  //   • scrollY — fallback for documents with no headings visible
  //     (e.g. the user is in the chapter opener before the first H1).
  // Cleared as soon as either is consumed.
  let pendingRestoreHeading = null;
  let pendingRestoreScrollY = 0;

  // Find the heading-id closest to the top of the iframe viewport.
  // Returns the numeric N from id="h-N", or null if no heading is
  // anywhere in view. Used to capture "where is the user reading?"
  // before a refresh, so we can land them at the same logical spot
  // afterwards rather than at y=0.
  function topmostVisibleHeadingId() {
    const iframe = $("#preview");
    if (!iframe) return null;
    let doc;
    try { doc = iframe.contentDocument; } catch (_) { return null; }
    if (!doc) return null;
    const headings = doc.querySelectorAll('[id^="h-"]');
    if (!headings.length) return null;
    let best = null;
    let bestTop = -Infinity;
    // We want the heading whose top is closest to but not below 0,
    // i.e. the "current section" the user is reading. If every
    // heading is below the viewport, fall back to the first one.
    for (const h of headings) {
      const top = h.getBoundingClientRect().top;
      if (top <= 4 && top > bestTop) {
        bestTop = top;
        best = h;
      }
    }
    if (!best) best = headings[0];
    const m = /^h-(\d+)$/.exec(best.id);
    return m ? parseInt(m[1], 10) : null;
  }

  function refreshPreview() {
    if (!currentPath) return;
    const iframe = $("#preview");
    const theme = effectiveTheme();
    const url = `/api/preview?path=${encodeURIComponent(currentPath)}&theme=${theme}&mode=${previewMode}&_=${Date.now()}`;

    // Capture the user's reading position so the post-refresh content
    // lands at the same place. Heading-id is the primary anchor;
    // scrollY is a fallback for the no-heading-visible case.
    pendingRestoreHeading = topmostVisibleHeadingId();
    try { pendingRestoreScrollY = iframe.contentWindow?.scrollY || 0; } catch (_) { pendingRestoreScrollY = 0; }

    pendingPreviewURL = url;  // updated below to resolved absolute URL
    if (previewLoadingTimer) clearTimeout(previewLoadingTimer);
    if (previewSafetyTimer) clearTimeout(previewSafetyTimer);
    const loadingLabel = previewMode === "paged" ? "Paginating" : "Rendering";
    $("#preview-loading-text").textContent = loadingLabel;
    if (previewMode === "paged") {
      $("#page-count-text").textContent = "…";
    }
    // In paged mode, paged.js layout begins after iframe load — show the
    // spinner immediately so the user has feedback during pagination.
    const spinnerDelay = previewMode === "paged" ? 0 : SPINNER_DELAY_MS;
    previewLoadingTimer = setTimeout(() => showLoading(true), spinnerDelay);
    previewSafetyTimer = setTimeout(() => clearPreviewState(), SPINNER_MAX_MS);

    const handleDone = () => {
      if (iframe.src !== pendingPreviewURL) return;
      if (previewMode === "continuous") {
        restorePreviewPosition();
        clearPreviewState();
      }
    };

    iframe.onload = handleDone;
    iframe.onerror = clearPreviewState;
    iframe.src = url;
    // The iframe's src getter returns the resolved absolute URL
    // (http://host/api/preview?…), but the assignment used the relative
    // form. Read back the resolved value so handleDone's stale-load
    // guard (`iframe.src !== pendingPreviewURL`) compares apples to
    // apples — without this, the guard always trips and the restore
    // never runs.
    pendingPreviewURL = iframe.src;
  }

  // Replay the pre-refresh reading position. Priority order:
  //   1. pendingScrollHeading (an explicit user nav: outline click,
  //      cursor-driven sync) — wins because it's a deliberate action.
  //   2. pendingRestoreHeading (the heading the user was reading
  //      before the refresh) — keeps the page from jumping to top
  //      after autosave / theme toggle / etc.
  //   3. pendingRestoreScrollY (raw pixel offset) — fallback when no
  //      heading was visible (early in the chapter opener).
  // All restores are instant ("auto"), never smooth — animations on a
  // re-render look like the page is "drifting" during normal typing.
  function restorePreviewPosition() {
    if (pendingScrollHeading != null) {
      if (scrollPreviewToHeading(pendingScrollHeading, "auto")) {
        pendingScrollHeading = null;
        pendingRestoreHeading = null;
        pendingRestoreScrollY = 0;
        return;
      }
    }
    if (pendingRestoreHeading != null) {
      if (scrollPreviewToHeading(pendingRestoreHeading, "auto")) {
        pendingRestoreHeading = null;
        pendingRestoreScrollY = 0;
        return;
      }
    }
    if (pendingRestoreScrollY > 0) {
      try {
        const iframe = $("#preview");
        iframe.contentWindow.scrollTo(0, pendingRestoreScrollY);
      } catch (_) {}
      pendingRestoreScrollY = 0;
    }
  }

  function clearPreviewState() {
    if (previewLoadingTimer) { clearTimeout(previewLoadingTimer); previewLoadingTimer = null; }
    if (previewSafetyTimer) { clearTimeout(previewSafetyTimer); previewSafetyTimer = null; }
    showLoading(false);
  }

  // Scroll the preview iframe to a heading by its positional id.
  // Returns true if the heading was found and scrolled, false otherwise.
  // In paged mode, paged.js wraps each heading inside .pagedjs_page, but
  // scrollIntoView walks up the offset tree fine — no special handling
  // is required.
  function scrollPreviewToHeading(n, behavior = "smooth") {
    if (!n) return false;
    const iframe = $("#preview");
    if (!iframe) return false;
    let target = null;
    try {
      const doc = iframe.contentDocument;
      target = doc && doc.getElementById(`h-${n}`);
    } catch (_) {
      return false;
    }
    if (!target) return false;
    target.scrollIntoView({ behavior, block: "start" });
    return true;
  }

  function showLoading(visible) {
    const el = $("#preview-loading");
    if (visible) el.removeAttribute("hidden");
    else el.setAttribute("hidden", "");
  }

  // ─── Preview mode toggle ───────────────────────────────────────────
  function setupModeToggle() {
    $$(".seg-btn[data-mode]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const mode = btn.dataset.mode;
        if (mode === previewMode) return;
        previewMode = mode;
        localStorage.setItem(MODE_KEY, mode);
        applyModeUI();
        refreshPreview();
      });
    });
  }

  function applyModeUI() {
    $$(".seg-btn[data-mode]").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.mode === previewMode);
    });
    const pageCount = $("#page-count");
    if (previewMode === "paged") pageCount.removeAttribute("hidden");
    else pageCount.setAttribute("hidden", "");
  }

  // Listen for paged.js render-complete posts from the iframe so we can
  // hide the spinner and update the page count badge.
  function setupPagedListener() {
    window.addEventListener("message", (e) => {
      if (!e.data || e.data.type !== "paged-rendered") return;
      const pages = e.data.pages | 0;
      $("#page-count-text").textContent =
        pages === 1 ? "1 page" : `${pages.toLocaleString()} pages`;
      clearPreviewState();
      // paged.js has finished laying out — replay the user's reading
      // position (deliberate nav first, then captured heading, then
      // raw scrollY). Without this, every save jumps the user back to
      // page 1 of the chapter.
      restorePreviewPosition();
    });
  }

  function setupPreviewActions() {
    $("#preview-open-btn").addEventListener("click", () => {
      if (!currentPath) return;
      const theme = effectiveTheme();
      const url = `/api/preview?path=${encodeURIComponent(currentPath)}&theme=${theme}&mode=${previewMode}`;
      window.open(url, "_blank", "noopener");
    });
    setupZoomControls();
  }

  // ─── Preview zoom ──────────────────────────────────────────────────
  function setupZoomControls() {
    $("#zoom-in").addEventListener("click", () => bumpZoom(+ZOOM_STEP));
    $("#zoom-out").addEventListener("click", () => bumpZoom(-ZOOM_STEP));
    $("#zoom-fit").addEventListener("click", () => setZoom(0));
    applyZoom();
  }

  function effectiveZoom() {
    if (previewZoom > 0) return clampZoom(previewZoom);
    const wrap = $("#preview-wrap");
    if (!wrap) return 1;
    const w = wrap.clientWidth;
    if (!w) return 1;
    // 24 px breathing room so the page isn't flush against the rail.
    return clampZoom((w - 24) / A4_PX);
  }

  function clampZoom(z) {
    if (!isFinite(z) || z <= 0) return 1;
    return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z));
  }

  function applyZoom() {
    const iframe = $("#preview");
    const label = $("#zoom-text");
    const fitBtn = $("#zoom-fit");
    if (!iframe) return;
    const z = effectiveZoom();
    iframe.style.transform = `scale(${z})`;
    iframe.style.width = `${100 / z}%`;
    iframe.style.height = `${100 / z}%`;
    if (label) {
      label.textContent = previewZoom === 0
        ? `Fit · ${Math.round(z * 100)}%`
        : `${Math.round(z * 100)}%`;
    }
    if (fitBtn) fitBtn.classList.toggle("is-fit", previewZoom === 0);
  }

  function bumpZoom(delta) {
    // First click on +/- exits Fit and snaps to the current rendered factor.
    const base = previewZoom > 0 ? previewZoom : effectiveZoom();
    setZoom(clampZoom(base + delta));
  }

  function setZoom(z) {
    previewZoom = z > 0 ? clampZoom(z) : 0;
    if (previewZoom === 0) {
      localStorage.removeItem(ZOOM_KEY);
    } else {
      localStorage.setItem(ZOOM_KEY, String(previewZoom));
    }
    applyZoom();
  }

  // ─── Outline (current chapter headings) ────────────────────────────
  let outlineItems = [];

  function renderOutline() {
    const list = $("#outline-list");
    const section = $("#outline");
    const text = editor ? editor.getValue() : "";
    const lines = text.split("\n");
    const items = [];
    let inFence = false;
    lines.forEach((line, idx) => {
      if (line.trim().startsWith("```")) inFence = !inFence;
      if (inFence) return;
      const m = /^(#{1,3})\s+(.*\S)\s*$/.exec(line);
      if (m) items.push({ level: m[1].length, text: m[2], line: idx });
    });
    outlineItems = items;
    if (!items.length) {
      section.setAttribute("hidden", "");
      list.innerHTML = "";
      return;
    }
    section.removeAttribute("hidden");
    list.innerHTML = "";
    items.forEach((it, i) => {
      const a = document.createElement("a");
      a.className = `outline-item h${it.level}`;
      a.dataset.idx = String(i);
      a.textContent = it.text;
      a.href = "#";
      a.addEventListener("click", (e) => {
        e.preventDefault();
        editor.setCursor({ line: it.line, ch: 0 });
        editor.scrollIntoView({ line: it.line, ch: 0 }, 80);
        editor.focus();
        // Mirror the navigation in the preview. If the iframe still has
        // the previous chapter or paged.js is mid-pagination, queue the
        // scroll — refreshPreview / setupPagedListener will replay it.
        const headingNum = i + 1;
        pendingScrollHeading = headingNum;
        if (scrollPreviewToHeading(headingNum)) {
          pendingScrollHeading = null;
        }
      });
      list.appendChild(a);
    });
    updateOutlineActive();
  }

  function updateOutlineActive() {
    if (!outlineItems.length || !editor) return;
    const cur = editor.getCursor().line;
    let activeIdx = -1;
    for (let i = 0; i < outlineItems.length; i++) {
      if (outlineItems[i].line <= cur) activeIdx = i;
      else break;
    }
    $$(".outline-item").forEach((el, i) => {
      el.classList.toggle("active", i === activeIdx);
    });
    // Cursor-driven preview sync intentionally NOT done here. It used
    // to fight the user: when typing in (say) the H1 title line, every
    // keystroke would drag the preview back to #h-1, even when the
    // user was reading the rendered version of section 4. Outline
    // clicks are an explicit nav and refreshPreview restores the last
    // reading position on its own — those two cover the real use
    // cases without surprising the user.
  }

  // ─── Toolbar ───────────────────────────────────────────────────────
  function setupToolbar() {
    $("#editor-toolbar").addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;
      e.preventDefault();
      runToolbarAction(btn.dataset.action);
      editor.focus();
    });
    $("#save-btn").addEventListener("click", save);
    $("#refresh-btn").addEventListener("click", refreshPreview);
    const helpBtn = $("#help-btn");
    if (helpBtn) helpBtn.addEventListener("click", openHelpDialog);
  }

  const CALLOUTS = { tipp: "Tipp", achtung: "Achtung", prompt: "Prompt-Vorlage" };

  function runToolbarAction(action) {
    switch (action) {
      case "bold":   return wrapInline("**");
      case "italic": return wrapInline("_");
      case "h2":     return prefixLine("## ");
      case "h3":     return prefixLine("### ");
      case "bullet": return prefixLine("- ");
      case "ordered":return prefixLine("1. ");
      case "task":   return prefixLine("- [ ] ");
      case "code":   return wrapBlock("```", "```");
      case "callout-tipp":
      case "callout-achtung":
      case "callout-prompt":
        return insertCallout(CALLOUTS[action.split("-")[1]]);
    }
  }

  function wrapInline(token) {
    const sel = editor.getSelection();
    if (sel) {
      editor.replaceSelection(`${token}${sel}${token}`, "around");
    } else {
      const cur = editor.getCursor();
      editor.replaceRange(`${token}${token}`, cur);
      editor.setCursor({ line: cur.line, ch: cur.ch + token.length });
    }
  }

  function prefixLine(prefix) {
    const cur = editor.getCursor();
    const line = editor.getLine(cur.line);
    if (line.startsWith(prefix)) return;
    editor.replaceRange(prefix, { line: cur.line, ch: 0 });
  }

  function wrapBlock(open, close) {
    const sel = editor.getSelection();
    const text = sel || "code here";
    editor.replaceSelection(`\n${open}\n${text}\n${close}\n`, "around");
  }

  function insertCallout(label) {
    const sel = editor.getSelection() || "Inhalt hier.";
    const text = `> **${label}:** ${sel}\n`;
    editor.replaceSelection(text, "around");
  }

  // ─── Shortcuts ─────────────────────────────────────────────────────
  function setupShortcuts() {
    document.addEventListener("keydown", (e) => {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && e.key === "\\") {
        e.preventDefault();
        toggleSidebar();
      }
      if (meta && e.key === "/") {
        e.preventDefault();
        $("#search").focus();
      }
      if (meta && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        openPalette();
      }
      if (meta && (e.key === "+" || e.key === "=")) {
        e.preventDefault();
        bumpZoom(+ZOOM_STEP);
      }
      if (meta && e.key === "-") {
        e.preventDefault();
        bumpZoom(-ZOOM_STEP);
      }
      if (meta && e.key === "0") {
        e.preventDefault();
        setZoom(0);
      }
      // `?` (Shift+/) opens the help dialog. Skip if the user is
      // typing in an input or the editor — they probably mean to
      // type a literal `?`.
      if (e.key === "?" && !isTextInput(e.target)) {
        e.preventDefault();
        openHelpDialog();
      }
      if (e.key === "Escape" && !$("#palette").hasAttribute("hidden")) {
        closePalette();
      }
    });
  }

  function isTextInput(el) {
    if (!el) return false;
    const tag = (el.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea") return true;
    if (el.isContentEditable) return true;
    // CodeMirror's contenteditable lives inside .CodeMirror-code
    if (el.closest && el.closest(".CodeMirror")) return true;
    return false;
  }

  // ─── Sidebar toggle ────────────────────────────────────────────────
  function setupSidebarToggle() {
    $("#sidebar-toggle").addEventListener("click", () => toggleSidebar());
  }
  function toggleSidebar(forceCollapsed) {
    const sb = $("#sidebar");
    const btn = $("#sidebar-toggle");
    const collapsed = typeof forceCollapsed === "boolean" ? forceCollapsed : !sb.classList.contains("collapsed");
    sb.classList.toggle("collapsed", collapsed);
    btn.classList.toggle("is-collapsed", collapsed);
    btn.setAttribute("aria-expanded", String(!collapsed));
    btn.setAttribute("data-tooltip", collapsed ? "Show sidebar" : "Hide sidebar");
    localStorage.setItem("editor.sidebar", collapsed ? "collapsed" : "open");
    setTimeout(() => editor && editor.refresh(), 240);
  }

  // ─── Resizer ───────────────────────────────────────────────────────
  function setupResizer() {
    const resizer = $("#resizer");
    let dragging = false;

    const onMove = (e) => {
      if (!dragging) return;
      const panes = $("#panes");
      const rect = panes.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const pct = (x / rect.width) * 100;
      const clamped = Math.max(20, Math.min(80, pct));
      applySplit(clamped);
      try { editor.refresh(); } catch (_) {}
    };

    const stop = () => {
      if (!dragging) return;
      dragging = false;
      resizer.classList.remove("dragging");
      document.body.classList.remove("dragging-resize");
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", stop);
      localStorage.setItem("editor.split", String(editorWidthPct));
    };

    resizer.addEventListener("mousedown", (e) => {
      dragging = true;
      resizer.classList.add("dragging");
      document.body.classList.add("dragging-resize");
      e.preventDefault();
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", stop);
    });

    resizer.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft") {
        applySplit(Math.max(20, editorWidthPct - 2));
        editor && editor.refresh();
        e.preventDefault();
      } else if (e.key === "ArrowRight") {
        applySplit(Math.min(80, editorWidthPct + 2));
        editor && editor.refresh();
        e.preventDefault();
      }
    });

    resizer.addEventListener("dblclick", () => {
      applySplit(50);
      editor && editor.refresh();
    });
  }

  function applySplit(pct) {
    editorWidthPct = pct;
    $("#editor-pane").style.flex = `0 0 ${pct}%`;
    $("#preview-pane").style.flex = `1 1 auto`;
  }

  // ─── Command palette (Cmd+K) ───────────────────────────────────────
  function setupPalette() {
    const pal = $("#palette");
    const input = $("#palette-input");
    pal.addEventListener("click", (e) => { if (e.target === pal) closePalette(); });
    input.addEventListener("input", () => renderPalette(input.value));
    input.addEventListener("keydown", paletteKeyHandler);
    $("#palette-btn").addEventListener("click", openPalette);
  }

  let paletteSelected = 0;

  function openPalette() {
    const pal = $("#palette");
    const input = $("#palette-input");
    pal.removeAttribute("hidden");
    input.value = "";
    paletteSelected = 0;
    renderPalette("");
    requestAnimationFrame(() => input.focus());
  }
  function closePalette() {
    $("#palette").setAttribute("hidden", "");
  }

  function paletteEntries() {
    const out = [];
    for (const book of tree) {
      for (const part of book.parts) {
        for (const ch of part.chapters) {
          out.push({
            path: ch.path, number: ch.number, title: ch.title, book: book.slug,
          });
        }
      }
    }
    return out;
  }

  function renderPalette(q) {
    const list = $("#palette-results");
    const entries = paletteEntries();
    const norm = q.trim().toLowerCase();
    const matched = norm
      ? entries.filter((e) => (`${e.number} ${e.title} ${e.book}`).toLowerCase().includes(norm))
      : entries;
    list.innerHTML = "";
    if (matched.length === 0) {
      list.innerHTML = `<li class="palette-empty">No chapter matches "${escapeHtml(q)}"</li>`;
      return;
    }
    matched.slice(0, 80).forEach((e, i) => {
      const li = document.createElement("li");
      li.className = "palette-row" + (i === paletteSelected ? " active" : "");
      li.dataset.path = e.path;
      li.setAttribute("role", "option");
      li.innerHTML = `
        <span class="pr-num">${String(e.number).padStart(2, "0")}</span>
        <span class="pr-title"></span>
        <span class="pr-book"></span>
        <span class="pr-enter"><span data-icon="corner-down-left" data-icon-size="11"></span></span>`;
      li.querySelector(".pr-title").textContent = e.title;
      li.querySelector(".pr-book").textContent = e.book;
      li.addEventListener("click", () => {
        loadFile(e.path);
        closePalette();
      });
      list.appendChild(li);
    });
    if (window.renderIcons) window.renderIcons(list);
  }

  function paletteKeyHandler(e) {
    const list = $("#palette-results");
    const rows = $$(".palette-row", list);
    if (e.key === "ArrowDown") {
      e.preventDefault();
      paletteSelected = Math.min(rows.length - 1, paletteSelected + 1);
      updatePaletteSelection();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      paletteSelected = Math.max(0, paletteSelected - 1);
      updatePaletteSelection();
    } else if (e.key === "Enter") {
      e.preventDefault();
      const row = rows[paletteSelected];
      if (row) {
        loadFile(row.dataset.path);
        closePalette();
      }
    }
  }

  function updatePaletteSelection() {
    const rows = $$(".palette-row");
    rows.forEach((r, i) => r.classList.toggle("active", i === paletteSelected));
    const active = rows[paletteSelected];
    if (active) active.scrollIntoView({ block: "nearest" });
  }

  // ─── Tooltips ──────────────────────────────────────────────────────
  // Branded replacement for native `title=""`. Hovering an element with
  // [data-tooltip] for 600ms shows a custom tooltip; reads optional
  // [data-shortcut] for the keyboard-chip suffix.
  function setupTooltips() {
    const tip = $("#tooltip");
    let target = null;
    let showTimer = null;
    let visible = false;

    const hide = () => {
      if (showTimer) { clearTimeout(showTimer); showTimer = null; }
      tip.classList.remove("is-visible");
      visible = false;
      target = null;
    };

    const show = (el) => {
      const text = el.getAttribute("data-tooltip");
      const shortcut = el.getAttribute("data-shortcut");
      if (!text) return;
      tip.innerHTML = "";
      const lab = document.createElement("span");
      lab.textContent = text;
      tip.appendChild(lab);
      if (shortcut) {
        const k = document.createElement("span");
        k.className = "tip-shortcut";
        k.textContent = shortcut;
        tip.appendChild(k);
      }

      // Position: above by default, below if near top.
      const rect = el.getBoundingClientRect();
      tip.style.left = "0px";
      tip.style.top = "0px";
      tip.classList.add("is-visible");

      const tipRect = tip.getBoundingClientRect();
      let x = rect.left + rect.width / 2 - tipRect.width / 2;
      let y = rect.top - tipRect.height - 8;
      if (y < 8) y = rect.bottom + 8;
      x = Math.max(8, Math.min(window.innerWidth - tipRect.width - 8, x));
      tip.style.left = `${Math.round(x)}px`;
      tip.style.top = `${Math.round(y)}px`;
      visible = true;
    };

    document.addEventListener("mouseover", (e) => {
      const el = e.target.closest("[data-tooltip]");
      if (!el || el === target) return;
      target = el;
      if (showTimer) clearTimeout(showTimer);
      showTimer = setTimeout(() => show(el), 500);
    });
    document.addEventListener("mouseout", (e) => {
      const el = e.target.closest("[data-tooltip]");
      if (el === target) hide();
    });
    document.addEventListener("mousedown", hide, true);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") hide(); });
    window.addEventListener("blur", hide);
    window.addEventListener("scroll", hide, true);
  }

  // ─── Status / breadcrumb / counts ──────────────────────────────────
  function setStatus(state, label) {
    const el = $("#status");
    el.setAttribute("data-state", state);
    $("#status-label").textContent = label;
  }

  function refreshLastSaved() {
    const el = $("#last-saved");
    if (!lastSavedAt) {
      el.setAttribute("hidden", "");
      return;
    }
    el.removeAttribute("hidden");
    const diffSec = Math.max(0, Math.floor((Date.now() - lastSavedAt.getTime()) / 1000));
    let label;
    if (diffSec < 8) label = "just now";
    else if (diffSec < 60) label = `${diffSec}s ago`;
    else if (diffSec < 3600) label = `${Math.floor(diffSec / 60)}m ago`;
    else if (diffSec < 86400) label = `${Math.floor(diffSec / 3600)}h ago`;
    else label = lastSavedAt.toLocaleDateString();
    el.textContent = `Saved ${label}`;
  }

  function updateBreadcrumb() {
    const info = findChapter(currentPath);
    if (!info) {
      $("#crumb-book").textContent = "";
      $("#crumb-chapter").textContent = "";
      return;
    }
    const { book, chapter } = info;
    $("#crumb-book").textContent = book.title;
    $("#crumb-chapter").textContent = `${String(chapter.number).padStart(2, "0")} · ${chapter.title}`;
  }

  function updateFilepath() {
    $("#filepath-text").textContent = currentPath || "No file open";
  }

  function updatePosition() {
    const cur = editor.getCursor();
    $("#position").textContent = `Ln ${cur.line + 1}, Col ${cur.ch + 1}`;
  }

  function updateWordCount() {
    const text = editor.getValue();
    const words = (text.match(/\S+/g) || []).length;
    const chars = text.length;
    $("#word-count").textContent = `${words.toLocaleString()} W · ${chars.toLocaleString()} C`;
    $("#filesize").textContent = `${chars.toLocaleString()} chars`;
    const minutes = Math.max(1, Math.round(words / 230));
    $("#reading-time").textContent = `${minutes} min read`;
  }

  function findChapter(path) {
    for (const book of tree) {
      for (const part of book.parts) {
        for (const ch of part.chapters) {
          if (ch.path === path) return { book, part, chapter: ch };
        }
      }
    }
    return null;
  }

  function formatBytes(n) {
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / 1024 / 1024).toFixed(1)} MB`;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // ─── Toasts ────────────────────────────────────────────────────────
  // Lightweight transient notifications. Auto-dismiss after `duration`
  // unless `actions` is provided (in which case the toast stays until
  // the user clicks an action or the close X). Returns a `dismiss`
  // function so callers can close the toast programmatically.
  const TOAST_ICON = {
    success: "circle-check",
    error: "circle-x",
    warn: "triangle-alert",
    info: "info",
  };
  function showToast({ kind = "info", title, message = "", duration = 3500, actions = null } = {}) {
    const host = $("#toasts");
    if (!host) return () => {};
    const el = document.createElement("div");
    el.className = `toast toast-${kind}`;
    el.setAttribute("role", kind === "error" ? "alert" : "status");

    const icon = document.createElement("span");
    icon.className = "toast-icon";
    icon.innerHTML = window.icons.i(TOAST_ICON[kind] || "info", { size: 14 });
    el.appendChild(icon);

    const body = document.createElement("div");
    body.className = "toast-body";
    if (title) {
      const t = document.createElement("div");
      t.className = "toast-title";
      t.textContent = title;
      body.appendChild(t);
    }
    if (message) {
      const m = document.createElement("div");
      m.className = "toast-msg";
      m.textContent = message;
      body.appendChild(m);
    }
    if (actions && actions.length) {
      const row = document.createElement("div");
      row.className = "toast-actions";
      actions.forEach((a) => {
        const btn = document.createElement("button");
        if (a.primary) btn.classList.add("primary");
        btn.textContent = a.label;
        btn.addEventListener("click", () => { try { a.onClick && a.onClick(); } finally { dismiss(); } });
        row.appendChild(btn);
      });
      body.appendChild(row);
    }
    el.appendChild(body);

    const close = document.createElement("button");
    close.className = "toast-close";
    close.setAttribute("aria-label", "Dismiss");
    close.innerHTML = "×";
    close.addEventListener("click", () => dismiss());
    el.appendChild(close);

    host.appendChild(el);
    let timer = null;
    function dismiss() {
      if (!el.isConnected) return;
      if (timer) { clearTimeout(timer); timer = null; }
      el.classList.add("is-leaving");
      el.addEventListener("animationend", () => el.remove(), { once: true });
    }
    if (!actions && duration > 0) {
      timer = setTimeout(dismiss, duration);
    }
    return dismiss;
  }

  // ─── Modal ─────────────────────────────────────────────────────────
  // Generic confirm/conflict/help dialog. `actions` is required: each
  // is { label, primary?, danger?, value }. Returns a Promise that
  // resolves with the chosen action's `value`, or `null` on Esc /
  // backdrop dismiss (unless `dismissValue` is set).
  function openModal({ title, body, actions, dismissValue = null }) {
    const root = $("#modal");
    const titleEl = $("#modal-title");
    const bodyEl = $("#modal-body");
    const actionsEl = $("#modal-actions");
    titleEl.textContent = title || "";
    bodyEl.innerHTML = "";
    if (typeof body === "string") {
      bodyEl.innerHTML = body;
    } else if (body instanceof Node) {
      bodyEl.appendChild(body);
    }
    actionsEl.innerHTML = "";

    return new Promise((resolve) => {
      const close = (value) => {
        root.setAttribute("hidden", "");
        document.removeEventListener("keydown", onKey, true);
        root.removeEventListener("click", onBackdrop);
        modalCloseHandler = null;
        resolve(value);
      };
      modalCloseHandler = () => close(dismissValue);
      const onKey = (e) => { if (e.key === "Escape") { e.stopPropagation(); close(dismissValue); } };
      const onBackdrop = (e) => { if (e.target.dataset.modalDismiss !== undefined) close(dismissValue); };

      (actions || [{ label: "OK", primary: true, value: true }]).forEach((a) => {
        const btn = document.createElement("button");
        if (a.primary) btn.classList.add("primary");
        if (a.danger) btn.classList.add("danger");
        btn.textContent = a.label;
        btn.addEventListener("click", () => close(a.value));
        actionsEl.appendChild(btn);
      });

      root.removeAttribute("hidden");
      document.addEventListener("keydown", onKey, true);
      root.addEventListener("click", onBackdrop);

      // Focus the primary action so Enter accepts it.
      const primary = actionsEl.querySelector(".primary") || actionsEl.querySelector("button");
      if (primary) requestAnimationFrame(() => primary.focus());
    });
  }

  // Promise-based replacement for window.confirm. Returns true/false.
  async function confirmDialog({ title, message, confirmLabel = "Confirm", cancelLabel = "Cancel", danger = false }) {
    return await openModal({
      title,
      body: `<p>${escapeHtml(message)}</p>`,
      actions: [
        { label: cancelLabel, value: false },
        { label: confirmLabel, primary: !danger, danger, value: true },
      ],
      dismissValue: false,
    });
  }

  function openHelpDialog() {
    const tpl = $("#help-template");
    const body = tpl ? tpl.content.cloneNode(true) : null;
    openModal({
      title: "Keyboard shortcuts",
      body,
      actions: [{ label: "Close", primary: true, value: true }],
      dismissValue: true,
    });
  }

  // ─── Unsaved-changes guard ─────────────────────────────────────────
  function setupBeforeUnload() {
    window.addEventListener("beforeunload", (e) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    });
  }

  // ─── Responsive layout (window + container resize) ─────────────────
  // CodeMirror caches its dimensions and stops painting beyond the
  // last known viewport when its container changes — a window resize,
  // a sidebar toggle, a split drag, even just web font loading can
  // leave the lower half of the buffer painting blank-white. We guard
  // against every one of those:
  //   • window.resize (debounced) — covers OS chrome and full-screen.
  //   • ResizeObserver on #editor-host — covers split drag, sidebar
  //     toggle, and CSS-driven layout shifts.
  //   • document.fonts.ready — refresh once when the typeface settles
  //     so character metrics are correct.
  //   • Two RAFs after init — the very first layout pass is often
  //     measured before flex resolves; refreshing after first paint
  //     fixes the cold-load case where the editor opens half-blank.
  let layoutResizeTimer = null;
  function setupResponsiveLayout() {
    const refresh = () => { try { editor && editor.refresh(); } catch (_) {} };
    const onResize = () => {
      if (layoutResizeTimer) clearTimeout(layoutResizeTimer);
      layoutResizeTimer = setTimeout(() => {
        layoutResizeTimer = null;
        refresh();
        applyZoom();
      }, 80);
    };
    window.addEventListener("resize", onResize);
    window.addEventListener("resize", () => requestAnimationFrame(refresh));

    const host = $("#editor-host");
    if (host && typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(() => refresh());
      ro.observe(host);
    }
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(refresh).catch(() => {});
    }
    // Cold-load belt-and-braces: refresh on the next two animation
    // frames after init so any late layout pass is caught.
    requestAnimationFrame(() => {
      refresh();
      requestAnimationFrame(refresh);
    });
  }

  // ─── Go ────────────────────────────────────────────────────────────
  init();
})();
