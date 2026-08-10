"use strict";
/* Purple hero-slime companion, adapted from matthorrigan.com. */
(function () {
  if (window.__heroSlime) return;
  window.__heroSlime = true;

  const CSS = `
  .hero-slime{position:fixed;right:18px;bottom:0;width:96px;height:84px;z-index:40;
    pointer-events:none;filter:drop-shadow(0 6px 7px rgba(0,0,0,.18))}
  .hero-slime svg{width:100%;height:100%;display:block;overflow:visible}
  .hero-slime .slime-dome{transform-box:view-box;transform-origin:50% 100%;
    animation:heroSlimePulse 3s ease-in-out infinite}
  @keyframes heroSlimePulse{0%,100%{transform:scale(1,1)}50%{transform:scale(1.05,.93)}}
  @media(max-width:700px){.hero-slime{width:64px;height:56px;right:10px}}
  @media(prefers-reduced-motion:reduce){.hero-slime .slime-dome{animation:none}}
  @media print{.hero-slime{display:none}}`;

  const SVG = `<svg viewBox="0 0 32 28" xmlns="http://www.w3.org/2000/svg">
    <defs><radialGradient id="heroGel" gradientUnits="userSpaceOnUse" cx="16" cy="20" r="16" fx="12" fy="9">
      <stop offset="0" stop-color="#b294d6"/><stop offset="0.5" stop-color="#5b2a86"/><stop offset="1" stop-color="#3d1a5c"/>
    </radialGradient></defs>
    <g class="slime-dome">
      <path d="M 3 27 C 3 15 7 8 16 8 C 25 8 29 15 29 27 Z" fill="url(#heroGel)" stroke="#261139" stroke-width="2" stroke-linejoin="round"/>
      <ellipse cx="10.5" cy="12" rx="2.1" ry="2.9" fill="#fff" opacity=".32" transform="rotate(-30 10.5 12)"/>
      <g stroke="#261139" stroke-linecap="round"><circle id="heroEyeWhite" cx="16" cy="15.5" r="5.5" fill="#fff" stroke-width="1.3"/>
        <g id="heroPupil"><circle cx="16" cy="15.5" r="2.75" fill="#261139" stroke="none"/><circle cx="15" cy="14.5" r="1" fill="#fff" stroke="none"/></g>
      </g>
    </g>
  </svg>`;

  function mount() {
    if (document.querySelector(".hero-slime")) return;
    const style = document.createElement("style");
    style.textContent = CSS;
    document.head.appendChild(style);
    const box = document.createElement("div");
    box.className = "hero-slime";
    box.setAttribute("aria-hidden", "true");
    box.innerHTML = SVG;
    document.body.appendChild(box);

    const white = box.querySelector("#heroEyeWhite");
    const pupil = box.querySelector("#heroPupil");
    if (!white || !pupil) return;
    const MAX = 2.3, SAT = 90, EASE = .2;
    let tx = 0, ty = 0, cx = 0, cy = 0, raf = null;
    function aim(px, py) {
      const r = white.getBoundingClientRect();
      if (!r.width) return;
      const dx = px - (r.left + r.width / 2), dy = py - (r.top + r.height / 2);
      const dist = Math.hypot(dx, dy) || 1;
      const mag = MAX * Math.min(1, dist / SAT);
      tx = dx / dist * mag;
      ty = dy / dist * mag;
      if (!raf) raf = requestAnimationFrame(tick);
    }
    function tick() {
      cx += (tx - cx) * EASE;
      cy += (ty - cy) * EASE;
      const done = Math.abs(tx - cx) < .01 && Math.abs(ty - cy) < .01;
      if (done) { cx = tx; cy = ty; }
      pupil.setAttribute("transform", `translate(${cx.toFixed(3)},${cy.toFixed(3)})`);
      raf = done ? null : requestAnimationFrame(tick);
    }
    window.addEventListener("mousemove", e => aim(e.clientX, e.clientY), {passive:true});
    window.addEventListener("touchmove", e => {
      const touch = e.touches && e.touches[0];
      if (touch) aim(touch.clientX, touch.clientY);
    }, {passive:true});
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
  else mount();
})();
