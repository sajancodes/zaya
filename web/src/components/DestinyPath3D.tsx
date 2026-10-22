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

    // 2. Scene, Atmospheric Glacial Fog & Camera
    const scene = new THREE.Scene();
    // Deep midnight glacial fog in dark navy/cyan
    scene.fog = new THREE.FogExp2(0x020914, 0.011);

    const camera = new THREE.PerspectiveCamera(
      52,
      window.innerWidth / window.innerHeight,
      0.1,
      1000
    );
    // Initial camera position at the entrance of the glacial pass
    camera.position.set(-6, 4.8, 36);

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
    renderer.toneMappingExposure = 1.2;
    container.appendChild(renderer.domElement);

    // 4. Glacial Lighting
    // Directional cold polar moonlight casting long, sharp crystalline shadows
    const polarMoon = new THREE.DirectionalLight(0xdcf5ff, 2.2);
    polarMoon.position.set(35, 45, 25);
    scene.add(polarMoon);

    // Northern horizon aurora rim light
    const northernRim = new THREE.DirectionalLight(0x5feaff, 1.5);
    northernRim.position.set(-25, 25, -60);
    scene.add(northernRim);

    // Deep blue ambient fill
    const ambientCold = new THREE.AmbientLight(0x06182c, 0.85);
    scene.add(ambientCold);

    // 5. Procedural Ice Mountain Ridge Geometry
    const noise2D = (x: number, z: number): number => {
      const s1 = Math.sin(x * 0.045) * Math.cos(z * 0.045);
      const s2 = Math.sin(x * 0.09 + 1.2) * Math.cos(z * 0.08 + 0.8) * 0.5;
      const s3 = Math.sin(x * 0.18 + 2.1) * Math.cos(z * 0.16 + 1.7) * 0.25;
      const s4 = Math.sin(x * 0.36 + 3.4) * Math.cos(z * 0.32 + 2.9) * 0.12;
      return s1 + s2 + s3 + s4;
    };

    const terrainWidth = 280;
    const terrainDepth = 240;
    const segX = window.innerWidth < 768 ? 90 : 130;
    const segZ = window.innerWidth < 768 ? 75 : 110;

    const terrainGeom = new THREE.PlaneGeometry(terrainWidth, terrainDepth, segX, segZ);
    terrainGeom.rotateX(-Math.PI / 2);

    const posAttr = terrainGeom.attributes.position;
    const v3 = new THREE.Vector3();
    const colors = new Float32Array(posAttr.count * 3);

    // Palette: Deep Glacial Base -> Translucent Cyan -> Snow Peak White
    const colDeepIce = new THREE.Color(0x041324);
    const colMidIce = new THREE.Color(0x133854);
    const colCyanIce = new THREE.Color(0x5feaff);
    const colSnow = new THREE.Color(0xebfcff);

    for (let i = 0; i < posAttr.count; i++) {
      v3.fromBufferAttribute(posAttr, i);

      const distFromCenter = Math.abs(v3.x);
      const distDeep = Math.max(0, -v3.z);

      // Flank peaks rise high on the left and right, naturally carving a central canyon
      const flankFactor = Math.pow(distFromCenter / (terrainWidth * 0.42), 1.8);
      const deepFactor = Math.pow(distDeep / terrainDepth, 1.4);

      let rawHeight = Math.abs(noise2D(v3.x, v3.z));
      let height = (rawHeight * 30 + 2) * (0.35 + flankFactor * 1.9 + deepFactor * 1.3);

      // Carve out a smooth, winding canyon valley through the center
      const canyonWiggle = Math.sin(v3.z * 0.04) * 8;
      const distFromValley = Math.abs(v3.x - canyonWiggle);
      if (distFromValley < 18) {
        const t = distFromValley / 18;
        height = THREE.MathUtils.lerp(-3.2, height, Math.pow(t, 2.2));
      }

      posAttr.setY(i, height);

      // Vertex color assignment based on elevation
      const normH = Math.min(1.0, Math.max(0.0, height / 34));
      const vertexColor = new THREE.Color();
      if (normH < 0.15) {
        vertexColor.copy(colDeepIce).lerp(colMidIce, normH / 0.15);
      } else if (normH < 0.58) {
        vertexColor.copy(colMidIce).lerp(colCyanIce, (normH - 0.15) / 0.43);
      } else {
        vertexColor.copy(colCyanIce).lerp(colSnow, (normH - 0.58) / 0.42);
      }

      colors[i * 3] = vertexColor.r;
      colors[i * 3 + 1] = vertexColor.g;
      colors[i * 3 + 2] = vertexColor.b;
    }

    terrainGeom.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    terrainGeom.computeVertexNormals();

    const terrainMat = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.4,
      metalness: 0.2,
      flatShading: true // Crisp faceted crystal aesthetic
    });
    const terrainMesh = new THREE.Mesh(terrainGeom, terrainMat);
    terrainMesh.position.set(0, 0, -45);
    scene.add(terrainMesh);

    // 6. Frozen Glacial Lake / Ice Sheet Mirror in the Valley
    const lakeGeom = new THREE.PlaneGeometry(140, 180);
    lakeGeom.rotateX(-Math.PI / 2);
    const lakeMat = new THREE.MeshStandardMaterial({
      color: 0x051a2e,
      roughness: 0.08,
      metalness: 0.85,
      emissive: 0x031220,
      emissiveIntensity: 0.35
    });
    const lakeMesh = new THREE.Mesh(lakeGeom, lakeMat);
    lakeMesh.position.set(0, -3.2, -20);
    scene.add(lakeMesh);

    // 7. Sharp Ice Crystal Monoliths Flanking the Pathway
    const spireGroup = new THREE.Group();
    const spireGeom = new THREE.ConeGeometry(1.6, 14, 5); // 5-sided crystalline spire
    spireGeom.translate(0, 7, 0);

    const spireMat = new THREE.MeshStandardMaterial({
      color: 0x18425d,
      emissive: 0x5feaff,
      emissiveIntensity: 0.28,
      roughness: 0.2,
      metalness: 0.5,
      flatShading: true
    });

    const spirePositions = [
      { x: -14, z: 24, scale: 1.1, rotY: 0.4 },
      { x: 16, z: 20, scale: 1.25, rotY: -0.6 },
      { x: -16, z: 2, scale: 1.4, rotY: 0.8 },
      { x: 18, z: -8, scale: 1.5, rotY: -0.7 },
      { x: -15, z: -25, scale: 1.7, rotY: 0.3 },
      { x: 19, z: -35, scale: 1.6, rotY: -0.5 },
      { x: -18, z: -55, scale: 2.1, rotY: 1.1 },
      { x: 20, z: -68, scale: 2.3, rotY: -1.0 },
      { x: -16, z: -82, scale: 2.5, rotY: 0.6 },
      { x: 18, z: -92, scale: 2.4, rotY: -0.8 }
    ];

    spirePositions.forEach((p) => {
      const spire = new THREE.Mesh(spireGeom, spireMat);
      spire.position.set(p.x, -3.2, p.z);
      spire.scale.set(p.scale, p.scale * (1 + Math.random() * 0.35), p.scale);
      spire.rotation.y = p.rotY;
      spire.rotation.z = (Math.random() - 0.5) * 0.12;
      spireGroup.add(spire);
    });
    scene.add(spireGroup);

    // 8. THE GLOWING PATHWAY THROUGH THE MOUNTAINS
    // Control points for the glowing ground path along the valley floor
    const groundPathPoints = [
      new THREE.Vector3(-6, -2.9, 36),
      new THREE.Vector3(-3, -2.9, 20),
      new THREE.Vector3(3, -2.8, 5),
      new THREE.Vector3(-2, -2.8, -12),
      new THREE.Vector3(4, -2.6, -30),
      new THREE.Vector3(-1, -2.2, -48),
      new THREE.Vector3(3, -1.5, -66),
      new THREE.Vector3(0, -0.5, -88),
      new THREE.Vector3(1, 1.2, -110)
    ];

    const groundCurve = new THREE.CatmullRomCurve3(groundPathPoints);
    groundCurve.curveType = 'catmullrom';
    groundCurve.tension = 0.45;

    const pathSamples = 400;
    const curvePoints = groundCurve.getPoints(pathSamples);
    const lineGeom = new THREE.BufferGeometry().setFromPoints(curvePoints);

    // Primary bright core strand
    const coreLineMat = new THREE.LineBasicMaterial({
      color: 0xebfcff,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending
    });
    const coreLine = new THREE.Line(lineGeom, coreLineMat);
    scene.add(coreLine);

    // Cyan outer glow line
    const glowLineMat = new THREE.LineBasicMaterial({
      color: 0x5feaff,
      transparent: true,
      opacity: 0.55,
      blending: THREE.AdditiveBlending
    });
    const glowLine = new THREE.Line(lineGeom, glowLineMat);
    glowLine.position.y += 0.08;
    scene.add(glowLine);

    // Parallel guide rails flanking the path
    [-0.5, 0.5].forEach((offset) => {
      const strandPoints = curvePoints.map((pt) =>
        new THREE.Vector3(pt.x + offset, pt.y, pt.z)
      );
      const sGeom = new THREE.BufferGeometry().setFromPoints(strandPoints);
      const sMat = new THREE.LineBasicMaterial({
        color: 0x80cfff,
        transparent: true,
        opacity: 0.35,
        blending: THREE.AdditiveBlending
      });
      const sLine = new THREE.Line(sGeom, sMat);
      scene.add(sLine);
    });

    // 9. Crystalline Milestone Nodes along the Pathway
    const milestoneGroup = new THREE.Group();
    const milestoneCount = 6;
    const milestoneNodes: { mesh: THREE.Mesh; ring: THREE.Mesh }[] = [];
    const octaGeom = new THREE.OctahedronGeometry(0.85, 0);

    for (let i = 0; i < milestoneCount; i++) {
      const u = (i + 1) / (milestoneCount + 1);
      const pt = groundCurve.getPointAt(u);

      const mMesh = new THREE.Mesh(
        octaGeom,
        new THREE.MeshBasicMaterial({
          color: 0xebfcff,
          transparent: true,
          opacity: 0.9,
          blending: THREE.AdditiveBlending
        })
      );
      mMesh.position.set(pt.x, pt.y + 0.8, pt.z);

      const mRing = new THREE.Mesh(
        new THREE.RingGeometry(1.2, 1.4, 24),
        new THREE.MeshBasicMaterial({
          color: 0x5feaff,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0.55,
          blending: THREE.AdditiveBlending
        })
      );
      mRing.rotation.x = Math.PI / 2;
      mMesh.add(mRing);

      milestoneGroup.add(mMesh);
      milestoneNodes.push({ mesh: mMesh, ring: mRing });
    }
    scene.add(milestoneGroup);

    // 10. Traveling Energy Pulses Along the Ground Path
    const pulseCount = 4;
    const pulses: { mesh: THREE.Mesh; progress: number; speed: number }[] = [];
    const pulseGeom = new THREE.SphereGeometry(0.4, 16, 16);
    const pulseMat = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      blending: THREE.AdditiveBlending
    });

    for (let i = 0; i < pulseCount; i++) {
      const pMesh = new THREE.Mesh(pulseGeom, pulseMat);
      scene.add(pMesh);
      pulses.push({
        mesh: pMesh,
        progress: (i / pulseCount) + Math.random() * 0.1,
        speed: 0.0008 + Math.random() * 0.0006
      });
    }

    // 11. FLIGHT CAMERA PATH THROUGH THE MOUNTAINS (Scroll-Driven Track)
    // Floats gracefully above the ground pathway, offering a grand first-person / third-person view
    const flightCameraPoints = [
      new THREE.Vector3(-6, 4.8, 36),     // Hero View: elevated overlooking the valley entrance
      new THREE.Vector3(-3, 3.2, 20),     // Descending toward the frozen lake
      new THREE.Vector3(3, 2.5, 4),       // Gliding over the ice sheet between spires
      new THREE.Vector3(-2, 2.8, -12),    // Weaving between midground monoliths
      new THREE.Vector3(4, 3.5, -30),     // Flying into the canyon pass
      new THREE.Vector3(-1, 4.2, -48),    // Winding past high crystalline ice crags
      new THREE.Vector3(3, 5.5, -66),     // Rising toward the high mountain pass
      new THREE.Vector3(0, 7.5, -88),     // Cresting the ridge with the aurora glowing ahead
      new THREE.Vector3(1, 9.5, -108)     // Into the deep northern horizon
    ];

    const flightCurve = new THREE.CatmullRomCurve3(flightCameraPoints);
    flightCurve.curveType = 'catmullrom';
    flightCurve.tension = 0.45;

    // 12. Floating Frost Crystals / Ice Dust Micro-Particles
    const frostCount = window.innerWidth < 768 ? 220 : 450;
    const frostGeom = new THREE.BufferGeometry();
    const frostPositions = new Float32Array(frostCount * 3);
    const frostVelocities = new Float32Array(frostCount * 3);

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
      frostPositions[i * 3 + 2] = 30 - Math.random() * 140;

      frostVelocities[i * 3] = (Math.random() - 0.5) * 0.005;
      frostVelocities[i * 3 + 1] = -0.003 - Math.random() * 0.006;
      frostVelocities[i * 3 + 2] = (Math.random() - 0.5) * 0.004;
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

    // 13. Aurora Borealis at the Horizon End of the Pass
    const auroraGeom = new THREE.PlaneGeometry(180, 50, 48, 12);
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
      grad.addColorStop(0.3, 'rgba(95, 234, 255, 0.3)');
      grad.addColorStop(0.7, 'rgba(64, 136, 255, 0.2)');
      grad.addColorStop(1, 'rgba(1, 5, 13, 0)');
      aCtx.fillStyle = grad;
      aCtx.fillRect(0, 0, 256, 128);
    }
    const auroraTexture = new THREE.CanvasTexture(auroraCanvas);

    const auroraMat = new THREE.MeshBasicMaterial({
      map: auroraTexture,
      transparent: true,
      opacity: 0.65,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const auroraMesh = new THREE.Mesh(auroraGeom, auroraMat);
    auroraMesh.position.set(0, 22, -125);
    scene.add(auroraMesh);

    // 14. Scroll and Mouse Event Handlers
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

    // 15. Main Animation Loop: Scroll-Driven Flight Between the Mountains
    let animId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);

      if (document.hidden) return;

      const elapsed = clock.getElapsedTime();

      // Smooth mouse parallax lerp
      mouseRef.current.x += (mouseRef.current.targetX - mouseRef.current.x) * 0.04;
      mouseRef.current.y += (mouseRef.current.targetY - mouseRef.current.y) * 0.04;

      const scroll = scrollRef.current;

      // ── GLIDING THROUGH THE MOUNTAIN PATHWAY ON SCROLL ────────────────────
      const t = THREE.MathUtils.clamp(scroll, 0, 0.999);
      const camTargetPos = flightCurve.getPointAt(t);

      // Look slightly ahead along the flight track so camera turns naturally with the valley
      const lookProgress = THREE.MathUtils.clamp(t + 0.07, 0, 1);
      const lookTargetPos = flightCurve.getPointAt(lookProgress);

      // Smoothly lerp camera position along the mountain pathway
      const targetCamX = camTargetPos.x + mouseRef.current.x * 2.2;
      const targetCamY = camTargetPos.y + mouseRef.current.y * 1.3;
      const targetCamZ = camTargetPos.z;

      camera.position.x += (targetCamX - camera.position.x) * 0.06;
      camera.position.y += (targetCamY - camera.position.y) * 0.06;
      camera.position.z += (targetCamZ - camera.position.z) * 0.06;

      // Look ahead along the mountain pathway with responsive mouse steering
      camera.lookAt(
        lookTargetPos.x + mouseRef.current.x * 1.8,
        lookTargetPos.y - 0.2 + mouseRef.current.y * 1.0,
        lookTargetPos.z
      );

      if (!prefersReducedMotion) {
        // Animate traveling energy pulses along the ground pathway
        pulses.forEach((p) => {
          p.progress += p.speed;
          if (p.progress > 1) p.progress = 0;
          const pt = groundCurve.getPointAt(p.progress);
          p.mesh.position.set(pt.x, pt.y + 0.15, pt.z);
        });

        // Rotate & pulse milestone crystal nodes
        milestoneNodes.forEach((node, idx) => {
          node.mesh.rotation.y = elapsed * 0.8 + idx;
          node.mesh.rotation.x = elapsed * 0.5 + idx;
          node.ring.rotation.z = elapsed * 0.4;
          const scale = 1 + Math.sin(elapsed * 2.0 + idx * 0.7) * 0.12;
          node.mesh.scale.set(scale, scale, scale);
        });

        // Floating Frost Crystals
        const fArr = frostGeom.attributes.position.array as Float32Array;
        for (let i = 0; i < frostCount; i++) {
          fArr[i * 3] += frostVelocities[i * 3];
          fArr[i * 3 + 1] += frostVelocities[i * 3 + 1];
          fArr[i * 3 + 2] += frostVelocities[i * 3 + 2];

          // Wrap around if below ground or past camera
          if (fArr[i * 3 + 1] < -3.5) {
            fArr[i * 3 + 1] = 22;
          }
        }
        frostGeom.attributes.position.needsUpdate = true;

        // Undulating Aurora Borealis wave
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

    // 16. Cleanup
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('scroll', handleScroll);
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
      coreLineMat.dispose();
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