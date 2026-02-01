import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

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
    camera.position.set(0, 0, 4);

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.style.display = "block";
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    container.appendChild(renderer.domElement);

    const geometry = new THREE.SphereGeometry(1, 64, 64);
    const material = new THREE.MeshStandardMaterial({
      color: new THREE.Color("#60a5fa"),
      metalness: 0.35,
      roughness: 0.2,
    });
    const sphere = new THREE.Mesh(geometry, material);
    scene.add(sphere);

    const ambient = new THREE.AmbientLight(0xffffff, 0.55);
    const light = new THREE.DirectionalLight(0xffffff, 1.1);
    light.position.set(3, 3, 4);
    scene.add(ambient, light);

    const state = {
      isDragging: false,
      lastX: 0,
      lastY: 0,
      targetX: 0,
      targetY: 0,
      distance: 4,
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
      state.distance = clamp(state.distance + event.deltaY * 0.01, 2.6, 6);
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
        state.targetY += 0.003;
      }
      sphere.rotation.x += (state.targetX - sphere.rotation.x) * 0.08;
      sphere.rotation.y += (state.targetY - sphere.rotation.y) * 0.08;
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
      material.dispose();
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
          <div className="text-sm font-semibold text-neutral-900">Interactive sphere</div>
          <div className="mt-1 text-xs text-neutral-500">Drag to rotate, scroll to zoom.</div>
        </div>
        <span className="rounded-full bg-neutral-100 px-3 py-1 text-[10px] font-semibold uppercase tracking-wide text-neutral-500">
          WebGL
        </span>
      </div>
      {supported ? (
        <div
          ref={containerRef}
          className="mt-4 h-64 w-full cursor-grab overflow-hidden rounded-xl bg-gradient-to-br from-neutral-900 via-slate-900 to-neutral-800 shadow-inner active:cursor-grabbing"
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
