import { motion } from "framer-motion";

export function TypingIndicator() {
  return (
    <motion.div className="msg msg-bot" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="who"><span>J.A.R.V.I.S.</span><em>analyse</em></div>
      <div className="flex gap-1.5 items-center h-4">
        {[0, 1, 2, 3].map((i) => (
          <motion.span
            key={i}
            className="block h-[3px] rounded-full"
            style={{ background: "var(--accent)", boxShadow: "0 0 6px var(--accent)" }}
            animate={{ width: [4, 16, 4], opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
          />
        ))}
      </div>
    </motion.div>
  );
}
