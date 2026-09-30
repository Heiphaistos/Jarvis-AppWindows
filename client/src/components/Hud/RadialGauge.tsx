import { motion } from "framer-motion";

/** Jauge circulaire HUD : arc de progression, graduations, valeur au centre. */
export function RadialGauge({ label, value, accent, size = 92, unit = "%" }: {
  label: string;
  value: number | null;
  accent: string;
  size?: number;
  unit?: string;
}) {
  const pct = Math.max(0, Math.min(100, value ?? 0));
  const color = value === null ? "#3a5a77" : pct > 88 ? "#ff4466" : pct > 70 ? "#ffaa33" : accent;
  const r = size / 2 - 9;
  const c = 2 * Math.PI * r;
  const sweep = 0.75; // arc de 270°
  const ticks = Array.from({ length: 28 }, (_, i) => i);
  return (
    <div className="flex flex-col items-center" style={{ width: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="overflow-visible">
        <g transform={`rotate(135 ${size / 2} ${size / 2})`}>
          {ticks.map((i) => {
            const a = (i / (ticks.length - 1)) * sweep * 2 * Math.PI;
            const on = i / (ticks.length - 1) <= pct / 100;
            const r1 = r + 5, r2 = r + (i % 7 === 0 ? 9 : 7);
            return (
              <line key={i}
                x1={size / 2 + r1 * Math.cos(a)} y1={size / 2 + r1 * Math.sin(a)}
                x2={size / 2 + r2 * Math.cos(a)} y2={size / 2 + r2 * Math.sin(a)}
                stroke={on ? color : "#ffffff"} strokeOpacity={on ? 0.8 : 0.08} strokeWidth={1} />
            );
          })}
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#ffffff" strokeOpacity={0.06}
            strokeWidth={4} strokeDasharray={`${c * sweep} ${c}`} strokeLinecap="round" />
          <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={4}
            strokeLinecap="round" strokeDasharray={`${c * sweep} ${c}`}
            initial={false}
            animate={{ strokeDashoffset: c * sweep * (1 - pct / 100) }}
            transition={{ duration: 0.9, ease: "easeOut" }}
            style={{ filter: `drop-shadow(0 0 4px ${color})` }} />
        </g>
        <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central"
          className="font-mono" fontSize={size * 0.2} fill={color} style={{ textShadow: `0 0 8px ${color}` }}>
          {value === null ? "—" : Math.round(pct)}
          {value !== null && <tspan fontSize={size * 0.1} fillOpacity={0.6}>{unit}</tspan>}
        </text>
      </svg>
      <span className="-mt-3 text-[9px] tracking-[0.3em] text-blue-200/50">{label}</span>
    </div>
  );
}
