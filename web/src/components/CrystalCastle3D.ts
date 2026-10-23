import * as THREE from 'three';

/**
 * Creates the Big 3D Crystal Castle (The Ice Citadel of Zaya).
 * Architected with faceted crystalline towers, soaring spires, stepped glacial dais,
 * glowing crystal windows, floating arcane shards, orbiting celestial rings,
 * and a radiant pulsing Heart of Ice core.
 */
export interface CrystalCastleInstance {
  group: THREE.Group;
  update: (elapsed: number) => void;
  dispose: () => void;
}

export function createCrystalCastle(): CrystalCastleInstance {
  const castleGroup = new THREE.Group();
  castleGroup.name = 'CrystalCastle';

  // Position the castle at the end of the mountain pass (destination of the destiny path)
  castleGroup.position.set(1.0, 0.5, -132);

  const geometries: THREE.BufferGeometry[] = [];
  const materials: THREE.Material[] = [];

  const trackGeom = <T extends THREE.BufferGeometry>(g: T): T => {
    geometries.push(g);
    return g;
  };
  const trackMat = <T extends THREE.Material>(m: T): T => {
    materials.push(m);
    return m;
  };

  // ── 1. MATERIALS ──────────────────────────────────────────────────────────
  // Deep Glacial Ice (citadel foundations & bastion bodies)
  const matDeepIce = trackMat(
    new THREE.MeshStandardMaterial({
      color: 0x092238,
      emissive: 0x051a2e,
      emissiveIntensity: 0.45,
      roughness: 0.22,
      metalness: 0.35,
      flatShading: true
    })
  );

  // Crystalline Wall & Tower Flutes (reflective ice facets)
  const matIceWall = trackMat(
    new THREE.MeshStandardMaterial({
      color: 0x144265,
      emissive: 0x1b5885,
      emissiveIntensity: 0.45,
      roughness: 0.14,
      metalness: 0.5,
      flatShading: true
    })
  );

  // Translucent Ice Crystal Prisms (spires, steeples, floating shards)
  const matCrystalPrism = trackMat(
    new THREE.MeshPhysicalMaterial({
      color: 0x88e7ff,
      emissive: 0x2278a8,
      emissiveIntensity: 0.55,
      roughness: 0.08,
      metalness: 0.25,
      transmission: 0.55,
      thickness: 3.0,
      transparent: true,
      opacity: 0.92,
      flatShading: true
    })
  );

  // Luminous Cyan Trim & Crests
  const matLuminousCyan = trackMat(
    new THREE.MeshStandardMaterial({
      color: 0x5feaff,
      emissive: 0x5feaff,
      emissiveIntensity: 0.85,
      roughness: 0.1,
      metalness: 0.2,
      flatShading: true
    })
  );

  // Glowing Crystal Windows & Light Slits
  const matGlowingWindow = trackMat(
    new THREE.MeshBasicMaterial({
      color: 0xc4f7ff,
      blending: THREE.AdditiveBlending
    })
  );

  // Pure Starlight / Cyan Additive Glow for Cores & Beacons
  const matBeacon = trackMat(
    new THREE.MeshBasicMaterial({
      color: 0xffffff,
      blending: THREE.AdditiveBlending
    })
  );

  const matCyanGlow = trackMat(
    new THREE.MeshBasicMaterial({
      color: 0x5feaff,
      transparent: true,
      opacity: 0.75,
      blending: THREE.AdditiveBlending
    })
  );

  // ── 2. STEPPED GLACIAL DAIS (TERRACED CITADEL FOUNDATION) ──────────────────
  // Tier 1: Wide octagonal bedrock bastion
  const tier1Geom = trackGeom(new THREE.CylinderGeometry(23, 26, 3.8, 8));
  const tier1Mesh = new THREE.Mesh(tier1Geom, matDeepIce);
  tier1Mesh.position.set(0, 1.9, 0);
  castleGroup.add(tier1Mesh);

  // Tier 2: Mid-level stepped terrace
  const tier2Geom = trackGeom(new THREE.CylinderGeometry(17, 19, 3.2, 8));
  const tier2Mesh = new THREE.Mesh(tier2Geom, matIceWall);
  tier2Mesh.position.set(0, 5.0, 0);
  castleGroup.add(tier2Mesh);

  // Tier 3: Inner palace courtyard
  const tier3Geom = trackGeom(new THREE.CylinderGeometry(12.5, 14, 2.6, 8));
  const tier3Mesh = new THREE.Mesh(tier3Geom, matIceWall);
  tier3Mesh.position.set(0, 7.6, 0);
  castleGroup.add(tier3Mesh);

  // Radial crystalline buttresses anchoring the citadel into the ice
  const buttressGeom = trackGeom(new THREE.ConeGeometry(2.4, 9, 5));
  for (let i = 0; i < 8; i++) {
    const angle = (i * Math.PI) / 4;
    const bMesh = new THREE.Mesh(buttressGeom, matDeepIce);
    bMesh.position.set(Math.cos(angle) * 22, 1.2, Math.sin(angle) * 22);
    bMesh.rotation.y = angle;
    bMesh.rotation.z = Math.PI / 4.5;
    castleGroup.add(bMesh);
  }

  // ── 3. GRAND ENTRANCE CAUSEWAY & GATEHOUSE ────────────────────────────────
  // Causeway connecting courtyard (z=7.5, y=7.6) down to destiny path (z=22, y=0.7)
  const causewayLength = 16.0;
  const causewaySlope = Math.atan2(6.9, 14.5); // ~0.44 rad
  const causewayGeom = trackGeom(new THREE.BoxGeometry(6.4, 1.2, causewayLength));
  const causewayMesh = new THREE.Mesh(causewayGeom, matIceWall);
  causewayMesh.position.set(0, 4.15, 14.75);
  causewayMesh.rotation.x = causewaySlope;
  castleGroup.add(causewayMesh);

  // Luminous centerline on the bridge connecting with the destiny path
  const bridgeLineGeom = trackGeom(new THREE.BoxGeometry(0.5, 0.15, causewayLength - 0.2));
  const bridgeLineMesh = new THREE.Mesh(bridgeLineGeom, matBeacon);
  bridgeLineMesh.position.set(0, 4.82, 14.75);
  bridgeLineMesh.rotation.x = causewaySlope;
  castleGroup.add(bridgeLineMesh);

  // Causeway balustrades & glowing lantern pylons
  const pylonGeom = trackGeom(new THREE.CylinderGeometry(0.35, 0.45, 2.2, 6));
  const lanternGeom = trackGeom(new THREE.OctahedronGeometry(0.4, 0));
  [-3.2, 3.2].forEach((xOffset) => {
    for (let p = 0; p < 4; p++) {
      const t = p / 3;
      const zOffset = 8.5 + t * 13.0;
      const yOffset = 7.6 - t * 6.8;

      const pylon = new THREE.Mesh(pylonGeom, matIceWall);
      pylon.position.set(xOffset, yOffset + 0.6, zOffset);
      castleGroup.add(pylon);

      const lantern = new THREE.Mesh(lanternGeom, matCyanGlow);
      lantern.position.set(xOffset, yOffset + 1.9, zOffset);
      castleGroup.add(lantern);
    }
  });

  // Grand Arch Gatehouse
  const gateArchGroup = new THREE.Group();
  gateArchGroup.position.set(0, 8.8, 8.5);

  const gatePillarGeom = trackGeom(new THREE.CylinderGeometry(1.2, 1.5, 9.0, 6));
  const leftPillar = new THREE.Mesh(gatePillarGeom, matIceWall);
  leftPillar.position.set(-3.2, 0, 0);
  gateArchGroup.add(leftPillar);

  const rightPillar = new THREE.Mesh(gatePillarGeom, matIceWall);
  rightPillar.position.set(3.2, 0, 0);
  gateArchGroup.add(rightPillar);

  // Gatehouse Spire Steeples
  const gateSpireGeom = trackGeom(new THREE.ConeGeometry(1.4, 7.5, 6));
  const leftGateSpire = new THREE.Mesh(gateSpireGeom, matCrystalPrism);
  leftGateSpire.position.set(-3.2, 8.0, 0);
  gateArchGroup.add(leftGateSpire);

  const rightGateSpire = new THREE.Mesh(gateSpireGeom, matCrystalPrism);
  rightGateSpire.position.set(3.2, 8.0, 0);
  gateArchGroup.add(rightGateSpire);

  // Pointed Gothic Crystal Archway Beam
  const archBeamGeom = trackGeom(new THREE.BoxGeometry(7.2, 1.4, 1.6));
  const archBeam = new THREE.Mesh(archBeamGeom, matLuminousCyan);
  archBeam.position.set(0, 4.6, 0);
  gateArchGroup.add(archBeam);

  // Arch Keystone Crystal
  const keystoneGeom = trackGeom(new THREE.OctahedronGeometry(1.1, 0));
  const keystone = new THREE.Mesh(keystoneGeom, matBeacon);
  keystone.position.set(0, 5.8, 0.4);
  keystone.scale.set(0.9, 1.4, 0.9);
  gateArchGroup.add(keystone);

  // Shimmering Crystal Energy Curtain inside the gate
  const curtainGeom = trackGeom(new THREE.PlaneGeometry(4.8, 6.8));
  const curtainMat = trackMat(
    new THREE.MeshBasicMaterial({
      color: 0x5feaff,
      transparent: true,
      opacity: 0.35,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending
    })
  );
  const curtain = new THREE.Mesh(curtainGeom, curtainMat);
  curtain.position.set(0, 1.6, 0);
  gateArchGroup.add(curtain);

  castleGroup.add(gateArchGroup);

  // ── 4. FOUR GRAND CORNER BASTION TOWERS ────────────────────────────────────
  const bastionPositions = [
    { x: -10.5, z: 6.5, height: 16, steepleH: 12, radius: 2.7 },
    { x: 10.5, z: 6.5, height: 16, steepleH: 12, radius: 2.7 },
    { x: -11.5, z: -8.5, height: 22, steepleH: 15, radius: 2.9 },
    { x: 11.5, z: -8.5, height: 22, steepleH: 15, radius: 2.9 }
  ];

  bastionPositions.forEach((b) => {
    const towerGroup = new THREE.Group();
    towerGroup.position.set(b.x, 8.0, b.z);

    const bodyGeom = trackGeom(new THREE.CylinderGeometry(b.radius * 0.9, b.radius, b.height, 6));
    const bodyMesh = new THREE.Mesh(bodyGeom, matIceWall);
    bodyMesh.position.set(0, b.height / 2, 0);
    towerGroup.add(bodyMesh);

    const corbelGeom = trackGeom(
      new THREE.CylinderGeometry(b.radius * 1.25, b.radius * 0.95, 1.4, 6)
    );
    const corbelMesh = new THREE.Mesh(corbelGeom, matLuminousCyan);
    corbelMesh.position.set(0, b.height + 0.6, 0);
    towerGroup.add(corbelMesh);

    const steepleGeom = trackGeom(
      new THREE.ConeGeometry(b.radius * 1.2, b.steepleH, 6)
    );
    const steepleMesh = new THREE.Mesh(steepleGeom, matCrystalPrism);
    steepleMesh.position.set(0, b.height + 1.3 + b.steepleH / 2, 0);
    towerGroup.add(steepleMesh);

    const finialGeom = trackGeom(new THREE.OctahedronGeometry(0.7, 0));
    const finialMesh = new THREE.Mesh(finialGeom, matBeacon);
    finialMesh.position.set(0, b.height + 1.5 + b.steepleH, 0);
    towerGroup.add(finialMesh);

    const windowGeom = trackGeom(new THREE.BoxGeometry(0.35, 2.4, 0.4));
    for (let w = 0; w < 3; w++) {
      const rotY = (w * Math.PI * 2) / 3;
      const win = new THREE.Mesh(windowGeom, matGlowingWindow);
      win.position.set(
        Math.sin(rotY) * (b.radius * 0.95),
        b.height * 0.55 + (w % 2) * 2.5,
        Math.cos(rotY) * (b.radius * 0.95)
      );
      win.rotation.y = rotY;
      towerGroup.add(win);
    }

    castleGroup.add(towerGroup);
  });

  // Connecting crystalline rampart curtain walls
  const wallSegments = [
    { fromX: -10.5, fromZ: 6.5, toX: -3.8, toZ: 8.5 },
    { fromX: 10.5, fromZ: 6.5, toX: 3.8, toZ: 8.5 },
    { fromX: -10.5, fromZ: 6.5, toX: -11.5, toZ: -8.5 },
    { fromX: 10.5, fromZ: 6.5, toX: 11.5, toZ: -8.5 },
    { fromX: -11.5, fromZ: -8.5, toX: 11.5, toZ: -8.5 }
  ];

  wallSegments.forEach((w) => {
    const dx = w.toX - w.fromX;
    const dz = w.toZ - w.fromZ;
    const len = Math.sqrt(dx * dx + dz * dz);
    const angle = Math.atan2(dx, dz);

    const wallGeom = trackGeom(new THREE.BoxGeometry(1.6, 7.5, len));
    const wallMesh = new THREE.Mesh(wallGeom, matIceWall);
    wallMesh.position.set((w.fromX + w.toX) / 2, 11.5, (w.fromZ + w.toZ) / 2);
    wallMesh.rotation.y = angle;
    castleGroup.add(wallMesh);

    const parapetGeom = trackGeom(new THREE.BoxGeometry(1.9, 0.6, len));
    const parapetMesh = new THREE.Mesh(parapetGeom, matLuminousCyan);
    parapetMesh.position.set((w.fromX + w.toX) / 2, 15.5, (w.fromZ + w.toZ) / 2);
    parapetMesh.rotation.y = angle;
    castleGroup.add(parapetMesh);
  });

  // ── 5. THE GREAT CITADEL KEEP (CENTRAL PALACE) ─────────────────────────────
  // Lower Grand Hall (12-sided faceted crystal keep base)
  const hallGeom = trackGeom(new THREE.CylinderGeometry(7.6, 8.8, 14, 12));
  const hallMesh = new THREE.Mesh(hallGeom, matIceWall);
  hallMesh.position.set(0, 15.5, -0.5);
  castleGroup.add(hallMesh);

  // Arched crystalline window slits circling the Great Hall
  const hallWinGeom = trackGeom(new THREE.BoxGeometry(0.5, 4.2, 0.4));
  for (let i = 0; i < 8; i++) {
    const angle = (i * Math.PI) / 4 + 0.2;
    const hWin = new THREE.Mesh(hallWinGeom, matGlowingWindow);
    hWin.position.set(
      Math.sin(angle) * 8.0,
      16.5,
      Math.cos(angle) * 8.0 - 0.5
    );
    hWin.rotation.y = angle;
    castleGroup.add(hWin);
  }

  // Mid-Tier Observation Gallery & Balcony
  const galleryGeom = trackGeom(new THREE.CylinderGeometry(5.8, 7.2, 10, 8));
  const galleryMesh = new THREE.Mesh(galleryGeom, matIceWall);
  galleryMesh.position.set(0, 27.5, -0.5);
  castleGroup.add(galleryMesh);

  // Flying Buttresses connecting outer towers into mid citadel
  const buttressCylGeom = trackGeom(new THREE.CylinderGeometry(0.4, 0.5, 8.5, 5));
  [-1, 1].forEach((sign) => {
    const fButtress = new THREE.Mesh(buttressCylGeom, matCrystalPrism);
    fButtress.position.set(sign * 7.5, 22.5, 1.5);
    fButtress.rotation.z = sign * 0.55;
    fButtress.rotation.x = -0.2;
    castleGroup.add(fButtress);

    const rButtress = new THREE.Mesh(buttressCylGeom, matCrystalPrism);
    rButtress.position.set(sign * 8.0, 24.5, -5.5);
    rButtress.rotation.z = sign * 0.55;
    rButtress.rotation.x = 0.2;
    castleGroup.add(rButtress);
  });

  // Four Satellite Turret Spires around the Gallery
  for (let s = 0; s < 4; s++) {
    const sAngle = (s * Math.PI) / 2 + Math.PI / 4;
    const sx = Math.sin(sAngle) * 5.6;
    const sz = Math.cos(sAngle) * 5.6 - 0.5;

    const turretGeom = trackGeom(new THREE.CylinderGeometry(0.9, 1.1, 7, 6));
    const turret = new THREE.Mesh(turretGeom, matIceWall);
    turret.position.set(sx, 30.5, sz);
    castleGroup.add(turret);

    const tSpireGeom = trackGeom(new THREE.ConeGeometry(1.2, 8.0, 6));
    const tSpire = new THREE.Mesh(tSpireGeom, matCrystalPrism);
    tSpire.position.set(sx, 38.0, sz);
    castleGroup.add(tSpire);
  }

  // ── 6. THE HIGH IMPERIAL SPIRE (SANCTUARY OF THE ICE PRINCESS) ─────────────
  // Soaring, razor-faceted octagonal spire tower
  const spireBodyGeom = trackGeom(new THREE.CylinderGeometry(2.4, 4.4, 18, 8));
  const spireBody = new THREE.Mesh(spireBodyGeom, matIceWall);
  spireBody.position.set(0, 41.5, -0.5);
  castleGroup.add(spireBody);

  // Crown of Ice: High crystalline needle pinnacle reaching high into the sky
  const pinnacleGeom = trackGeom(new THREE.ConeGeometry(2.8, 22, 8));
  const pinnacle = new THREE.Mesh(pinnacleGeom, matCrystalPrism);
  pinnacle.position.set(0, 61.5, -0.5);
  castleGroup.add(pinnacle);

  // Apex Crown Diamond Finial
  const apexDiamondGeom = trackGeom(new THREE.OctahedronGeometry(1.3, 0));
  const apexDiamond = new THREE.Mesh(apexDiamondGeom, matBeacon);
  apexDiamond.position.set(0, 73.0, -0.5);
  apexDiamond.scale.set(0.8, 2.0, 0.8);
  castleGroup.add(apexDiamond);

  // Eight radiating satellite crystal needles forming the royal crown
  const crownNeedleGeom = trackGeom(new THREE.ConeGeometry(0.55, 6.5, 5));
  for (let c = 0; c < 8; c++) {
    const cAngle = (c * Math.PI) / 4;
    const needle = new THREE.Mesh(crownNeedleGeom, matCrystalPrism);
    needle.position.set(
      Math.sin(cAngle) * 2.8,
      52.0,
      Math.cos(cAngle) * 2.8 - 0.5
    );
    needle.rotation.y = cAngle;
    needle.rotation.z = Math.sin(cAngle) * 0.35;
    needle.rotation.x = Math.cos(cAngle) * 0.35;
    castleGroup.add(needle);
  }

  // ── 7. THE HEART OF ICE (RADIANT HOVERING CORE) ───────────────────────────
  const heartGroup = new THREE.Group();
  heartGroup.position.set(0, 36.5, -0.5);

  const gemGeom = trackGeom(new THREE.OctahedronGeometry(2.4, 0));
  const gemMesh = new THREE.Mesh(gemGeom, matBeacon);
  gemMesh.scale.set(1.0, 1.7, 1.0);
  heartGroup.add(gemMesh);

  const cageGeom = trackGeom(new THREE.IcosahedronGeometry(3.2, 0));
  const cageMat = trackMat(
    new THREE.MeshBasicMaterial({
      color: 0x5feaff,
      wireframe: true,
      transparent: true,
      opacity: 0.65,
      blending: THREE.AdditiveBlending
    })
  );
  const cageMesh = new THREE.Mesh(cageGeom, cageMat);
  heartGroup.add(cageMesh);

  // Castle Core Point Light casting real cyan radiance on peaks and walls
  const coreLight = new THREE.PointLight(0x5feaff, 5.0, 95, 1.1);
  coreLight.position.set(0, 0, 0);
  heartGroup.add(coreLight);

  castleGroup.add(heartGroup);

  // ── 8. CELESTIAL ORBITING CRYSTAL RINGS ───────────────────────────────────
  const ring1Geom = trackGeom(new THREE.TorusGeometry(7.6, 0.18, 8, 48));
  const ring1Mesh = new THREE.Mesh(ring1Geom, matLuminousCyan);
  ring1Mesh.position.set(0, 54.0, -0.5);
  ring1Mesh.rotation.x = Math.PI / 2.8;
  castleGroup.add(ring1Mesh);

  const ring2Geom = trackGeom(new THREE.TorusGeometry(10.2, 0.14, 8, 48));
  const ring2Mesh = new THREE.Mesh(ring2Geom, matLuminousCyan);
  ring2Mesh.position.set(0, 54.0, -0.5);
  ring2Mesh.rotation.x = -Math.PI / 3.2;
  castleGroup.add(ring2Mesh);

  // ── 9. LEVITATING AURA CRYSTAL SHARDS ─────────────────────────────────────
  const shardCount = 14;
  const shards: {
    mesh: THREE.Mesh;
    basePos: THREE.Vector3;
    bobSpeed: number;
    bobAmount: number;
    rotSpeedX: number;
    rotSpeedY: number;
    rotSpeedZ: number;
    phase: number;
  }[] = [];

  const shardGeomA = trackGeom(new THREE.OctahedronGeometry(1.3, 0));
  const shardGeomB = trackGeom(new THREE.ConeGeometry(0.85, 3.5, 5));

  for (let i = 0; i < shardCount; i++) {
    const angle = (i * Math.PI * 2) / shardCount + Math.random() * 0.3;
    const dist = 11.5 + (i % 4) * 3.8;
    const yBase = 18 + (i % 5) * 9.0;
    const xBase = Math.sin(angle) * dist;
    const zBase = Math.cos(angle) * dist - 0.5;

    const useCone = i % 2 === 0;
    const sMesh = new THREE.Mesh(useCone ? shardGeomB : shardGeomA, matCrystalPrism);
    sMesh.position.set(xBase, yBase, zBase);
    sMesh.scale.setScalar(0.75 + (i % 3) * 0.35);

    castleGroup.add(sMesh);

    shards.push({
      mesh: sMesh,
      basePos: new THREE.Vector3(xBase, yBase, zBase),
      bobSpeed: 1.2 + (i % 3) * 0.5,
      bobAmount: 0.8 + (i % 4) * 0.35,
      rotSpeedX: (Math.random() - 0.5) * 0.8,
      rotSpeedY: 0.6 + Math.random() * 0.6,
      rotSpeedZ: (Math.random() - 0.5) * 0.8,
      phase: i * 0.7
    });
  }

  // ── 10. ANIMATION UPDATE LOOP ─────────────────────────────────────────────
  const update = (elapsed: number) => {
    // Pulse the Heart of Ice
    const pulse = Math.sin(elapsed * 2.8);
    const gemScale = 1.0 + pulse * 0.12;
    gemMesh.scale.set(gemScale, gemScale * 1.7, gemScale);
    cageMesh.rotation.y = elapsed * 0.6;
    cageMesh.rotation.x = elapsed * 0.4;
    coreLight.intensity = 4.5 + pulse * 1.8;

    // Slowly rotate celestial crown rings
    ring1Mesh.rotation.z = elapsed * 0.35;
    ring2Mesh.rotation.z = -elapsed * 0.25;

    // Apex diamond slow rotation
    apexDiamond.rotation.y = elapsed * 0.8;

    // Animate levitating crystal shards
    shards.forEach((s) => {
      const bob = Math.sin(elapsed * s.bobSpeed + s.phase) * s.bobAmount;
      s.mesh.position.y = s.basePos.y + bob;
      s.mesh.rotation.x += s.rotSpeedX * 0.02;
      s.mesh.rotation.y += s.rotSpeedY * 0.02;
      s.mesh.rotation.z += s.rotSpeedZ * 0.02;
    });
  };

  // ── 11. CLEANUP ───────────────────────────────────────────────────────────
  const dispose = () => {
    geometries.forEach((g) => g.dispose());
    materials.forEach((m) => m.dispose());
    castleGroup.clear();
  };

  return {
    group: castleGroup,
    update,
    dispose
  };
}
