import type React from "react";

type ButtonVariant = "primary" | "outline" | "ghost";

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
};

export function Button({ variant = "primary", className, ...props }: ButtonProps) {
  const variants = {
    primary: "bg-[var(--navy)] text-white hover:bg-[var(--navy-deep)]",
    outline: "border border-border bg-white text-[var(--navy)]",
    ghost: "bg-transparent text-[var(--navy)] hover:bg-[var(--navy-soft)]"
  };

  return <button className={`rounded-xl px-4 py-2 font-semibold ring-[var(--gold)] focus-visible:outline-none focus-visible:ring-2 ${variants[variant]} ${className ?? ""}`} {...props} />;
}
