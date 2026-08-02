/**
 * 达芬七 Z-Image — 纯前端灯箱（不经 Gradio 传 base64，可反复开关）
 * 交互对齐常见 SD 预览：点图 / 角标全屏、± 缩放、拖拽、Esc/× 关闭
 */
(function () {
  if (window.__dvFsInit) return;
  window.__dvFsInit = true;

  var scale = 1;
  var tx = 0;
  var ty = 0;
  var dragging = false;
  var lx = 0;
  var ly = 0;

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  function root() {
    return document.getElementById("dv-fs");
  }

  function applyTransform() {
    var img = $("[data-dv-fs='img']", root());
    if (!img) return;
    img.style.transform =
      "translate(" + tx + "px," + ty + "px) scale(" + scale + ")";
    var lab = $("[data-dv-fs='zoom-label']", root());
    if (lab) lab.textContent = Math.round(scale * 100) + "%";
  }

  function resetView() {
    scale = 1;
    tx = 0;
    ty = 0;
    applyTransform();
  }

  function closeFs() {
    var r = root();
    if (r) r.remove();
    document.body.classList.remove("dv-fs-open");
    scale = 1;
    tx = 0;
    ty = 0;
    dragging = false;
  }

  function zoomBy(factor) {
    scale = Math.max(0.2, Math.min(6, scale * factor));
    applyTransform();
  }

  function openFs(src) {
    if (!src) return;
    closeFs();
    var el = document.createElement("div");
    el.id = "dv-fs";
    el.className = "dv-fs-root";
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-modal", "true");
    el.innerHTML =
      '<div class="dv-fs-bar">' +
      '<div class="dv-fs-zoom-group">' +
      '<button type="button" class="dv-fs-btn" data-dv-fs="zoom-out" title="缩小">−</button>' +
      '<span class="dv-fs-zoom-label" data-dv-fs="zoom-label">100%</span>' +
      '<button type="button" class="dv-fs-btn" data-dv-fs="zoom-in" title="放大">+</button>' +
      '<button type="button" class="dv-fs-btn dv-fs-btn-text" data-dv-fs="zoom-reset">重置</button>' +
      "</div>" +
      '<button type="button" class="dv-fs-btn dv-fs-close" data-dv-fs="close" title="关闭">×</button>' +
      "</div>" +
      '<div class="dv-fs-stage" data-dv-fs="stage">' +
      '<img class="dv-fs-img" data-dv-fs="img" alt="preview" draggable="false"/>' +
      "</div>" +
      '<div class="dv-fs-hint">滚轮缩放 · 拖拽移动 · × / Esc 关闭</div>';
    document.body.appendChild(el);
    var img = $("[data-dv-fs='img']", el);
    img.src = src;
    document.body.classList.add("dv-fs-open");
    resetView();
  }

  function pickPreviewSrc(fromHist) {
    var sel = fromHist ? "#dv-hist-preview img" : "#dv-output img";
    var img = document.querySelector(sel);
    if (!img) return "";
    return img.currentSrc || img.src || "";
  }

  /* 工具栏按钮 */
  document.addEventListener(
    "click",
    function (e) {
      var t = e.target && e.target.closest ? e.target.closest("[data-dv-fs]") : null;
      if (t && root()) {
        var act = t.getAttribute("data-dv-fs");
        if (act === "close") {
          e.preventDefault();
          e.stopPropagation();
          closeFs();
          return;
        }
        if (act === "zoom-in") {
          e.preventDefault();
          zoomBy(1.25);
          return;
        }
        if (act === "zoom-out") {
          e.preventDefault();
          zoomBy(1 / 1.25);
          return;
        }
        if (act === "zoom-reset") {
          e.preventDefault();
          resetView();
          return;
        }
      }

      /* 角标 ⛶ / 预览图：纯前端打开，拦截 Gradio */
      var openBtn =
        e.target.closest &&
        e.target.closest("#dv-fs-open-btn, #dv-hist-fs-btn");
      if (openBtn) {
        e.preventDefault();
        e.stopPropagation();
        var hist = openBtn.id === "dv-hist-fs-btn";
        openFs(pickPreviewSrc(hist));
        return;
      }

      if (
        e.target.closest &&
        e.target.closest(
          "#dv-preview-icons, #dv-hist-preview-icons, #dv-copy-btn, #dv-hist-copy-btn"
        )
      ) {
        return;
      }

      var img =
        e.target.closest &&
        e.target.closest("#dv-output img, #dv-hist-preview img");
      if (img) {
        e.preventDefault();
        e.stopPropagation();
        openFs(img.currentSrc || img.src);
      }
    },
    true
  );

  document.addEventListener(
    "keydown",
    function (e) {
      if (!root()) return;
      if (e.key === "Escape") {
        e.preventDefault();
        closeFs();
      } else if (e.key === "+" || e.key === "=") {
        e.preventDefault();
        zoomBy(1.25);
      } else if (e.key === "-") {
        e.preventDefault();
        zoomBy(1 / 1.25);
      } else if (e.key === "0") {
        e.preventDefault();
        resetView();
      }
    },
    true
  );

  document.addEventListener(
    "wheel",
    function (e) {
      if (!root()) return;
      if (!e.target.closest || !e.target.closest("#dv-fs")) return;
      e.preventDefault();
      if (e.deltaY < 0) zoomBy(1.12);
      else zoomBy(1 / 1.12);
    },
    { passive: false, capture: true }
  );

  document.addEventListener(
    "pointerdown",
    function (e) {
      var stage = e.target.closest && e.target.closest("[data-dv-fs='stage']");
      if (!stage || !root()) return;
      if (e.target.closest && e.target.closest(".dv-fs-bar, .dv-fs-btn")) return;
      dragging = true;
      lx = e.clientX;
      ly = e.clientY;
      try {
        stage.setPointerCapture(e.pointerId);
      } catch (_err) {}
      e.preventDefault();
    },
    true
  );

  document.addEventListener(
    "pointermove",
    function (e) {
      if (!dragging || !root()) return;
      tx += e.clientX - lx;
      ty += e.clientY - ly;
      lx = e.clientX;
      ly = e.clientY;
      applyTransform();
    },
    true
  );

  function endDrag(e) {
    if (!dragging) return;
    dragging = false;
    try {
      if (e && e.target && e.target.releasePointerCapture) {
        e.target.releasePointerCapture(e.pointerId);
      }
    } catch (_err) {}
  }
  document.addEventListener("pointerup", endDrag, true);
  document.addEventListener("pointercancel", endDrag, true);

  /* —— 顶栏空隙：压掉 chrome 文档流占位，再按实测把内容贴到 Tab 下 —— */
  function zeroFlow(el, keepFixed) {
    if (!el || !el.style) return;
    el.style.setProperty("margin", "0", "important");
    el.style.setProperty("padding", "0", "important");
    el.style.setProperty("border", "none", "important");
    el.style.setProperty("min-height", "0", "important");
    el.style.setProperty("line-height", "0", "important");
    if (!keepFixed) {
      el.style.setProperty("height", "0", "important");
      el.style.setProperty("max-height", "0", "important");
      el.style.setProperty("overflow", "visible", "important");
    }
  }

  function crushChromeHosts() {
    var ids = [
      "dv-base-css-host",
      "dv-theme-css-host",
      "dv-title-host",
      "dv-stats-shell-host",
      "dv-stats-live",
    ];
    ids.forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      var keep = id === "dv-stats-live";
      zeroFlow(el, keep);
      /* Gradio 外层 wrap 也会占高，向上压 4 层，直到 container / tabs */
      var p = el.parentElement;
      for (var i = 0; i < 5 && p; i++) {
        if (
          p.classList &&
          (p.classList.contains("gradio-container") ||
            p.id === "dv-main-tabs" ||
            p.tagName === "BODY" ||
            p.tagName === "HTML")
        ) {
          break;
        }
        zeroFlow(p, false);
        p = p.parentElement;
      }
    });
  }

  /* 只在加载/主题切换/resize 时校准一次；生成时 DOM 狂刷不要反复改 margin，否则整页上下跳 */
  var gapLocked = false;
  var lastPad = -1;
  var lastMargin = null;
  var syncTimer = null;

  function syncChromeGap(force) {
    try {
      if (!force && gapLocked) return;
      if (window.scrollY > 8) return;
      crushChromeHosts();
      var tab =
        document.querySelector("#dv-main-tabs [role='tablist']") ||
        document.querySelector(".gradio-container [role='tablist']") ||
        document.querySelector(".tab-nav");
      var box =
        document.querySelector(".gradio-container") ||
        document.querySelector(".main");
      var tabsRoot = document.getElementById("dv-main-tabs");
      if (!tab || !box) return;

      var chromeBottom = Math.round(tab.getBoundingClientRect().bottom);
      if (chromeBottom < 60) chromeBottom = 110;
      if (chromeBottom > 200) chromeBottom = 140;

      if (chromeBottom !== lastPad) {
        box.style.setProperty("padding-top", chromeBottom + "px", "important");
        document.documentElement.style.setProperty(
          "--chrome-h",
          chromeBottom + "px"
        );
        lastPad = chromeBottom;
      }

      var content =
        document.querySelector("#dv-workspace") ||
        document.querySelector("#dv-main-tabs .prose") ||
        document.querySelector("#dv-main-tabs h2") ||
        document.querySelector("#dv-main-tabs .dv-section-head");
      if (!content || !tabsRoot) return;
      var gap =
        content.getBoundingClientRect().top - tab.getBoundingClientRect().bottom;
      var nextMargin = null;
      if (gap > 10) {
        nextMargin = -(gap - 6) + "px";
      } else if (gap < -4 && gap > -100) {
        nextMargin = "0";
      }
      if (nextMargin !== null && nextMargin !== lastMargin) {
        tabsRoot.style.setProperty("margin-top", nextMargin, "important");
        lastMargin = nextMargin;
      }
      /* 稳定两次后锁定，避免进度条/状态刷新触发布局抖动 */
      if (!force && gap <= 12 && gap >= -4) {
        gapLocked = true;
      }
    } catch (_e) {}
  }

  function scheduleSync(force) {
    if (force) gapLocked = false;
    if (syncTimer) clearTimeout(syncTimer);
    syncTimer = setTimeout(function () {
      syncChromeGap(!!force);
    }, force ? 50 : 120);
  }

  window.addEventListener("resize", function () {
    scheduleSync(true);
  });
  window.addEventListener("load", function () {
    scheduleSync(true);
  });
  /* 仅启动阶段校准几次，之后锁定 */
  setTimeout(function () {
    scheduleSync(true);
  }, 30);
  setTimeout(function () {
    scheduleSync(true);
  }, 200);
  setTimeout(function () {
    scheduleSync(true);
  }, 600);
  setTimeout(function () {
    scheduleSync(false);
    gapLocked = true;
  }, 1200);

  /* 主题切换会换顶栏高度：监听 title host 变化时解锁一次 */
  var titleHost = null;
  function watchTheme() {
    titleHost = document.getElementById("dv-title-host");
    if (!titleHost) return;
    new MutationObserver(function () {
      scheduleSync(true);
      setTimeout(function () {
        gapLocked = true;
      }, 800);
    }).observe(titleHost, { childList: true, subtree: true, characterData: true });
  }
  setTimeout(watchTheme, 100);
})();
