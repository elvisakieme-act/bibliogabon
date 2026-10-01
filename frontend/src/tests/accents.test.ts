import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Les textes affichés portent leurs accents.
 *
 * Le produit est francophone et national : « Acces requis », « 6 resultats »,
 * « Creer mon compte » ou « Deja inscrit ? » ne sont pas des détails de style,
 * ce sont des fautes — et elles se lisent sur chaque écran du parcours public.
 *
 * Ce test existe parce qu'un correctif les avait déjà dites rétablies : la
 * relecture à l'œil en avait rattrapé une partie, et une trentaine de chaînes
 * étaient restées, dont la barre de pagination que l'on voit partout. Une
 * faute d'orthographe ne casse rien, aucun test ne tombe, et c'est exactement
 * pour cela qu'elle survit.
 *
 * La liste nomme les mots fautifs, pas une règle d'accentuation : on ne peut
 * pas deviner qu'« etudiant » devait être « étudiant » sans savoir que c'est du
 * français. Elle s'allonge quand une faute nouvelle est trouvée.
 */
const FAUTES: Record<string, string> = {
  Acces: "Accès",
  acces: "accès",
  Annee: "Année",
  Decouverte: "Découverte",
  Creer: "Créer",
  Creation: "Création",
  Deja: "Déjà",
  Precedent: "Précédent",
  Reessayer: "Réessayer",
  Reessayez: "Réessayez",
  Verifiez: "Vérifiez",
  resultat: "résultat",
  resultats: "résultats",
  Resultats: "Résultats",
  necessaire: "nécessaire",
  depots: "dépôts",
  ecrans: "écrans",
  echoue: "échoué",
  categorie: "catégorie",
  modele: "modèle",
  etudiant: "étudiant",
  Publie: "Publié",
  Agregats: "Agrégats",
  telecharger: "télécharger",
  renseigne: "renseigné",
  affiche: "affiché"
};

/**
 * Seules les chaînes **affichées** sont examinées.
 *
 * Une classe CSS, un chemin d'URL ou un identifiant s'écrivent sans accent et
 * doivent le rester : `/bibliotheque` est une adresse, pas un mot. On ne retient
 * donc que le texte d'un nœud JSX et les chaînes qui ressemblent à une phrase.
 */
function textesAffiches(source: string): string[] {
  // Les commentaires partent d'abord : ils sont en français eux aussi, et une
  // faute y est sans conséquence pour qui lit l'écran.
  const sansCommentaires = source
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");

  const candidats: string[] = [];
  // Texte entre deux balises. Le `>` de TypeScript — génériques, comparaisons,
  // flèches — en produit beaucoup de faux : le filtre ci-dessous les écarte.
  for (const [, texte] of sansCommentaires.matchAll(/>\s*([^<>{}\n][^<>{}]*?)\s*</g)) {
    candidats.push(texte);
  }
  // Chaînes passées à des propriétés qui finissent à l'écran.
  for (const [, texte] of sansCommentaires.matchAll(
    /(?:title|label|description|placeholder|aria-label|message)[=:]\s*"([^"]+)"/g
  )) {
    candidats.push(texte);
  }

  // Ne reste que ce qui ressemble à une phrase : des lettres, des espaces et
  // la ponctuation d'un texte. Dès qu'une parenthèse, un point-virgule ou un
  // signe d'opérateur apparaît, c'est du code.
  return candidats.filter((texte) => /^[\p{L}\p{N}\s'’«»,.:;!?…—–-]+$/u.test(texte));
}

function fichiersSource(racine: string): string[] {
  const trouves: string[] = [];
  for (const entree of readdirSync(racine)) {
    const chemin = join(racine, entree);
    if (statSync(chemin).isDirectory()) {
      if (entree === "tests" || entree === "node_modules") continue;
      trouves.push(...fichiersSource(chemin));
    } else if (
      (entree.endsWith(".tsx") || entree.endsWith(".ts")) &&
      !entree.includes(".test.")
    ) {
      trouves.push(chemin);
    }
  }
  return trouves;
}

describe("orthographe des textes affichés", () => {
  it("n'affiche aucun mot français privé de ses accents", () => {
    const fautes: string[] = [];
    for (const fichier of fichiersSource(join(__dirname, ".."))) {
      const source = readFileSync(fichier, "utf8");
      for (const texte of textesAffiches(source)) {
        for (const [faux, vrai] of Object.entries(FAUTES)) {
          // Le mot entier : « acces » ne doit pas se déclencher sur « access »,
          // ni « affiche » sur « affichent ».
          if (new RegExp(`(?<![\\p{L}-])${faux}(?![\\p{L}-])`, "u").test(texte)) {
            fautes.push(
              `${fichier.split("/src/")[1]} : « ${faux} » devrait être « ${vrai} » — ${texte.trim().slice(0, 70)}`
            );
          }
        }
      }
    }
    expect(fautes).toEqual([]);
  });
});
