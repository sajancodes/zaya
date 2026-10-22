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
  const scrollRef = useRef<number>(0);
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

    // 2. Scene, Fog & Perspective Camera
    const scene = new THREE.Scene();
    // Deep cosmic fog blending to void black / deep space midnight
    scene.fog = new THREE.FogExp2(0x010409, 0.008);

    const camera = new THREE.PerspectiveCamera(
      54,
      window.innerWidth / window.innerHeight,
      0.1,
      1200
    );
    // Initial hero camera position framing the cosmic highway
    camera.position.set(0, 0.8, 30);

    // 3. Renderer Setup
    const renderer = new THREE.WebGLRenderer({
      powerPreference: 'high-performance',
      antialias: true,
      alpha: true
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x010409, 1.0);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    container.appendChild(renderer.domElement);

    // 4. Procedural Textures (Generated via Off-screen Canvas)
    // Texture A: Star Particle Texture
    const starCanvas = document.createElement('canvas');
    starCanvas.width = 64;
    starCanvas.height = 64;
    const sCtx = starCanvas.getContext('2d');
    if (sCtx) {
      const grad = sCtx.createRadialGradient(32, 32, 0, 32, 32, 32);
      grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
      grad.addColorStop(0.2, 'rgba(235, 252, 255, 0.9)');
      grad.addColorStop(0.5, 'rgba(95, 234, 255, 0.4)');
      grad.addColorStop(0.8, 'rgba(64, 136, 255, 0.1)');
      grad.addColorStop(1, 'rgba(1, 4, 9, 0)');
      sCtx.fillStyle = grad;
      sCtx.fillRect(0, 0, 64, 64);
    }
    const starTexture = new THREE.CanvasTexture(starCanvas);

    // Texture B: Volumetric Dark Cosmic Nebula Cloud Puff Texture
    const cloudCanvas = document.createElement('canvas');
    cloudCanvas.width = 256;
    cloudCanvas.height = 256;
    const cCtx = cloudCanvas.getContext('2d');
    if (cCtx) {
      const grad = cCtx.createRadialGradient(128, 128, 0, 128, 128, 128);
      grad.addColorStop(0, 'rgba(4, 19, 33, 0.85)');
      grad.addColorStop(0.35, 'rgba(3, 12, 22, 0.7)');
      grad.addColorStop(0.65, 'rgba(64, 136, 255, 0.25)');
      grad.addColorStop(0.85, 'rgba(95, 234, 255, 0.15)');
      grad.addColorStop(1, 'rgba(1, 4, 9, 0)');
      cCtx.fillStyle = grad;
      cCtx.fillRect(0, 0, 256, 256);
    }
    const cloudTexture = new THREE.CanvasTexture(cloudCanvas);

    // Texture C: Vertical Light Beam Gradient
    const beamCanvas = document.createElement('canvas');
    beamCanvas.width = 64;
    beamCanvas.height = 256;
    const bCtx = beamCanvas.getContext('2d');
    if (bCtx) {
      const grad = bCtx.createLinearGradient(0, 0, 0, 256);
      grad.addColorStop(0, 'rgba(235, 252, 255, 0.95)');
      grad.addColorStop(0.2, 'rgba(95, 234, 255, 0.7)');
      grad.addColorStop(0.7, 'rgba(64, 136, 255, 0.25)');
      grad.addColorStop(1, 'rgba(1, 4, 9, 0)');
      bCtx.fillStyle = grad;
      bCtx.fillRect(0, 0, 64, 256);
    }
    const beamTexture = new THREE.CanvasTexture(beamCanvas);

    // 5. Cosmic Lighting Environment
    const ambientLight = new THREE.AmbientLight(0x041321, 0.8);
    scene.add(ambientLight);

    const directionalRim = new THREE.DirectionalLight(0xebfcff, 1.5);
    directionalRim.position.set(-30, 40, 20);
    scene.add(directionalRim);

    // Radiant Sun Orb Light at Upper Right
    const sunOrbLight = new THREE.PointLight(0x5feaff, 4.0, 400);
    sunOrbLight.position.set(26, 13, -92);
    scene.add(sunOrbLight);

    // Foreground Planet Cyan Specular Light
    const fgPlanetLight = new THREE.PointLight(0x4088ff, 1.8, 80);
    fgPlanetLight.position.set(-18, -4, 18);
    scene.add(fgPlanetLight);

    // 6. Volumetric Dark Cosmic Nebula Clouds (Bottom and Sides Framing)
    const nebulaGroup = new THREE.Group();
    const cloudMaterial = new THREE.SpriteMaterial({
      map: cloudTexture,
      transparent: true,
      opacity: 0.55,
      blending: THREE.NormalBlending,
      depthWrite: false
    });

    const cloudCount = window.innerWidth < 768 ? 26 : 48;
    const cloudSprites: { sprite: THREE.Sprite; rotSpeed: number; baseScale: number }[] = [];

    for (let i = 0; i < cloudCount; i++) {
      const sprite = new THREE.Sprite(cloudMaterial);
      // Position primarily in lower half, flanks, and receding depth
      const side = Math.random() < 0.5 ? -1 : 1;
      const x = (Math.random() * 35 + 8) * side;
      const y = -14 - Math.random() * 22;
      const z = 20 - Math.random() * 180;
      sprite.position.set(x, y, z);

      const baseScale = 25 + Math.random() * 35;
      sprite.scale.set(baseScale, baseScale, 1);

      nebulaGroup.add(sprite);
      cloudSprites.push({
        sprite,
        rotSpeed: (Math.random() - 0.5) * 0.0003,
        baseScale
      });
    }
    scene.add(nebulaGroup);

    // 7. Realistic Multi-Layer Starfield
    const starCount = 1800;
    const starGeom = new THREE.BufferGeometry();
    const starPositions = new Float32Array(starCount * 3);
    const starColors = new Float32Array(starCount * 3);

    const starPalette = [
      new THREE.Color(0xffffff),
      new THREE.Color(0xebfcff),
      new THREE.Color(0x80cfff),
      new THREE.Color(0x5feaff),
      new THREE.Color(0xa5b4fc)
    ];

    for (let i = 0; i < starCount; i++) {
      const radius = 90 + Math.random() * 320;
      const theta = Math.random() * Math.PI * 2;
      const phi = (Math.random() - 0.5) * Math.PI * 0.95;

      starPositions[i * 3] = radius * Math.cos(phi) * Math.sin(theta);
      starPositions[i * 3 + 1] = radius * Math.sin(phi);
      starPositions[i * 3 + 2] = -30 - Math.random() * 320;

      const col = starPalette[Math.floor(Math.random() * starPalette.length)];
      starColors[i * 3] = col.r;
      starColors[i * 3 + 1] = col.g;
      starColors[i * 3 + 2] = col.b;
    }
    starGeom.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
    starGeom.setAttribute('color', new THREE.BufferAttribute(starColors, 3));

    const starMat = new THREE.PointsMaterial({
      size: 1.5,
      map: starTexture,
      vertexColors: true,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const starField = new THREE.Points(starGeom, starMat);
    scene.add(starField);

    // 8. The Destiny Highway Spline (Curving from lower-left to upper-right sun orb)
    const curveControlPoints = [
      new THREE.Vector3(-22, -6, 25),    // Lower-left foreground (near foreground planet)
      new THREE.Vector3(-12, -2, 10),    // Ascending mid-ground
      new THREE.Vector3(-2, 1, -8),      // Milestone 1 (Voice)
      new THREE.Vector3(7, 4, -28),      // Milestone 2 (Vision & Memory)
      new THREE.Vector3(15, 7, -50),     // Milestone 3 (Autonomy & Hands)
      new THREE.Vector3(22, 10, -72),    // Milestone 4 (Spatial & Phone)
      new THREE.Vector3(26, 12.8, -92),  // Approaching radiant celestial sun orb
      new THREE.Vector3(28, 14.5, -125)  // Trailing into the infinite cosmos
    ];

    const destinyCurve = new THREE.CatmullRomCurve3(curveControlPoints);
    destinyCurve.curveType = 'catmullrom';
    destinyCurve.tension = 0.45;

    const pathSamples = 600;
    const curvePoints = destinyCurve.getPoints(pathSamples);

    // Multi-strand luminous lines
    const mainLineGeom = new THREE.BufferGeometry().setFromPoints(curvePoints);
    
    // Core Bright Line
    const coreLineMat = new THREE.LineBasicMaterial({
      color: 0xebfcff,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending
    });
    const coreLine = new THREE.Line(mainLineGeom, coreLineMat);
    scene.add(coreLine);

    // Cyan Glow Outer Line
    const glowLineMat = new THREE.LineBasicMaterial({
      color: 0x5feaff,
      transparent: true,
      opacity: 0.6,
      blending: THREE.AdditiveBlending
    });
    const glowLine = new THREE.Line(mainLineGeom, glowLineMat);
    glowLine.position.y -= 0.15;
    scene.add(glowLine);

    // Parallel Companion Strands (Offset tracks)
    const strandCount = 4;
    const strandLines: THREE.Line[] = [];
    const strandOffsets = [
      { x: -0.4, y: 0.2, c: 0x80cfff },
      { x: 0.4, y: -0.2, c: 0x5feaff },
      { x: -0.7, y: -0.3, c: 0x4088ff },
      { x: 0.7, y: 0.3, c: 0x4088ff }
    ];

    strandOffsets.forEach((off) => {
      const strandPoints = curvePoints.map((pt) =>
        new THREE.Vector3(pt.x + off.x, pt.y + off.y, pt.z)
      );
      const sGeom = new THREE.BufferGeometry().setFromPoints(strandPoints);
      const sMat = new THREE.LineBasicMaterial({
        color: off.c,
        transparent: true,
        opacity: 0.35,
        blending: THREE.AdditiveBlending
      });
      const sLine = new THREE.Line(sGeom, sMat);
      scene.add(sLine);
      strandLines.push(sLine);
    });

    // Sweeping Celestial Echo Arcs (Concentric curved rings framing the horizon)
    const echoArcsGroup = new THREE.Group();
    const arcRadius = [28, 42, 60];
    arcRadius.forEach((r, idx) => {
      const arcGeom = new THREE.BufferGeometry();
      const aPoints: THREE.Vector3[] = [];
      const numSegments = 60;
      for (let s = 0; s <= numSegments; s++) {
        const angle = -Math.PI * 0.25 + (s / numSegments) * Math.PI * 0.7;
        aPoints.push(new THREE.Vector3(
          Math.cos(angle) * r + 10,
          Math.sin(angle) * (r * 0.4) - 2,
          -40 - idx * 25
        ));
      }
      arcGeom.setFromPoints(aPoints);
      const aMat = new THREE.LineBasicMaterial({
        color: 0x5feaff,
        transparent: true,
        opacity: 0.18 - idx * 0.04,
        blending: THREE.AdditiveBlending
      });
      const aLine = new THREE.Line(arcGeom, aMat);
      echoArcsGroup.add(aLine);
    });
    scene.add(echoArcsGroup);

    // 9. Dense Streaming Particle Flow (River of Light — 1,600 Particles)
    const streamParticleCount = window.innerWidth < 768 ? 700 : 1600;
    const streamGeom = new THREE.BufferGeometry();
    const streamPositions = new Float32Array(streamParticleCount * 3);
    const streamColors = new Float32Array(streamParticleCount * 3);
    const particleProgress: Float32Array = new Float32Array(streamParticleCount);
    const particleSpeeds: Float32Array = new Float32Array(streamParticleCount);
    const particleOffsetsX: Float32Array = new Float32Array(streamParticleCount);
    const particleOffsetsY: Float32Array = new Float32Array(streamParticleCount);

    for (let i = 0; i < streamParticleCount; i++) {
      particleProgress[i] = Math.random();
      particleSpeeds[i] = 0.0006 + Math.random() * 0.0014;
      particleOffsetsX[i] = (Math.random() - 0.5) * 1.8;
      particleOffsetsY[i] = (Math.random() - 0.5) * 1.2;

      const pt = destinyCurve.getPointAt(particleProgress[i]);
      streamPositions[i * 3] = pt.x + particleOffsetsX[i];
      streamPositions[i * 3 + 1] = pt.y + particleOffsetsY[i];
      streamPositions[i * 3 + 2] = pt.z;

      const cRand = Math.random();
      const col = cRand > 0.6 ? starPalette[1] : cRand > 0.2 ? starPalette[3] : starPalette[2];
      streamColors[i * 3] = col.r;
      streamColors[i * 3 + 1] = col.g;
      streamColors[i * 3 + 2] = col.b;
    }
    streamGeom.setAttribute('position', new THREE.BufferAttribute(streamPositions, 3));
    streamGeom.setAttribute('color', new THREE.BufferAttribute(streamColors, 3));

    const streamMat = new THREE.PointsMaterial({
      size: 1.6,
      map: starTexture,
      vertexColors: true,
      transparent: true,
      opacity: 0.9,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const streamParticles = new THREE.Points(streamGeom, streamMat);
    scene.add(streamParticles);

    // 10. Foreground Planet (Lower-Left Obsidian/Ice Celestial Sphere with Orbital Arcs)
    const fgPlanetGroup = new THREE.Group();
    fgPlanetGroup.position.set(-17, -4.5, 12);

    const fgSphereGeom = new THREE.SphereGeometry(6.8, 48, 48);
    const fgSphereMat = new THREE.MeshStandardMaterial({
      color: 0x081a2b,
      metalness: 0.85,
      roughness: 0.25,
      emissive: 0x02101e,
      emissiveIntensity: 0.5
    });
    const fgSphereMesh = new THREE.Mesh(fgSphereGeom, fgSphereMat);
    fgPlanetGroup.add(fgSphereMesh);

    // Atmospheric rim glow
    const fgAtmoMesh = new THREE.Mesh(
      new THREE.SphereGeometry(7.2, 48, 48),
      new THREE.MeshBasicMaterial({
        color: 0x5feaff,
        transparent: true,
        opacity: 0.2,
        side: THREE.BackSide,
        blending: THREE.AdditiveBlending
      })
    );
    fgPlanetGroup.add(fgAtmoMesh);

    // Concentric glowing orbital latitude/longitude rings
    const fgRings: THREE.Mesh[] = [];
    const ringRadii = [8.8, 9.8, 11.2];
    ringRadii.forEach((r, idx) => {
      const ringMesh = new THREE.Mesh(
        new THREE.TorusGeometry(r, 0.06, 16, 96),
        new THREE.MeshBasicMaterial({
          color: idx === 1 ? 0xebfcff : 0x5feaff,
          transparent: true,
          opacity: 0.7 - idx * 0.15,
          blending: THREE.AdditiveBlending
        })
      );
      ringMesh.rotation.x = 0.5 + idx * 0.4;
      ringMesh.rotation.y = 0.3 - idx * 0.3;
      fgPlanetGroup.add(ringMesh);
      fgRings.push(ringMesh);
    });

    // Orbiting moon satellite
    const fgMoonPivot = new THREE.Group();
    fgPlanetGroup.add(fgMoonPivot);
    const fgMoonMesh = new THREE.Mesh(
      new THREE.SphereGeometry(0.85, 24, 24),
      new THREE.MeshStandardMaterial({
        color: 0x80cfff,
        roughness: 0.5,
        emissive: 0x4088ff,
        emissiveIntensity: 0.4
      })
    );
    fgMoonMesh.position.set(13.5, 1.5, 0);
    fgMoonPivot.add(fgMoonMesh);

    scene.add(fgPlanetGroup);

    // 11. Brilliant Radiant Sun Orb (Upper Right Destination with Gyroscopic Rings)
    const sunOrbGroup = new THREE.Group();
    sunOrbGroup.position.set(26, 12.8, -92);

    // Luminous Sun Core
    const sunCoreMesh = new THREE.Mesh(
      new THREE.SphereGeometry(5.2, 36, 36),
      new THREE.MeshBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.95,
        blending: THREE.AdditiveBlending
      })
    );
    sunOrbGroup.add(sunCoreMesh);

    // Radiant Corona Flare
    const sunCoronaMesh = new THREE.Mesh(
      new THREE.SphereGeometry(8.5, 36, 36),
      new THREE.MeshBasicMaterial({
        color: 0x5feaff,
        transparent: true,
        opacity: 0.35,
        blending: THREE.AdditiveBlending
      })
    );
    sunOrbGroup.add(sunCoronaMesh);

    // Outer Aura
    const sunAuraMesh = new THREE.Mesh(
      new THREE.SphereGeometry(14.0, 32, 32),
      new THREE.MeshBasicMaterial({
        color: 0x4088ff,
        transparent: true,
        opacity: 0.12,
        blending: THREE.AdditiveBlending
      })
    );
    sunOrbGroup.add(sunAuraMesh);

    // Concentric Gyroscopic Celestial Light Rings
    const sunRings: THREE.Mesh[] = [];
    const sunRingRadii = [8.5, 11.5, 15.0, 19.0];
    sunRingRadii.forEach((r, idx) => {
      const ringMesh = new THREE.Mesh(
        new THREE.RingGeometry(r, r + 0.3, 64),
        new THREE.MeshBasicMaterial({
          color: idx % 2 === 0 ? 0xebfcff : 0x5feaff,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0.6 - idx * 0.1,
          blending: THREE.AdditiveBlending
        })
      );
      ringMesh.rotation.x = Math.PI * 0.38 + idx * 0.15;
      ringMesh.rotation.y = idx * 0.25;
      sunOrbGroup.add(ringMesh);
      sunRings.push(ringMesh);
    });

    scene.add(sunOrbGroup);

    // 12. Milestone Planets Spaced Along the Destiny Highway
    const milestonePlanets: {
      group: THREE.Group;
      sphere: THREE.Mesh;
      ring: THREE.Mesh;
      pillar: THREE.Mesh;
      satellitePivot: THREE.Group;
      baseY: number;
      u: number;
    }[] = [];

    const milestoneConfig = [
      { u: 0.22, radius: 1.8, color: 0x092036, emissive: 0x03182b, ringR: 2.8 },
      { u: 0.44, radius: 2.3, color: 0x0c253d, emissive: 0x042038, ringR: 3.5 },
      { u: 0.66, radius: 2.1, color: 0x092036, emissive: 0x03182b, ringR: 3.2 },
      { u: 0.84, radius: 2.6, color: 0x0e2c48, emissive: 0x052844, ringR: 4.0 }
    ];

    milestoneConfig.forEach((cfg) => {
      const pt = destinyCurve.getPointAt(cfg.u);
      const group = new THREE.Group();
      group.position.copy(pt);

      // Dark Glossy Sphere
      const sphereGeom = new THREE.SphereGeometry(cfg.radius, 32, 32);
      const sphereMat = new THREE.MeshStandardMaterial({
        color: cfg.color,
        roughness: 0.3,
        metalness: 0.8,
        emissive: cfg.emissive,
        emissiveIntensity: 0.4
      });
      const sphere = new THREE.Mesh(sphereGeom, sphereMat);
      group.add(sphere);

      // Atmospheric Rim
      const atmo = new THREE.Mesh(
        new THREE.SphereGeometry(cfg.radius * 1.08, 32, 32),
        new THREE.MeshBasicMaterial({
          color: 0x5feaff,
          transparent: true,
          opacity: 0.25,
          side: THREE.BackSide,
          blending: THREE.AdditiveBlending
        })
      );
      group.add(atmo);

      // Equatorial Glowing Orbital Ring
      const ringGeom = new THREE.RingGeometry(cfg.ringR * 0.9, cfg.ringR * 1.08, 36);
      const ringMat = new THREE.MeshBasicMaterial({
        color: 0x5feaff,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.65,
        blending: THREE.AdditiveBlending
      });
      const ring = new THREE.Mesh(ringGeom, ringMat);
      ring.rotation.x = Math.PI * 0.45;
      group.add(ring);

      // Vertical Beacon Light Pillar (Dropping downward from planet into nebula clouds)
      const pillarGeom = new THREE.PlaneGeometry(0.5, 24);
      const pillarMat = new THREE.MeshBasicMaterial({
        map: beamTexture,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.6,
        blending: THREE.AdditiveBlending,
        depthWrite: false
      });
      const pillar = new THREE.Mesh(pillarGeom, pillarMat);
      pillar.position.y = -12;
      group.add(pillar);

      // Cross plane for 3D volumetric beacon appearance
      const pillarCross = new THREE.Mesh(pillarGeom, pillarMat);
      pillarCross.position.y = -12;
      pillarCross.rotation.y = Math.PI / 2;
      group.add(pillarCross);

      // Tiny Orbiting Satellite
      const satellitePivot = new THREE.Group();
      group.add(satellitePivot);
      const satMesh = new THREE.Mesh(
        new THREE.SphereGeometry(0.35, 16, 16),
        new THREE.MeshBasicMaterial({
          color: 0xebfcff,
          transparent: true,
          opacity: 0.9,
          blending: THREE.AdditiveBlending
        })
      );
      satMesh.position.set(cfg.ringR * 1.25, 0, 0);
      satellitePivot.add(satMesh);

      scene.add(group);
      milestonePlanets.push({
        group,
        sphere,
        ring,
        pillar,
        satellitePivot,
        baseY: pt.y,
        u: cfg.u
      });
    });

    // 13. Event Listeners for Smooth Scroll & Mouse Parallax
    const handleScroll = () => {
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
      const progress = maxScroll > 0 ? window.scrollY / maxScroll : 0;
      scrollRef.current = progress;
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

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

    // 14. Main Animation & Orbit Render Loop
    let animId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);

      if (document.hidden) return;

      const delta = clock.getDelta();
      const elapsed = clock.getElapsedTime();

      // Smooth mouse parallax lerp
      mouseRef.current.x += (mouseRef.current.targetX - mouseRef.current.x) * 0.05;
      mouseRef.current.y += (mouseRef.current.targetY - mouseRef.current.y) * 0.05;

      const scroll = scrollRef.current;

      // ── FLUID SCROLL-DRIVEN CAMERA FLIGHT ─────────────────────────────────
      // When scrolling down, camera glides forward through the cosmic highway,
      // weaving past the foreground planet, between the milestone planets,
      // and up toward the radiant celestial sun orb.
      const startCam = new THREE.Vector3(0, 0.8, 30);
      const midCam = new THREE.Vector3(12, 6.5, -30);
      const endCam = new THREE.Vector3(25, 12.0, -82);

      let targetCamX: number;
      let targetCamY: number;
      let targetCamZ: number;

      if (scroll < 0.5) {
        const t = scroll * 2;
        targetCamX = THREE.MathUtils.lerp(startCam.x, midCam.x, t);
        targetCamY = THREE.MathUtils.lerp(startCam.y, midCam.y, t);
        targetCamZ = THREE.MathUtils.lerp(startCam.z, midCam.z, t);
      } else {
        const t = (scroll - 0.5) * 2;
        targetCamX = THREE.MathUtils.lerp(midCam.x, endCam.x, t);
        targetCamY = THREE.MathUtils.lerp(midCam.y, endCam.y, t);
        targetCamZ = THREE.MathUtils.lerp(midCam.z, endCam.z, t);
      }

      // Add gentle mouse parallax
      targetCamX += mouseRef.current.x * 2.2;
      targetCamY += mouseRef.current.y * 1.5;

      camera.position.x += (targetCamX - camera.position.x) * 0.07;
      camera.position.y += (targetCamY - camera.position.y) * 0.07;
      camera.position.z += (targetCamZ - camera.position.z) * 0.07;

      // Dynamic lookAt point tracking forward along the destiny highway
      const lookAheadZ = camera.position.z - 35;
      const lookAheadX = camera.position.x + 2.5 + mouseRef.current.x * 1.5;
      const lookAheadY = camera.position.y + 0.8 + mouseRef.current.y * 1.0;
      camera.lookAt(lookAheadX, lookAheadY, lookAheadZ);

      // ── CELESTIAL MOTIONS: PLANETS ACTUALLY MOVING ────────────────────────
      if (!prefersReducedMotion) {
        // Deep stars slow rotation
        starField.rotation.y = elapsed * 0.002;
        starField.rotation.x = elapsed * 0.0008;

        // Billowing cosmic clouds subtle drift
        cloudSprites.forEach((c) => {
          c.sprite.material.rotation += c.rotSpeed;
        });

        // Foreground Planet Motion
        fgSphereMesh.rotation.y = elapsed * 0.012; // Slow axial rotation
        fgRings[0].rotation.z = elapsed * 0.015;
        fgRings[1].rotation.y = -elapsed * 0.018;
        fgRings[2].rotation.x = elapsed * 0.011;
        fgMoonPivot.rotation.y = elapsed * 0.025; // Moon orbiting

        // Radiant Celestial Sun Orb & Gyroscopic Rings Motion
        sunCoreMesh.rotation.y = elapsed * 0.03;
        sunCoronaMesh.rotation.z = -elapsed * 0.02;
        sunRings.forEach((ring, idx) => {
          const dir = idx % 2 === 0 ? 1 : -1;
          ring.rotation.z = elapsed * 0.018 * dir;
          ring.rotation.y = Math.sin(elapsed * 0.4 + idx) * 0.15;
        });

        // Milestone Planets Motion along the Highway
        milestonePlanets.forEach((m, idx) => {
          m.sphere.rotation.y = elapsed * 0.02 + idx;
          m.ring.rotation.z = elapsed * 0.035;
          m.satellitePivot.rotation.y = elapsed * 0.05 + idx;

          // Gentle harmonic bobbing floating in space
          m.group.position.y = m.baseY + Math.sin(elapsed * 1.2 + idx * 1.5) * 0.35;
        });

        // ── CONTINUOUS STREAMING PARTICLE FLOW (RIVER OF LIGHT) ─────────────
        const posArray = streamGeom.attributes.position.array as Float32Array;
        for (let i = 0; i < streamParticleCount; i++) {
          particleProgress[i] += particleSpeeds[i];
          if (particleProgress[i] > 1) {
            particleProgress[i] = 0;
          }

          const pt = destinyCurve.getPointAt(particleProgress[i]);
          posArray[i * 3] = pt.x + particleOffsetsX[i];
          posArray[i * 3 + 1] = pt.y + particleOffsetsY[i];
          posArray[i * 3 + 2] = pt.z;
        }
        streamGeom.attributes.position.needsUpdate = true;
      }

      renderer.render(scene, camera);
    };

    animate();

    // 15. Cleanup
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', handleResize);
      if (container && renderer.domElement) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
      starGeom.dispose();
      starMat.dispose();
      cloudMaterial.dispose();
      mainLineGeom.dispose();
      coreLineMat.dispose();
      glowLineMat.dispose();
      streamGeom.dispose();
      streamMat.dispose();
      fgSphereGeom.dispose();
      fgSphereMat.dispose();
      starTexture.dispose();
      cloudTexture.dispose();
      beamTexture.dispose();
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