interface KenBurnsImageProps {
  src: string;
  alt: string;
  className?: string;
}

export function KenBurnsImage({
  src,
  alt,
  className = ""
}: KenBurnsImageProps) {
  return (
    <img
      src={src}
      alt={alt}
      loading="eager"
      decoding="async"
      fetchPriority="high"
      className={`h-full w-full object-cover animate-ken-burns ${className}`}
    />
  );
}
