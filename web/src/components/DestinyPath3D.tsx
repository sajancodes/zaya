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

    // 2. Scene, Fog & Camera
    const scene = new THREE.Scene();
    // Deep space fog in midnight black/navy
    scene.fog = new THREE.FogExp2(0x010409, 0.009);

    const camera = new THREE.PerspectiveCamera(
      58,
      window.innerWidth / window.innerHeight,
      0.1,
      1200
    );
    camera.position.set(0, 1.5, 32);

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
    renderer.toneMappingExposure = 1.15;
    container.appendChild(renderer.domElement);

    // 4. Cosmic Lighting (Directional Star + Ambient)
    const starSunLight = new THREE.DirectionalLight(0xebfcff, 1.8);
    starSunLight.position.set(45, 50, 30);
    scene.add(starSunLight);

    const ambientLight = new THREE.AmbientLight(0x041321, 0.6);
    scene.add(ambientLight);

    // Soft cyan back light from the distant destiny destination
    const destinationLight = new THREE.PointLight(0x5feaff, 2.5, 350);
    destinationLight.position.set(0, 0, -230);
    scene.add(destinationLight);

    // 5. Multi-Layer Living Star Field
    // Layer A: Deep distant stars (thousands of micro points)
    const deepStarCount = 1800;
    const deepStarGeom = new THREE.BufferGeometry();
    const deepStarPositions = new Float32Array(deepStarCount * 3);
    const deepStarColors = new Float32Array(deepStarCount * 3);

    const starPalette = [
      new THREE.Color(0xffffff),
      new THREE.Color(0xebfcff),
      new THREE.Color(0x80cfff),
      new THREE.Color(0x5feaff),
      new THREE.Color(0xa5b4fc)
    ];

    for (let i = 0; i < deepStarCount; i++) {
      // Cylindrical/spherical distribution in deep space
      const radius = 100 + Math.random() * 320;
      const theta = Math.random() * Math.PI * 2;
      const phi = (Math.random() - 0.5) * Math.PI * 0.9;

      deepStarPositions[i * 3] = radius * Math.cos(phi) * Math.sin(theta);
      deepStarPositions[i * 3 + 1] = radius * Math.sin(phi);
      deepStarPositions[i * 3 + 2] = -50 - Math.random() * 350;

      const col = starPalette[Math.floor(Math.random() * starPalette.length)];
      deepStarColors[i * 3] = col.r;
      deepStarColors[i * 3 + 1] = col.g;
      deepStarColors[i * 3 + 2] = col.b;
    }
    deepStarGeom.setAttribute('position', new THREE.BufferAttribute(deepStarPositions, 3));
    deepStarGeom.setAttribute('color', new THREE.BufferAttribute(deepStarColors, 3));

    // Circular star texture
    const starCanvas = document.createElement('canvas');
    starCanvas.width = 32;
    starCanvas.height = 32;
    const sCtx = starCanvas.getContext('2d');
    if (sCtx) {
      const grad = sCtx.createRadialGradient(16, 16, 0, 16, 16, 16);
      grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
      grad.addColorStop(0.3, 'rgba(220, 245, 255, 0.8)');
      grad.addColorStop(0.7, 'rgba(95, 234, 255, 0.2)');
      grad.addColorStop(1, 'rgba(1, 4, 9, 0)');
      sCtx.fillStyle = grad;
      sCtx.fillRect(0, 0, 32, 32);
    }
    const starTexture = new THREE.CanvasTexture(starCanvas);

    const deepStarMat = new THREE.PointsMaterial({
      size: 1.6,
      map: starTexture,
      vertexColors: true,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const deepStars = new THREE.Points(deepStarGeom, deepStarMat);
    scene.add(deepStars);

    // Layer B: Near Floating Ice Crystal Dust (Parallax drifting)
    const dustCount = window.innerWidth < 768 ? 140 : 360;
    const dustGeom = new THREE.BufferGeometry();
    const dustPositions = new Float32Array(dustCount * 3);
    const dustVelocities = new Float32Array(dustCount * 3);

    for (let i = 0; i < dustCount; i++) {
      dustPositions[i * 3] = (Math.random() - 0.5) * 60;
      dustPositions[i * 3 + 1] = (Math.random() - 0.5) * 45;
      dustPositions[i * 3 + 2] = 20 - Math.random() * 120;

      dustVelocities[i * 3] = (Math.random() - 0.5) * 0.004;
      dustVelocities[i * 3 + 1] = 0.002 + Math.random() * 0.005;
      dustVelocities[i * 3 + 2] = (Math.random() - 0.5) * 0.003;
    }
    dustGeom.setAttribute('position', new THREE.BufferAttribute(dustPositions, 3));

    const dustMat = new THREE.PointsMaterial({
      size: 1.1,
      map: starTexture,
      color: 0x80cfff,
      transparent: true,
      opacity: 0.65,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const dustParticles = new THREE.Points(dustGeom, dustMat);
    scene.add(dustParticles);

    // 6. Physically Shaded Realistic Celestial Bodies (Planets & Moons)
    // Planet A: Distant Crystalline Ice Terrestrial Planet
    const planetAGroup = new THREE.Group();
    planetAGroup.position.set(-36, 12, -110);

    const planetAGeom = new THREE.SphereGeometry(9.5, 48, 48);
    // Procedural ice/crystal rock material with limb illumination
    const planetAMat = new THREE.MeshStandardMaterial({
      color: 0x14324f,
      roughness: 0.55,
      metalness: 0.35,
      emissive: 0x051a2e,
      emissiveIntensity: 0.4
    });
    const planetAMesh = new THREE.Mesh(planetAGeom, planetAMat);
    planetAGroup.add(planetAMesh);

    // Atmosphere Rim Glow for Planet A
    const atmoGeom = new THREE.SphereGeometry(10.2, 48, 48);
    const atmoMat = new THREE.MeshBasicMaterial({
      color: 0x5feaff,
      transparent: true,
      opacity: 0.18,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending
    });
    const planetAAtmo = new THREE.Mesh(atmoGeom, atmoMat);
    planetAGroup.add(planetAAtmo);

    // Planet A's Moon (Slow Majestic Orbit)
    const moonPivot = new THREE.Group();
    planetAGroup.add(moonPivot);

    const moonGeom = new THREE.SphereGeometry(1.8, 24, 24);
    const moonMat = new THREE.MeshStandardMaterial({
      color: 0x4088ff,
      roughness: 0.7,
      metalness: 0.2
    });
    const moonMesh = new THREE.Mesh(moonGeom, moonMat);
    moonMesh.position.set(18, 2, 0);
    moonPivot.add(moonMesh);

    scene.add(planetAGroup);

    // Planet B: Distant Gas Giant in Upper Right
    const planetBGroup = new THREE.Group();
    planetBGroup.position.set(44, 24, -170);

    const planetBGeom = new THREE.SphereGeometry(14, 48, 48);
    const planetBMat = new THREE.MeshStandardMaterial({
      color: 0x0a2238,
      roughness: 0.8,
      metalness: 0.1,
      emissive: 0x02101e,
      emissiveIntensity: 0.3
    });
    const planetBMesh = new THREE.Mesh(planetBGeom, planetBMat);
    planetBGroup.add(planetBMesh);

    const planetBAtmoMat = new THREE.MeshBasicMaterial({
      color: 0x80cfff,
      transparent: true,
      opacity: 0.12,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending
    });
    const planetBAtmo = new THREE.Mesh(new THREE.SphereGeometry(14.8, 48, 48), planetBAtmoMat);
    planetBGroup.add(planetBAtmo);

    scene.add(planetBGroup);

    // Grand Distant Celestial Destination Sphere (Vanishing point light)
    const destinationGeom = new THREE.SphereGeometry(22, 32, 32);
    const destinationMat = new THREE.MeshBasicMaterial({
      color: 0x5feaff,
      transparent: true,
      opacity: 0.08,
      blending: THREE.AdditiveBlending
    });
    const destinationMesh = new THREE.Mesh(destinationGeom, destinationMat);
    destinationMesh.position.set(0, 0, -235);
    scene.add(destinationMesh);

    // 7. The Destiny Path (Smooth Spline through 3D Cosmos)
    const pathControlPoints = [
      new THREE.Vector3(0, -1, 38),       // Near viewer
      new THREE.Vector3(-4, 0, 18),      // Subtle curve
      new THREE.Vector3(6, 2, -15),      // Curve toward voice milestone
      new THREE.Vector3(-8, -2, -55),    // Curve toward vision & memory
      new THREE.Vector3(10, 4, -95),     // Branching / autonomy
      new THREE.Vector3(-6, -1, -135),   // Hand & Spatial
      new THREE.Vector3(4, 1, -175),     // Mobile & WhatsApp
      new THREE.Vector3(0, 0, -225)      // Distant destination
    ];

    const destinyCurve = new THREE.CatmullRomCurve3(pathControlPoints);
    destinyCurve.curveType = 'catmullrom';
    destinyCurve.tension = 0.45;

    const pathSamples = 500;
    const curvePoints = destinyCurve.getPoints(pathSamples);

    // Primary Core Line (Bright Frozen White / Ice Cyan)
    const coreGeom = new THREE.BufferGeometry().setFromPoints(curvePoints);
    const coreMat = new THREE.LineBasicMaterial({
      color: 0xebfcff,
      linewidth: 2,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending
    });
    const coreLine = new THREE.Line(coreGeom, coreMat);
    scene.add(coreLine);

    // Secondary Ambient Cyan Glow Trail
    const glowMat = new THREE.LineBasicMaterial({
      color: 0x5feaff,
      linewidth: 4,
      transparent: true,
      opacity: 0.5,
      blending: THREE.AdditiveBlending
    });
    const glowLine = new THREE.Line(coreGeom, glowMat);
    glowLine.position.y -= 0.12;
    scene.add(glowLine);

    // Tertiary Deep Electric Blue halo
    const deepGlowMat = new THREE.LineBasicMaterial({
      color: 0x4088ff,
      linewidth: 6,
      transparent: true,
      opacity: 0.25,
      blending: THREE.AdditiveBlending
    });
    const deepGlowLine = new THREE.Line(coreGeom, deepGlowMat);
    scene.add(deepGlowLine);

    // 8. Traveling Energy Pulses Along the Destiny Path
    // Small luminous packets of light moving toward the future
    const pulseCount = 4;
    const pulseSpheres: { mesh: THREE.Mesh; progress: number; speed: number }[] = [];
    const pulseGeom = new THREE.SphereGeometry(0.55, 16, 16);
    const pulseMat = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.9,
      blending: THREE.AdditiveBlending
    });

    for (let i = 0; i < pulseCount; i++) {
      const mesh = new THREE.Mesh(pulseGeom, pulseMat);
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(0.8, 1.2, 24),
        new THREE.MeshBasicMaterial({
          color: 0x5feaff,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0.6,
          blending: THREE.AdditiveBlending
        })
      );
      ring.rotation.x = Math.PI / 2;
      mesh.add(ring);

      scene.add(mesh);
      pulseSpheres.push({
        mesh,
        progress: (i / pulseCount) + Math.random() * 0.1,
        speed: 0.0007 + Math.random() * 0.0005
      });
    }

    // 9. Crystalline Milestone Nodes along Path
    const milestoneGroup = new THREE.Group();
    const milestoneCount = 8;
    const milestones: { mesh: THREE.Mesh; point: THREE.Vector3; ring: THREE.Mesh }[] = [];

    const nodeOctahedronGeom = new THREE.OctahedronGeometry(0.9, 0); // Faceted crystal node
    const nodeMajorGeom = new THREE.OctahedronGeometry(1.4, 0);

    for (let i = 0; i < milestoneCount; i++) {
      const u = (i + 1) / (milestoneCount + 1);
      const pos = destinyCurve.getPointAt(u);
      const isMajor = i % 2 === 0;

      const nodeMat = new THREE.MeshBasicMaterial({
        color: isMajor ? 0xebfcff : 0x5feaff,
        wireframe: false,
        transparent: true,
        opacity: 0.85,
        blending: THREE.AdditiveBlending
      });

      const mesh = new THREE.Mesh(isMajor ? nodeMajorGeom : nodeOctahedronGeom, nodeMat);
      mesh.position.copy(pos);

      // Fine crystal orbital ring
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(isMajor ? 1.8 : 1.2, isMajor ? 2.1 : 1.4, 32),
        new THREE.MeshBasicMaterial({
          color: 0x80cfff,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0.4,
          blending: THREE.AdditiveBlending
        })
      );
      ring.rotation.x = Math.PI / 2;
      mesh.add(ring);

      milestoneGroup.add(mesh);
      milestones.push({ mesh, point: pos, ring });
    }
    scene.add(milestoneGroup);

    // 10. Waveform for Voice Section
    const waveGeom = new THREE.BufferGeometry();
    const wavePointsCount = 100;
    const wavePositions = new Float32Array(wavePointsCount * 3);
    for (let i = 0; i < wavePointsCount; i++) {
      const x = (i - 50) * 0.35;
      wavePositions[i * 3] = x;
      wavePositions[i * 3 + 1] = 0;
      wavePositions[i * 3 + 2] = -25;
    }
    waveGeom.setAttribute('position', new THREE.BufferAttribute(wavePositions, 3));
    const waveLine = new THREE.Line(
      waveGeom,
      new THREE.LineBasicMaterial({
        color: 0x5feaff,
        transparent: true,
        opacity: 0.6,
        blending: THREE.AdditiveBlending
      })
    );
    scene.add(waveLine);

    // 11. Event Handlers
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

    // 12. Main Animation & Orbit Render Loop
    let animId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);

      if (document.hidden) return;

      const delta = clock.getDelta();
      const elapsed = clock.getElapsedTime();

      // Smooth camera mouse parallax
      mouseRef.current.x += (mouseRef.current.targetX - mouseRef.current.x) * 0.04;
      mouseRef.current.y += (mouseRef.current.targetY - mouseRef.current.y) * 0.04;

      const scroll = scrollRef.current;

      // Camera moves forward through the cosmic destiny path driven by scroll
      // Z moves from 32 (Hero) down to -210 (Roadmap/Infinity)
      const targetZ = 32 - scroll * 245;
      const targetY = 1.5 + Math.sin(scroll * Math.PI * 3.5) * 2.2 + mouseRef.current.y * 1.2;
      const targetX = Math.cos(scroll * Math.PI * 2.8) * 3.5 + mouseRef.current.x * 2.2;

      camera.position.z += (targetZ - camera.position.z) * 0.07;
      camera.position.y += (targetY - camera.position.y) * 0.07;
      camera.position.x += (targetX - camera.position.x) * 0.07;

      // Look toward the forward path point
      camera.lookAt(
        Math.sin(elapsed * 0.3) * 0.6,
        mouseRef.current.y * 0.5,
        camera.position.z - 35
      );

      // Celestial Planetary Motions (Extremely slow & majestic)
      if (!prefersReducedMotion) {
        // Deep stars slow rotation
        deepStars.rotation.y = elapsed * 0.003;
        deepStars.rotation.x = elapsed * 0.001;

        // Planet A axial rotation (period ~80s)
        planetAMesh.rotation.y = elapsed * 0.015;
        // Moon orbit around Planet A (period ~100s)
        moonPivot.rotation.y = elapsed * 0.02;

        // Planet B axial rotation (period ~120s)
        planetBMesh.rotation.y = elapsed * 0.008;

        // Floating ice crystal dust parallax
        const dustArr = dustGeom.attributes.position.array as Float32Array;
        for (let i = 0; i < dustCount; i++) {
          dustArr[i * 3 + 1] += dustVelocities[i * 3 + 1];
          if (dustArr[i * 3 + 1] > 25) {
            dustArr[i * 3 + 1] = -25;
          }
        }
        dustGeom.attributes.position.needsUpdate = true;

        // Animate traveling energy pulses along the path
        pulseSpheres.forEach((p) => {
          p.progress += p.speed;
          if (p.progress > 1) p.progress = 0;

          const pt = destinyCurve.getPointAt(p.progress);
          p.mesh.position.copy(pt);
          p.mesh.rotation.y = elapsed * 2;
        });

        // Rotate & pulse milestone crystals
        milestones.forEach((m, idx) => {
          m.mesh.rotation.y = elapsed * 0.6 + idx;
          m.mesh.rotation.x = elapsed * 0.4 + idx;
          m.ring.rotation.z = elapsed * 0.3;

          const scale = 1 + Math.sin(elapsed * 2.2 + idx * 0.8) * 0.12;
          m.mesh.scale.set(scale, scale, scale);
        });

        // Animate Voice Waveform
        const waveArr = waveGeom.attributes.position.array as Float32Array;
        for (let i = 0; i < wavePointsCount; i++) {
          const x = (i - 50) * 0.35;
          const w = Math.sin(x * 0.4 + elapsed * 3.5) * Math.cos(x * 0.2 + elapsed * 1.8);
          waveArr[i * 3 + 1] = w * 1.8;
        }
        waveGeom.attributes.position.needsUpdate = true;
      }

      renderer.render(scene, camera);
    };

    animate();

    // 13. Cleanup
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', handleResize);
      if (container && renderer.domElement) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
      deepStarGeom.dispose();
      deepStarMat.dispose();
      dustGeom.dispose();
      dustMat.dispose();
      coreGeom.dispose();
      coreMat.dispose();
      glowMat.dispose();
      planetAGeom.dispose();
      planetAMat.dispose();
      planetBGeom.dispose();
      planetBMat.dispose();
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
