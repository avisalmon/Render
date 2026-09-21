"""The browser probes SensorLab's phone tests share.

Extracted in SL-E2, when a third copy was about to diverge from the other
two. SL-B4 wrote the tap and overflow checks, SL-D2 copied them, and SL-E2
needed a corrected version — at which point the choice was to fix one of
three copies or to stop having three. This app has spent whole sprints on
the cost of a second definition (`LAB_STEPS`, the sensor names, the rail),
so it stops here.
"""

#: spec §7.4 — the app is used one-handed, possibly outdoors.
MIN_TAP_PX = 44

PHONE = {"width": 390, "height": 844}

#: **What counts as the tap target.** Corrected in SL-E2. The earlier
#: version measured every control directly, which flagged a radio button as
#: a 20px failure while it sat inside a 44px label — and the whole label is
#: tappable, which is precisely what §7.4 asks for. Measuring the control
#: alone was not a stricter reading of the rule, it was the wrong reading:
#: it would have pushed the design towards giant radios rather than large
#: rows, which is worse on a phone.
#:
#: So the target is the control, or the label that wraps it, whichever is
#: actually tappable. A bare control with no such wrapper is still measured
#: on its own and still has to clear the floor.
TAP_JS = """(minPx) => {
    const bad = [];
    const sel = 'a, button, input, select, textarea, [role=button]';
    document.querySelectorAll(sel).forEach(el => {
        if (el.type === 'hidden') return;
        const target = el.closest('label') || el;
        const r = target.getBoundingClientRect();
        if (r.width > 0 && r.height > 0 && r.height < minPx) {
            bad.push((target.textContent || el.name || el.tagName).trim().slice(0, 28) +
                     ' h=' + Math.round(r.height));
        }
    });
    return [...new Set(bad)];
}"""

#: A page that scrolls sideways on a phone is broken, whatever it looks like
#: in a screenshot taken at the top.
OVERFLOW_JS = """() => {
    const doc = document.documentElement;
    return {overflow: doc.scrollWidth > doc.clientWidth + 1,
            scrollW: doc.scrollWidth, clientW: doc.clientWidth};
}"""

#: SL-A4.1's specificity trap, guarded generally in SL-B4: `.sl-shell a` is
#: (0,1,1) and outranks any single component class (0,1,0), so an anchor
#: wearing a component's clothes silently keeps the shell's link styling.
#: Computed style in a real browser is the only place a cascade is true.
COMPONENT_LINK_JS = """() => {
    const bad = [];
    document.querySelectorAll('a.sl-card, a.sl-button, a.sl-chip').forEach(el => {
        const s = getComputedStyle(el);
        if ((s.textDecorationLine || '').includes('underline')) {
            bad.push((el.className || '') + ' :: ' + el.textContent.trim().slice(0, 24));
        }
    });
    return bad;
}"""

#: Text the same colour as what is behind it. Found the SL-A4 instrument-mode
#: bug and the live landing-page button; kept because "invisible" is the one
#: failure a structural assertion can never see.
CONTRAST_JS = """() => {
    const lum = (c) => {
        const m = c.match(/[\\d.]+/g) || [0, 0, 0];
        const [r, g, b] = m.slice(0, 3).map(v => {
            const s = v / 255;
            return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
        });
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const bg = (el) => {
        let n = el;
        while (n && n !== document.documentElement) {
            const c = getComputedStyle(n).backgroundColor;
            if (c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') return c;
            n = n.parentElement;
        }
        return getComputedStyle(document.body).backgroundColor;
    };
    const bad = [];
    document.querySelectorAll('main *').forEach(el => {
        if (!el.textContent || !el.textContent.trim()) return;
        if (el.children.length) return;
        const s = getComputedStyle(el);
        if (s.visibility === 'hidden' || s.display === 'none') return;
        const a = lum(s.color), b = lum(bg(el));
        const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
        if (ratio < 2) bad.push(el.textContent.trim().slice(0, 30) + ' ratio=' + ratio.toFixed(2));
    });
    return bad;
}"""
