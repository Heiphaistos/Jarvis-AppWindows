import { useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { useJarvisStore, getTtsAnalyser, accentOf } from "../../stores/jarvisStore";
import type { HoloStyle, HoloDensity, HoloSpeed } from "../../stores/jarvisStore";
import type { JarvisStatus } from "../../types";

const DENSITY_COUNTS: Record<HoloDensity, number> = { low: 3000, normal: 6000, high: 11000 };
const SPEED_FACTORS: Record<HoloSpeed, number> = { slow: 0.5, normal: 1, fast: 1.8 };

/** Couleur pilotée par le statut — idle suit l'accent du thème actif. */
function statusColor(status: JarvisStatus): string {
  const s = useJarvisStore.getState();
  const accent = accentOf(s.theme, s.customAccent);
  const map: Record<JarvisStatus, string> = {
    idle: accent,
    standby: "#3388cc",
    listening: "#00ff88",
    processing: "#ffaa00",
    speaking: "#8866ff",
    error: "#ff3333",
  };
  return map[status];
}

/** Niveau audio TTS [0,1] — 0 si pas d'analyseur ou silence. */
function readTtsLevel(buf: Uint8Array): number {
  const analyser = getTtsAnalyser();
  if (!analyser) return 0;
  analyser.getByteFrequencyData(buf as Uint8Array<ArrayBuffer>);
  let sum = 0;
  for (let i = 0; i < buf.length; i++) sum += buf[i];
  return sum / (buf.length * 255);
}

// ── Générateurs de nuages de points par style ────────────────────────────────

function genSphere(PARTICLE_COUNT: number): Float32Array {
  const pos = new Float32Array(PARTICLE_COUNT * 3);
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    // Distribution uniforme sur la sphère (méthode de Marsaglia)
    const u = Math.random() * 2 - 1;
    const theta = Math.random() * Math.PI * 2;
    const s = Math.sqrt(1 - u * u);
    const r = 1.55 + (Math.random() - 0.5) * 0.12;
    pos[i * 3] = s * Math.cos(theta) * r;
    pos[i * 3 + 1] = u * r;
    pos[i * 3 + 2] = s * Math.sin(theta) * r;
  }
  return pos;
}

function genReactor(PARTICLE_COUNT: number): Float32Array {
  // Anneaux concentriques denses face caméra + moyeu central — arc reactor
  const pos = new Float32Array(PARTICLE_COUNT * 3);
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    const ring = i % 4;
    const theta = Math.random() * Math.PI * 2;
    let r: number;
    if (ring === 0) r = 0.35 + Math.random() * 0.25;            // moyeu
    else r = 0.9 + ring * 0.42 + (Math.random() - 0.5) * 0.1;   // 3 anneaux
    pos[i * 3] = Math.cos(theta) * r;
    pos[i * 3 + 1] = Math.sin(theta) * r;
    pos[i * 3 + 2] = (Math.random() - 0.5) * 0.14;
  }
  return pos;
}

function genGalaxy(PARTICLE_COUNT: number): Float32Array {
  // Spirale à 3 bras, légèrement bombée au centre
  const pos = new Float32Array(PARTICLE_COUNT * 3);
  const ARMS = 3;
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    const arm = i % ARMS;
    const t = Math.pow(Math.random(), 0.6);            // densité vers le centre
    const r = 0.25 + t * 2.1;
    const spin = t * 4.2;                               // enroulement
    const theta = (arm / ARMS) * Math.PI * 2 + spin + (Math.random() - 0.5) * 0.45;
    const thickness = (1 - t) * 0.32 + 0.04;
    pos[i * 3] = Math.cos(theta) * r;
    pos[i * 3 + 1] = (Math.random() - 0.5) * thickness;
    pos[i * 3 + 2] = Math.sin(theta) * r;
  }
  return pos;
}

function genDna(PARTICLE_COUNT: number): Float32Array {
  // Double hélice verticale + barreaux
  const pos = new Float32Array(PARTICLE_COUNT * 3);
  const TURNS = 3.2;
  const HEIGHT = 4.2;
  const R = 0.85;
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    const kind = i % 5; // 2 brins denses + 1 particule de barreau sur 5
    const t = Math.random();
    const angle = t * Math.PI * 2 * TURNS;
    const y = (t - 0.5) * HEIGHT;
    if (kind < 2) {
      const strand = kind === 0 ? 0 : Math.PI;
      pos[i * 3] = Math.cos(angle + strand) * R + (Math.random() - 0.5) * 0.06;
      pos[i * 3 + 1] = y;
      pos[i * 3 + 2] = Math.sin(angle + strand) * R + (Math.random() - 0.5) * 0.06;
    } else if (kind < 4) {
      // second passage des brins (densité)
      const strand = kind === 2 ? 0 : Math.PI;
      pos[i * 3] = Math.cos(angle + strand) * R;
      pos[i * 3 + 1] = y;
      pos[i * 3 + 2] = Math.sin(angle + strand) * R;
    } else {
      // barreau entre les deux brins
      const mix = Math.random();
      pos[i * 3] = Math.cos(angle) * R * (1 - 2 * mix);
      pos[i * 3 + 1] = y;
      pos[i * 3 + 2] = Math.sin(angle) * R * (1 - 2 * mix);
    }
  }
  return pos;
}

