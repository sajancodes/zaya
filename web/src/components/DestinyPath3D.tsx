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
    // Check WebGL availability
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

    // Check reduced motion
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // 1. Scene & Camera Setup
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x020407, 0.012);

    const camera = new THREE.PerspectiveCamera(
      60,
      window.innerWidth / window.innerHeight,
      0.1,
      800
    );
    camera.position.set(0, 2, 28);

    // 2. Renderer Setup
    const renderer = new THREE.WebGLRenderer({
      powerPreference: 'high-performance',
      antialias: true,
      alpha: true
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x020407, 0.95);
    container.appendChild(renderer.domElement);

    // 3. Create Persistent Destiny Path Spline
    // A long curving path extending from distance (z = -220) to foreground (z = 40)
    const baseControlPoints = [
      new THREE.Vector3(0, 0, -220),
      new THREE.Vector3(6, 4, -180),
      new THREE.Vector3(-8, -2, -140),
      new THREE.Vector3(10, 5, -100),
      new THREE.Vector3(-12, -3, -60),
      new THREE.Vector3(8, 2, -20),
      new THREE.Vector3(-6, -1, 15),
      new THREE.Vector3(0, 0, 45)
    ];

    const curve = new THREE.CatmullRomCurve3(baseControlPoints);
    curve.curveType = 'catmullrom';
    curve.tension = 0.5;

    const pathSamples = 400;
    const curvePoints = curve.getPoints(pathSamples);

    // Primary Core Path (Bright Cyan / White)
    const coreGeometry = new THREE.BufferGeometry().setFromPoints(curvePoints);
    const coreMaterial = new THREE.LineBasicMaterial({
      color: 0x49dfff,
      linewidth: 2,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending
    });
    const coreLine = new THREE.Line(coreGeometry, coreMaterial);
    scene.add(coreLine);

    // Secondary Ambient Glow Trail (Deep Electric Blue, wider)
    const glowMaterial = new THREE.LineBasicMaterial({
      color: 0x1e3a8a,
      linewidth: 4,
      transparent: true,
      opacity: 0.5,
      blending: THREE.AdditiveBlending
    });
    const glowLine = new THREE.Line(coreGeometry, glowMaterial);
    glowLine.position.y -= 0.15;
    scene.add(glowLine);

    // 4. Milestone Checkpoint Spheres Along the Path
    const milestonesGroup = new THREE.Group();
    const milestoneCount = 8;
    const milestoneSpheres: THREE.Mesh[] = [];

    const sphereGeom = new THREE.SphereGeometry(0.7, 16, 16);
    const majorSphereGeom = new THREE.SphereGeometry(1.2, 24, 24);

    for (let i = 0; i < milestoneCount; i++) {
      const u = (i + 1) / (milestoneCount + 1);
      const pos = curve.getPointAt(u);

      const isMajor = i % 2 === 0;
      const mat = new THREE.MeshBasicMaterial({
        color: isMajor ? 0xffffff : 0x49dfff,
        transparent: true,
        opacity: 0.85,
        blending: THREE.AdditiveBlending
      });

      const sphere = new THREE.Mesh(isMajor ? majorSphereGeom : sphereGeom, mat);
      sphere.position.copy(pos);

      // Add a soft halo ring around milestones
      const ringGeom = new THREE.RingGeometry(isMajor ? 1.4 : 0.9, isMajor ? 1.7 : 1.1, 32);
      const ringMat = new THREE.MeshBasicMaterial({
        color: 0x3478ff,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.45,
        blending: THREE.AdditiveBlending
      });
      const ring = new THREE.Mesh(ringGeom, ringMat);
      ring.rotation.x = Math.PI / 2;
      sphere.add(ring);

      milestonesGroup.add(sphere);
      milestoneSpheres.push(sphere);
    }
    scene.add(milestonesGroup);

    // 5. Floating Particle Traces along Path
    const isMobile = window.innerWidth < 768;
    const particleCount = isMobile ? 180 : 500;
    const particleGeom = new THREE.BufferGeometry();
    const particlePositions = new Float32Array(particleCount * 3);
    const particleSpeeds = new Float32Array(particleCount);
    const particleOffsets = new Float32Array(particleCount * 3);
    const particleCurveProgress = new Float32Array(particleCount);

    for (let i = 0; i < particleCount; i++) {
      particleCurveProgress[i] = Math.random();
      particleSpeeds[i] = 0.0003 + Math.random() * 0.0008;

      // Random radial displacement
      const angle = Math.random() * Math.PI * 2;
      const radius = 0.5 + Math.random() * 3.5;
      particleOffsets[i * 3] = Math.cos(angle) * radius;
      particleOffsets[i * 3 + 1] = Math.sin(angle) * radius;
      particleOffsets[i * 3 + 2] = (Math.random() - 0.5) * 2;

      const pt = curve.getPointAt(particleCurveProgress[i]);
      particlePositions[i * 3] = pt.x + particleOffsets[i * 3];
      particlePositions[i * 3 + 1] = pt.y + particleOffsets[i * 3 + 1];
      particlePositions[i * 3 + 2] = pt.z + particleOffsets[i * 3 + 2];
    }

    particleGeom.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));

    // Particle texture canvas
    const canvas = document.createElement('canvas');
    canvas.width = 32;
    canvas.height = 32;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      const gradient = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
      gradient.addColorStop(0, 'rgba(221, 251, 255, 1)');
      gradient.addColorStop(0.3, 'rgba(73, 223, 255, 0.6)');
      gradient.addColorStop(1, 'rgba(2, 4, 7, 0)');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, 32, 32);
    }
    const particleTexture = new THREE.CanvasTexture(canvas);

    const particleMaterial = new THREE.PointsMaterial({
      size: 1.2,
      map: particleTexture,
      transparent: true,
      opacity: 0.7,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });

    const particles = new THREE.Points(particleGeom, particleMaterial);
    scene.add(particles);

    // 6. Section Interactive Structures (3D Gestures, Spatial Engine, Waves)
    // Structure A: Waveform Geometry for Voice Section
    const waveGeom = new THREE.BufferGeometry();
    const wavePointsCount = 120;
    const wavePositions = new Float32Array(wavePointsCount * 3);
    for (let i = 0; i < wavePointsCount; i++) {
      const x = (i - 60) * 0.4;
      wavePositions[i * 3] = x;
      wavePositions[i * 3 + 1] = 0;
      wavePositions[i * 3 + 2] = -40;
    }
    waveGeom.setAttribute('position', new THREE.BufferAttribute(wavePositions, 3));
    const waveMat = new THREE.LineBasicMaterial({
      color: 0x49dfff,
      transparent: true,
      opacity: 0.65,
      blending: THREE.AdditiveBlending
    });
    const waveLine = new THREE.Line(waveGeom, waveMat);
    scene.add(waveLine);

    // Structure B: Stylized 3D Hand Skeleton Points
    const handGroup = new THREE.Group();
    handGroup.position.set(12, -4, -90);
    const handJointGeom = new THREE.SphereGeometry(0.35, 12, 12);
    const handJointMat = new THREE.MeshBasicMaterial({
      color: 0x49dfff,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending
    });

    // 21 Joint landmark points for hand skeleton
    const jointPositions = [
      [0, -2, 0], // Wrist
      [-1.2, -1.2, 0.2], [-1.8, -0.4, 0.4], [-2.2, 0.4, 0.5], [-2.5, 1.2, 0.6], // Thumb
      [-0.8, 0.2, 0.1], [-1.0, 1.2, 0.2], [-1.1, 2.0, 0.2], [-1.2, 2.7, 0.2], // Index
      [-0.1, 0.3, 0], [-0.1, 1.4, 0], [-0.1, 2.3, 0], [-0.1, 3.0, 0], // Middle
      [0.6, 0.2, -0.1], [0.8, 1.2, -0.1], [0.9, 1.9, -0.1], [1.0, 2.6, -0.1], // Ring
      [1.3, -0.2, -0.2], [1.6, 0.6, -0.3], [1.8, 1.3, -0.3], [2.0, 2.0, -0.3] // Pinky
    ];

    jointPositions.forEach((pos) => {
      const jointMesh = new THREE.Mesh(handJointGeom, handJointMat);
      jointMesh.position.set(pos[0], pos[1], pos[2]);
      handGroup.add(jointMesh);
    });

    // Bone links
    const bones = [
      [0, 1], [1, 2], [2, 3], [3, 4],
      [0, 5], [5, 6], [6, 7], [7, 8],
      [0, 9], [9, 10], [10, 11], [11, 12],
      [0, 13], [13, 14], [14, 15], [15, 16],
      [0, 17], [17, 18], [18, 19], [19, 20]
    ];
    bones.forEach(([from, to]) => {
      const bGeom = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(...jointPositions[from]),
        new THREE.Vector3(...jointPositions[to])
      ]);
      const bMat = new THREE.LineBasicMaterial({
        color: 0x3478ff,
        transparent: true,
        opacity: 0.5,
        blending: THREE.AdditiveBlending
      });
      const bLine = new THREE.Line(bGeom, bMat);
      handGroup.add(bLine);
    });
    scene.add(handGroup);

    // Structure C: 3D Spatial Wireframe Polyhedron
    const spatialGeom = new THREE.IcosahedronGeometry(4.5, 1);
    const spatialWireframe = new THREE.WireframeGeometry(spatialGeom);
    const spatialMat = new THREE.LineBasicMaterial({
      color: 0x49dfff,
      transparent: true,
      opacity: 0.4,
      blending: THREE.AdditiveBlending
    });
    const spatialMesh = new THREE.LineSegments(spatialWireframe, spatialMat);
    spatialMesh.position.set(-14, 2, -130);
    scene.add(spatialMesh);

    // 7. Event Handlers
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

    // 8. Animation & Render Loop
    let animationFrameId: number;
    let clock = new THREE.Clock();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      if (document.hidden) return;

      const elapsedTime = clock.getElapsedTime();
      const delta = clock.getDelta();

      // Smooth mouse lerping
      mouseRef.current.x += (mouseRef.current.targetX - mouseRef.current.x) * 0.05;
      mouseRef.current.y += (mouseRef.current.targetY - mouseRef.current.y) * 0.05;

      const scroll = scrollRef.current;

      // Camera flies forward along the Z-axis driven by scroll
      // Z goes from 35 (Hero) down to -200 (Roadmap/Footer)
      const targetZ = 35 - scroll * 240;
      const targetY = 1.8 + Math.sin(scroll * Math.PI * 4) * 2.5 + mouseRef.current.y * 1.5;
      const targetX = Math.cos(scroll * Math.PI * 3) * 4.0 + mouseRef.current.x * 2.5;

      camera.position.z += (targetZ - camera.position.z) * 0.08;
      camera.position.y += (targetY - camera.position.y) * 0.08;
      camera.position.x += (targetX - camera.position.x) * 0.08;

      // Look slightly ahead along the path
      const lookAtZ = camera.position.z - 30;
      const lookAtX = Math.sin(elapsedTime * 0.5) * 0.8;
      camera.lookAt(lookAtX, 0, lookAtZ);

      // Animate Particles
      const positions = particleGeom.attributes.position.array as Float32Array;
      for (let i = 0; i < particleCount; i++) {
        particleCurveProgress[i] += particleSpeeds[i];
        if (particleCurveProgress[i] > 1) {
          particleCurveProgress[i] = 0;
        }

        const pointOnCurve = curve.getPointAt(particleCurveProgress[i]);
        positions[i * 3] = pointOnCurve.x + particleOffsets[i * 3];
        positions[i * 3 + 1] = pointOnCurve.y + particleOffsets[i * 3 + 1];
        positions[i * 3 + 2] = pointOnCurve.z + particleOffsets[i * 3 + 2];
      }
      particleGeom.attributes.position.needsUpdate = true;

      // Pulse milestones
      milestoneSpheres.forEach((sphere, index) => {
        const scale = 1 + Math.sin(elapsedTime * 2 + index) * 0.15;
        sphere.scale.set(scale, scale, scale);
      });

      // Animate voice wave
      const wavePos = waveGeom.attributes.position.array as Float32Array;
      for (let i = 0; i < wavePointsCount; i++) {
        const x = (i - 60) * 0.4;
        const wave = Math.sin(x * 0.3 + elapsedTime * 4.0) * Math.cos(x * 0.15 + elapsedTime * 2.0);
        wavePos[i * 3 + 1] = wave * 2.2;
      }
      waveGeom.attributes.position.needsUpdate = true;

      // Animate spatial polyhedron
      spatialMesh.rotation.x = elapsedTime * 0.2;
      spatialMesh.rotation.y = elapsedTime * 0.3;

      // Animate hand skeleton subtle floating
      handGroup.rotation.y = Math.sin(elapsedTime * 0.8) * 0.15;
      handGroup.position.y = -4 + Math.sin(elapsedTime * 1.2) * 0.4;

      renderer.render(scene, camera);
    };

    if (!prefersReducedMotion) {
      animate();
    } else {
      renderer.render(scene, camera);
    }

    // Cleanup
    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', handleResize);
      if (container && renderer.domElement) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
      coreGeometry.dispose();
      glowMaterial.dispose();
      particleGeom.dispose();
      particleMaterial.dispose();
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
          zIndex: -1,
          background: 'radial-gradient(circle at 50% 30%, #0d2847 0%, #020407 80%)',
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
