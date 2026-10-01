/** Fonds décoratifs ; le CSS n'affiche que ceux de l'esthétique active. */
export function Backdrop() {
  return (
    <>
      <div className="bg-layer bg-holo bg-glow" />
      <div className="bg-layer bg-holo bg-grid" />
      <div className="bg-layer bg-holo bg-vignette" />
      <div className="bg-layer bg-holo bg-scan" />
      <div className="bg-layer bg-aurora"><i /><i /><i /></div>
      <div className="bg-layer bg-tactical bg-tgrid" />
    </>
  );
}
