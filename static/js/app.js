/* ============================================================================
   LocalFix shared behaviour — vanilla JS, no dependencies
   Theme, drawer, scroll reveals, counters, toasts, nav state, password eyes
   ========================================================================== */
(function () {
  "use strict";

  var prefersReduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- Theme (respects saved choice, then OS preference) ---------- */
  var root = document.documentElement;
  var saved = localStorage.getItem("localfix-theme");
  var prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = saved || (prefersDark ? "dark" : "light");

  document.addEventListener("click", function (e) {
    var toggle = e.target.closest("[data-theme-toggle]");
    if (!toggle) return;
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    localStorage.setItem("localfix-theme", root.dataset.theme);
  });

  /* ---------- Password visibility toggles ---------- */
  document.addEventListener("click", function (e) {
    var eye = e.target.closest("[data-pw-toggle]");
    if (!eye) return;
    var input = document.getElementById(eye.getAttribute("data-pw-toggle"));
    if (!input) return;
    var show = input.type === "password";
    input.type = show ? "text" : "password";
    eye.setAttribute("aria-pressed", show ? "true" : "false");
    eye.setAttribute("aria-label", show ? "Hide password" : "Show password");
    eye.textContent = show ? "🙈" : "👁";
    input.focus({ preventScroll: true });
  });

  /* ---------- Mobile drawer ---------- */
  var drawer = document.getElementById("drawer");
  var overlay = document.getElementById("drawer-overlay");
  function openDrawer() {
    if (!drawer) return;
    drawer.classList.add("open");
    if (overlay) overlay.classList.add("open");
    document.body.style.overflow = "hidden";
  }
  function closeDrawer() {
    if (!drawer) return;
    drawer.classList.remove("open");
    if (overlay) overlay.classList.remove("open");
    document.body.style.overflow = "";
  }
  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-drawer-open]")) { openDrawer(); return; }
    if (e.target.closest("[data-drawer-close]") || e.target === overlay) { closeDrawer(); }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeDrawer();
  });
  if (drawer) {
    drawer.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", closeDrawer);
    });
  }

  /* ---------- Active nav link ---------- */
  var path = window.location.pathname;
  document.querySelectorAll(".nav a, .drawer nav a").forEach(function (a) {
    var href = a.getAttribute("href");
    if (!href || href === "#") return;
    if (href === "/" ? path === "/" : path.indexOf(href) === 0) a.classList.add("active");
  });

  /* ---------- Scroll reveals (IntersectionObserver) ---------- */
  var revealEls = document.querySelectorAll(".reveal");
  if (revealEls.length) {
    if (prefersReduced || !("IntersectionObserver" in window)) {
      revealEls.forEach(function (el) { el.classList.add("revealed"); });
    } else {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("revealed");
            io.unobserve(entry.target);
          }
        });
      }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
      revealEls.forEach(function (el) { io.observe(el); });
    }
  }

  /* ---------- Animated number counters ---------- */
  var counters = document.querySelectorAll("[data-count]");
  function animateCounter(el) {
    var target = parseFloat(el.dataset.count || "0");
    if (isNaN(target)) return;
    var decimals = (el.dataset.count.split(".")[1] || "").length;
    var dur = 1200;
    var start = null;
    function frame(ts) {
      if (start === null) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3); /* easeOutCubic */
      el.textContent = (target * eased).toFixed(decimals);
      if (p < 1) requestAnimationFrame(frame);
      else el.textContent = target.toFixed(decimals);
    }
    if (prefersReduced) { el.textContent = target.toFixed(decimals); return; }
    requestAnimationFrame(frame);
  }
  if (counters.length) {
    if (prefersReduced || !("IntersectionObserver" in window)) {
      counters.forEach(animateCounter);
    } else {
      var cio = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            animateCounter(entry.target);
            cio.unobserve(entry.target);
          }
        });
      }, { threshold: 0.4 });
      counters.forEach(function (el) { cio.observe(el); });
    }
  }

  /* ---------- Toasts: dismiss button + auto-hide ---------- */
  var toastBox = document.getElementById("toasts");
  if (toastBox) {
    toastBox.querySelectorAll(".toast").forEach(function (t) {
      var close = document.createElement("button");
      close.className = "toast-close";
      close.setAttribute("aria-label", "Dismiss");
      close.innerHTML = "&times;";
      close.style.cssText = "margin-left:auto;background:none;border:0;font-size:1.1rem;cursor:pointer;color:inherit;opacity:.6;line-height:1;padding:0 0 0 .4rem";
      close.addEventListener("click", function () { dismiss(t); });
      t.appendChild(close);
    });
    function dismiss(t) {
      t.style.transition = "opacity .35s ease, transform .35s ease";
      t.style.opacity = "0";
      t.style.transform = "translateX(24px)";
      setTimeout(function () { t.remove(); }, 350);
    }
    setTimeout(function () {
      toastBox.querySelectorAll(".toast").forEach(dismiss);
    }, 5000);
  }

  /* ---------- Ripple feedback on buttons ---------- */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".btn");
    if (!btn || prefersReduced) return;
    var rect = btn.getBoundingClientRect();
    var ripple = document.createElement("span");
    var size = Math.max(rect.width, rect.height);
    ripple.style.cssText =
      "position:absolute;border-radius:50%;pointer-events:none;" +
      "width:" + size + "px;height:" + size + "px;" +
      "left:" + (e.clientX - rect.left - size / 2) + "px;" +
      "top:" + (e.clientY - rect.top - size / 2) + "px;" +
      "background:rgba(255,255,255,.35);transform:scale(0);animation:ripple .55s ease-out forwards";
    if (getComputedStyle(btn).position === "static") btn.style.position = "relative";
    btn.style.overflow = "hidden";
    btn.appendChild(ripple);
    setTimeout(function () { ripple.remove(); }, 600);
  });
  var style = document.createElement("style");
  style.textContent = "@keyframes ripple{to{transform:scale(2.6);opacity:0}}";
  document.head.appendChild(style);

  /* ---------- Confirm forms marked data-confirm ---------- */
  document.addEventListener("submit", function (e) {
    var form = e.target;
    var msg = form.getAttribute && form.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) e.preventDefault();
  });

  /* ---------- Simple client-side helpers ---------- */
  /* Book buttons keep their own logic server-side; this only enhances UX. */
  window.LocalFix = {
    toast: function (text, kind) {
      if (!toastBox) return;
      var t = document.createElement("div");
      t.className = "toast " + (kind || "info");
      t.textContent = text;
      toastBox.appendChild(t);
      setTimeout(function () { dismiss(t); }, 4500);
    },
  };
})();
