/**
 * Quantum Lattice Background — WebGL
 *
 * A2 crystal lattice rendered with WebGL, featuring:
 *  - Animated nebula background with drifting color blobs
 *  - Aurora sweep bands that slowly rotate and pulse
 *  - Floor lattice (cyan/teal palette) scrolling toward viewer
 *  - Ceiling lattice (rose/magenta palette) scrolling away
 *  - NTT harmonic morphing on lattice geometry
 *  - Cursor-reactive glow: nodes and edges near pointer brighten
 *  - Time-based hue cycling on nodes
 *  - Click pulse ripples emanating from cursor
 *  - Subtle scanline vignette overlay
 */
(function () {
  'use strict';

  const canvas = document.getElementById('bg-lattice');
  if (!canvas) return;

  const gl = canvas.getContext('webgl', { alpha: false, antialias: false })
        || canvas.getContext('experimental-webgl', { alpha: false, antialias: false });
  if (!gl) return;

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── Mouse / touch / click tracking ─────────────── */
  let mouseNX = 0.5, mouseNY = 0.5;
  let targetMX = 0.5, targetMY = 0.5;
  let mouseActive = false;

  // Click pulse ripples
  let pulses = [];

  function onPointerMove(x, y) {
    targetMX = x / window.innerWidth;
    targetMY = y / window.innerHeight;
    mouseActive = true;
  }

  function onPointerClick(x, y) {
    pulses.push({
      x: x / window.innerWidth,
      y: y / window.innerHeight,
      age: 0,
      maxAge: 90,
    });
    if (pulses.length > 6) pulses.shift();
  }

  window.addEventListener('mousemove', function (e) { onPointerMove(e.clientX, e.clientY); });
  window.addEventListener('touchmove', function (e) {
    if (e.touches.length) onPointerMove(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: true });
  window.addEventListener('mouseleave', function () { mouseActive = false; });
  window.addEventListener('click', function (e) { onPointerClick(e.clientX, e.clientY); });

  /* ── Shaders ───────────────────────────────────── */

  const VERT = [
    'precision highp float;',
    'attribute vec2 aLattice;',
    'attribute float aFlip;',
    'uniform float uTime;',
    'uniform vec2  uRes;',
    'uniform float uCell;',
    'uniform vec2  uMouse;',
    'uniform float uMouseActive;',
    // Pulse uniforms (up to 4 simultaneous)
    'uniform vec2  uPulse0; uniform float uPulseAge0;',
    'uniform vec2  uPulse1; uniform float uPulseAge1;',
    'varying float vDepth;',
    'varying float vFlip;',
    'varying float vNodeType;',
    'varying float vGlow;',
    'varying float vTime;',
    'varying float vPulse;',

    'const float E2X      = -0.5;',
    'const float E2Y      =  0.866025;',
    'const float CAM_H    = 180.0;',
    'const float CAM_D    = 300.0;',
    'const float FL       = 420.0;',
    'const float PI2      = 6.2831853;',
    'const float NTT_N    = 41.0;',
    'const float WRAP_NEAR = 2.0;',
    'const float WRAP_RANGE = 2400.0;',

    'void main() {',
    '  float a = aLattice.x, b = aLattice.y;',
    '  float lx = a + b * E2X;',
    '  float lz = b * E2Y;',

    // NTT harmonic morph
    '  float phase = uTime * 0.06;',
    '  float apb = a + b;',
    '  float amb = a - b;',
    '  float m2 = 0.14 * sin(PI2 * 2.0 * apb / NTT_N + phase);',
    '  float m3 = 0.10 * sin(PI2 * 3.0 * amb / NTT_N + phase * 0.7);',
    '  float m5 = 0.06 * sin(PI2 * 5.0 * a   / NTT_N + phase * 1.3);',
    '  float m7 = 0.04 * sin(PI2 * 7.0 * b   / NTT_N + phase * 1.7);',
    '  float morph = m2 + m3 + m5 + m7;',
    '  lx += morph * 0.35;',
    '  lz += (m2 - m3 + m7) * 0.25;',

    // Y-axis rotation
    '  float rotY = uTime * 0.00033 * 60.0;',
    '  float cr = cos(rotY), sr = sin(rotY);',
    '  float wx = lx * uCell, wz = lz * uCell;',
    '  float rx = wx * cr - wz * sr;',
    '  float rz = wx * sr + wz * cr;',

    // Unbounded scroll
    '  float scrollSpeed = (aFlip > 0.5) ? -14.0 : 20.0;',
    '  float scrollZ = uTime * scrollSpeed;',
    '  float fz = rz - scrollZ + CAM_D;',
    '  fz = mod(fz - WRAP_NEAR, WRAP_RANGE) + WRAP_NEAR;',

    '  float scale = FL / fz;',
    '  float depth = min(1.0, FL / (FL + fz * 0.42));',
    '  if (aFlip > 0.5) depth *= 0.7;',

    '  float cx = uRes.x * 0.5;',
    '  float cy = uRes.y * 0.5;',
    '  float hz = cy;',
    // Curce factor limits at 1.5708 (Pi/2) so the walls go vertical at the edges and stop.
    '  float curve = clamp(abs(rx) * 0.0008, 0.0, 1.5708);',
    '  float currentH = cos(curve) * CAM_H;',
    '  float tubeX = sign(rx) * sin(curve) * 1200.0;',
    
    '  float sy = hz + currentH * scale;',
    '  if (aFlip > 0.5) sy = hz - currentH * scale;',
    '  float sx = cx + tubeX * scale;',

    '  float ndcX = (sx / uRes.x) * 2.0 - 1.0;',
    '  float ndcY = 1.0 - (sy / uRes.y) * 2.0;',

    // Cursor proximity glow
    '  float mx = uMouse.x * 2.0 - 1.0;',
    '  float my = 1.0 - uMouse.y * 2.0;',
    '  float mouseDist = length(vec2(ndcX - mx, ndcY - my));',
    '  float glow = smoothstep(0.4, 0.0, mouseDist) * uMouseActive;',

    // Click pulse contribution
    '  float pulseGlow = 0.0;',
    '  if (uPulseAge0 > 0.0) {',
    '    float px = uPulse0.x * 2.0 - 1.0;',
    '    float py = 1.0 - uPulse0.y * 2.0;',
    '    float pdist = length(vec2(ndcX - px, ndcY - py));',
    '    float ring = abs(pdist - uPulseAge0 * 0.015) < 0.04 ? 1.0 : 0.0;',
    '    pulseGlow += ring * (1.0 - uPulseAge0 / 90.0) * 0.8;',
    '  }',
    '  if (uPulseAge1 > 0.0) {',
    '    float px = uPulse1.x * 2.0 - 1.0;',
    '    float py = 1.0 - uPulse1.y * 2.0;',
    '    float pdist = length(vec2(ndcX - px, ndcY - py));',
    '    float ring = abs(pdist - uPulseAge1 * 0.015) < 0.04 ? 1.0 : 0.0;',
    '    pulseGlow += ring * (1.0 - uPulseAge1 / 90.0) * 0.8;',
    '  }',

    '  vDepth = depth;',
    '  vFlip  = aFlip;',
    '  vNodeType = mod(abs(a - b), 3.0) < 0.5 ? 1.0 : 0.0;',
    '  vGlow = glow + min(1.0, pulseGlow);',
    '  vTime = uTime;',
    '  vPulse = pulseGlow;',

    '  float pulse = 0.75 + 0.25 * sin(uTime * 1.4 + a * 0.31 + b * 0.53);',
    '  float baseSize = max(1.0, scale * 9.0 * pulse) * (aFlip > 0.5 ? 0.7 : 0.9);',
    '  gl_PointSize = baseSize * (1.0 + vGlow * 2.0);',
    '  gl_Position = vec4(ndcX, ndcY, 0.0, 1.0);',
    '}'
  ].join('\n');

  const FRAG = [
    'precision mediump float;',
    'varying float vDepth;',
    'varying float vFlip;',
    'varying float vNodeType;',
    'varying float vGlow;',
    'varying float vTime;',
    'varying float vPulse;',
    'void main() {',
    '  float d = length(gl_PointCoord - 0.5) * 2.0;',
    '  if (d > 1.0) discard;',
    '  float soft = 1.0 - d * d;',
    '  float alpha = vDepth * vDepth * soft * (vFlip > 0.5 ? 0.65 : 0.9);',
    '  alpha = alpha + vGlow * 0.7 * soft;',

    // Time-based hue cycle
    '  float cycle = sin(vTime * 0.035) * 0.5 + 0.5;',
    '  float cycle2 = sin(vTime * 0.022 + 1.3) * 0.5 + 0.5;',

    // Color palettes: floor = cyan/teal, ceiling = rose/magenta
    '  vec3 cyan   = vec3(0.49, 0.827, 0.988);',  // #7dd3fc
    '  vec3 teal   = vec3(0.133, 0.827, 0.933);', // #22d3ee
    '  vec3 lime   = vec3(0.35, 0.95, 0.65);',    // soft matrix green
    '  vec3 rose   = vec3(0.98, 0.35, 0.65);',    // rose
    '  vec3 violet = vec3(0.65, 0.22, 0.97);',    // violet
    '  vec3 magenta= vec3(0.93, 0.18, 0.72);',    // magenta

    '  vec3 floorCol = mix(cyan, teal, vNodeType * 0.5 + cycle * 0.25);',
    '  floorCol = mix(floorCol, lime, vNodeType * cycle2 * 0.12);',
    '  vec3 ceilCol = mix(violet, magenta, cycle * 0.6);',
    '  ceilCol = mix(ceilCol, rose, vNodeType * 0.4);',

    '  vec3 col = vFlip > 0.5 ? ceilCol : floorCol;',

    // Pulse rings shift toward white
    '  col = mix(col, vec3(1.0, 0.97, 0.85), min(1.0, vPulse) * 0.85);',

    // Cursor glow: shift toward bright white-cyan
    '  col = mix(col, vec3(0.92, 0.98, 1.0), vGlow * 0.55);',

    '  gl_FragColor = vec4(col, alpha);',
    '}'
  ].join('\n');

  /* ── Edge shaders ──────────────────────────────── */

  const EDGE_VERT = [
    'precision mediump float;',
    'attribute vec2 aPos;',
    'attribute float aAlpha;',
    'attribute float aColType;',
    'attribute float aFlipEdge;',
    'uniform vec2 uRes;',
    'varying float vAlpha;',
    'varying float vColType;',
    'varying float vFlipEdge;',
    'void main() {',
    '  float ndcX = (aPos.x / uRes.x) * 2.0 - 1.0;',
    '  float ndcY = 1.0 - (aPos.y / uRes.y) * 2.0;',
    '  gl_Position = vec4(ndcX, ndcY, 0.0, 1.0);',
    '  vAlpha = aAlpha;',
    '  vColType = aColType;',
    '  vFlipEdge = aFlipEdge;',
    '}'
  ].join('\n');

  const EDGE_FRAG = [
    'precision mediump float;',
    'varying float vAlpha;',
    'varying float vColType;',
    'varying float vFlipEdge;',
    'uniform float uTime;',
    'void main() {',
    '  float cycle = sin(uTime * 0.035) * 0.5 + 0.5;',

    '  vec3 accent = vec3(0.49, 0.827, 0.988);',
    '  vec3 purple = vec3(0.45, 0.15, 0.78);',
    '  vec3 floorCol = mix(accent, purple, vColType * 0.7 + cycle * 0.15);',

    '  vec3 rose   = vec3(0.90, 0.22, 0.60);',
    '  vec3 violet = vec3(0.60, 0.18, 0.90);',
    '  vec3 ceilCol = mix(violet, rose, cycle * 0.5 + vColType * 0.3);',

    '  vec3 col = vFlipEdge > 0.5 ? ceilCol : floorCol;',
    '  gl_FragColor = vec4(col, vAlpha);',
    '}'
  ].join('\n');

  function compileShader(src, type) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    return s;
  }

  function linkProgram(vs, fs) {
    const p = gl.createProgram();
    gl.attachShader(p, compileShader(vs, gl.VERTEX_SHADER));
    gl.attachShader(p, compileShader(fs, gl.FRAGMENT_SHADER));
    gl.linkProgram(p);
    return p;
  }

  /* ── Lattice geometry ──────────────────────────── */
  const RANGE = 20;
  const E2X = -0.5, E2Y = Math.sqrt(3) / 2;
  const NN = [[1,0],[0,1],[1,-1]];
  const PI2 = Math.PI * 2;
  const NTT_N = 2 * RANGE + 1;
  const WRAP_NEAR  = 2;
  const WRAP_RANGE = 2400;

  const latticeData = [];
  (function () {
    for (let a = -RANGE; a <= RANGE; a++) {
      for (let b = -RANGE; b <= RANGE; b++) {
        latticeData.push(a, b, 0);  // floor
        latticeData.push(a, b, 1);  // ceiling
      }
    }
  }());

  const latticeArr = new Float32Array(latticeData);
  const numPoints = latticeArr.length / 3;

  /* ── Node program ──────────────────────────────── */
  const nodeProg = linkProgram(VERT, FRAG);
  const aLattice     = gl.getAttribLocation(nodeProg, 'aLattice');
  const aFlip        = gl.getAttribLocation(nodeProg, 'aFlip');
  const uTime        = gl.getUniformLocation(nodeProg, 'uTime');
  const uRes         = gl.getUniformLocation(nodeProg, 'uRes');
  const uCell        = gl.getUniformLocation(nodeProg, 'uCell');
  const uMouse       = gl.getUniformLocation(nodeProg, 'uMouse');
  const uMouseActive = gl.getUniformLocation(nodeProg, 'uMouseActive');
  const uPulse0      = gl.getUniformLocation(nodeProg, 'uPulse0');
  const uPulseAge0   = gl.getUniformLocation(nodeProg, 'uPulseAge0');
  const uPulse1      = gl.getUniformLocation(nodeProg, 'uPulse1');
  const uPulseAge1   = gl.getUniformLocation(nodeProg, 'uPulseAge1');

  const latticeBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, latticeBuf);
  gl.bufferData(gl.ARRAY_BUFFER, latticeArr, gl.STATIC_DRAW);

  /* ── Edge program ──────────────────────────────── */
  const edgeProg = linkProgram(EDGE_VERT, EDGE_FRAG);
  const eAPos      = gl.getAttribLocation(edgeProg, 'aPos');
  const eAAlpha    = gl.getAttribLocation(edgeProg, 'aAlpha');
  const eAColType  = gl.getAttribLocation(edgeProg, 'aColType');
  const eAFlipEdge = gl.getAttribLocation(edgeProg, 'aFlipEdge');
  const eURes      = gl.getUniformLocation(edgeProg, 'uRes');
  const eUTime     = gl.getUniformLocation(edgeProg, 'uTime');

  function a2Count() { return (2 * RANGE + 1) * (2 * RANGE + 1); }
  const maxEdges = a2Count() * 3 * 2;
  const edgeBuf = gl.createBuffer();
  // 5 floats per vertex: x,y, alpha, colType, flipEdge
  const edgeFloats = new Float32Array(maxEdges * 2 * 5);

  /* ── CPU projection for edges ──────────────────── */
  const CAM_H_V = 180, CAM_D_V = 300, FL_V = 420;
  const projFloor = new Float32Array(a2Count() * 5);
  const projCeil  = new Float32Array(a2Count() * 5);

  function nttMorph(a, b, time) {
    const phase = time * 0.06;
    const apb = a + b, amb = a - b;
    const m2 = 0.14 * Math.sin(PI2 * 2 * apb / NTT_N + phase);
    const m3 = 0.10 * Math.sin(PI2 * 3 * amb / NTT_N + phase * 0.7);
    const m5 = 0.06 * Math.sin(PI2 * 5 * a   / NTT_N + phase * 1.3);
    const m7 = 0.04 * Math.sin(PI2 * 7 * b   / NTT_N + phase * 1.7);
    const morph = m2 + m3 + m5 + m7;
    return { dx: morph * 0.35, dz: (m2 - m3 + m7) * 0.25 };
  }

  function pmod(x, m) { return ((x % m) + m) % m; }

  function projectPass(time, cell, vW, vH, buf, scrollSpeed, depthMul) {
    const cx = vW / 2, cy = vH / 2, hz = cy;
    const rotY = time * 0.00033 * 60;
    const cr = Math.cos(rotY), sr = Math.sin(rotY);
    const scrollZ = time * scrollSpeed;
    let idx = 0;
    for (let a = -RANGE; a <= RANGE; a++) {
      for (let b = -RANGE; b <= RANGE; b++) {
        let lx = a + b * E2X;
        let lz = b * E2Y;
        const m = nttMorph(a, b, time);
        lx += m.dx; lz += m.dz;
        const wx = lx * cell, wz = lz * cell;
        const rx = wx * cr - wz * sr;
        const rz = wx * sr + wz * cr;
        let fz = rz - scrollZ + CAM_D_V;
        fz = pmod(fz - WRAP_NEAR, WRAP_RANGE) + WRAP_NEAR;
        const scale = FL_V / fz;
        const depth = Math.min(1, FL_V / (FL_V + fz * 0.28)) * depthMul;
        const curve = Math.min(Math.abs(rx) * 0.0008, 1.5708);
        const currentH = Math.cos(curve) * CAM_H_V;
        // tunnel topography
        const tubeX = Math.sign(rx) * Math.sin(curve) * 1200.0;
        const sx = cx + tubeX * scale;
        const sy = hz + currentH * scale;
        buf[idx]   = sx;
        buf[idx+1] = sy;
        buf[idx+2] = depth;
        buf[idx+3] = 1;
        buf[idx+4] = fz;
        idx += 5;
      }
    }
  }

  function buildEdges(vW, vH) {
    const hz = vH / 2;
    const count = 2 * RANGE + 1;
    let ei = 0;
    const halfWrap = WRAP_RANGE * 0.5;

    const mpx = mouseNX * vW;
    const mpy = mouseNY * vH;
    const glowRadiusSq = Math.pow(Math.min(vW, vH) * 0.22, 2);
    const mActive = mouseActive ? 1.0 : 0.0;

    for (let pass = 0; pass < 2; pass++) {
      const flip = pass === 1;
      const buf = flip ? projCeil : projFloor;
      const alphaMul = flip ? 0.28 : 0.30;
      const flipVal = flip ? 1.0 : 0.0;

      for (let a = -RANGE; a <= RANGE; a++) {
        for (let b = -RANGE; b <= RANGE; b++) {
          const i = (a + RANGE) * count + (b + RANGE);
          const base = i * 5;
          const sx1 = buf[base];
          let sy1 = buf[base+1];
          const d1 = buf[base+2];
          const fz1 = buf[base+4];
          if (flip) sy1 = hz - (sy1 - hz);
          if (d1 < 0.03) continue;

          for (let n = 0; n < 3; n++) {
            const na = a + NN[n][0], nb = b + NN[n][1];
            if (na < -RANGE || na > RANGE || nb < -RANGE || nb > RANGE) continue;
            const j = (na + RANGE) * count + (nb + RANGE);
            const jbase = j * 5;
            const sx2 = buf[jbase];
            let sy2 = buf[jbase+1];
            const d2 = buf[jbase+2];
            const fz2 = buf[jbase+4];
            if (flip) sy2 = hz - (sy2 - hz);

            if (Math.abs(fz1 - fz2) > halfWrap) continue;

            const avgD = (d1 + d2) * 0.5;
            if (avgD < 0.03) continue;
            let alpha = avgD * avgD * alphaMul;

            // Mouse glow boost
            const emx = (sx1 + sx2) * 0.5 - mpx;
            const emy = (sy1 + sy2) * 0.5 - mpy;
            const edgeDistSq = emx * emx + emy * emy;
            const edgeGlow = Math.max(0, 1.0 - edgeDistSq / glowRadiusSq) * mActive;
            alpha = alpha + edgeGlow * 0.4;

            const colType = edgeGlow > 0.3 ? 0.0 : (avgD > 0.55 ? 0.0 : 1.0);

            // 5 floats per vertex: x,y, alpha, colType, flipVal
            edgeFloats[ei++] = sx1;edgeFloats[ei++] = sy1;
            edgeFloats[ei++] = alpha;edgeFloats[ei++] = colType;edgeFloats[ei++] = flipVal;
            edgeFloats[ei++] = sx2;edgeFloats[ei++] = sy2;
            edgeFloats[ei++] = alpha;edgeFloats[ei++] = colType;edgeFloats[ei++] = flipVal;
          }
        }
      }
    }
    return ei / 5;
  }

  /* ── Sizing ────────────────────────────────────── */
  let W, H, CELL;
  const dpr = Math.min(window.devicePixelRatio || 1, 1.5);

  function resize() {
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width  = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    gl.viewport(0, 0, canvas.width, canvas.height);
    CELL = Math.max(52, Math.round(Math.min(W, H) / 9));
  }

  /* ── Animated background (nebula + aurora) ─────── */
  const bg = document.createElement('canvas');
  const bgCtx = bg.getContext('2d');
  const bgTex = gl.createTexture();
  let bgDirty = true;
  const bgUpdateInterval = 30; // re-render every N frames
  let bgFrameCount = 0;

  function updateBgTexture(time) {
    const bw = Math.round(W * 0.5);
    const bh = Math.round(H * 0.5);
    if (bg.width !== bw || bg.height !== bh) {
      bg.width = bw;
      bg.height = bh;
    }
    const c = bgCtx;
    const t = time || 0;

    // Base
    c.fillStyle = '#0b0d10';
    c.fillRect(0, 0, bw, bh);

    // Deep radial center glow
    const hx = bw / 2, hy = bh / 2;
    const grd = c.createRadialGradient(hx, hy * 0.9, 0, hx, hy, Math.max(bw, bh) * 0.7);
    grd.addColorStop(0,   'rgba(8,18,38,0.9)');
    grd.addColorStop(0.5, 'rgba(11,13,20,0.5)');
    grd.addColorStop(1,   'rgba(11,13,16,0)');
    c.fillStyle = grd;
    c.fillRect(0, 0, bw, bh);

    // Animated nebula blobs (positions drift with time)
    const blobs = [
      [0.12 + 0.08 * Math.sin(t * 0.28),   0.18 + 0.06 * Math.cos(t * 0.22),   '125,211,252', 0.38],
      [0.82 + 0.07 * Math.sin(t * 0.20+1), 0.22 + 0.09 * Math.cos(t * 0.17+2), '147,51,234',  0.32],
      [0.48 + 0.06 * Math.sin(t * 0.15+3), 0.52 + 0.07 * Math.cos(t * 0.19+1), '34,211,238',  0.28],
      [0.10 + 0.05 * Math.cos(t * 0.13),   0.72 + 0.06 * Math.sin(t * 0.18+2), '180,40,234',  0.25],
      [0.88 + 0.06 * Math.sin(t * 0.24+4), 0.78 + 0.05 * Math.cos(t * 0.16+3), '125,211,252', 0.28],
      [0.50 + 0.07 * Math.cos(t * 0.11+2), 0.10 + 0.04 * Math.sin(t * 0.21),   '125,211,252', 0.20],
      [0.28 + 0.06 * Math.sin(t * 0.19+5), 0.88 + 0.04 * Math.cos(t * 0.23+1), '34,211,238',  0.22],
      [0.68 + 0.05 * Math.cos(t * 0.14+3), 0.60 + 0.06 * Math.sin(t * 0.20+4), '220,50,150',  0.18],
    ];

    for (let i = 0; i < blobs.length; i++) {
      const bl = blobs[i];
      const bx = bl[0] * bw, by = bl[1] * bh;
      const br = bl[3] * Math.min(bw, bh);
      const g = c.createRadialGradient(bx, by, 0, bx, by, br);
      const alpha0 = 0.062 * (1 + 0.25 * Math.sin(t * 0.4 + i));
      const alpha1 = 0.022 * (1 + 0.2  * Math.sin(t * 0.3 + i * 0.7));
      g.addColorStop(0,   'rgba(' + bl[2] + ',' + alpha0.toFixed(3) + ')');
      g.addColorStop(0.5, 'rgba(' + bl[2] + ',' + alpha1.toFixed(3) + ')');
      g.addColorStop(1,   'rgba(' + bl[2] + ',0)');
      c.beginPath();
      c.arc(bx, by, br, 0, Math.PI * 2);
      c.fillStyle = g;
      c.fill();
    }

    // Aurora bands — sweeping diagonal gradients
    const auroraConfig = [
      { baseAngle: 0.28, speed: 0.008, cx: 0.35, cy: 0.38, color: '125,211,252', intensity: 0.055 },
      { baseAngle: -0.18, speed: 0.006, cx: 0.62, cy: 0.55, color: '147,51,234',  intensity: 0.045 },
      { baseAngle: 0.52, speed: 0.010, cx: 0.45, cy: 0.72, color: '220,50,150',   intensity: 0.038 },
    ];

    for (let ai = 0; ai < auroraConfig.length; ai++) {
      const ac = auroraConfig[ai];
      const angle = ac.baseAngle + t * ac.speed;
      const acx = ac.cx * bw + Math.sin(t * 0.07 + ai) * bw * 0.12;
      const acy = ac.cy * bh + Math.cos(t * 0.05 + ai) * bh * 0.10;
      const bandW = bw * 3;
      const bandH = bh * 0.10 + bh * 0.04 * Math.sin(t * 0.12 + ai * 2);

      c.save();
      c.translate(acx, acy);
      c.rotate(angle);

      const aBand = c.createLinearGradient(0, -bandH / 2, 0, bandH / 2);
      const peakAlpha = ac.intensity * (0.8 + 0.2 * Math.sin(t * 0.25 + ai));
      aBand.addColorStop(0,    'rgba(' + ac.color + ',0)');
      aBand.addColorStop(0.35, 'rgba(' + ac.color + ',' + (peakAlpha * 0.5).toFixed(3) + ')');
      aBand.addColorStop(0.5,  'rgba(' + ac.color + ',' + peakAlpha.toFixed(3) + ')');
      aBand.addColorStop(0.65, 'rgba(' + ac.color + ',' + (peakAlpha * 0.5).toFixed(3) + ')');
      aBand.addColorStop(1,    'rgba(' + ac.color + ',0)');

      c.fillStyle = aBand;
      c.fillRect(-bandW / 2, -bandH / 2, bandW, bandH);
      c.restore();
    }

    // Subtle vignette
    const vig = c.createRadialGradient(hx, hy, Math.min(bw, bh) * 0.35, hx, hy, Math.max(bw, bh) * 0.8);
    vig.addColorStop(0, 'rgba(0,0,0,0)');
    vig.addColorStop(1, 'rgba(0,0,0,0.55)');
    c.fillStyle = vig;
    c.fillRect(0, 0, bw, bh);

    gl.bindTexture(gl.TEXTURE_2D, bgTex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, bg);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    bgDirty = false;
  }

  /* ── Quad (background blit) ────────────────────── */
  const QUAD_VERT = [
    'precision mediump float;',
    'attribute vec2 aPos;',
    'varying vec2 vUV;',
    'void main() {',
    '  vUV = aPos * 0.5 + 0.5;',
    '  gl_Position = vec4(aPos, 0.0, 1.0);',
    '}'
  ].join('\n');

  const QUAD_FRAG = [
    'precision mediump float;',
    'uniform sampler2D uTex;',
    'varying vec2 vUV;',
    'void main() {',
    '  gl_FragColor = texture2D(uTex, vec2(vUV.x, 1.0 - vUV.y));',
    '}'
  ].join('\n');

  const quadProg = linkProgram(QUAD_VERT, QUAD_FRAG);
  const qAPos = gl.getAttribLocation(quadProg, 'aPos');
  const qUTex = gl.getUniformLocation(quadProg, 'uTex');
  const quadBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, 1,1]), gl.STATIC_DRAW);

  /* ── Frame ─────────────────────────────────────── */
  let t = 0;
  let raf = null;
  let bgTime = 0;

  function frame() {
    // Update background every N frames
    bgFrameCount++;
    if (bgDirty || bgFrameCount >= bgUpdateInterval) {
      bgTime += 0.016 * bgUpdateInterval;
      updateBgTexture(bgTime);
      bgFrameCount = 0;
    }

    // Smooth mouse
    mouseNX += (targetMX - mouseNX) * 0.08;
    mouseNY += (targetMY - mouseNY) * 0.08;

    // Advance pulse ages
    for (let pi = 0; pi < pulses.length; pi++) {
      pulses[pi].age++;
    }
    // Remove dead pulses
    pulses = pulses.filter(function (p) { return p.age < p.maxAge; });

    gl.clearColor(0.043, 0.051, 0.063, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);

    // Background quad
    gl.disable(gl.BLEND);
    gl.useProgram(quadProg);
    gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf);
    gl.enableVertexAttribArray(qAPos);
    gl.vertexAttribPointer(qAPos, 2, gl.FLOAT, false, 0, 0);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, bgTex);
    gl.uniform1i(qUTex, 0);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    gl.disableVertexAttribArray(qAPos);

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    // Edges (CPU-projected)
    projectPass(t, CELL, W, H, projFloor, 20,  1.0);
    projectPass(t, CELL, W, H, projCeil,  -14, 0.7);
    const edgeVerts = buildEdges(W, H);

    if (edgeVerts > 0) {
      gl.useProgram(edgeProg);
      gl.uniform2f(eURes, W, H);
      gl.uniform1f(eUTime, t);
      gl.bindBuffer(gl.ARRAY_BUFFER, edgeBuf);
      gl.bufferData(gl.ARRAY_BUFFER, edgeFloats.subarray(0, edgeVerts * 5), gl.DYNAMIC_DRAW);
      // stride = 5 floats * 4 bytes = 20
      gl.enableVertexAttribArray(eAPos);
      gl.enableVertexAttribArray(eAAlpha);
      gl.enableVertexAttribArray(eAColType);
      gl.enableVertexAttribArray(eAFlipEdge);
      gl.vertexAttribPointer(eAPos,      2, gl.FLOAT, false, 20, 0);
      gl.vertexAttribPointer(eAAlpha,    1, gl.FLOAT, false, 20, 8);
      gl.vertexAttribPointer(eAColType,  1, gl.FLOAT, false, 20, 12);
      gl.vertexAttribPointer(eAFlipEdge, 1, gl.FLOAT, false, 20, 16);
      gl.drawArrays(gl.LINES, 0, edgeVerts);
      gl.disableVertexAttribArray(eAPos);
      gl.disableVertexAttribArray(eAAlpha);
      gl.disableVertexAttribArray(eAColType);
      gl.disableVertexAttribArray(eAFlipEdge);
    }

    // Nodes (GPU shader)
    gl.useProgram(nodeProg);
    gl.uniform1f(uTime, t);
    gl.uniform2f(uRes, W, H);
    gl.uniform1f(uCell, CELL);
    gl.uniform2f(uMouse, mouseNX, mouseNY);
    gl.uniform1f(uMouseActive, mouseActive ? 1.0 : 0.0);

    // Upload pulse data (up to 2 pulses)
    const p0 = pulses[0] || { x: 0, y: 0, age: 0 };
    const p1 = pulses[1] || { x: 0, y: 0, age: 0 };
    gl.uniform2f(uPulse0, p0.x, p0.y);
    gl.uniform1f(uPulseAge0, p0.age || 0);
    gl.uniform2f(uPulse1, p1.x, p1.y);
    gl.uniform1f(uPulseAge1, p1.age || 0);

    gl.bindBuffer(gl.ARRAY_BUFFER, latticeBuf);
    gl.enableVertexAttribArray(aLattice);
    gl.enableVertexAttribArray(aFlip);
    gl.vertexAttribPointer(aLattice, 2, gl.FLOAT, false, 12, 0);
    gl.vertexAttribPointer(aFlip,    1, gl.FLOAT, false, 12, 8);
    gl.drawArrays(gl.POINTS, 0, numPoints);
    gl.disableVertexAttribArray(aLattice);
    gl.disableVertexAttribArray(aFlip);

    t += 0.016;
    raf = requestAnimationFrame(frame);
  }

  /* ── Init ──────────────────────────────────────── */
  function init() {
    resize();
    bgDirty = true;
    bgTime = 0;
    if (reduced) {
      updateBgTexture(0);
      frame();
      cancelAnimationFrame(raf);
      raf = null;
      return;
    }
    frame();
  }

  /* ── Resize ────────────────────────────────────── */
  let rTimer;
  window.addEventListener('resize', function () {
    clearTimeout(rTimer);
    rTimer = setTimeout(function () {
      if (raf) { cancelAnimationFrame(raf); raf = null; }
      resize();
      bgDirty = true;
      if (!reduced) frame();
    }, 150);
  });

  /* ── Visibility pause ──────────────────────────── */
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
      if (raf) { cancelAnimationFrame(raf); raf = null; }
    } else if (!reduced) {
      frame();
    }
  });

  init();
}());
