export function BugViperLogo({ size = 40 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Snake body coil */}
      <path
        d="M32 8C18 8 12 18 12 28C12 38 20 42 28 38C36 34 38 26 34 20C30 14 22 16 20 22C18 28 22 32 28 30"
        stroke="#22c55e"
        strokeWidth="4"
        strokeLinecap="round"
        fill="none"
      />
      {/* Snake head */}
      <circle cx="28" cy="30" r="4" fill="#22c55e" />
      {/* Snake eye */}
      <circle cx="27" cy="28.5" r="1.2" fill="#0a0a0a" />
      {/* Snake tongue */}
      <path
        d="M32 31L36 29M36 29L38 27M36 29L38 31"
        stroke="#ef4444"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      {/* Bug/crosshair circle */}
      <circle cx="44" cy="44" r="12" stroke="#22c55e" strokeWidth="2" strokeDasharray="4 3" />
      {/* Crosshair lines */}
      <line x1="44" y1="30" x2="44" y2="36" stroke="#22c55e" strokeWidth="1.5" />
      <line x1="44" y1="52" x2="44" y2="58" stroke="#22c55e" strokeWidth="1.5" />
      <line x1="30" y1="44" x2="36" y2="44" stroke="#22c55e" strokeWidth="1.5" />
      <line x1="52" y1="44" x2="58" y2="44" stroke="#22c55e" strokeWidth="1.5" />
      {/* Bug dot */}
      <circle cx="44" cy="44" r="2" fill="#22c55e" />
    </svg>
  );
}
