import { describe, expect, it } from "vitest";

import type { DocumentMetadata } from "@/api/types";
import { documentAccessNote, documentCategoryLabel } from "@/components/catalog/documentAccess";
import { documentCitation } from "@/components/catalog/documentCitation";

/**
 * La notice d'un document : ce qu'on a le droit d'en faire, et comment le citer.
 *
 * Les deux énoncés engagent la plateforme auprès d'un lecteur. Annoncer un
 * droit qu'il n'a pas lui fait perdre son temps ; une référence fausse se
 * recopie dans une bibliographie et lui survit.
 */
function document(patch: Partial<DocumentMetadata> = {}): DocumentMetadata {
  return {
    id: 9,
    slug: "algorithmes",
    title: "Algorithmes et structures de données",
    abstract: "",
    language_code: "fr",
    publication_year: 2025,
    document_type: { id: 8, name: "Cours", slug: "cours", icon: "book-open", color: "#2563EB" },
    category: "open_resource",
    access_model: "free",
    domain: { id: 8, name: "Informatique", slug: "informatique" },
    authors: [
      { id: 7, display_name: "Levis ANDONGUI", role: "author" },
      { id: 10, display_name: "Ulrich ESSONE", role: "author" }
    ],
    owner: "Université des Sciences et Techniques de Masuku",
    page_count: 3,
    cover: null,
    access: { can_read: true, access_model: "free", reason: "free" },
    ...patch
  };
}

describe("ce que l'accès autorise", () => {
  it("dit qu'un document libre s'ouvre sans compte", () => {
    expect(documentAccessNote(document())).toContain("sans compte");
  });

  it("distingue le droit acquis du droit à obtenir", () => {
    // Même document, deux lecteurs : l'un entre, l'autre doit se rattacher.
    const ouvert = document({
      access_model: "institution_only",
      access: { can_read: true, access_model: "institution_only", reason: "active_entitlement" }
    });
    const ferme = document({
      access_model: "institution_only",
      access: {
        can_read: false,
        access_model: "institution_only",
        reason: "entitlement_required"
      }
    });

    expect(documentAccessNote(ouvert)).toBe("Votre établissement vous ouvre ce document.");
    expect(documentAccessNote(ferme)).toContain("pas encore rattaché");
  });

  it("invite à se connecter plutôt qu'à s'abonner quand le droit est inconnu", () => {
    // Visiteur anonyme : il a peut-être déjà le droit. Lui annoncer qu'il lui
    // manque un abonnement serait faux une fois sur deux.
    const note = documentAccessNote(
      document({
        access_model: "subscription",
        access: {
          can_read: false,
          access_model: "subscription",
          reason: "authentication_required"
        }
      })
    );

    expect(note).toContain("Connectez-vous");
    expect(note).not.toContain("que votre compte n'a pas");
  });

  it("reste lisible pour un document indisponible", () => {
    const note = documentAccessNote(
      document({ access: { can_read: false, access_model: "private", reason: "unavailable" } })
    );

    expect(note).toContain("pas accessible");
  });
});

describe("régime de droits", () => {
  it("nomme les catégories connues et se tait sur les autres", () => {
    // Se taire plutôt qu'afficher `partner_publication_v2` : un intitulé
    // technique sur une fiche publique n'apprend rien et trahit l'inachevé.
    expect(documentCategoryLabel("student_work")).toBe("Travail d'étudiant");
    expect(documentCategoryLabel("quelque_chose_de_nouveau")).toBeNull();
  });
});

describe("référence à citer", () => {
  it("assemble auteurs, titre, nature, établissement et année", () => {
    expect(documentCitation(document(), "https://bibliogabon.ga/documents/9")).toBe(
      "Levis ANDONGUI ; Ulrich ESSONE. Algorithmes et structures de données. " +
        "Cours, Université des Sciences et Techniques de Masuku, 2025. BiblioGABON. " +
        "Disponible sur : https://bibliogabon.ga/documents/9"
    );
  });

  it("omet ce qui manque au lieu de l'inventer", () => {
    // Pas de « s.d. », pas d'« anonyme » : une mention fabriquée se recopie
    // dans une bibliographie et devient vraie pour celui qui la lit.
    const nu = documentCitation(
      document({ authors: [], owner: null, publication_year: null, document_type: null }),
      "https://bibliogabon.ga/documents/9"
    );

    expect(nu).toBe(
      "Algorithmes et structures de données. BiblioGABON. " +
        "Disponible sur : https://bibliogabon.ga/documents/9"
    );
    expect(nu).not.toContain("null");
    expect(nu).not.toContain("undefined");
  });

  it("garde les noms tels qu'ils sont enregistrés", () => {
    // Réordonner « Levis ANDONGUI » en « ANDONGUI, Levis » suppose qu'on sait
    // lequel est le patronyme. On ne le sait pas.
    expect(documentCitation(document(), "https://x")).toContain(
      "Levis ANDONGUI ; Ulrich ESSONE"
    );
  });
});
