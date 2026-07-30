interface LogoProps {
  withWordmark?: boolean;
  className?: string;
}

export function Logo({ withWordmark = true, className }: LogoProps) {
  return (
    <a href="/" aria-label="BiblioGABON" className={`inline-flex items-center gap-2 ${className ?? ""}`}>
      <img src="/bibliogabon-logo.png" alt="" className="h-10 w-10" />
      {withWordmark ? <span className="font-display text-xl">BiblioGABON</span> : null}
    </a>
  );
}
