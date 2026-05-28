import { motion } from "framer-motion";

export function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex justify-start mb-4"
    >
      <div className="flex-shrink-0 w-6 mt-1 mr-2 flex flex-col items-center gap-1">
        <motion.div
          className="w-1.5 h-1.5 rounded-full"
          style={{ background: "#00d4ff", boxShadow: "0 0 6px #00d4ff" }}
          animate={{ opacity: [1, 0.3, 1] }}
          transition={{ duration: 0.8, repeat: Infinity }}
        />
      </div>
      <div
        className="flex flex-col gap-1"
        style={{
          background: "linear-gradient(135deg, rgba(0,20,50,0.6), rgba(0,10,30,0.8))",
          border: "1px solid rgba(0,136,170,0.2)",
          borderRadius: "2px 12px 12px 12px",
          padding: "8px 16px",
          backdropFilter: "blur(12px)",
        }}
      >
        <div className="text-[9px] tracking-widest text-cyan-400/50 mb-1">J.A.R.V.I.S.</div>
        <div className="flex gap-1.5 items-center h-3">
          {[0, 1, 2, 3].map((i) => (
            <motion.div
              key={i}
              className="rounded-full"
              style={{ background: "#00d4ff", boxShadow: "0 0 4px #00d4ff88" }}
              animate={{
                width: ["3px", "14px", "3px"],
                height: ["3px", "3px", "3px"],
                opacity: [0.4, 1, 0.4],
              }}
              transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
            />
          ))}
          <span className="text-[10px] text-cyan-400/40 tracking-widest ml-1">TRAITEMENT</span>
        </div>
      </div>
    </motion.div>
  );
}
