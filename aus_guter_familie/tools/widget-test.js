/* Exercises every interactive widget on a page and reports pass/fail.
   Injected into a temporary copy of each lesson by tools/test_widgets.py.
   Rendering correctly is not the same as working - this drives the widgets. */
window.addEventListener("load", function () {
  setTimeout(function () {
    var R = [];
    function ok(name, cond, detail) {
      R.push((cond ? "PASS " : "FAIL ") + name + (detail ? " (" + detail + ")" : ""));
    }
    var $  = function (s, r) { return (r || document).querySelector(s); };
    var $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };

    // reveal everything so hidden groups are testable
    var ea = $(".expand-all"); if (ea) ea.click();

    /* ---- knowledge checks ---- */
    $$(".kc").forEach(function (kc, n) {
      var kind = kc.getAttribute("data-kc");
      var id = kind + "#" + n;
      var submit = $(".kc-submit", kc), res = $(".kc-result", kc);
      if (!submit || !res) { ok(id, false, "no submit/result"); return; }

      try {
        if (kind === "matching") {
          $$(".match-row", kc).forEach(function (row) {
            var want = row.getAttribute("data-answer");
            var chip = $$(".match-pool .chip", kc).filter(function (c) {
              return c.getAttribute("data-value") === want;
            })[0];
            if (chip) { chip.click(); row.click(); }
          });
          ok(id + ":pool-emptied", $$(".match-pool .chip", kc).length === 0);
        } else if (kind === "fillin") {
          var inp = $(".fillin input", kc);
          inp.value = JSON.parse(inp.getAttribute("data-accept"))[0];
        } else {
          $$(".kc-options li input", kc).forEach(function (i) {
            if (i.getAttribute("data-correct") === "1") i.checked = true;
          });
        }
        submit.click();
        ok(id + ":correct-graded", !res.hidden && /ok/.test(res.className),
           res.hidden ? "result hidden" : res.className);

        var retry = $(".kc-retry", kc);
        if (retry) { retry.click(); ok(id + ":retry-resets", res.hidden); }
      } catch (e) { ok(id, false, String(e).slice(0, 80)); }
    });

    /* ---- scenarios: walk to the end ---- */
    $$(".scenario").forEach(function (sc, n) {
      var stage = $(".scenario-stage", sc), steps = 0, prev = null, choice = 0;
      function sig() { return (stage.textContent || "").replace(/\s+/g, " ").trim().slice(0, 40); }
      while (steps++ < 120) {
        if (/Szenario beendet/.test(stage.textContent)) break;
        var c = $(".cont", stage); if (c) { c.click(); continue; }
        var nx = $(".go-next", stage); if (nx) { nx.click(); prev = null; choice = 0; continue; }
        var bs = $$(".sc-responses button", stage);
        if (!bs.length) break;
        var now = sig();
        choice = (now === prev) ? choice + 1 : 0;
        if (choice >= bs.length) break;
        prev = now; bs[choice].click();
      }
      ok("scenario#" + n + ":reaches-end", /Szenario beendet/.test(stage.textContent),
         "stopped at: " + sig());
    });

    /* ---- sorting ---- */
    $$(".sorting").forEach(function (s, n) {
      $$(".sort-card", s).forEach(function (card) {
        var pile = $('.pile[data-pile="' + card.getAttribute("data-pile") + '"]', s);
        if (pile) { card.click(); pile.click(); }
      });
      var pool = $(".sort-pool", s), res = $(".kc-result", s);
      ok("sorting#" + n + ":all-placed", $$(".sort-card", pool).length === 0);
      $(".sort-check", s).click();
      ok("sorting#" + n + ":graded-ok", !res.hidden && /ok/.test(res.className),
         res.hidden ? "no result" : res.className);
      $(".sort-reset", s).click();
      ok("sorting#" + n + ":reset", $$(".sort-card", pool).length > 0 && res.hidden);
    });

    /* ---- flashcards ---- */
    $$(".flash-grid").forEach(function (g, n) {
      var c = $(".card", g); if (!c) { ok("flashgrid#" + n, false, "no card"); return; }
      c.click();
      ok("flashgrid#" + n + ":flips", c.getAttribute("aria-pressed") === "true");
      c.click();
      ok("flashgrid#" + n + ":flips-back", c.getAttribute("aria-pressed") === "false");
    });
    $$(".flash-stack").forEach(function (s, n) {
      var nav = s.parentNode.querySelector(".stack-nav");
      if (!nav) { ok("flashstack#" + n, false, "no nav"); return; }
      var pos = $(".stack-pos", nav), first = pos.textContent;
      $(".next", nav).click();
      ok("flashstack#" + n + ":advances", pos.textContent !== first,
         first + " -> " + pos.textContent);
      var vis = $$(".card", s).filter(function (c) { return c.style.display !== "none"; });
      ok("flashstack#" + n + ":one-visible", vis.length === 1, vis.length + " visible");
    });

    /* ---- process stepper ---- */
    $$(".process").forEach(function (p, n) {
      var steps = $$(".step", p), next = $(".next", p), prev = $(".prev", p);
      ok("process#" + n + ":starts-disabled", prev.disabled);
      var moved = 0;
      for (var i = 0; i < steps.length + 2; i++) { if (!next.disabled) { next.click(); moved++; } }
      ok("process#" + n + ":reaches-last", moved === steps.length - 1 && next.disabled,
         "moved " + moved + " of " + (steps.length - 1));
      var vis = steps.filter(function (s) { return !s.hidden; });
      ok("process#" + n + ":one-visible", vis.length === 1, vis.length + " visible");
    });

    /* ---- tabs ---- */
    $$(".tabs").forEach(function (t, n) {
      var tabs = $$('[role="tab"]', t), panes = $$('[role="tabpanel"]', t);
      var last = tabs.length - 1;
      tabs[last].click();
      ok("tabs#" + n + ":switches",
         tabs[last].getAttribute("aria-selected") === "true" && !panes[last].hidden);
      ok("tabs#" + n + ":one-pane",
         panes.filter(function (p) { return !p.hidden; }).length === 1);
    });

    /* ---- labeled graphic ---- */
    $$(".lg").forEach(function (g, n) {
      var m = $(".marker", g); if (!m) { ok("lg#" + n, false, "no marker"); return; }
      m.click();
      var pop = $('.pop[data-i="' + m.getAttribute("data-i") + '"]', g);
      ok("lg#" + n + ":opens", pop && !pop.hidden);
      var close = $(".pop-close", pop); if (close) close.click();
      ok("lg#" + n + ":closes", pop.hidden);
    });

    /* ---- quote carousel ---- */
    $$(".q-carousel").forEach(function (c, n) {
      var slides = $$(".q-slide", c), dots = $$(".q-dot", c);
      ok("carousel#" + n + ":one-visible",
         slides.filter(function (s) { return !s.hidden; }).length === 1);
      $(".next", c).click();
      ok("carousel#" + n + ":advances", !slides[1].hidden && slides[0].hidden);
      dots[dots.length - 1].click();
      ok("carousel#" + n + ":dot-jumps",
         !slides[slides.length - 1].hidden &&
         dots[dots.length - 1].getAttribute("aria-current") === "true");
      $(".next", c).click();   // wraps round to the first
      ok("carousel#" + n + ":wraps", !slides[0].hidden);
    });

    /* ---- checkbox persistence ---- */
    var cb = $("input[data-persist]");
    if (cb) {
      cb.checked = true;
      cb.dispatchEvent(new Event("change", { bubbles: true }));
      var key = "reuter:cb:" + location.pathname.split("/").pop() + ":" + cb.getAttribute("data-persist");
      ok("checkbox:persists", localStorage.getItem(key) === "1");
    }

    /* ---- reveal gates ---- */
    var hiddenGroups = $$(".group[hidden]").length;
    ok("gates:expand-all-reveals", hiddenGroups === 0, hiddenGroups + " still hidden");

    console.log("WTEST>>" + R.join(" ;; ") + "<<WTEST");
  }, 500);
});
