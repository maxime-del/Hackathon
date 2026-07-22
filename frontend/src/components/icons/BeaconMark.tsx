/**
 * Signature mark: a lighthouse sweep. Reused for the SOS logo (static) and
 * for Phare, the assistant, where the rings pulse gently (motion-safe).
 */
export function BeaconMark({ size = 28, pulse = false }: { size?: number; pulse?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="var(--ink)" />
      <circle cx="16" cy="16" r="9.5" stroke="var(--signal)" strokeOpacity="0.5" strokeWidth="1.6" className={pulse ? "beacon-ring beacon-ring-1" : undefined} />
      <circle cx="16" cy="16" r="13" stroke="var(--signal)" strokeOpacity="0.25" strokeWidth="1.4" className={pulse ? "beacon-ring beacon-ring-2" : undefined} />
      <circle cx="16" cy="16" r="4.5" fill="var(--signal)" />
    </svg>
  );
}
