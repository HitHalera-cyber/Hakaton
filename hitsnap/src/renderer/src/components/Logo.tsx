export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
      <defs>
        <linearGradient id="hs-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--accent)" />
          <stop offset="1" stopColor="var(--accent-2)" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="18" fill="url(#hs-g)" />
      {[14, 22, 30, 38, 46].map((x, i) => {
        const h = [14, 26, 36, 22, 12][i]
        return <rect key={x} x={x} y={32 - h / 2} width="5" height={h} rx="2.5" fill="white" opacity={0.95} />
      })}
    </svg>
  )
}

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark />
      <div className="leading-tight">
        <div className="text-lg font-extrabold tracking-tight">HitSnap</div>
        <div className="text-[11px] text-muted">угадай песню</div>
      </div>
    </div>
  )
}
