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

    // 2. Scene, Atmospheric Glacial Fog & Fixed Camera
    const scene = new THREE.Scene();
    // Deep midnight glacial fog in dark navy/cyan
    scene.fog = new THREE.FogExp2(0x020914, 0.012);

    const camera = new THREE.PerspectiveCamera(
      48,
      window.innerWidth / window.innerHeight,
      0.1,
      1000
    );
    // Fixed cinematic camera overlooking the glacial valley and ice peaks
    camera.position.set(0, 8.5, 38);

    // 3. High-Performance Renderer
    const renderer = new THREE.WebGLRenderer({
      powerPreference: 'high-performance',
      antialias: true,
      alpha: true
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x01050d, 1.0);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    container.appendChild(renderer.domElement);

    // 4. Glacial Lighting
    // Directional cold polar moonlight creating sharp crystalline shadows
    const polarMoon = new THREE.DirectionalLight(0xdcf5ff, 2.2);
    polarMoon.position.set(30, 45, 20);
    scene.add(polarMoon);

    // Cyan rim light from the northern horizon / aurora
    const northernRim = new THREE.DirectionalLight(0x5feaff, 1.4);
    northernRim.position.set(-25, 25, -50);
    scene.add(northernRim);

    // Soft deep blue ambient fill
    const ambientCold = new THREE.AmbientLight(0x06182c, 0.85);
    scene.add(ambientCold);

    // 5. Procedural Ice Mountain Ridge Geometry
    // Multi-octave pseudo-noise generator for natural crystalline crags
    const noise2D = (x: number, z: number): number => {
      const s1 = Math.sin(x * 0.045) * Math.cos(z * 0.045);
      const s2 = Math.sin(x * 0.09 + 1.2) * Math.cos(z * 0.08 + 0.8) * 0.5;
      const s3 = Math.sin(x * 0.18 + 2.1) * Math.cos(z * 0.16 + 1.7) * 0.25;
      const s4 = Math.sin(x * 0.36 + 3.4) * Math.cos(z * 0.32 + 2.9) * 0.12;
      return s1 + s2 + s3 + s4;
    };

    const terrainWidth = 260;
    const terrainDepth = 200;
    const segX = window.innerWidth < 768 ? 90 : 130;
    const segZ = window.innerWidth < 768 ? 70 : 100;

    const terrainGeom = new THREE.PlaneGeometry(terrainWidth, terrainDepth, segX, segZ);
    terrainGeom.rotateX(-Math.PI / 2);

    const posAttr = terrainGeom.attributes.position;
    const v3 = new THREE.Vector3();
    const colors = new Float32Array(posAttr.count * 3);

    // Color Palette: Deep Glacial Base -> Translucent Cyan -> Snow Peak White
    const colDeepIce = new THREE.Color(0x041324);
    const colMidIce = new THREE.Color(0x133854);
    const colCyanIce = new THREE.Color(0x5feaff);
    const colSnow = new THREE.Color(0xebfcff);

    for (let i = 0; i < posAttr.count; i++) {
      v3.fromBufferAttribute(posAttr, i);

      // Distance from center valley (Z: 0 is camera, negative is horizon)
      const distFromCenter = Math.abs(v3.x);
      const distDeep = Math.max(0, -v3.z);

      // Flank peaks rise high on the left and right, leaving a dramatic central valley
      const flankFactor = Math.pow(distFromCenter / (terrainWidth * 0.42), 1.8);
      const deepFactor = Math.pow(distDeep / terrainDepth, 1.4);

      // Elevation profile: Sharp crystalline ridges
      let rawHeight = noise2D(v3.x, v3.z);
      // Make ridges sharp and crystalline (faceted ridge math)
      rawHeight = Math.abs(rawHeight);
      let height = (rawHeight * 28 + 2) * (0.35 + flankFactor * 1.8 + deepFactor * 1.2);

      // Flatten valley center for frozen glacial ice lake
      if (distFromCenter < 18 && v3.z > -70) {
        height = Math.min(height, 0.4 + Math.sin(v3.x * 0.2) * 0.3);
      }

      posAttr.setY(i, height);

      // Vertex color assignment based on elevation & slope
      const normH = Math.min(1.0, Math.max(0.0, height / 32));
      let vertexColor = new THREE.Color();
      if (normH < 0.15) {
        vertexColor.copy(colDeepIce).lerp(colMidIce, normH / 0.15);
      } else if (normH < 0.6) {
        vertexColor.copy(colMidIce).lerp(colCyanIce, (normH - 0.15) / 0.45);
      } else {
        vertexColor.copy(colCyanIce).lerp(colSnow, (normH - 0.6) / 0.4);
      }

      colors[i * 3] = vertexColor.r;
      colors[i * 3 + 1] = vertexColor.g;
      colors[i * 3 + 2] = vertexColor.b;
    }

    terrainGeom.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    terrainGeom.computeVertexNormals();

    // Material: Crystalline faceted ice surface with subtle metallic luster
    const terrainMat = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.4,
      metalness: 0.2,
      flatShading: true // Gives that crisp, faceted crystal/ice aesthetic
    });
    const terrainMesh = new THREE.Mesh(terrainGeom, terrainMat);
    terrainMesh.position.set(0, -3.5, -45);
    scene.add(terrainMesh);

    // 6. Frozen Glacial Lake Mirror Plane in the Valley
    const lakeGeom = new THREE.PlaneGeometry(120, 100);
    lakeGeom.rotateX(-Math.PI / 2);
    const lakeMat = new THREE.MeshStandardMaterial({
      color: 0x051a2e,
      roughness: 0.1,  // Ultra glossy reflective ice sheet
      metalness: 0.8,
      emissive: 0x031220,
      emissiveIntensity: 0.4
    });
    const lakeMesh = new THREE.Mesh(lakeGeom, lakeMat);
    lakeMesh.position.set(0, -3.3, 0);
    scene.add(lakeMesh);

    // 7. Sharp Ice Crystal Monoliths & Spires Rising from Valley
    const spireGroup = new THREE.Group();
    const spireCount = 8;
    const spireGeom = new THREE.ConeGeometry(1.6, 12, 5); // 5-sided crystalline spire
    spireGeom.translate(0, 6, 0);

    const spireMat = new THREE.MeshStandardMaterial({
      color: 0x18425d,
      emissive: 0x5feaff,
      emissiveIntensity: 0.25,
      roughness: 0.2,
      metalness: 0.5,
      flatShading: true
    });

    const spirePositions = [
      { x: -16, z: 8, scale: 1.1, rotY: 0.4 },
      { x: 18, z: 5, scale: 1.25, rotY: -0.6 },
      { x: -26, z: -18, scale: 1.8, rotY: 0.9 },
      { x: 28, z: -15, scale: 1.6, rotY: -0.8 },
      { x: -11, z: -32, scale: 1.4, rotY: 0.2 },
      { x: 13, z: -38, scale: 1.5, rotY: -0.5 },
      { x: -38, z: -55, scale: 2.4, rotY: 1.2 },
      { x: 40, z: -50, scale: 2.2, rotY: -1.1 }
    ];

    spirePositions.forEach((p) => {
      const spire = new THREE.Mesh(spireGeom, spireMat);
      spire.position.set(p.x, -3.3, p.z);
      spire.scale.set(p.scale, p.scale * (1 + Math.random() * 0.4), p.scale);
      spire.rotation.y = p.rotY;
      spire.rotation.z = (Math.random() - 0.5) * 0.15; // Subtle natural lean
      spireGroup.add(spire);
    });
    scene.add(spireGroup);

    // 8. Crystalline Destiny Path Through the Frozen Pass
    const pathPoints = [
      new THREE.Vector3(-12, -2.8, 28),
      new THREE.Vector3(-6, -2.9, 14),
      new THREE.Vector3(3, -2.8, 0),
      new THREE.Vector3(-2, -2.6, -16),
      new THREE.Vector3(5, -2.2, -32),
      new THREE.Vector3(-1, -1.5, -48),
      new THREE.Vector3(3, 1.0, -65),
      new THREE.Vector3(0, 5.0, -90)
    ];

    const pathCurve = new THREE.CatmullRomCurve3(pathPoints);
    pathCurve.curveType = 'catmullrom';
    pathCurve.tension = 0.4;

    const pathSamples = 300;
    const curvePoints = pathCurve.getPoints(pathSamples);
    const lineGeom = new THREE.BufferGeometry().setFromPoints(curvePoints);

    // Bright Core Ice-Light Strand
    const lineMat = new THREE.LineBasicMaterial({
      color: 0xebfcff,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending
    });
    const pathLine = new THREE.Line(lineGeom, lineMat);
    scene.add(pathLine);

    // Cyan Glacial Outer Glow Trail
    const glowLineMat = new THREE.LineBasicMaterial({
      color: 0x5feaff,
      transparent: true,
      opacity: 0.55,
      blending: THREE.AdditiveBlending
    });
    const glowLine = new THREE.Line(lineGeom, glowLineMat);
    glowLine.position.y += 0.08;
    scene.add(glowLine);

    // 9. Floating Frost Crystals / Ice Dust Micro-Particles
    const frostCount = window.innerWidth < 768 ? 220 : 450;
    const frostGeom = new THREE.BufferGeometry();
    const frostPositions = new Float32Array(frostCount * 3);
    const frostVelocities = new Float32Array(frostCount * 3);

    // Soft crystal spark texture
    const sparkCanvas = document.createElement('canvas');
    sparkCanvas.width = 32;
    sparkCanvas.height = 32;
    const sCtx = sparkCanvas.getContext('2d');
    if (sCtx) {
      const grad = sCtx.createRadialGradient(16, 16, 0, 16, 16, 16);
      grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
      grad.addColorStop(0.3, 'rgba(220, 248, 255, 0.85)');
      grad.addColorStop(0.7, 'rgba(95, 234, 255, 0.3)');
      grad.addColorStop(1, 'rgba(1, 5, 13, 0)');
      sCtx.fillStyle = grad;
      sCtx.fillRect(0, 0, 32, 32);
    }
    const sparkTexture = new THREE.CanvasTexture(sparkCanvas);

    for (let i = 0; i < frostCount; i++) {
      frostPositions[i * 3] = (Math.random() - 0.5) * 80;
      frostPositions[i * 3 + 1] = -2 + Math.random() * 25;
      frostPositions[i * 3 + 2] = 25 - Math.random() * 85;

      frostVelocities[i * 3] = (Math.random() - 0.5) * 0.006;
      frostVelocities[i * 3 + 1] = -0.003 - Math.random() * 0.007; // Gentle falling snow/frost
      frostVelocities[i * 3 + 2] = (Math.random() - 0.5) * 0.005;
    }
    frostGeom.setAttribute('position', new THREE.BufferAttribute(frostPositions, 3));

    const frostMat = new THREE.PointsMaterial({
      size: 1.2,
      map: sparkTexture,
      color: 0x80cfff,
      transparent: true,
      opacity: 0.75,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const frostParticles = new THREE.Points(frostGeom, frostMat);
    scene.add(frostParticles);

    // 10. Aurora Borealis Curtain / Glacial Sky Glow
    const auroraGeom = new THREE.PlaneGeometry(160, 45, 48, 12);
    const aPos = auroraGeom.attributes.position;
    for (let i = 0; i < aPos.count; i++) {
      const x = aPos.getX(i);
      const wave = Math.sin(x * 0.08) * 4;
      aPos.setZ(i, wave);
    }
    auroraGeom.computeVertexNormals();

    const auroraCanvas = document.createElement('canvas');
    auroraCanvas.width = 256;
    auroraCanvas.height = 128;
    const aCtx = auroraCanvas.getContext('2d');
    if (aCtx) {
      const grad = aCtx.createLinearGradient(0, 128, 0, 0);
      grad.addColorStop(0, 'rgba(95, 234, 255, 0)');
      grad.addColorStop(0.3, 'rgba(95, 234, 255, 0.25)');
      grad.addColorStop(0.7, 'rgba(64, 136, 255, 0.18)');
      grad.addColorStop(1, 'rgba(1, 5, 13, 0)');
      aCtx.fillStyle = grad;
      aCtx.fillRect(0, 0, 256, 128);
    }
    const auroraTexture = new THREE.CanvasTexture(auroraCanvas);

    const auroraMat = new THREE.MeshBasicMaterial({
      map: auroraTexture,
      transparent: true,
      opacity: 0.6,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const auroraMesh = new THREE.Mesh(auroraGeom, auroraMat);
    auroraMesh.position.set(0, 18, -80);
    scene.add(auroraMesh);

    // 11. Mouse Movement Listener for Gentle Restrained Parallax (No Scroll Movement)
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

    // 12. Main Animation Render Loop
    let animId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);

      if (document.hidden) return;

      const elapsed = clock.getElapsedTime();

      // Smooth mouse parallax lerp (Restrained, serene fixed perspective)
      mouseRef.current.x += (mouseRef.current.targetX - mouseRef.current.x) * 0.04;
      mouseRef.current.y += (mouseRef.current.targetY - mouseRef.current.y) * 0.04;

      // Camera is FIXED at overlooking height, with calm responsive perspective tilt
      camera.position.x = mouseRef.current.x * 2.2;
      camera.position.y = 8.5 + mouseRef.current.y * 1.4;
      camera.position.z = 38;
      camera.lookAt(mouseRef.current.x * 1.0, 4.0, -20);

      if (!prefersReducedMotion) {
        // Floating / Falling Frost Crystals
        const fArr = frostGeom.attributes.position.array as Float32Array;
        for (let i = 0; i < frostCount; i++) {
          fArr[i * 3] += frostVelocities[i * 3];
          fArr[i * 3 + 1] += frostVelocities[i * 3 + 1];
          fArr[i * 3 + 2] += frostVelocities[i * 3 + 2];

          // Wrap around if below valley floor
          if (fArr[i * 3 + 1] < -3.5) {
            fArr[i * 3 + 1] = 22;
            fArr[i * 3] = (Math.random() - 0.5) * 80;
          }
        }
        frostGeom.attributes.position.needsUpdate = true;

        // Gentle undulating Aurora Borealis wave
        const aPosArr = auroraGeom.attributes.position;
        for (let i = 0; i < aPosArr.count; i++) {
          const x = aPosArr.getX(i);
          const w = Math.sin(x * 0.08 + elapsed * 0.6) * 3.5 + Math.cos(x * 0.04 + elapsed * 0.3) * 2;
          aPosArr.setZ(i, w);
        }
        aPosArr.needsUpdate = true;
      }

      renderer.render(scene, camera);
    };

    animate();

    // 13. Cleanup
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', handleResize);
      if (container && renderer.domElement) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
      terrainGeom.dispose();
      terrainMat.dispose();
      lakeGeom.dispose();
      lakeMat.dispose();
      spireGeom.dispose();
      spireMat.dispose();
      lineGeom.dispose();
      lineMat.dispose();
      glowLineMat.dispose();
      frostGeom.dispose();
      frostMat.dispose();
      auroraGeom.dispose();
      auroraMat.dispose();
      sparkTexture.dispose();
      auroraTexture.dispose();
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
          background: 'radial-gradient(circle at 50% 30%, #06192e 0%, #01050d 95%)',
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