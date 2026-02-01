import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";

import earthDayMapUrl from "../../assets/space/earth_day_8k.jpg";
import earthNightMapUrl from "../../assets/space/earth_night_8k.jpg";
import starsMapUrl from "../../assets/space/stars_8k.jpg";
import earthNormalUrl from "../../assets/earth/earth_normal_2048.jpg";
import earthSpecularUrl from "../../assets/earth/earth_specular_2048.jpg";
import earthCloudsUrl from "../../assets/earth/earth_clouds_2048.png";

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));
const loadTexture = (loader: THREE.TextureLoader, url: string) =>
  new Promise<THREE.Texture>((resolve, reject) => {
    loader.load(url, (texture) => resolve(texture), undefined, (err) => reject(err));
  });

const createSunTexture = () => {
  const size = 512;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;
  const gradient = ctx.createRadialGradient(size * 0.5, size * 0.5, size * 0.12, size * 0.5, size * 0.5, size * 0.5);
  gradient.addColorStop(0, "#fff7c2");
  gradient.addColorStop(0.45, "#fbbf24");
  gradient.addColorStop(0.75, "#f97316");
  gradient.addColorStop(1, "#7c2d12");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  for (let i = 0; i < 1200; i += 1) {
    ctx.fillStyle = `rgba(255, 255, 255, ${Math.random() * 0.08})`;
    ctx.beginPath();
    ctx.arc(Math.random() * size, Math.random() * size, Math.random() * 6, 0, Math.PI * 2);
    ctx.fill();
  }
  return canvas;
};

const createPlanetTexture = (base: string, accent: string) => {
  const width = 512;
  const height = 256;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, width, height);
  for (let i = 0; i < 220; i += 1) {
    const radius = 8 + Math.random() * 28;
    ctx.fillStyle = accent;
    ctx.beginPath();
    ctx.arc(Math.random() * width, Math.random() * height, radius, 0, Math.PI * 2);
    ctx.fill();
  }
  const noise = ctx.getImageData(0, 0, width, height);
  for (let i = 0; i < noise.data.length; i += 4) {
    const n = (Math.random() - 0.5) * 16;
    noise.data[i] = clamp(noise.data[i] + n, 0, 255);
    noise.data[i + 1] = clamp(noise.data[i + 1] + n, 0, 255);
    noise.data[i + 2] = clamp(noise.data[i + 2] + n, 0, 255);
  }
  ctx.putImageData(noise, 0, 0);
  return canvas;
};

const PLANET_BUTTONS = [
  { key: "earth", label: "Earth" },
  { key: "moon", label: "Moon" },
  { key: "mars", label: "Mars" },
  { key: "venus", label: "Venus" },
  { key: "sun", label: "Sun" },
];