function genMatrix(PARTICLE_COUNT: number): Float32Array {
  // Grille cubique de points — cube holographique
  const pos = new Float32Array(PARTICLE_COUNT * 3);
  const SIDE = Math.round(Math.cbrt(PARTICLE_COUNT));
  const SPACING = 2.6 / SIDE;
  let i = 0;
  for (let x = 0; x < SIDE && i < PARTICLE_COUNT; x++)
    for (let y = 0; y < SIDE && i < PARTICLE_COUNT; y++)
      for (let z = 0; z < SIDE && i < PARTICLE_COUNT; z++, i++) {
        pos[i * 3] = (x - SIDE / 2) * SPACING;
        pos[i * 3 + 1] = (y - SIDE / 2) * SPACING;
        pos[i * 3 + 2] = (z - SIDE / 2) * SPACING;
      }
  return pos;
}

function genVortex(PARTICLE_COUNT: number): Float32Array {
  // Tourbillon conique — entonnoir de particules
  const pos = new Float32Array(PARTICLE_COUNT * 3);
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    const t = Math.pow(Math.random(), 0.7);
    const y = (t - 0.5) * 3.6;
    const r = 0.15 + (1 - t) * 1.9 + (Math.random() - 0.5) * 0.15;
    const theta = t * 14 + Math.random() * Math.PI * 2 * 0.12 + (i % 2) * Math.PI;
    pos[i * 3] = Math.cos(theta) * r;
    pos[i * 3 + 1] = y;
    pos[i * 3 + 2] = Math.sin(theta) * r;
  }
  return pos;
}

const GENERATORS: Record<HoloStyle, (n: number) => Float32Array> = {
  sphere: genSphere,
  reactor: genReactor,
  galaxy: genGalaxy,
  dna: genDna,
  matrix: genMatrix,
  vortex: genVortex,
};

function ParticleCloud({ style, count, speedFactor }: { style: HoloStyle; count: number; speedFactor: number }) {
  const points = useRef<THREE.Points>(null);
  const material = useRef<THREE.PointsMaterial>(null);
  const freqBuf = useMemo(() => new Uint8Array(256), []);
  const color = useRef(new THREE.Color(statusColor("idle")));

  const positions = useMemo(() => GENERATORS[style](count), [style, count]);

  useFrame(({ clock }) => {
    if (!points.current || !material.current) return;
    const status = useJarvisStore.getState().status;
    const t = clock.elapsedTime;
    const level = status === "speaking" ? readTtsLevel(freqBuf) : 0;
    const speed =
      (status === "processing" ? 0.5 : status === "listening" ? 0.25 : 0.1) * speedFactor;

    if (style === "reactor") {
      // Face caméra : rotation dans le plan écran uniquement
      points.current.rotation.z = t * speed * 1.6;
      points.current.rotation.x = 0;
      points.current.rotation.y = 0;
    } else if (style === "galaxy") {
      points.current.rotation.y = t * speed * 1.8;
      points.current.rotation.x = 0.5;                 // vue inclinée
    } else if (style === "dna") {
      points.current.rotation.y = t * speed * 2.2;
      points.current.rotation.x = 0.12;
    } else if (style === "matrix") {
      points.current.rotation.y = t * speed * 0.9;
      points.current.rotation.x = Math.sin(t * 0.15) * 0.35;
    } else if (style === "vortex") {
      points.current.rotation.y = t * speed * 3.0;
      points.current.rotation.x = 0.1;
    } else {
      points.current.rotation.y = t * speed;
      points.current.rotation.x = Math.sin(t * 0.08) * 0.15;
    }

    const breath = 1 + Math.sin(t * 1.4) * 0.02 + level * 0.35;
    points.current.scale.setScalar(breath);

    color.current.lerp(new THREE.Color(statusColor(status)), 0.06);
    material.current.color.copy(color.current);
    material.current.opacity = status === "standby" ? 0.45 : 0.9 + level * 0.1;
  });

  return (
    <points ref={points}>
      <bufferGeometry key={`${style}-${count}`}>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        ref={material}
        size={0.022}
        transparent
        opacity={0.9}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        sizeAttenuation
      />
    </points>
  );
}

