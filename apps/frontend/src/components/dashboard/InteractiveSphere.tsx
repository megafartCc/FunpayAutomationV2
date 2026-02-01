import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";

import earthMapUrl from "../../assets/earth/earth_atmos_2048.jpg";
import earthNormalUrl from "../../assets/earth/earth_normal_2048.jpg";
import earthSpecularUrl from "../../assets/earth/earth_specular_2048.jpg";
import earthCloudsUrl from "../../assets/earth/earth_clouds_1024.png";

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));
const loadTexture = (loader: THREE.TextureLoader, url: string) =>
  new Promise<THREE.Texture>((resolve, reject) => {
    loader.load(url, (texture) => resolve(texture), undefined, (err) => reject(err));
  });

const InteractiveSphere: React.FC = () => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [supported, setSupported] = useState(true);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let disposed = false;
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

    let earth: THREE.Mesh | null = null;
    let clouds: THREE.Mesh | null = null;
    let glow: THREE.Mesh | null = null;
    let earthGeometry: THREE.SphereGeometry | null = null;
    let cloudGeometry: THREE.SphereGeometry | null = null;
    let glowGeometry: THREE.SphereGeometry | null = null;
    let earthMaterial: THREE.MeshPhongMaterial | THREE.MeshStandardMaterial | null = null;
    let cloudMaterial: THREE.MeshStandardMaterial | null = null;
    let glowMaterial: THREE.MeshBasicMaterial | null = null;
    const textures: THREE.Texture[] = [];

    const buildFallbackEarth = () => {
      if (disposed) return;
      earthGeometry = new THREE.SphereGeometry(1, 64, 64);
      earthMaterial = new THREE.MeshStandardMaterial({
        color: new THREE.Color("#3b82f6"),
        metalness: 0.1,
        roughness: 0.4,
      });
      earth = new THREE.Mesh(earthGeometry, earthMaterial);
      scene.add(earth);

      glowGeometry = new THREE.SphereGeometry(1.07, 64, 64);
      glowMaterial = new THREE.MeshBasicMaterial({
        color: new THREE.Color("#7dd3fc"),
        transparent: true,
        opacity: 0.18,
        blending: THREE.AdditiveBlending,
        side: THREE.BackSide,
      });
      glow = new THREE.Mesh(glowGeometry, glowMaterial);
      scene.add(glow);
    };

    const init = async () => {
      try {
        const loader = new THREE.TextureLoader();
        const [earthMap, earthNormal, earthSpecular, earthClouds] = await Promise.all([
          loadTexture(loader, earthMapUrl),
          loadTexture(loader, earthNormalUrl),
          loadTexture(loader, earthSpecularUrl),
          loadTexture(loader, earthCloudsUrl),
        ]);

        textures.push(earthMap, earthNormal, earthSpecular, earthClouds);
        if (disposed) {
          textures.forEach((texture) => texture.dispose());
          return;
        }
        earthMap.colorSpace = THREE.SRGBColorSpace;
        earthClouds.colorSpace = THREE.SRGBColorSpace;

        earthGeometry = new THREE.SphereGeometry(1, 128, 128);
        earthMaterial = new THREE.MeshPhongMaterial({
          map: earthMap,
          normalMap: earthNormal,
          specularMap: earthSpecular,
          specular: new THREE.Color("#40547a"),
          shininess: 18,
        });
        earth = new THREE.Mesh(earthGeometry, earthMaterial);
        scene.add(earth);

        cloudGeometry = new THREE.SphereGeometry(1.01, 96, 96);
        cloudMaterial = new THREE.MeshStandardMaterial({
          map: earthClouds,
          transparent: true,
          opacity: 0.75,
          depthWrite: false,
        });
        clouds = new THREE.Mesh(cloudGeometry, cloudMaterial);
        scene.add(clouds);

        glowGeometry = new THREE.SphereGeometry(1.07, 64, 64);
        glowMaterial = new THREE.MeshBasicMaterial({
          color: new THREE.Color("#7dd3fc"),
          transparent: true,
          opacity: 0.22,
          blending: THREE.AdditiveBlending,
          side: THREE.BackSide,
        });
        glow = new THREE.Mesh(glowGeometry, glowMaterial);
        scene.add(glow);
      } catch {
        buildFallbackEarth();
      }
    };

    void init();

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
      if (earth) {
        earth.rotation.x += (state.targetX - earth.rotation.x) * 0.08;
        earth.rotation.y += (state.targetY - earth.rotation.y) * 0.08;
        if (clouds) {
          clouds.rotation.x = earth.rotation.x * 1.02;
          clouds.rotation.y = earth.rotation.y + 0.008;
        }
      }
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
      disposed = true;
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
      earthGeometry?.dispose();
      cloudGeometry?.dispose();
      glowGeometry?.dispose();
      earthMaterial?.dispose();
      cloudMaterial?.dispose();
      glowMaterial?.dispose();
      textures.forEach((texture) => texture.dispose());
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
