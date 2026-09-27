import { fieldErrorId } from "@/components/ui/fieldErrors";

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
