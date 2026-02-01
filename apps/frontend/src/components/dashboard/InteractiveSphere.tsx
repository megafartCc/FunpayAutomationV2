import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const createEarthTexture = (size = 1024) => {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size / 2;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;

  ctx.fillStyle = "#0b1f3a";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const continents = 220;
  for (let i = 0; i < continents; i += 1) {
    const x = Math.random() * canvas.width;
    const y = Math.random() * canvas.height;
    const radius = 18 + Math.random() * 45;
    const hue = 110 + Math.random() * 20;
    const lightness = 28 + Math.random() * 20;
    ctx.beginPath();
    ctx.fillStyle = `hsl(${hue}, 45%, ${lightness}%)`;
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.fillStyle = "rgba(255, 255, 255, 0.6)";
  ctx.beginPath();
  ctx.ellipse(canvas.width * 0.5, canvas.height * 0.06, canvas.width * 0.5, canvas.height * 0.1, 0, 0, Math.PI * 2);
  ctx.ellipse(canvas.width * 0.5, canvas.height * 0.94, canvas.width * 0.5, canvas.height * 0.1, 0, 0, Math.PI * 2);
  ctx.fill();

  const noise = ctx.getImageData(0, 0, canvas.width, canvas.height);
  for (let i = 0; i < noise.data.length; i += 4) {
    const n = (Math.random() - 0.5) * 16;
    noise.data[i] = clamp(noise.data[i] + n, 0, 255);
    noise.data[i + 1] = clamp(noise.data[i + 1] + n, 0, 255);
    noise.data[i + 2] = clamp(noise.data[i + 2] + n, 0, 255);
  }
  ctx.putImageData(noise, 0, 0);

  return canvas;
};

const createCloudTexture = (size = 1024) => {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size / 2;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  for (let i = 0; i < 160; i += 1) {
    const x = Math.random() * canvas.width;
    const y = Math.random() * canvas.height;
    const radius = 20 + Math.random() * 55;
    const alpha = 0.08 + Math.random() * 0.12;
    ctx.beginPath();
    ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
  }

  return canvas;
};

const createBumpTexture = (size = 1024) => {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size / 2;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;

  const imageData = ctx.createImageData(canvas.width, canvas.height);
  for (let i = 0; i < imageData.data.length; i += 4) {
    const v = 180 + Math.random() * 50;
    imageData.data[i] = v;
    imageData.data[i + 1] = v;
    imageData.data[i + 2] = v;
    imageData.data[i + 3] = 255;
  }
  ctx.putImageData(imageData, 0, 0);
  return canvas;
};

const InteractiveSphere: React.FC = () => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [supported, setSupported] = useState(true);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let renderer: THREE.WebGLRenderer | null = null;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setSupported(false);
      return;
    }

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    camera.position.set(0, 0, 4.2);

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.style.display = "block";
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    container.appendChild(renderer.domElement);

    const earthCanvas = createEarthTexture();
    const earthTexture = new THREE.CanvasTexture(earthCanvas);
    earthTexture.colorSpace = THREE.SRGBColorSpace;

    const bumpCanvas = createBumpTexture();
    const bumpTexture = new THREE.CanvasTexture(bumpCanvas);

    const cloudCanvas = createCloudTexture();
    const cloudTexture = new THREE.CanvasTexture(cloudCanvas);
    cloudTexture.colorSpace = THREE.SRGBColorSpace;

    const geometry = new THREE.SphereGeometry(1, 96, 96);
    const material = new THREE.MeshPhongMaterial({
      map: earthTexture,
      bumpMap: bumpTexture,
      bumpScale: 0.05,
      specular: new THREE.Color("#1d4ed8"),
      shininess: 15,
    });
    const earth = new THREE.Mesh(geometry, material);
    scene.add(earth);

    const cloudGeometry = new THREE.SphereGeometry(1.01, 72, 72);
    const cloudMaterial = new THREE.MeshStandardMaterial({
      map: cloudTexture,
      transparent: true,
      opacity: 0.6,
      depthWrite: false,
    });
    const clouds = new THREE.Mesh(cloudGeometry, cloudMaterial);
    scene.add(clouds);

    const glowGeometry = new THREE.SphereGeometry(1.07, 64, 64);
    const glowMaterial = new THREE.MeshBasicMaterial({
      color: new THREE.Color("#7dd3fc"),
      transparent: true,
      opacity: 0.2,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
    });
    const glow = new THREE.Mesh(glowGeometry, glowMaterial);
    scene.add(glow);

    const ambient = new THREE.AmbientLight(0xffffff, 0.5);
    const light = new THREE.DirectionalLight(0xffffff, 1.15);
    light.position.set(4, 3, 4);
    scene.add(ambient, light);

    const state = {
      isDragging: false,
      lastX: 0,
      lastY: 0,
      targetX: 0,
      targetY: 0,
      distance: 4.2,
    };

    const handlePointerDown = (event: PointerEvent) => {
      state.isDragging = true;
      state.lastX = event.clientX;
      state.lastY = event.clientY;
      (event.target as HTMLElement).setPointerCapture?.(event.pointerId);
    };

    const handlePointerMove = (event: PointerEvent) => {
      if (!state.isDragging) return;
      const dx = event.clientX - state.lastX;
      const dy = event.clientY - state.lastY;
      state.lastX = event.clientX;
      state.lastY = event.clientY;
      state.targetY += dx * 0.005;
      state.targetX += dy * 0.005;
      state.targetX = clamp(state.targetX, -Math.PI / 2, Math.PI / 2);
    };

    const endDrag = (event: PointerEvent) => {
      state.isDragging = false;
      (event.target as HTMLElement).releasePointerCapture?.(event.pointerId);
    };

    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      state.distance = clamp(state.distance + event.deltaY * 0.01, 2.4, 6.5);
    };

    container.addEventListener("pointerdown", handlePointerDown);
    container.addEventListener("pointermove", handlePointerMove);
    container.addEventListener("pointerup", endDrag);
    container.addEventListener("pointerleave", endDrag);
    container.addEventListener("pointercancel", endDrag);
    container.addEventListener("wheel", handleWheel, { passive: false });

    let frame = 0;
    const animate = () => {
      frame = window.requestAnimationFrame(animate);
      if (!state.isDragging) {
        state.targetY += 0.0025;
      }
      earth.rotation.x += (state.targetX - earth.rotation.x) * 0.08;
      earth.rotation.y += (state.targetY - earth.rotation.y) * 0.08;
      clouds.rotation.x = earth.rotation.x * 1.02;
      clouds.rotation.y = earth.rotation.y + 0.008;
      camera.position.z += (state.distance - camera.position.z) * 0.1;
      renderer?.render(scene, camera);
    };
    animate();

    const resize = () => {
      const { width, height } = container.getBoundingClientRect();
      if (!width || !height) return;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer?.setSize(width, height, false);
    };
    resize();

    let resizeObserver: ResizeObserver | null = null;
    if ("ResizeObserver" in window) {
      resizeObserver = new ResizeObserver(resize);
      resizeObserver.observe(container);
    } else {
      window.addEventListener("resize", resize);
    }

    return () => {
      window.cancelAnimationFrame(frame);
      if (resizeObserver) {
        resizeObserver.disconnect();
      } else {
        window.removeEventListener("resize", resize);
      }
      container.removeEventListener("pointerdown", handlePointerDown);
      container.removeEventListener("pointermove", handlePointerMove);
      container.removeEventListener("pointerup", endDrag);
      container.removeEventListener("pointerleave", endDrag);
      container.removeEventListener("pointercancel", endDrag);
      container.removeEventListener("wheel", handleWheel);
      geometry.dispose();
      cloudGeometry.dispose();
      glowGeometry.dispose();
      material.dispose();
      cloudMaterial.dispose();
      glowMaterial.dispose();
      earthTexture.dispose();
      bumpTexture.dispose();
      cloudTexture.dispose();
      renderer?.dispose();
      if (renderer?.domElement && renderer.domElement.parentElement === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-sm font-semibold text-neutral-900">Interactive Earth</div>
          <div className="mt-1 text-xs text-neutral-500">Drag to rotate, scroll to zoom.</div>
        </div>
        <span className="rounded-full bg-neutral-100 px-3 py-1 text-[10px] font-semibold uppercase tracking-wide text-neutral-500">
          WebGL
        </span>
      </div>
      {supported ? (
        <div
          ref={containerRef}
          className="mt-4 h-64 w-full cursor-grab overflow-hidden rounded-xl bg-gradient-to-br from-neutral-950 via-slate-900 to-slate-800 shadow-inner active:cursor-grabbing"
          style={{ touchAction: "none" }}
        />
      ) : (
        <div className="mt-4 rounded-xl border border-dashed border-neutral-300 bg-neutral-50 px-4 py-10 text-center text-sm text-neutral-500">
          WebGL is unavailable in this browser.
        </div>
      )}
    </div>
  );
};

export default InteractiveSphere;
