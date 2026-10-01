import { motion } from "framer-motion";

/** Anneaux HUD animés autour de l'hologramme (SVG, aucun coût GPU notable). */
export function ArcOverlay({ color, busy }: { color: string; busy: boolean }) {
  const speed = busy ? 0.35 : 1; // tourne plus vite quand JARVIS travaille
  return (
    <svg viewBox="0 0 600 600" className="absolute inset-0 m-auto w-full h-full max-w-[min(100%,78vh)] max-h-full pointer-events-none">
      <defs>
        <radialGradient id="hudFade" cx="50%" cy="50%" r="50%">
          <stop offset="60%" stopColor={color} stopOpacity="0" />
          <stop offset="100%" stopColor={color} stopOpacity="0.06" />
        </radialGradient>
      </defs>
      <circle cx="300" cy="300" r="290" fill="url(#hudFade)" />
      {/* Graduations extérieures */}
      <motion.g style={{ originX: "300px", originY: "300px" }}
        animate={{ rotate: 360 }} transition={{ duration: 120 * speed, repeat: Infinity, ease: "linear" }}>
        {Array.from({ length: 120 }, (_, i) => {
          const a = (i / 120) * Math.PI * 2;
          const long = i % 10 === 0;
          const r1 = 272, r2 = long ? 286 : 279;
          return (
            <line key={i} x1={300 + r1 * Math.cos(a)} y1={300 + r1 * Math.sin(a)}
              x2={300 + r2 * Math.cos(a)} y2={300 + r2 * Math.sin(a)}
              stroke={color} strokeOpacity={long ? 0.55 : 0.2} strokeWidth={long ? 1.5 : 1} />
          );
        })}
      </motion.g>
      {/* Arcs segmentés */}
      <motion.g style={{ originX: "300px", originY: "300px" }}
        animate={{ rotate: -360 }} transition={{ duration: 40 * speed, repeat: Infinity, ease: "linear" }}>
        <circle cx="300" cy="300" r="255" fill="none" stroke={color} strokeOpacity={0.35} strokeWidth={2}
          strokeDasharray="120 40 30 40 200 60" />
      </motion.g>
      <motion.g style={{ originX: "300px", originY: "300px" }}
        animate={{ rotate: 360 }} transition={{ duration: 22 * speed, repeat: Infinity, ease: "linear" }}>
        <circle cx="300" cy="300" r="238" fill="none" stroke={color} strokeOpacity={0.5} strokeWidth={1}
          strokeDasharray="4 10" />
        <path d="M 300 58 A 242 242 0 0 1 510 180" fill="none" stroke={color} strokeWidth={3} strokeOpacity={0.8}
          strokeLinecap="round" style={{ filter: `drop-shadow(0 0 6px ${color})` }} />
      </motion.g>
      {/* Réticule */}
      {[0, 90, 180, 270].map((deg) => (
        <g key={deg} transform={`rotate(${deg} 300 300)`}>
          <path d="M 300 18 L 292 30 L 308 30 Z" fill={color} fillOpacity={0.6} />
        </g>
      ))}
    </svg>
  );
}
