/**
 * Erreurs de champ, associées à leur input.
 *
 * Sans `aria-invalid` ni `aria-describedby`, une erreur de champ n'existe
 * que visuellement : un lecteur d'écran annonce le message quelque part
 * dans la page, sans dire quel champ est en cause. Le couple id / describedby
 * est ce qui fait le lien, et il est facile à oublier — d'où ce composant.
 */
export function fieldErrorId(form: string, field: string): string {
  return `${form}-${field}-error`;
}

export function fieldErrorProps(
  form: string,
  field: string,
  fieldErrors: Record<string, string[]>
) {
  if (!fieldErrors[field]?.length) return {};
  return {
    "aria-invalid": true as const,
    "aria-describedby": fieldErrorId(form, field),
  };
}

export function FieldErrors({
  form,
  field,
  fieldErrors
}: {
  form: string;
  field: string;
  fieldErrors: Record<string, string[]>;
}) {
  const messages = fieldErrors[field];
  if (!messages?.length) return null;
  return (
    <span id={fieldErrorId(form, field)} className="mt-2 block text-sm text-red-700">
      {messages.join(" ")}
    </span>
  );
}
