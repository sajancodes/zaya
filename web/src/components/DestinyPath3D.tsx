import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';

interface DestinyPath3DProps {
  currentSection?: string;
  scrollProgress?: number;
  interactive?: boolean;
}

export const DestinyPath3D: React.FC<DestinyPath3DProps> = ({
  interactive = true
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [webGLSupported, setWebGLSupported] = useState<boolean>(true);
  const mouseRef = useRef<{ x: number; y: number; targetX: number; targetY: number }>({
    x: 0,
    y: 0,
    targetX: 0,
    targetY: 0
  });

  useEffect(() => {
    // 1. Verify WebGL support
    try {
      const testCanvas = document.createElement('canvas');
      const gl = testCanvas.getContext('webgl') || testCanvas.getContext('experimental-webgl');
      if (!gl) {
        setWebGLSupported(false);
        return;
      }
    } catch {
      setWebGLSupported(false);
      return;
    }

    const container = containerRef.current;
    if (!container) return;

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // 2. Scene, Fog & Fixed Cinematic Camera
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x010409, 0.0035);

    const camera = new THREE.PerspectiveCamera(
      48,
      window.innerWidth / window.innerHeight,
      0.1,
      1500
    );
    // Fixed cinematic viewpoint: Framing Earth in the mid/left, Moon orbiting, and Saturn in the distance
    camera.position.set(0, 1.5, 34);

    // 3. High-Performance Renderer
    const renderer = new THREE.WebGLRenderer({
      powerPreference: 'high-performance',
      antialias: true,
      alpha: true
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x010409, 1.0);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.25;
    container.appendChild(renderer.domElement);

    // 4. Procedural High-Detail Planet Textures (Generated via Off-screen Canvas)

    // A. Real Earth Surface Map (1024x512)
    const earthCanvas = document.createElement('canvas');
    earthCanvas.width = 1024;
    earthCanvas.height = 512;
    const eCtx = earthCanvas.getContext('2d');
    if (eCtx) {
      // 1. Deep Ocean Base with realistic marine depth
      const oceanGrad = eCtx.createLinearGradient(0, 0, 0, 512);
      oceanGrad.addColorStop(0, '#10273f');
      oceanGrad.addColorStop(0.3, '#0b1d33');
      oceanGrad.addColorStop(0.5, '#081729');
      oceanGrad.addColorStop(0.7, '#0b1d33');
      oceanGrad.addColorStop(1, '#10273f');
      eCtx.fillStyle = oceanGrad;
      eCtx.fillRect(0, 0, 1024, 512);

      // 2. Continents: Real world landmass outlines with organic fractal borders
      eCtx.save();

      // Coastal Shallow Shelf Water (Turquoise Cyan)
      eCtx.strokeStyle = 'rgba(28, 128, 168, 0.5)';
      eCtx.lineWidth = 8;
      eCtx.lineJoin = 'round';

      const drawLandmass = (
        points: [number, number][],
        fillColor: string,
        strokeShelf: boolean = true
      ) => {
        if (points.length < 3) return;
        eCtx.beginPath();
        eCtx.moveTo(points[0][0], points[0][1]);
        for (let i = 1; i < points.length; i++) {
          eCtx.lineTo(points[i][0], points[i][1]);
        }
        eCtx.closePath();
        if (strokeShelf) eCtx.stroke();
        eCtx.fillStyle = fillColor;
        eCtx.fill();
      };

      // North America
      drawLandmass([
        [100, 75], [160, 65], [230, 80], [320, 85], [370, 110],
        [320, 135], [300, 180], [270, 220], [285, 255], [265, 275],
        [240, 275], [215, 305], [195, 270], [180, 230], [130, 190],
        [90, 140], [80, 95]
      ], '#2f4f2c');

      // Greenland (Ice cap)
      drawLandmass([
        [360, 50], [420, 45], [440, 75], [390, 105], [350, 80]
      ], '#eaf3f8');

      // South America
      drawLandmass([
        [285, 320], [330, 315], [380, 345], [405, 385], [385, 435],
        [350, 470], [315, 495], [310, 450], [290, 400], [275, 350]
      ], '#284626');

      // Europe
      drawLandmass([
        [490, 130], [535, 110], [570, 135], [540, 175], [500, 190],
        [475, 220], [460, 200], [470, 160]
      ], '#3b5832');

      // Scandinavia
      drawLandmass([
        [525, 75], [560, 70], [550, 125], [520, 120]
      ], '#344e2e');

      // Africa
      drawLandmass([
        [480, 230], [540, 215], [605, 230], [635, 275], [645, 335],
        [605, 395], [570, 450], [540, 420], [510, 350], [470, 320],
        [465, 270]
      ], '#736142'); // Sahara / Savannah ochre

      // Congo / Central Africa green basin
      drawLandmass([
        [515, 330], [565, 330], [580, 380], [545, 400], [520, 365]
      ], '#264222', false);

      // Asia
      drawLandmass([
        [580, 120], [670, 100], [770, 85], [880, 95], [925, 140],
        [880, 190], [820, 195], [835, 255], [770, 280], [730, 330],
        [690, 290], [650, 260], [600, 240]
      ], '#3d5634');

      // India
      drawLandmass([
        [680, 265], [725, 270], [705, 335], [680, 300]
      ], '#455e37');

      // Southeast Asia & Indonesia
      drawLandmass([
        [775, 305], [825, 310], [805, 360], [770, 340]
      ], '#224424');

      // Australia
      drawLandmass([
        [820, 390], [880, 385], [915, 420], [890, 470], [835, 465],
        [810, 425]
      ], '#886d47'); // Outback ochre

      // Antarctica (Immense Southern Ice Sheet)
      drawLandmass([
        [0, 485], [200, 475], [400, 480], [600, 470], [800, 480],
        [1024, 485], [1024, 512], [0, 512]
      ], '#f0f7fb');

      // Arctic Sea Ice Sheet
      drawLandmass([
        [0, 0], [1024, 0], [1024, 40], [750, 45], [500, 35],
        [250, 45], [0, 35]
      ], '#f0f7fb');

      // Mountain Ranges & Peaks (Snow / slate accents)
      eCtx.strokeStyle = 'rgba(235, 245, 255, 0.7)';
      eCtx.lineWidth = 3;
      // Himalayas
      eCtx.beginPath();
      eCtx.moveTo(710, 245);
      eCtx.lineTo(775, 240);
      eCtx.stroke();
      // Andes
      eCtx.beginPath();
      eCtx.moveTo(290, 330);
      eCtx.lineTo(315, 470);
      eCtx.stroke();
      // Rockies
      eCtx.beginPath();
      eCtx.moveTo(180, 120);
      eCtx.lineTo(220, 230);
      eCtx.stroke();

      eCtx.restore();
    }
    const earthTexture = new THREE.CanvasTexture(earthCanvas);

    // B. Earth Specular / Roughness Map (Oceans shiny, land matte)
    const specCanvas = document.createElement('canvas');
    specCanvas.width = 512;
    specCanvas.height = 256;
    const spCtx = specCanvas.getContext('2d');
    if (spCtx) {
      // Draw ocean black (roughness = 0 -> mirror specular reflection for sunlight)
      spCtx.fillStyle = '#000000';
      spCtx.fillRect(0, 0, 512, 256);
      // Copy landmasses as white (roughness = 1 -> diffuse land)
      spCtx.drawImage(earthCanvas, 0, 0, 512, 256);
      const imgData = spCtx.getImageData(0, 0, 512, 256);
      const d = imgData.data;
      for (let i = 0; i < d.length; i += 4) {
        // If not ocean blue, turn bright white for matte roughness
        const isOcean = d[i] < 25 && d[i + 1] < 45 && d[i + 2] > 40;
        const val = isOcean ? 15 : 230;
        d[i] = val;
        d[i + 1] = val;
        d[i + 2] = val;
      }
      spCtx.putImageData(imgData, 0, 0);
    }
    const earthRoughnessMap = new THREE.CanvasTexture(specCanvas);

    // C. Real Earth Clouds Layer (1024x512)
    const cloudCanvas = document.createElement('canvas');
    cloudCanvas.width = 1024;
    cloudCanvas.height = 512;
    const clCtx = cloudCanvas.getContext('2d');
    if (clCtx) {
      clCtx.clearRect(0, 0, 1024, 512);

      // Equatorial ITCZ Cloud Bands & Swirls
      for (let i = 0; i < 90; i++) {
        const x = Math.random() * 1024;
        const y = 220 + (Math.random() - 0.5) * 80;
        const r = 25 + Math.random() * 55;
        const grad = clCtx.createRadialGradient(x, y, 0, x, y, r);
        grad.addColorStop(0, 'rgba(255, 255, 255, 0.7)');
        grad.addColorStop(0.5, 'rgba(240, 248, 255, 0.4)');
        grad.addColorStop(1, 'rgba(255, 255, 255, 0)');
        clCtx.fillStyle = grad;
        clCtx.fillRect(x - r, y - r, r * 2, r * 2);
      }

      // Mid-Latitude Cyclonic Storm Swirls
      const stormCenters = [
        [280, 150], [680, 160], [850, 170],
        [320, 380], [620, 410], [820, 390]
      ];
      stormCenters.forEach(([sx, sy]) => {
        for (let a = 0; a < 6; a++) {
          const angle = (a / 6) * Math.PI * 2;
          const dist = 30 + a * 8;
          const cx = sx + Math.cos(angle) * dist;
          const cy = sy + Math.sin(angle) * (dist * 0.55);
          const r = 35 + Math.random() * 25;
          const grad = clCtx.createRadialGradient(cx, cy, 0, cx, cy, r);
          grad.addColorStop(0, 'rgba(255, 255, 255, 0.75)');
          grad.addColorStop(0.6, 'rgba(230, 245, 255, 0.35)');
          grad.addColorStop(1, 'rgba(255, 255, 255, 0)');
          clCtx.fillStyle = grad;
          clCtx.fillRect(cx - r, cy - r, r * 2, r * 2);
        }
      });
    }
    const earthCloudTexture = new THREE.CanvasTexture(cloudCanvas);

    // D. Real Moon Texture (512x256)
    const moonCanvas = document.createElement('canvas');
    moonCanvas.width = 512;
    moonCanvas.height = 256;
    const mCtx = moonCanvas.getContext('2d');
    if (mCtx) {
      mCtx.fillStyle = '#9aa0a6';
      mCtx.fillRect(0, 0, 512, 256);

      // Dark Basaltic Lunar Maria (Plains)
      const maria = [
        [150, 100, 50], [220, 90, 60], [280, 120, 45],
        [180, 150, 55], [350, 110, 40]
      ];
      maria.forEach(([x, y, r]) => {
        const grad = mCtx.createRadialGradient(x, y, 0, x, y, r);
        grad.addColorStop(0, 'rgba(70, 75, 82, 0.85)');
        grad.addColorStop(0.7, 'rgba(90, 95, 102, 0.6)');
        grad.addColorStop(1, 'rgba(154, 160, 166, 0)');
        mCtx.fillStyle = grad;
        mCtx.fillRect(x - r, y - r, r * 2, r * 2);
      });

      // Bright Impact Craters with Rays
      for (let i = 0; i < 40; i++) {
        const x = Math.random() * 512;
        const y = Math.random() * 256;
        const r = 4 + Math.random() * 12;
        mCtx.strokeStyle = 'rgba(240, 245, 250, 0.75)';
        mCtx.lineWidth = 1.5;
        mCtx.beginPath();
        mCtx.arc(x, y, r, 0, Math.PI * 2);
        mCtx.stroke();
      }
    }
    const moonTexture = new THREE.CanvasTexture(moonCanvas);

    // E. Real Saturn Banded Atmosphere Map (512x256)
    const saturnCanvas = document.createElement('canvas');
    saturnCanvas.width = 512;
    saturnCanvas.height = 256;
    const satCtx = saturnCanvas.getContext('2d');
    if (satCtx) {
      const grad = satCtx.createLinearGradient(0, 0, 0, 256);
      grad.addColorStop(0, '#5a4c38');
      grad.addColorStop(0.15, '#c8ad85');
      grad.addColorStop(0.3, '#dfc59e');
      grad.addColorStop(0.45, '#eed9b7');
      grad.addColorStop(0.5, '#f5e4cc');
      grad.addColorStop(0.55, '#eed9b7');
      grad.addColorStop(0.7, '#cbb28b');
      grad.addColorStop(0.85, '#9d8463');
      grad.addColorStop(1, '#534433');
      satCtx.fillStyle = grad;
      satCtx.fillRect(0, 0, 512, 256);

      // Fine atmospheric jet-stream streaks
      for (let y = 0; y < 256; y += 4) {
        satCtx.fillStyle = (y % 8 === 0) ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)';
        satCtx.fillRect(0, y, 512, 2);
      }
    }
    const saturnTexture = new THREE.CanvasTexture(saturnCanvas);

    // F. Saturn Ring Texture (512x64 with Cassini Division)
    const ringCanvas = document.createElement('canvas');
    ringCanvas.width = 512;
    ringCanvas.height = 64;
    const rCtx = ringCanvas.getContext('2d');
    if (rCtx) {
      const rGrad = rCtx.createLinearGradient(0, 0, 512, 0);
      rGrad.addColorStop(0, 'rgba(160, 135, 100, 0)');
      rGrad.addColorStop(0.12, 'rgba(180, 150, 115, 0.35)'); // C Ring (Crepe)
      rGrad.addColorStop(0.32, 'rgba(225, 195, 155, 0.95)'); // B Ring (Dense)
      rGrad.addColorStop(0.64, 'rgba(215, 185, 145, 0.85)'); // Inner edge Cassini
      rGrad.addColorStop(0.66, 'rgba(10, 8, 6, 0.03)');       // Cassini Division (Gap)
      rGrad.addColorStop(0.72, 'rgba(10, 8, 6, 0.03)');       // Cassini Division (Gap)
      rGrad.addColorStop(0.74, 'rgba(205, 175, 135, 0.8)');   // A Ring
      rGrad.addColorStop(0.96, 'rgba(175, 145, 110, 0.5)');   // Encke Gap region
      rGrad.addColorStop(1, 'rgba(140, 115, 85, 0)');
      rCtx.fillStyle = rGrad;
      rCtx.fillRect(0, 0, 512, 64);
    }
    const saturnRingTexture = new THREE.CanvasTexture(ringCanvas);

    // 5. Lighting Environment: Brilliant Directional Sunlight
    // Simulates the Sun illuminating one hemisphere of Earth and planets realistically
    const sunlight = new THREE.DirectionalLight(0xfff8ee, 2.4);
    sunlight.position.set(-45, 30, 35);
    scene.add(sunlight);

    // Soft galactic ambient light so shadow sides remain visible
    const deepSpaceAmbient = new THREE.AmbientLight(0x0a1628, 0.65);
    scene.add(deepSpaceAmbient);

    // Distant star highlight
    const distantGlow = new THREE.DirectionalLight(0x5feaff, 0.4);
    distantGlow.position.set(40, -20, -50);
    scene.add(distantGlow);

    // 6. Deep Space Realistic Starfield (3,200 Stars with Realistic Stellar Temperatures)
    const starCount = 3200;
    const starGeom = new THREE.BufferGeometry();
    const starPositions = new Float32Array(starCount * 3);
    const starColors = new Float32Array(starCount * 3);

    const starPalette = [
      new THREE.Color(0xffffff), // Class A (White)
      new THREE.Color(0xdbeafe), // Class B (Blue-white)
      new THREE.Color(0x93c5fd), // Class O (Deep blue)
      new THREE.Color(0xfef08a), // Class G (Yellow sun-like)
      new THREE.Color(0xfed7aa)  // Class K/M (Warm orange/red)
    ];

    for (let i = 0; i < starCount; i++) {
      const radius = 120 + Math.random() * 500;
      const theta = Math.random() * Math.PI * 2;
      const phi = (Math.random() - 0.5) * Math.PI;

      starPositions[i * 3] = radius * Math.cos(phi) * Math.sin(theta);
      starPositions[i * 3 + 1] = radius * Math.sin(phi);
      starPositions[i * 3 + 2] = radius * Math.cos(phi) * Math.cos(theta);

      const col = starPalette[Math.floor(Math.random() * starPalette.length)];
      starColors[i * 3] = col.r;
      starColors[i * 3 + 1] = col.g;
      starColors[i * 3 + 2] = col.b;
    }
    starGeom.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
    starGeom.setAttribute('color', new THREE.BufferAttribute(starColors, 3));

    // Star Glow Texture
    const dotCanvas = document.createElement('canvas');
    dotCanvas.width = 32;
    dotCanvas.height = 32;
    const dCtx = dotCanvas.getContext('2d');
    if (dCtx) {
      const grad = dCtx.createRadialGradient(16, 16, 0, 16, 16, 16);
      grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
      grad.addColorStop(0.3, 'rgba(240, 250, 255, 0.8)');
      grad.addColorStop(0.7, 'rgba(147, 197, 253, 0.25)');
      grad.addColorStop(1, 'rgba(1, 4, 9, 0)');
      dCtx.fillStyle = grad;
      dCtx.fillRect(0, 0, 32, 32);
    }
    const starDotTexture = new THREE.CanvasTexture(dotCanvas);

    const starMat = new THREE.PointsMaterial({
      size: 1.4,
      map: starDotTexture,
      vertexColors: true,
      transparent: true,
      opacity: 0.9,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const starField = new THREE.Points(starGeom, starMat);
    scene.add(starField);

    // 7. REAL EARTH SYSTEM (Earth Sphere + Clouds + Rayleigh Atmospheric Glow)
    const earthSystem = new THREE.Group();
    // Positioned gracefully in the left-center viewport, majestic and serene
    earthSystem.position.set(-11, -1.8, 4);
    // Real 23.5° axial tilt
    earthSystem.rotation.z = (23.5 * Math.PI) / 180;
    earthSystem.rotation.x = 0.15;

    // A. Earth Surface
    const earthRadius = 9.2;
    const earthGeom = new THREE.SphereGeometry(earthRadius, 64, 64);
    const earthMat = new THREE.MeshStandardMaterial({
      map: earthTexture,
      roughnessMap: earthRoughnessMap,
      roughness: 0.7,
      metalness: 0.15
    });
    const earthMesh = new THREE.Mesh(earthGeom, earthMat);
    earthSystem.add(earthMesh);

    // B. Real Earth Clouds Layer (Floating 0.15 units above surface, rotating independently)
    const cloudGeom = new THREE.SphereGeometry(earthRadius * 1.018, 64, 64);
    const cloudMat = new THREE.MeshStandardMaterial({
      map: earthCloudTexture,
      transparent: true,
      opacity: 0.82,
      blending: THREE.NormalBlending,
      roughness: 0.9
    });
    const earthCloudsMesh = new THREE.Mesh(cloudGeom, cloudMat);
    earthSystem.add(earthCloudsMesh);

    // C. Rayleigh Atmospheric Blue Rim Glow
    const atmoGeom = new THREE.SphereGeometry(earthRadius * 1.045, 64, 64);
    const atmoMat = new THREE.MeshBasicMaterial({
      color: 0x4db5ff,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending,
      transparent: true,
      opacity: 0.28
    });
    const earthAtmoMesh = new THREE.Mesh(atmoGeom, atmoMat);
    earthSystem.add(earthAtmoMesh);

    scene.add(earthSystem);

    // 8. REAL MOON (Orbiting Earth System)
    const moonOrbitGroup = new THREE.Group();
    moonOrbitGroup.position.copy(earthSystem.position);

    const moonGeom = new THREE.SphereGeometry(2.3, 36, 36);
    const moonMat = new THREE.MeshStandardMaterial({
      map: moonTexture,
      roughness: 0.85,
      metalness: 0.05
    });
    const moonMesh = new THREE.Mesh(moonGeom, moonMat);
    moonOrbitGroup.add(moonMesh);
    scene.add(moonOrbitGroup);

    // 9. REAL SATURN SYSTEM WITH CONCENTRIC RINGS
    const saturnSystem = new THREE.Group();
    saturnSystem.position.set(28, 14, -85);
    // Real 26.7° axial tilt
    saturnSystem.rotation.z = 0.44;
    saturnSystem.rotation.x = 0.28;

    const saturnRadius = 6.8;
    const saturnGeom = new THREE.SphereGeometry(saturnRadius, 48, 48);
    const saturnMat = new THREE.MeshStandardMaterial({
      map: saturnTexture,
      roughness: 0.75,
      metalness: 0.1
    });
    const saturnMesh = new THREE.Mesh(saturnGeom, saturnMat);
    saturnSystem.add(saturnMesh);

    // Saturn's Majestic Rings
    const saturnRingGeom = new THREE.RingGeometry(8.5, 17.5, 96);
    // Align ring to Saturn's equatorial plane
    const pos = saturnRingGeom.attributes.position;
    const v3 = new THREE.Vector3();
    for (let i = 0; i < pos.count; i++) {
      v3.fromBufferAttribute(pos, i);
      saturnRingGeom.attributes.uv.setXY(i, (v3.length() - 8.5) / 9.0, 0.5);
    }
    const saturnRingMat = new THREE.MeshStandardMaterial({
      map: saturnRingTexture,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.95,
      roughness: 0.6
    });
    const saturnRingMesh = new THREE.Mesh(saturnRingGeom, saturnRingMat);
    saturnRingMesh.rotation.x = Math.PI / 2;
    saturnSystem.add(saturnRingMesh);

    scene.add(saturnSystem);

    // 10. REAL MARS IN DISTANT ORBIT
    const marsGroup = new THREE.Group();
    marsGroup.position.set(-36, 17, -115);
    marsGroup.rotation.z = 0.44; // 25° tilt

    const marsGeom = new THREE.SphereGeometry(3.2, 32, 32);
    // Rust-red procedural canvas
    const marsCanvas = document.createElement('canvas');
    marsCanvas.width = 256;
    marsCanvas.height = 128;
    const marCtx = marsCanvas.getContext('2d');
    if (marCtx) {
      marCtx.fillStyle = '#b35432';
      marCtx.fillRect(0, 0, 256, 128);
      // Dark basalt patches (Syrtis Major)
      marCtx.fillStyle = '#5c2d1c';
      marCtx.beginPath();
      marCtx.arc(120, 64, 35, 0, Math.PI * 2);
      marCtx.fill();
      // White Polar Ice Cap
      marCtx.fillStyle = '#edf7fa';
      marCtx.beginPath();
      marCtx.arc(128, 6, 20, 0, Math.PI);
      marCtx.fill();
    }
    const marsMat = new THREE.MeshStandardMaterial({
      map: new THREE.CanvasTexture(marsCanvas),
      roughness: 0.8,
      metalness: 0.1
    });
    const marsMesh = new THREE.Mesh(marsGeom, marsMat);
    marsGroup.add(marsMesh);
    scene.add(marsGroup);

    // 11. Zaya's Cyan Orbital Destiny Trails (Uniting Real Astronomy with Zaya's Brand)
    // A delicate, high-precision cyan orbital ring curving around Earth into deep space
    const orbitCurvePoints: THREE.Vector3[] = [];
    const orbitRadius = 14.5;
    for (let i = 0; i <= 100; i++) {
      const angle = (i / 100) * Math.PI * 2;
      orbitCurvePoints.push(
        new THREE.Vector3(
          Math.cos(angle) * orbitRadius,
          Math.sin(angle) * (orbitRadius * 0.4),
          Math.sin(angle) * (orbitRadius * 0.7)
        )
      );
    }
    const orbitGeom = new THREE.BufferGeometry().setFromPoints(orbitCurvePoints);
    const orbitMat = new THREE.LineBasicMaterial({
      color: 0x5feaff,
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending
    });
    const orbitLine = new THREE.Line(orbitGeom, orbitMat);
    orbitLine.position.copy(earthSystem.position);
    orbitLine.rotation.x = 0.45;
    orbitLine.rotation.y = 0.3;
    scene.add(orbitLine);

    // Small luminous satellite traveling along this orbit
    const satMesh = new THREE.Mesh(
      new THREE.SphereGeometry(0.3, 16, 16),
      new THREE.MeshBasicMaterial({
        color: 0xebfcff,
        blending: THREE.AdditiveBlending
      })
    );
    scene.add(satMesh);

    // 12. Gentle Interactive Mouse Parallax (No Scroll Movement)
    const handleMouseMove = (e: MouseEvent) => {
      if (!interactive) return;
      const x = (e.clientX / window.innerWidth) * 2 - 1;
      const y = -(e.clientY / window.innerHeight) * 2 + 1;
      mouseRef.current.targetX = x;
      mouseRef.current.targetY = y;
    };
    window.addEventListener('mousemove', handleMouseMove, { passive: true });

    const handleResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    };
    window.addEventListener('resize', handleResize);

    // 13. Main Real-Time Celestial Revolution Loop
    let animId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);

      if (document.hidden) return;

      const elapsed = clock.getElapsedTime();

      // Smooth mouse parallax (Gentle and restrained, fixed perspective)
      mouseRef.current.x += (mouseRef.current.targetX - mouseRef.current.x) * 0.035;
      mouseRef.current.y += (mouseRef.current.targetY - mouseRef.current.y) * 0.035;

      // Camera position remains fixed in place with serene mouse tilt
      camera.position.x = mouseRef.current.x * 1.4;
      camera.position.y = 1.5 + mouseRef.current.y * 1.0;
      camera.lookAt(0, 0.5, 0);

      if (!prefersReducedMotion) {
        // Deep stars slow cosmic rotation
        starField.rotation.y = elapsed * 0.0006;

        // 1. REAL EARTH AXIAL REVOLUTION
        // Earth spins continuously on its axis
        earthMesh.rotation.y = elapsed * 0.018;

        // Earth Clouds rotate independently (different speed, atmospheric motion)
        earthCloudsMesh.rotation.y = elapsed * 0.023;

        // 2. REAL MOON ORBIT AROUND EARTH
        // Moon revolves around Earth at realistic distance
        const moonSpeed = 0.035;
        const moonDist = 26;
        moonMesh.position.set(
          Math.cos(elapsed * moonSpeed) * moonDist,
          Math.sin(elapsed * moonSpeed) * (moonDist * 0.25) + 1.2,
          Math.sin(elapsed * moonSpeed) * (moonDist * 0.65)
        );
        moonMesh.rotation.y = elapsed * 0.015;

        // 3. REAL SATURN AXIAL ROTATION & REVOLUTION
        saturnMesh.rotation.y = elapsed * 0.022;
        saturnRingMesh.rotation.z = elapsed * 0.005;

        // 4. REAL MARS ROTATION
        marsMesh.rotation.y = elapsed * 0.016;

        // 5. ZAYA ORBITAL SATELLITE
        const satAngle = elapsed * 0.25;
        satMesh.position.set(
          earthSystem.position.x + Math.cos(satAngle) * orbitRadius,
          earthSystem.position.y + Math.sin(satAngle) * (orbitRadius * 0.4),
          earthSystem.position.z + Math.sin(satAngle) * (orbitRadius * 0.7)
        );
      }

      renderer.render(scene, camera);
    };

    animate();

    // 14. Cleanup
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', handleResize);
      if (container && renderer.domElement) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
      starGeom.dispose();
      starMat.dispose();
      starDotTexture.dispose();
      earthGeom.dispose();
      earthMat.dispose();
      earthTexture.dispose();
      earthRoughnessMap.dispose();
      cloudGeom.dispose();
      cloudMat.dispose();
      earthCloudTexture.dispose();
      atmoGeom.dispose();
      atmoMat.dispose();
      moonGeom.dispose();
      moonMat.dispose();
      moonTexture.dispose();
      saturnGeom.dispose();
      saturnMat.dispose();
      saturnTexture.dispose();
      saturnRingGeom.dispose();
      saturnRingMat.dispose();
      saturnRingTexture.dispose();
      marsGeom.dispose();
      marsMat.dispose();
      orbitGeom.dispose();
      orbitMat.dispose();
    };
  }, [interactive]);

  if (!webGLSupported) {
    return (
      <div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100vh',
          zIndex: 0,
          background: 'radial-gradient(circle at 60% 40%, #041321 0%, #010409 90%)',
          pointerEvents: 'none'
        }}
      />
    );
  }

  return (
    <div
      ref={containerRef}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        zIndex: 0,
        pointerEvents: 'none',
        overflow: 'hidden'
      }}
    />
  );
};