/* ------------------------------------------------------------------
   Reuter: Aus guter Familie (1895) — offline archive
   Vanilla ES5-ish, no modules, no fetch: must run from file://
   ------------------------------------------------------------------ */
(function () {
  "use strict";

  var $  = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var STORE = "reuter:";

  function save(k, v) { try { localStorage.setItem(STORE + k, v); } catch (e) {} }
  function load(k)    { try { return localStorage.getItem(STORE + k); } catch (e) { return null; } }

  // Wire each component in isolation. A throw in one interactive must never
  // take the rest of the page down with it - that failure mode once blanked
  // every quiz and scenario on a lesson because one gate had no button.
  function each(sel, label, fn) {
    $$(sel).forEach(function (el, i) {
      try { fn(el, i); }
      catch (e) { if (window.console) console.error("[" + label + "]", e, el); }
    });
  }

  function revealGroup(n) {
    var g = $('.group[data-group="' + n + '"]');
    if (g) g.hidden = false;
    return g;
  }

  /* ---------------- nav toggle (narrow / mobile) ---------------- */

  (function () {
    var toggle = $(".nav-toggle");
    var sidebar = $(".sidebar");
    if (!toggle || !sidebar) return;
    toggle.addEventListener("click", function () {
      var open = sidebar.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    // Collapse again once a chapter is picked, so the panel doesn't stay
    // open over the lesson content after navigating.
    $$(".lessons a", sidebar).forEach(function (a) {
      a.addEventListener("click", function () {
        sidebar.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  })();

  /* ---------------- continue gates ---------------- */

  each(".gate", "gate", function (gate) {
    var n = parseInt(gate.getAttribute("data-gate"), 10);
    var btn = $(".gate-btn", gate);
    if (!btn) return;   // end-of-lesson gates are plain links, not buttons
    btn.addEventListener("click", function () {
      var g = revealGroup(n + 1);
      gate.classList.add("done");
      if (g) {
        var y = g.getBoundingClientRect().top + window.pageYOffset - 70;
        window.scrollTo({ top: y, behavior: "smooth" });
      }
    });
  });

  var expand = $(".expand-all");
  if (expand) {
    expand.addEventListener("click", function () {
      $$(".group[hidden]").forEach(function (g) { g.hidden = false; });
      $$(".gate").forEach(function (g) { g.classList.add("done"); });
      expand.hidden = true;
    });
  }

  /* ---------------- persisted checkboxes ---------------- */

  each("input[data-persist]", "checkbox", function (cb) {
    var key = "cb:" + location.pathname.split("/").pop() + ":" + cb.getAttribute("data-persist");
    if (load(key) === "1") cb.checked = true;
    cb.addEventListener("change", function () { save(key, cb.checked ? "1" : "0"); });
  });

  /* ---------------- knowledge checks ---------------- */

  function norm(s) {
    return (s || "").toLowerCase().replace(/\s+/g, " ").replace(/[.,;:!?]+$/, "").trim();
  }

  each(".kc", "quiz", function (kc) {
    var kind    = kc.getAttribute("data-kc");
    var submit  = $(".kc-submit", kc);
    var retry   = $(".kc-retry", kc);
    var result  = $(".kc-result", kc);
    var feedback = $(".kc-feedback", kc);

    function clear() {
      $$("li", kc).forEach(function (li) { li.classList.remove("right", "wrong", "missed"); });
      $$(".match-row", kc).forEach(function (r) { r.classList.remove("right", "wrong"); });
      var fi = $(".fillin", kc); if (fi) fi.classList.remove("right", "wrong");
      result.hidden = true;
      if (feedback) feedback.hidden = true;
      retry.hidden = true;
      submit.hidden = false;
    }

    function finish(ok, msgOk, msgNo) {
      result.hidden = false;
      result.className = "kc-result " + (ok ? "ok" : "no");
      result.textContent = ok ? (msgOk || "Richtig.") : (msgNo || "Noch nicht ganz.");
      if (feedback) feedback.hidden = false;
      submit.hidden = true;
      retry.hidden = false;
    }

    submit.addEventListener("click", function () {
      if (kind === "matching") {
        var rows = $$(".match-row", kc), ok = true, answered = 0;
        rows.forEach(function (row) {
          var chip = $(".chip", row);
          if (chip) answered++;
          var good = chip && chip.getAttribute("data-value") === row.getAttribute("data-answer");
          row.classList.add(good ? "right" : "wrong");
          if (!good) ok = false;
        });
        if (!answered) { clear(); return; }
        finish(ok, "Alle Zuordnungen stimmen.", "Einige Zuordnungen stimmen noch nicht.");

      } else if (kind === "fillin") {
        var box = $(".fillin", kc), input = $("input", box);
        var accept = JSON.parse(input.getAttribute("data-accept") || "[]").map(norm);
        var good = accept.indexOf(norm(input.value)) !== -1;
        box.classList.add(good ? "right" : "wrong");
        finish(good);

      } else {
        var lis = $$(".kc-options li", kc), ok2 = true, any = false;
        lis.forEach(function (li) {
          var input = $("input", li);
          var correct = input.getAttribute("data-correct") === "1";
          if (input.checked) any = true;
          if (input.checked && correct) li.classList.add("right");
          else if (input.checked && !correct) { li.classList.add("wrong"); ok2 = false; }
          else if (!input.checked && correct) { li.classList.add("missed"); ok2 = false; }
        });
        if (!any) return;
        finish(ok2);
      }
    });

    retry.addEventListener("click", function () {
      clear();
      $$("input", kc).forEach(function (i) {
        if (i.type === "text") i.value = ""; else i.checked = false;
      });
      var pool = $(".match-pool", kc);
      if (pool) $$(".chip", kc).forEach(function (c) {
        c.classList.remove("sel");
        pool.appendChild(c);
      });
    });

    /* Matching: drag a chip onto a row, as in the original. Click-to-assign
       is offered alongside because HTML5 drag-and-drop does not work on touch
       and is awkward under file://. */
    if (kind === "matching") {
      var pool = $(".match-pool", kc);
      var picked = null;

      function place(slot, chip) {
        if (!slot || !chip) return;
        var sitting = slot !== pool ? $(".chip", slot) : null;
        if (sitting && sitting !== chip) pool.appendChild(sitting);  // evict
        slot.appendChild(chip);
        chip.classList.remove("sel");
        picked = null;
        $$(".drop-over", kc).forEach(function (e) { e.classList.remove("drop-over"); });
      }

      $$(".chip", kc).forEach(function (chip) {
        chip.addEventListener("click", function (e) {
          e.preventDefault();
          // Chips sit inside drop targets (the pool, and each row's slot).
          // Without this the click bubbles to the container's own handler,
          // which would immediately re-drop the chip and clear the selection.
          e.stopPropagation();
          if (picked === chip) { chip.classList.remove("sel"); picked = null; return; }
          if (picked) picked.classList.remove("sel");
          picked = chip;
          chip.classList.add("sel");
        });
        chip.addEventListener("dragstart", function (e) {
          picked = chip;
          try { e.dataTransfer.setData("text/plain", chip.getAttribute("data-value")); } catch (err) {}
          e.dataTransfer.effectAllowed = "move";
        });
        chip.addEventListener("dragend", function () {
          $$(".drop-over", kc).forEach(function (el) { el.classList.remove("drop-over"); });
        });
      });

      $$("[data-slot]", kc).forEach(function (slot) {
        var target = slot.classList.contains("match-slot") ? slot.parentNode : slot;
        slot.addEventListener("dragover", function (e) {
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
          target.classList.add("drop-over");
        });
        slot.addEventListener("dragleave", function () { target.classList.remove("drop-over"); });
        slot.addEventListener("drop", function (e) {
          e.preventDefault();
          target.classList.remove("drop-over");
          place(slot, picked);
        });
        slot.addEventListener("click", function () { if (picked) place(slot, picked); });
      });

      $$(".match-row", kc).forEach(function (row) {
        row.addEventListener("click", function () {
          if (picked) place($(".match-slot", row), picked);
        });
      });
    }
  });

  /* ---------------- scenario ---------------- */

  each(".scenario", "scenario", function (root) {
    var data = JSON.parse($(".scenario-data", root).textContent);
    var head = $(".scenario-head", root);
    var headTitleEl = document.createElement("span");
    headTitleEl.className = "sc-head-title";
    headTitleEl.textContent = head.textContent;
    var headCountEl = document.createElement("span");
    headCountEl.className = "sc-count";
    head.textContent = "";
    head.appendChild(headTitleEl);
    head.appendChild(headCountEl);
    var stage = $(".scenario-stage", root);
    var slides = [];
    data.scenes.forEach(function (sc) {
      sc.slides.forEach(function (s) { slides.push(s); });
    });
    var byId = {};
    slides.forEach(function (s, i) { byId[s.id] = i; });

    function go(i) {
      if (i < 0 || i >= slides.length) return end();
      render(i);
      stage.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }

    function end() {
      headCountEl.textContent = "";
      stage.innerHTML =
        '<p class="sc-end">Szenario beendet.</p>' +
        '<div class="sc-nav"><button class="btn ghost restart">Von vorne beginnen</button></div>';
      $(".restart", stage).addEventListener("click", function () { go(0); });
    }

    function advance(from, goTo, target) {
      if (goTo === "end") return end();
      if (goTo === "slide" && target && byId[target] !== undefined) return go(byId[target]);
      return go(from + 1);
    }

    // "tryAgain" means: show the feedback, then let the learner answer this
    // slide again. Some authored responses also carry a nextSlide pointer left
    // over from editing; honouring it would silently restart the scenario, so
    // the action wins over the pointer.
    function follow(i, r) {
      if (r.action === "tryAgain") return go(i);
      advance(i, r.goTo, r.target);
    }

    // Narration and feedback render as "incoming" speech bubbles, response
    // choices as "outgoing" ones on the right - a chat with the scenario's
    // speaker. A slide with no real choice (or one collapsed by the build,
    // see DROP_RESPONSES/nav in build.py) just gets a round Weiter button:
    // it isn't part of the conversation, so it shouldn't look like a reply.
    function render(i) {
      var s = slides[i];
      headCountEl.textContent = (i + 1) + " von " + slides.length;

      var html = "";
      if (s.title) html += '<h3 class="sc-title">' + s.title + "</h3>";
      html += '<div class="sc-body sc-bubble sc-bubble-in">' + s.html + "</div>";

      if (s.responses.length) {
        html += '<div class="sc-responses">';
        s.responses.forEach(function (r, ri) {
          html += '<button class="sc-bubble sc-bubble-out" data-r="' + ri + '">' + r.html + "</button>";
        });
        html += "</div>";
      } else {
        html += '<div class="sc-nav"><button class="btn-round go-next" aria-label="Weiter">›</button></div>';
      }
      stage.innerHTML = html;

      var nx = $(".go-next", stage);
      if (nx) nx.addEventListener("click", function () { advance(i, s.goTo, s.target); });

      $$(".sc-responses button", stage).forEach(function (btn) {
        btn.addEventListener("click", function () {
          var r = s.responses[parseInt(btn.getAttribute("data-r"), 10)];
          var list = $(".sc-responses", stage);

          if (r.feedback) {
            list.remove();
            var fb = document.createElement("div");
            fb.className = "sc-feedback sc-bubble sc-bubble-in";
            fb.innerHTML = r.feedback;
            stage.appendChild(fb);
            var nav = document.createElement("div");
            nav.className = "sc-nav";
            nav.innerHTML = r.action === "tryAgain"
              ? '<button class="btn ghost cont">Nochmal versuchen</button>'
              : '<button class="btn-round cont" aria-label="Weiter">›</button>';
            stage.appendChild(nav);
            $(".cont", nav).addEventListener("click", function () { follow(i, r); });
          } else {
            follow(i, r);
          }
        });
      });
    }

    go(0);
  });

  /* ---------------- flashcards ---------------- */

  each(".card", "flashcard", function (card) {
    card.addEventListener("click", function () {
      card.setAttribute("aria-pressed", card.getAttribute("aria-pressed") === "true" ? "false" : "true");
    });
  });

  each(".flash-stack", "flash-stack", function (stack) {
    var cards = $$(".card", stack);
    var nav = stack.parentNode.querySelector(".stack-nav");
    var pos = $(".stack-pos", nav);
    var i = 0;
    function draw() {
      cards.forEach(function (c, n) { c.style.display = n === i ? "" : "none"; });
      pos.textContent = (i + 1) + " / " + cards.length;
    }
    $(".prev", nav).addEventListener("click", function () { i = (i - 1 + cards.length) % cards.length; draw(); });
    $(".next", nav).addEventListener("click", function () { i = (i + 1) % cards.length; draw(); });
    draw();
  });

  /* ---------------- quote carousel ---------------- */

  each(".q-carousel", "quote-carousel", function (root) {
    var slides = $$(".q-slide", root), dots = $$(".q-dot", root), i = 0;
    function draw() {
      slides.forEach(function (s, n) { s.hidden = n !== i; });
      dots.forEach(function (d, n) { d.setAttribute("aria-current", n === i ? "true" : "false"); });
    }
    $(".prev", root).addEventListener("click", function () { i = (i - 1 + slides.length) % slides.length; draw(); });
    $(".next", root).addEventListener("click", function () { i = (i + 1) % slides.length; draw(); });
    dots.forEach(function (d, n) { d.addEventListener("click", function () { i = n; draw(); }); });
    draw();
  });

  /* ---------------- sorting ---------------- */

  each(".sorting", "sorting", function (root) {
    var sel = null;
    var result = $(".kc-result", root);
    var pool = $(".sort-pool", root);

    $$(".sort-card", root).forEach(function (c) {
      c.addEventListener("click", function () {
        if (sel) sel.classList.remove("sel");
        sel = sel === c ? null : c;
        if (sel) sel.classList.add("sel");
      });
    });

    $$(".pile", root).forEach(function (p) {
      p.addEventListener("click", function () {
        if (!sel) return;
        sel.classList.remove("sel");
        sel.setAttribute("data-placed", p.getAttribute("data-pile"));
        $(".pile-drop", p).appendChild(sel);
        sel = null;
      });
    });

    $(".sort-check", root).addEventListener("click", function () {
      var cards = $$(".sort-card", root), ok = true, placed = 0;
      cards.forEach(function (c) {
        var at = c.getAttribute("data-placed");
        if (!at) { ok = false; return; }
        placed++;
        var good = at === c.getAttribute("data-pile");
        c.classList.add(good ? "right" : "wrong");
        if (!good) ok = false;
      });
      if (!placed) return;
      result.hidden = false;
      result.className = "kc-result " + (ok ? "ok" : "no");
      result.textContent = ok ? "Alle Karten richtig zugeordnet."
                              : "Einige Karten liegen noch falsch.";
    });

    $(".sort-reset", root).addEventListener("click", function () {
      $$(".sort-card", root).forEach(function (c) {
        c.classList.remove("right", "wrong", "sel");
        c.removeAttribute("data-placed");
        pool.appendChild(c);
      });
      result.hidden = true;
    });
  });

  /* ---------------- process stepper ---------------- */

  each(".process", "process", function (root) {
    var steps = $$(".step", root);
    var prev = $(".prev", root), next = $(".next", root);
    var i = 0;
    function draw() {
      steps.forEach(function (s, n) { s.hidden = n !== i; });
      prev.disabled = i === 0;
      next.disabled = i === steps.length - 1;
    }
    prev.addEventListener("click", function () { if (i > 0) { i--; draw(); } });
    next.addEventListener("click", function () { if (i < steps.length - 1) { i++; draw(); } });
    draw();
  });

  /* ---------------- labeled graphic ---------------- */

  each(".lg", "labeledgraphic", function (root) {
    function close() { $$(".pop", root).forEach(function (p) { p.hidden = true; }); }
    $$(".marker", root).forEach(function (m) {
      m.addEventListener("click", function () {
        var i = m.getAttribute("data-i");
        var pop = root.querySelector('.pop[data-i="' + i + '"]');
        var wasOpen = !pop.hidden;
        close();
        pop.hidden = wasOpen;
      });
    });
    $$(".pop-close", root).forEach(function (b) {
      b.addEventListener("click", close);
    });
  });

  /* ---------------- tabs ---------------- */

  each(".tabs", "tabs", function (root) {
    var tabs = $$('[role="tab"]', root);
    var panes = $$('[role="tabpanel"]', root);
    function show(i) {
      tabs.forEach(function (t, n) { t.setAttribute("aria-selected", n === i ? "true" : "false"); });
      panes.forEach(function (p, n) { p.hidden = n !== i; });
    }
    tabs.forEach(function (t, i) {
      t.addEventListener("click", function () { show(i); });
      t.addEventListener("keydown", function (e) {
        if (e.key === "ArrowRight") { tabs[(i + 1) % tabs.length].focus(); show((i + 1) % tabs.length); }
        if (e.key === "ArrowLeft")  { var j = (i - 1 + tabs.length) % tabs.length; tabs[j].focus(); show(j); }
      });
    });
  });

  /* ---------------- lightbox ---------------- */

  var lb = $(".lightbox");
  if (lb) {
    var lbImg = $("img", lb);
    function closeLb() { lb.hidden = true; lbImg.removeAttribute("src"); }
    $$("img[data-zoom]").forEach(function (img) {
      img.addEventListener("click", function () {
        lbImg.src = img.currentSrc || img.src;
        lb.hidden = false;
      });
    });
    lb.addEventListener("click", closeLb);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !lb.hidden) closeLb();
    });
  }
})();
