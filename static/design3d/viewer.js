// design3d: the 3D view (REQ-D3.24). The part in filament orange on the
// print bed, turned by finger or mouse. window.d3View.load(url) swaps the
// part; the page calls it when a new version is ready.
//
// Two tap modes (Avi, 2026-10-29):
//   Point:   tap the part to mark "here" for the chat. The point is kept in
//            the code's own coordinates (the view moves the part to sit
//            centred on the bed, and that offset is added back), with the
//            face's direction; the page sends it with the next message,
//            and a picture of the view with the marker.
//   Measure: tap two points on the part for the distance between them.
// A tap is a press and release that barely moved; anything else turns the
// view as before.

import * as THREE from "three";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const box = document.getElementById("d3-view");
if (box) {
  // preserveDrawingBuffer: the page takes a picture of the view with the
  // marker to send with the message.
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  box.prepend(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 5000);
  camera.up.set(0, 0, 1);
  scene.add(new THREE.HemisphereLight(0xfff1dc, 0x2a2418, 1.1));
  const sun = new THREE.DirectionalLight(0xffffff, 1.6);
  sun.position.set(1, -1.4, 2);
  scene.add(sun);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;

  const material = new THREE.MeshStandardMaterial({ color: 0xff7a1a, roughness: 0.55, metalness: 0.05 });
  const markMaterial = new THREE.MeshBasicMaterial({ color: 0x35d0ff, depthTest: false });
  const lineMaterial = new THREE.LineBasicMaterial({ color: 0x35d0ff, depthTest: false });
  let model = null;      // a Group: one mesh, or one per part (Chapter 7)
  let meshes = [];       // [{name, mesh, dir}] for parts: hide, show, explode
  let grid = null;
  let span = 10;
  const offset = new THREE.Vector3();  // view + offset = the code's coordinates
  let mode = "";
  let pin = null;        // {x, y, z, nx, ny, nz, version}
  let pinMark = null;
  let measure = [];      // up to two points, view coordinates
  let measureMarks = [];
  const label = document.getElementById("d3-measure-label");

  function size() {
    const w = box.clientWidth, h = box.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(h, 1);
    camera.updateProjectionMatrix();
  }

  function frame(group) {
    const bb = new THREE.Box3().setFromObject(group);
    const c = new THREE.Vector3();
    bb.getCenter(c);
    offset.set(c.x, c.y, bb.min.z);
    group.position.set(-c.x, -c.y, -bb.min.z);
    const s = new THREE.Vector3();
    bb.getSize(s);
    span = Math.max(s.x, s.y, s.z) || 10;
    if (grid) scene.remove(grid);
    grid = new THREE.GridHelper(Math.ceil(span * 2.4 / 10) * 10, Math.ceil(span * 2.4 / 10), 0x5a4a30, 0x3d3424);
    grid.rotation.x = Math.PI / 2;
    scene.add(grid);
    // Frame the whole part: the distance at which its bounding sphere fits
    // both the height and the width of the view, whatever its shape.
    const radius = 0.5 * Math.sqrt(s.x * s.x + s.y * s.y + s.z * s.z) || 10;
    const vfov = THREE.MathUtils.degToRad(camera.fov);
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * camera.aspect);
    const dist = 1.15 * radius / Math.sin(Math.min(vfov, hfov) / 2);
    const dir = new THREE.Vector3(0.55, -0.75, 0.48).normalize();
    controls.target.set(0, 0, s.z / 2);
    camera.position.copy(dir.multiplyScalar(dist)).add(controls.target);
    camera.near = dist / 100;
    camera.far = dist * 20;
    camera.updateProjectionMatrix();
    controls.update();
  }

  function marker(at) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(Math.max(span / 40, 0.6), 16, 12), markMaterial);
    m.position.copy(at);
    m.renderOrder = 10;
    scene.add(m);
    return m;
  }

  function drop(obj) {
    if (!obj) return;
    scene.remove(obj);
    if (obj.geometry) obj.geometry.dispose();
  }

  function clearPin() {
    drop(pinMark);
    pinMark = null;
    pin = null;
    box.dispatchEvent(new CustomEvent("d3:pin", { bubbles: true, detail: null }));
  }

  function clearMeasure() {
    measureMarks.forEach(drop);
    measureMarks = [];
    measure = [];
    if (label) label.hidden = true;
  }

  function setMode(next) {
    mode = mode === next ? "" : next;
    box.dataset.mode = mode;
    document.querySelectorAll("[data-d3-mode]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.d3Mode === mode)));
    if (mode !== "measure") clearMeasure();
  }

  function swap(group, key) {
    if (model) {
      scene.remove(model);
      model.traverse((o) => { if (o.geometry) o.geometry.dispose(); });
    }
    model = group;
    scene.add(model);
    frame(model);
    clearPin();
    clearMeasure();
    const empty = document.getElementById("d3-view-empty");
    if (empty) empty.hidden = true;
    box.dataset.loaded = key;
  }

  function load(url) {
    if (!url) return;
    new STLLoader().load(url, (geometry) => {
      geometry.computeVertexNormals();
      const group = new THREE.Group();
      group.add(new THREE.Mesh(geometry, material));
      meshes = [];
      swap(group, url);
    });
  }

  // Several parts, each in its place and its own colour; hardware the
  // person buys is shown see-through.
  function loadParts(parts) {
    if (!parts || !parts.length) return;
    const loader = new STLLoader();
    Promise.all(parts.map((p) => loader.loadAsync(p.stl))).then((geoms) => {
      const group = new THREE.Group();
      const list = [];
      geoms.forEach((g, i) => {
        g.computeVertexNormals();
        const p = parts[i];
        const mat = new THREE.MeshStandardMaterial({ color: p.color, roughness: 0.55, metalness: p.printed ? 0.05 : 0.6,
                                                     transparent: !p.printed, opacity: p.printed ? 1 : 0.55 });
        const mesh = new THREE.Mesh(g, mat);
        mesh.userData.name = p.name;
        group.add(mesh);
        list.push({ name: p.name, mesh });
      });
      const all = new THREE.Box3().setFromObject(group).getCenter(new THREE.Vector3());
      list.forEach((m) => {
        const c = new THREE.Box3().setFromObject(m.mesh).getCenter(new THREE.Vector3());
        // Pulled out from the middle, but never down through the bed.
        m.dir = c.sub(all);
        m.dir.z = Math.max(m.dir.z, 0);
        if (m.dir.length() > 1e-6) m.dir.normalize();
      });
      meshes = list;
      swap(group, parts.map((p) => p.stl).join(" "));
    });
  }

  function explode(t) {
    meshes.forEach((m) => m.mesh.position.copy(m.dir).multiplyScalar(t * span * 0.7));
  }

  function setVisible(name, on) {
    meshes.forEach((m) => { if (m.name === name) m.mesh.visible = on; });
  }

  // ---- taps ----
  const ray = new THREE.Raycaster();
  let down = null;
  renderer.domElement.addEventListener("pointerdown", (e) => { down = { x: e.clientX, y: e.clientY }; });
  renderer.domElement.addEventListener("pointerup", (e) => {
    if (!down || !mode || !model) return;
    const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y);
    down = null;
    if (moved > 6) return;
    const r = renderer.domElement.getBoundingClientRect();
    ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
    const hit = ray.intersectObject(model, true).find((h) => h.object.visible);
    if (!hit) return;
    tapped(hit.point.clone(), hit.face ? hit.face.normal.clone() : new THREE.Vector3(0, 0, 1), hit.object.userData.name);
  });

  function tapped(at, normal, partName) {
    if (mode === "pin") {
      drop(pinMark);
      pinMark = marker(at);
      // The code's coordinates: the view's, plus how far the view moved the
      // model, less how far an exploded part was pulled out.
      const hitPart = meshes.find((m) => m.name === partName);
      const p = at.clone().add(offset);
      if (hitPart) p.sub(hitPart.mesh.position);
      pin = { x: p.x, y: p.y, z: p.z, nx: normal.x, ny: normal.y, nz: normal.z,
              version: Number(document.getElementById("d3-work")?.dataset.shown || 0) };
      if (partName) pin.part = partName;
      box.dispatchEvent(new CustomEvent("d3:pin", { bubbles: true, detail: pin }));
    } else if (mode === "measure") {
      if (measure.length === 2) clearMeasure();
      measure.push(at);
      measureMarks.push(marker(at));
      if (measure.length === 2) {
        const g = new THREE.BufferGeometry().setFromPoints(measure);
        const line = new THREE.Line(g, lineMaterial);
        line.renderOrder = 10;
        scene.add(line);
        measureMarks.push(line);
        const d = measure[1].clone().sub(measure[0]);
        const f = (n) => Math.abs(n).toFixed(1);
        label.textContent = `${d.length().toFixed(1)} mm  (x ${f(d.x)}, y ${f(d.y)}, z ${f(d.z)})`;
        label.hidden = false;
        box.dataset.measured = d.length().toFixed(1);
      }
    }
  }

  // A picture of the view as it is now (the marker included), for the chat.
  function snapshot() {
    renderer.render(scene, camera);
    return new Promise((resolve) => renderer.domElement.toBlob(resolve, "image/jpeg", 0.85));
  }

  new ResizeObserver(size).observe(box);
  size();
  (function tick() {
    controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  })();

  document.querySelectorAll("[data-d3-mode]").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.d3Mode)));

  window.d3View = { load, loadParts, explode, setVisible, snapshot, clearPin, getPin: () => pin, tap: tapped, setMode, offset };
  let first = null;
  try { first = JSON.parse(document.getElementById("design3d-shown")?.textContent || "null"); } catch (err) { first = null; }
  if (first && first.parts && first.parts.length) loadParts(first.parts); else load(box.dataset.stl);
}
