// Reusable STL 3D viewer (Three.js). Renders an .stl into a container with
// orbit controls (drag to rotate, scroll to zoom). Used on the final-lesson
// upload step (live preview of the picked file) and on the certificate page.
//
// Resolution of the bare "three" / "three/addons/" specifiers is provided by an
// <script type="importmap"> declared in the host page (see lesson.html /
// certificate.html), so this file stays build-free.
import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export function initStlViewer(container, url, opts = {}) {
  // Clear any prior viewer (e.g. user re-picks a file).
  container.innerHTML = '';

  const width = container.clientWidth || 400;
  const height = container.clientHeight || 320;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100000);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  renderer.setSize(width, height);
  container.appendChild(renderer.domElement);

  scene.add(new THREE.HemisphereLight(0xffffff, 0x404040, 1.1));
  const key = new THREE.DirectionalLight(0xffffff, 0.9);
  key.position.set(1, 1, 1);
  scene.add(key);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.autoRotate = opts.autoRotate !== false; // gentle spin by default
  controls.autoRotateSpeed = 1.2;

  const loader = new STLLoader();
  loader.load(
    url,
    (geometry) => {
      geometry.computeVertexNormals();
      const material = new THREE.MeshStandardMaterial({
        color: opts.color || 0x6f9c8f, metalness: 0.15, roughness: 0.7,
      });
      const mesh = new THREE.Mesh(geometry, material);

      // Center the model at the origin and frame the camera to fit it.
      geometry.computeBoundingBox();
      const bb = geometry.boundingBox;
      const center = new THREE.Vector3();
      bb.getCenter(center);
      mesh.position.sub(center);
      scene.add(mesh);

      const size = new THREE.Vector3();
      bb.getSize(size);
      const maxDim = Math.max(size.x, size.y, size.z) || 1;
      const dist = maxDim * 2.2;
      camera.position.set(dist, dist * 0.6, dist);
      camera.near = maxDim / 100;
      camera.far = maxDim * 100;
      camera.updateProjectionMatrix();
      controls.target.set(0, 0, 0);
      controls.update();

      if (typeof opts.onload === 'function') opts.onload();
    },
    undefined,
    (err) => { if (typeof opts.onerror === 'function') opts.onerror(err); }
  );

  let alive = true;
  (function animate() {
    if (!alive) return;
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  })();

  function onResize() {
    const w = container.clientWidth || width;
    const h = container.clientHeight || height;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }
  window.addEventListener('resize', onResize);

  return {
    stop() { alive = false; window.removeEventListener('resize', onResize); },
    controls,
  };
}

// Turn every .stl-tile on the page into a tile, and wire clicks to the shared
// #stl-modal for an enlarged view. STL tiles (data-stl) get a small auto-rotating
// 3D viewer + an orbitable modal; Scratch tiles (data-scratch) show a thumbnail
// and open the live embedded player in the modal.
export function initGallery() {
  const tiles = document.querySelectorAll('.stl-tile[data-stl], .stl-tile[data-scratch]');
  if (!tiles.length) return;

  const modal = document.getElementById('stl-modal');
  const mCanvas = modal && modal.querySelector('#stl-modal-canvas');
  const mFrame = modal && modal.querySelector('#stl-modal-frame');
  const mTitle = modal && modal.querySelector('#stl-modal-title');
  const mDl = modal && modal.querySelector('#stl-modal-dl');
  const mOpen = modal && modal.querySelector('#stl-modal-open');
  let mViewer = null;

  function closeModal() {
    if (mViewer) { mViewer.stop(); mViewer = null; }
    if (mCanvas) mCanvas.innerHTML = '';
    if (mFrame) mFrame.innerHTML = '';
    if (modal) modal.style.display = 'none';
  }
  function openModal(ds) {
    if (!modal) return;
    if (mTitle) mTitle.textContent = ds.title || '';
    if (mViewer) { mViewer.stop(); mViewer = null; }
    if (mCanvas) mCanvas.innerHTML = '';
    if (mFrame) mFrame.innerHTML = '';

    if (ds.scratch) {
      // Embedded Scratch player.
      if (mCanvas) mCanvas.style.display = 'none';
      if (mDl) mDl.style.display = 'none';
      if (mFrame) {
        mFrame.style.display = '';
        const f = document.createElement('iframe');
        f.src = 'https://scratch.mit.edu/projects/' + ds.scratch + '/embed';
        f.setAttribute('allowtransparency', 'true');
        f.setAttribute('allowfullscreen', 'true');
        f.setAttribute('frameborder', '0');
        f.setAttribute('scrolling', 'no');
        mFrame.appendChild(f);
      }
      if (mOpen) {
        mOpen.style.display = '';
        mOpen.setAttribute('href', ds.open || ('https://scratch.mit.edu/projects/' + ds.scratch + '/'));
      }
    } else {
      // 3D STL viewer.
      if (mFrame) mFrame.style.display = 'none';
      if (mOpen) mOpen.style.display = 'none';
      if (mCanvas) mCanvas.style.display = '';
      if (mDl) {
        if (ds.dl) { mDl.style.display = ''; mDl.setAttribute('href', ds.dl); }
        else mDl.style.display = 'none';
      }
      mViewer = initStlViewer(mCanvas, ds.stl, { autoRotate: false });
    }
    modal.style.display = 'flex';
  }
  if (modal) {
    modal.querySelectorAll('[data-stl-close]').forEach((b) => b.addEventListener('click', closeModal));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
  }

  tiles.forEach((tile) => {
    if (tile.dataset.stl) {
      const canvas = tile.querySelector('.stl-tile-canvas');
      if (canvas) initStlViewer(canvas, tile.dataset.stl, { autoRotate: true });
    }
    tile.addEventListener('click', () => openModal(tile.dataset));
  });
}