const InteractiveSphere: React.FC = () => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const targetsRef = useRef<Record<string, { object: THREE.Object3D; zoom: number }>>({});
  const focusHandlerRef = useRef<(key: string) => void>(() => {});
  const [supported, setSupported] = useState(true);
  const [activeTarget, setActiveTarget] = useState("earth");
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [loading, setLoading] = useState(true);
  const activeTargetRef = useRef(activeTarget);

  useEffect(() => {
    activeTargetRef.current = activeTarget;
  }, [activeTarget]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let disposed = false;
    let renderer: THREE.WebGLRenderer | null = null;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
    } catch {
      setSupported(false);
      return;
    }

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#05060f");
    scene.fog = new THREE.FogExp2(0x05060f, 0.04);

    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 200);
    camera.position.set(0, 0.7, 7.6);

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.6));
    renderer.setClearColor(0x05060f, 1);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1;
    renderer.domElement.style.display = "block";
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    container.appendChild(renderer.domElement);

    const textures: THREE.Texture[] = [];
    const geometries: THREE.BufferGeometry[] = [];
    const materials: THREE.Material[] = [];
    const pickables: THREE.Object3D[] = [];
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const tempVec = new THREE.Vector3();

    const earthGroup = new THREE.Group();
    scene.add(earthGroup);

    const sunLight = new THREE.DirectionalLight(0xffffff, 1.6);
    sunLight.position.set(9, 1.5, -2);
    scene.add(sunLight);
    scene.add(new THREE.AmbientLight(0xffffff, 0.18));

    let earthMesh: THREE.Mesh | null = null;
    let earthMaterial: THREE.MeshPhongMaterial | null = null;
    let cloudMesh: THREE.Mesh | null = null;
    let cloudMaterial: THREE.MeshStandardMaterial | null = null;
    let mapPlane: THREE.Mesh | null = null;
    let starSphere: THREE.Mesh | null = null;
    let moonOrbit: THREE.Group | null = null;
    const spinTargets: THREE.Object3D[] = [];

    const loadingManager = new THREE.LoadingManager();
    loadingManager.onProgress = (_url, loaded, total) => {
      if (!disposed) setLoadingProgress(total ? loaded / total : 0);
    };
    loadingManager.onLoad = () => {
      if (!disposed) setLoading(false);
    };
    const loader = new THREE.TextureLoader(loadingManager);

    const buildFallback = () => {
      if (disposed) return;
      const fallbackGeo = new THREE.SphereGeometry(1, 64, 64);
      const fallbackMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color("#3b82f6"),
        metalness: 0.1,
        roughness: 0.4,
      });
      const fallbackMesh = new THREE.Mesh(fallbackGeo, fallbackMat);
      earthGroup.add(fallbackMesh);
      geometries.push(fallbackGeo);
      materials.push(fallbackMat);
      targetsRef.current.earth = { object: fallbackMesh, zoom: 2.2 };
      pickables.push(fallbackMesh);
      if (!disposed) setLoading(false);
    };

    const init = async () => {
      try {
        const [earthDay, earthNight, stars, earthNormal, earthSpecular, earthClouds] = await Promise.all([
          loadTexture(loader, earthDayMapUrl),
          loadTexture(loader, earthNightMapUrl),
          loadTexture(loader, starsMapUrl),
          loadTexture(loader, earthNormalUrl),
          loadTexture(loader, earthSpecularUrl),
          loadTexture(loader, earthCloudsUrl),
        ]);

        textures.push(earthDay, earthNight, stars, earthNormal, earthSpecular, earthClouds);
        if (disposed) {
          textures.forEach((texture) => texture.dispose());
          return;
        }

        earthDay.colorSpace = THREE.SRGBColorSpace;
        earthNight.colorSpace = THREE.SRGBColorSpace;
        stars.colorSpace = THREE.SRGBColorSpace;
        earthClouds.colorSpace = THREE.SRGBColorSpace;

        const maxAniso = renderer?.capabilities.getMaxAnisotropy() ?? 1;
        [earthDay, earthNight, stars, earthNormal, earthSpecular, earthClouds].forEach((texture) => {
          texture.anisotropy = maxAniso;
        });

        const starGeo = new THREE.SphereGeometry(80, 64, 64);
        const starMat = new THREE.MeshBasicMaterial({ map: stars, side: THREE.BackSide });
        starSphere = new THREE.Mesh(starGeo, starMat);
        scene.add(starSphere);
        geometries.push(starGeo);
        materials.push(starMat);

        const sunTexture = new THREE.CanvasTexture(createSunTexture());
        sunTexture.colorSpace = THREE.SRGBColorSpace;
        sunTexture.anisotropy = maxAniso;
        textures.push(sunTexture);
        const sunGeo = new THREE.SphereGeometry(1.6, 64, 64);
        const sunMat = new THREE.MeshBasicMaterial({ map: sunTexture });
        const sunMesh = new THREE.Mesh(sunGeo, sunMat);
        sunMesh.position.copy(sunLight.position);
        sunMesh.userData.targetKey = "sun";
        scene.add(sunMesh);
        pickables.push(sunMesh);
        targetsRef.current.sun = { object: sunMesh, zoom: 3.8 };
        spinTargets.push(sunMesh);
        geometries.push(sunGeo);
        materials.push(sunMat);

        const sunGlowGeo = new THREE.SphereGeometry(2.4, 32, 32);
        const sunGlowMat = new THREE.MeshBasicMaterial({
          color: new THREE.Color("#fbbf24"),
          transparent: true,
          opacity: 0.35,
          blending: THREE.AdditiveBlending,
        });
        const sunGlow = new THREE.Mesh(sunGlowGeo, sunGlowMat);
        sunGlow.position.copy(sunLight.position);
        scene.add(sunGlow);
        geometries.push(sunGlowGeo);
        materials.push(sunGlowMat);

        const earthGeo = new THREE.SphereGeometry(1, 128, 128);
        earthMaterial = new THREE.MeshPhongMaterial({
          map: earthDay,
          normalMap: earthNormal,
          specularMap: earthSpecular,
          emissiveMap: earthNight,
          emissive: new THREE.Color("#ffffff"),
          emissiveIntensity: 1,
          shininess: 18,
          transparent: true,
          opacity: 1,
        });
        earthMaterial.onBeforeCompile = (shader) => {
          shader.uniforms.uSunDirection = { value: new THREE.Vector3(1, 0, 0) };
          shader.fragmentShader = shader.fragmentShader.replace(
            "#include <emissivemap_fragment>",
            [
              "#include <emissivemap_fragment>",
              "float lightStrength = max(dot(normalize(vNormal), normalize(uSunDirection)), 0.0);",
              "float nightMask = 1.0 - smoothstep(0.05, 0.35, lightStrength);",
              "totalEmissiveRadiance *= nightMask;",
            ].join("\n"),
          );
          if (earthMaterial) {
            earthMaterial.userData.shader = shader;
          }
        };
        earthMesh = new THREE.Mesh(earthGeo, earthMaterial);
        earthMesh.userData.targetKey = "earth";
        earthGroup.add(earthMesh);
        pickables.push(earthMesh);
        targetsRef.current.earth = { object: earthMesh, zoom: 2.4 };
        geometries.push(earthGeo);
        materials.push(earthMaterial);

        const cloudGeo = new THREE.SphereGeometry(1.01, 96, 96);
        cloudMaterial = new THREE.MeshStandardMaterial({
          map: earthClouds,
          transparent: true,
          opacity: 0.65,
          depthWrite: false,
        });
        cloudMesh = new THREE.Mesh(cloudGeo, cloudMaterial);
        earthGroup.add(cloudMesh);
        geometries.push(cloudGeo);
        materials.push(cloudMaterial);

        const atmosphereGeo = new THREE.SphereGeometry(1.07, 64, 64);
        const atmosphereMat = new THREE.MeshBasicMaterial({
          color: new THREE.Color("#7dd3fc"),
          transparent: true,
          opacity: 0.18,
          blending: THREE.AdditiveBlending,
          side: THREE.BackSide,
        });
        const atmosphere = new THREE.Mesh(atmosphereGeo, atmosphereMat);
        earthGroup.add(atmosphere);
        geometries.push(atmosphereGeo);
        materials.push(atmosphereMat);

        const mapGeo = new THREE.PlaneGeometry(2, 1);
        const mapMat = new THREE.MeshBasicMaterial({
          map: earthDay,
          transparent: true,
          opacity: 0,
          depthTest: false,
        });
        mapPlane = new THREE.Mesh(mapGeo, mapMat);
        mapPlane.position.z = -1.6;
        mapPlane.renderOrder = 5;
        camera.add(mapPlane);
        scene.add(camera);
        geometries.push(mapGeo);
        materials.push(mapMat);

        const moonTexture = new THREE.CanvasTexture(createPlanetTexture("#9ca3af", "#6b7280"));
        moonTexture.colorSpace = THREE.SRGBColorSpace;
        moonTexture.anisotropy = maxAniso;
        textures.push(moonTexture);
        const moonGeo = new THREE.SphereGeometry(0.27, 48, 48);
        const moonMat = new THREE.MeshStandardMaterial({ map: moonTexture, roughness: 0.9, metalness: 0.02 });
        moonOrbit = new THREE.Group();
        moonOrbit.position.set(0, 0, 0);
        const moonMesh = new THREE.Mesh(moonGeo, moonMat);
        moonMesh.position.set(2.1, 0.35, 0.4);
        moonMesh.userData.targetKey = "moon";
        moonOrbit.add(moonMesh);
        earthGroup.add(moonOrbit);
        pickables.push(moonMesh);
        targetsRef.current.moon = { object: moonMesh, zoom: 1.4 };
        geometries.push(moonGeo);
        materials.push(moonMat);

        const marsTexture = new THREE.CanvasTexture(createPlanetTexture("#b45309", "#7c2d12"));
        marsTexture.colorSpace = THREE.SRGBColorSpace;
        marsTexture.anisotropy = maxAniso;
        textures.push(marsTexture);
        const marsGeo = new THREE.SphereGeometry(0.53, 48, 48);
        const marsMat = new THREE.MeshStandardMaterial({ map: marsTexture, roughness: 0.8, metalness: 0.05 });
        const marsMesh = new THREE.Mesh(marsGeo, marsMat);
        marsMesh.position.set(5.6, -1.4, -4.4);
        marsMesh.userData.targetKey = "mars";
        scene.add(marsMesh);
        pickables.push(marsMesh);
        targetsRef.current.mars = { object: marsMesh, zoom: 2.2 };
        spinTargets.push(marsMesh);
        geometries.push(marsGeo);
        materials.push(marsMat);

        const venusTexture = new THREE.CanvasTexture(createPlanetTexture("#f59e0b", "#d97706"));
        venusTexture.colorSpace = THREE.SRGBColorSpace;
        venusTexture.anisotropy = maxAniso;
        textures.push(venusTexture);
        const venusGeo = new THREE.SphereGeometry(0.95, 64, 64);
        const venusMat = new THREE.MeshStandardMaterial({ map: venusTexture, roughness: 0.85, metalness: 0.03 });
        const venusMesh = new THREE.Mesh(venusGeo, venusMat);
        venusMesh.position.set(-4.6, 1.2, 4.8);
        venusMesh.userData.targetKey = "venus";
        scene.add(venusMesh);
        pickables.push(venusMesh);
        targetsRef.current.venus = { object: venusMesh, zoom: 2.6 };
        spinTargets.push(venusMesh);
        geometries.push(venusGeo);
        materials.push(venusMat);

        focusHandlerRef.current("earth");
      } catch {
        buildFallback();
      }
    };

    void init();

    const state = {
      isDragging: false,
      dragMoved: false,
      lastX: 0,
      lastY: 0,
      theta: 0.2,
      phi: 1.25,
      targetTheta: 0.2,
      targetPhi: 1.25,
      radius: 7.2,
      targetRadius: 7.2,
      focus: new THREE.Vector3(0, 0, 0),
      targetFocus: new THREE.Vector3(0, 0, 0),
    };

    focusHandlerRef.current = (key: string) => {
      const target = targetsRef.current[key];
      if (!target) return;
      target.object.getWorldPosition(state.targetFocus);
      state.targetRadius = target.zoom;
      setActiveTarget(key);
    };

    const setPointer = (event: PointerEvent) => {
      const rect = renderer?.domElement.getBoundingClientRect();
      if (!rect) return;
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    };

    const handlePointerDown = (event: PointerEvent) => {
      state.isDragging = true;
      state.dragMoved = false;
      state.lastX = event.clientX;
      state.lastY = event.clientY;
      (event.target as HTMLElement).setPointerCapture?.(event.pointerId);
    };

    const handlePointerMove = (event: PointerEvent) => {
      if (!state.isDragging) return;
      const dx = event.clientX - state.lastX;
      const dy = event.clientY - state.lastY;
      if (Math.abs(dx) + Math.abs(dy) > 2) state.dragMoved = true;
      state.lastX = event.clientX;
      state.lastY = event.clientY;
      state.targetTheta += dx * 0.0045;
      state.targetPhi += dy * 0.0045;
      state.targetPhi = clamp(state.targetPhi, 0.2, Math.PI - 0.2);
    };

    const handlePointerUp = (event: PointerEvent) => {
      state.isDragging = false;
      (event.target as HTMLElement).releasePointerCapture?.(event.pointerId);
      if (state.dragMoved) return;
      setPointer(event);
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(pickables, true);
      const hit = hits.find((item) => item.object.userData.targetKey);
      if (hit) {
        const key = hit.object.userData.targetKey as string;
        focusHandlerRef.current(key);
      }
    };

    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      state.targetRadius = clamp(state.targetRadius + event.deltaY * 0.01, 1.2, 18);
    };

    const handleDoubleClick = () => focusHandlerRef.current("earth");

    container.addEventListener("pointerdown", handlePointerDown);
    container.addEventListener("pointermove", handlePointerMove);
    container.addEventListener("pointerup", handlePointerUp);
    container.addEventListener("pointerleave", handlePointerUp);
    container.addEventListener("pointercancel", handlePointerUp);
    container.addEventListener("wheel", handleWheel, { passive: false });
    container.addEventListener("dblclick", handleDoubleClick);

    let frame = 0;
    const animate = () => {
      frame = window.requestAnimationFrame(animate);
      state.theta += (state.targetTheta - state.theta) * 0.08;
      state.phi += (state.targetPhi - state.phi) * 0.08;
      state.radius += (state.targetRadius - state.radius) * 0.08;
      state.focus.lerp(state.targetFocus, 0.08);

      const sinPhi = Math.sin(state.phi);
      camera.position.set(
        state.focus.x + state.radius * sinPhi * Math.sin(state.theta),
        state.focus.y + state.radius * Math.cos(state.phi),
        state.focus.z + state.radius * sinPhi * Math.cos(state.theta),
      );
      camera.lookAt(state.focus);

      if (earthMesh) {
        earthMesh.rotation.y += 0.0009;
        if (cloudMesh) cloudMesh.rotation.y += 0.0013;
      }
      if (moonOrbit) moonOrbit.rotation.y += 0.002;
      spinTargets.forEach((target) => {
        target.rotation.y += 0.0008;
      });
      if (starSphere) starSphere.rotation.y += 0.00008;

      if (earthMaterial?.userData.shader && earthMesh) {
        const sunDirection = new THREE.Vector3()
          .subVectors(sunLight.position, earthMesh.getWorldPosition(tempVec))
          .normalize();
        sunDirection.transformDirection(camera.matrixWorldInverse);
        earthMaterial.userData.shader.uniforms.uSunDirection.value.copy(sunDirection);
      }

      if (earthMesh && mapPlane && earthMaterial && cloudMaterial) {
        const earthDistance = camera.position.distanceTo(earthMesh.getWorldPosition(tempVec));
        const mapStart = 2.6;
        const mapEnd = 1.5;
        const mapT = activeTargetRef.current === "earth"
          ? clamp((mapStart - earthDistance) / (mapStart - mapEnd), 0, 1)
          : 0;
        const mapMat = mapPlane.material as THREE.MeshBasicMaterial;
        mapMat.opacity = mapT;
        earthMaterial.opacity = 1 - mapT * 0.7;
        cloudMaterial.opacity = 0.65 * (1 - mapT);
      }

      renderer?.render(scene, camera);
    };
    animate();

    const resize = () => {
      const { width, height } = container.getBoundingClientRect();
      if (!width || !height) return;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer?.setSize(width, height, false);
      if (mapPlane) {
        const distance = Math.abs(mapPlane.position.z);
        const vHeight = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov * 0.5)) * distance;
        const targetHeight = vHeight * 0.78;
        mapPlane.scale.set(targetHeight, targetHeight, 1);
      }
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
      container.removeEventListener("pointerup", handlePointerUp);
      container.removeEventListener("pointerleave", handlePointerUp);
      container.removeEventListener("pointercancel", handlePointerUp);
      container.removeEventListener("wheel", handleWheel);
      container.removeEventListener("dblclick", handleDoubleClick);
      geometries.forEach((geometry) => geometry.dispose());
      materials.forEach((material) => material.dispose());
      textures.forEach((texture) => texture.dispose());
      renderer?.dispose();
      if (renderer?.domElement && renderer.domElement.parentElement === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-sm font-semibold text-neutral-900">Interactive space</div>
          <div className="mt-1 text-xs text-neutral-500">
            Drag to orbit, scroll to zoom, click a planet to focus.
          </div>
        </div>
        <span className="rounded-full bg-neutral-100 px-3 py-1 text-[10px] font-semibold uppercase tracking-wide text-neutral-500">
          WebGL
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {PLANET_BUTTONS.map((planet) => (
          <button
            key={planet.key}
            type="button"
            onClick={() => focusHandlerRef.current(planet.key)}
            className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide transition ${
              activeTarget === planet.key
                ? "border-blue-500/60 bg-blue-50 text-blue-700"
                : "border-neutral-200 bg-white text-neutral-500 hover:border-neutral-300 hover:text-neutral-700"
            }`}
          >
            {planet.label}
          </button>
        ))}
      </div>
      {supported ? (
        <div
          ref={containerRef}
          className="relative mt-4 h-[360px] w-full cursor-grab overflow-hidden rounded-xl bg-black shadow-inner active:cursor-grabbing"
          style={{ touchAction: "none" }}
        >
          {loading ? (
            <div className="absolute inset-0 flex items-center justify-center bg-black/60 text-xs font-semibold uppercase tracking-widest text-white">
              Loading textures {Math.round(loadingProgress * 100)}%
            </div>
          ) : null}
        </div>
      ) : (
        <div className="mt-4 rounded-xl border border-dashed border-neutral-300 bg-neutral-50 px-4 py-10 text-center text-sm text-neutral-500">
          WebGL is unavailable in this browser.
        </div>
      )}
      <div className="mt-3 text-[10px] text-neutral-400">
        Textures from Solar System Scope (CC BY 4.0). Earth day/night maps and stars are 8k.
      </div>
    </div>
  );
};

export default InteractiveSphere;
