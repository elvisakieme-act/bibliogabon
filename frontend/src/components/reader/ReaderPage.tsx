import type { ReaderPage as ReaderPagePayload } from "@/api/types";

interface ReaderPageProps {
  title: string;
  page: ReaderPagePayload;
}

export function ReaderPage({ title, page }: ReaderPageProps) {
  return (
    <article className="border border-border bg-white px-6 py-8 shadow-editorial sm:px-10 sm:py-12">
      <header className="border-b border-border pb-5">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--green)]">Lecture</p>
        <h1 className="mt-2 font-display text-3xl font-semibold text-[var(--navy)] sm:text-4xl">{title}</h1>
      </header>
      <div className="whitespace-pre-wrap pt-8 font-display text-lg leading-8 text-[var(--navy)] sm:text-xl sm:leading-9">
        {page.text}
      </div>
    </article>
  );
}
