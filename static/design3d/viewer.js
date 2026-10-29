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
  let part = null;
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

  function frame(geometry) {
    geometry.computeBoundingBox();
    const bb = geometry.boundingBox;
    const c = new THREE.Vector3();
    bb.getCenter(c);
    offset.set(c.x, c.y, bb.min.z);
    geometry.translate(-c.x, -c.y, -bb.min.z);
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

  function load(url) {
    if (!url) return;
    new STLLoader().load(url, (geometry) => {
      geometry.computeVertexNormals();
      if (part) { scene.remove(part); part.geometry.dispose(); }
      part = new THREE.Mesh(geometry, material);
      scene.add(part);
      frame(geometry);
      clearPin();
      clearMeasure();
      const empty = document.getElementById("d3-view-empty");
      if (empty) empty.hidden = true;
      box.dataset.loaded = url;
    });
  }

  // ---- taps ----
  const ray = new THREE.Raycaster();
  let down = null;
  renderer.domElement.addEventListener("pointerdown", (e) => { down = { x: e.clientX, y: e.clientY }; });
  renderer.domElement.addEventListener("pointerup", (e) => {
    if (!down || !mode || !part) return;
    const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y);
    down = null;
    if (moved > 6) return;
    const r = renderer.domElement.getBoundingClientRect();
    ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
    const hit = ray.intersectObject(part)[0];
    if (!hit) return;
    tapped(hit.point.clone(), hit.face ? hit.face.normal.clone() : new THREE.Vector3(0, 0, 1));
  });

  function tapped(at, normal) {
    if (mode === "pin") {
      drop(pinMark);
      pinMark = marker(at);
      const p = at.clone().add(offset);
      pin = { x: p.x, y: p.y, z: p.z, nx: normal.x, ny: normal.y, nz: normal.z,
              version: Number(document.getElementById("d3-work")?.dataset.shown || 0) };
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

  window.d3View = { load, snapshot, clearPin, getPin: () => pin, tap: tapped, setMode, offset };
  load(box.dataset.stl);
}
