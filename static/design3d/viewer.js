// design3d: the 3D view (REQ-D3.24). The part in filament orange on the
// print bed, turned by finger or mouse. window.d3View.load(url) swaps the
// part; the page calls it when a new version is ready.

import * as THREE from "three";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const box = document.getElementById("d3-view");
if (box) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
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
  let part = null;
  let grid = null;

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
    geometry.translate(-c.x, -c.y, -bb.min.z);
    const s = new THREE.Vector3();
    bb.getSize(s);
    const span = Math.max(s.x, s.y, s.z) || 10;
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

  function load(url) {
    if (!url) return;
    new STLLoader().load(url, (geometry) => {
      geometry.computeVertexNormals();
      if (part) { scene.remove(part); part.geometry.dispose(); }
      part = new THREE.Mesh(geometry, material);
      scene.add(part);
      frame(geometry);
      const empty = document.getElementById("d3-view-empty");
      if (empty) empty.hidden = true;
      box.dataset.loaded = url;
    });
  }

  new ResizeObserver(size).observe(box);
  size();
  (function tick() {
    controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  })();

  window.d3View = { load };
  load(box.dataset.stl);
}