function OrbitalRing({ radius, tilt, speed }: { radius: number; tilt: number; speed: number }) {
  const group = useRef<THREE.Group>(null);
  const material = useRef<THREE.MeshBasicMaterial>(null);
  const color = useRef(new THREE.Color(statusColor("idle")));

  useFrame(({ clock }) => {
    if (!group.current || !material.current) return;
    const status = useJarvisStore.getState().status;
    group.current.rotation.z = clock.elapsedTime * speed;
    color.current.lerp(new THREE.Color(statusColor(status)), 0.06);
    material.current.color.copy(color.current);
  });

  return (
    <group rotation={[tilt, 0, 0]}>
      <group ref={group}>
        <mesh>
          <torusGeometry args={[radius, 0.006, 8, 128]} />
          <meshBasicMaterial
            ref={material}
            transparent
            opacity={0.55}
            blending={THREE.AdditiveBlending}
          />
        </mesh>
        {/* Traceur lumineux sur l'anneau */}
        <mesh position={[radius, 0, 0]}>
          <sphereGeometry args={[0.03, 12, 12]} />
          <meshBasicMaterial color="#ffffff" transparent opacity={0.9} />
        </mesh>
      </group>
    </group>
  );
}

function CoreGlow({ intense }: { intense?: boolean }) {
  const material = useRef<THREE.MeshBasicMaterial>(null);
  const freqBuf = useMemo(() => new Uint8Array(256), []);
  const color = useRef(new THREE.Color(statusColor("idle")));

  useFrame(({ clock }) => {
    if (!material.current) return;
    const status = useJarvisStore.getState().status;
    const level = status === "speaking" ? readTtsLevel(freqBuf) : 0;
    color.current.lerp(new THREE.Color(statusColor(status)), 0.06);
    material.current.color.copy(color.current);
    const base = intense ? 0.3 : 0.12;
    material.current.opacity = base + Math.sin(clock.elapsedTime * 2) * 0.05 + level * 0.3;
  });

  return (
    <mesh>
      <sphereGeometry args={[intense ? 0.45 : 0.65, 32, 32]} />
      <meshBasicMaterial
        ref={material}
        transparent
        opacity={0.15}
        blending={THREE.AdditiveBlending}
      />
    </mesh>
  );
}

/** Recule la caméra pour que l'hologramme (anneaux compris, ~3 unités de
 *  demi-largeur) tienne en entier, quel que soit le format du panneau. */
function FitCamera() {
  const { camera, size } = useThree();
  const aspect = size.width / Math.max(size.height, 1);
  const k = Math.tan((48 / 2) * (Math.PI / 180));
  camera.position.z = Math.max(5.2, 2.6 / k, 3.0 / (k * aspect));
  camera.updateProjectionMatrix();
  return null;
}

/** Hologramme 3D animé — style et couleur pilotés par le thème du store.
 *  Remplit son conteneur parent (position: relative requis). */
export function JarvisScene() {
  const holoStyle = useJarvisStore((s) => s.holoStyle);
  const holoDensity = useJarvisStore((s) => s.holoDensity);
  const holoSpeed = useJarvisStore((s) => s.holoSpeed);
  // Re-render à chaque changement de couleur (lue dans useFrame)
  useJarvisStore((s) => s.theme);
  useJarvisStore((s) => s.customAccent);

  const count = DENSITY_COUNTS[holoDensity];
  const speedFactor = SPEED_FACTORS[holoSpeed];

  return (
    <div className="absolute inset-0 pointer-events-none">
      <Canvas
        camera={{ position: [0, 0, 5.0], fov: 48 }}
        gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
        dpr={[1, 1.5]}
      >
        <FitCamera />
        <ParticleCloud
          key={`${holoStyle}-${count}`}
          style={holoStyle}
          count={count}
          speedFactor={speedFactor}
        />
        {holoStyle === "sphere" && (
          <>
            <OrbitalRing radius={2.05} tilt={Math.PI / 2.6} speed={0.3 * speedFactor} />
            <OrbitalRing radius={2.35} tilt={-Math.PI / 3.2} speed={-0.18 * speedFactor} />
            <OrbitalRing radius={2.7} tilt={Math.PI / 5} speed={0.1 * speedFactor} />
            <CoreGlow />
          </>
        )}
        {holoStyle === "reactor" && (
          <>
            <OrbitalRing radius={2.45} tilt={0} speed={-0.35 * speedFactor} />
            <CoreGlow intense />
          </>
        )}
        {(holoStyle === "galaxy" || holoStyle === "vortex") && <CoreGlow intense />}
        {holoStyle === "dna" && <CoreGlow />}
      </Canvas>
    </div>
  );
}
