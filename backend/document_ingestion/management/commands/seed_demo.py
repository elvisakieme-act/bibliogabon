"""Jeu de données de démonstration pour BiblioGabon.

Ré-exécutable sans risque (get_or_create partout). À n'utiliser qu'en
développement / démo — jamais en production.

    python manage.py seed_demo
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Entitlement, Organization, OrganizationMembership, User
from billing.models import CommercialOffer
from catalog.models import (
    AcademicDomain,
    Author,
    Collection,
    CollectionItem,
    Document,
    DocumentAuthor,
    DocumentType,
    RightsAgreement,
)
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage, ExtractedText
from search_discovery.services import rebuild_document_search_index

PASSWORD = "demo1234"

TEACHERS = [
    ("levis.andongui@bibliogabon.ga", "Levis ANDONGUI"),
    ("mpiga.jess@bibliogabon.ga", "Mpiga JESS"),
    ("elvis.oyono@bibliogabon.ga", "Elvis OYONO"),
    ("ulrich.essone@bibliogabon.ga", "Ulrich ESSONE"),
    ("aline.nze@bibliogabon.ga", "Aline NZE"),
    ("brice.ondo@bibliogabon.ga", "Brice ONDO"),
]

LEARNERS = [
    ("sarah.moussavou@example.ga", "Sarah MOUSSAVOU"),
    ("yannick.boulingui@example.ga", "Yannick BOULINGUI"),
]

ORG_ADMIN = ("recteur.uob@bibliogabon.ga", "Recteur UOB")

DOMAINS = [
    ("Droit", "droit"),
    ("Médecine", "medecine"),
    ("Informatique", "informatique"),
    ("Sciences économiques", "sciences-economiques"),
    ("Lettres et Sciences humaines", "lettres-sciences-humaines"),
]

# (nom, slug, icône, couleur, ordre)
TYPES = [
    ("Cours", "cours", "book-open", "#2563EB", 10),
    ("Travaux dirigés", "td", "pencil", "#7C3AED", 20),
    ("Article scientifique", "article", "file-text", "#0891B2", 30),
    ("Mémoire", "memoire", "notebook", "#059669", 40),
    ("Thèse", "these", "graduation-cap", "#DC2626", 50),
    ("Examen", "examen", "clipboard-check", "#EA580C", 60),
    ("Rapport", "rapport", "folder", "#4B5563", 70),
]

ORGANIZATIONS = [
    # (nom, slug, type, exige_verification)
    ("Université Omar Bongo", "uob", Organization.OrganizationType.UNIVERSITY, True),
    ("Université des Sciences et Techniques de Masuku", "ustm", Organization.OrganizationType.UNIVERSITY, True),
    ("Fondation pour l'Éducation Numérique", "fondation-edunum", Organization.OrganizationType.SPONSOR, False),
]

# (titre, slug, type, domaine, catégorie, modèle d'accès, année, [emails auteurs], nb pages, [mots-clés])
DOCUMENTS = [
    (
        "Introduction au droit public gabonais", "intro-droit-public-gabonais",
        "cours", "droit", Document.Category.OPEN_RESOURCE, Document.AccessModel.FREE, 2024,
        ["elvis.oyono@bibliogabon.ga"], 4, ["constitution", "administration", "état"],
    ),
    (
        "Cardiologie : notions fondamentales", "cardiologie-notions-fondamentales",
        "cours", "medecine", Document.Category.VOLUNTARY_TEACHER_DEPOSIT, Document.AccessModel.SUBSCRIPTION, 2023,
        ["aline.nze@bibliogabon.ga"], 3, ["cœur", "circulation", "diagnostic"],
    ),
    (
        "Algorithmes et structures de données", "algorithmes-structures-donnees",
        "cours", "informatique", Document.Category.OPEN_RESOURCE, Document.AccessModel.FREE, 2025,
        ["levis.andongui@bibliogabon.ga", "ulrich.essone@bibliogabon.ga"], 5, ["tri", "graphe", "complexité"],
    ),
    (
        "Mémoire : microfinance et inclusion au Gabon", "memoire-microfinance-inclusion-gabon",
        "memoire", "sciences-economiques", Document.Category.STUDENT_WORK, Document.AccessModel.INSTITUTION_ONLY, 2024,
        ["mpiga.jess@bibliogabon.ga"], 4, ["microfinance", "inclusion", "épargne"],
    ),
    (
        "Examen de droit constitutionnel — session 2024", "examen-droit-constitutionnel-2024",
        "examen", "droit", Document.Category.INSTITUTIONAL_FUND, Document.AccessModel.INSTITUTION_ONLY, 2024,
        ["brice.ondo@bibliogabon.ga"], 2, ["séparation des pouvoirs", "souveraineté"],
    ),
    (
        "Thèse : littérature gabonaise contemporaine", "these-litterature-gabonaise-contemporaine",
        "these", "lettres-sciences-humaines", Document.Category.VOLUNTARY_TEACHER_DEPOSIT, Document.AccessModel.SUBSCRIPTION, 2022,
        ["elvis.oyono@bibliogabon.ga"], 4, ["roman", "oralité", "identité"],
    ),
]

AGREEMENT_BY_CATEGORY = {
    Document.Category.OPEN_RESOURCE: RightsAgreement.AgreementType.OPEN_LICENSE,
    Document.Category.VOLUNTARY_TEACHER_DEPOSIT: RightsAgreement.AgreementType.TEACHER_VOLUNTARY,
    Document.Category.INSTITUTIONAL_FUND: RightsAgreement.AgreementType.INSTITUTIONAL_ARCHIVE,
    Document.Category.STUDENT_WORK: RightsAgreement.AgreementType.STUDENT_CONSENT,
    Document.Category.COMMERCIAL_PARTNER_CONTENT: RightsAgreement.AgreementType.COMMERCIAL_DISTRIBUTION,
}


class Command(BaseCommand):
    help = "Crée un jeu de données de démonstration (ré-exécutable). Développement uniquement."

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()

        # --- Utilisateurs ---
        teachers: dict[str, User] = {}
        for email, name in TEACHERS:
            teachers[email] = self._get_user(email, name, User.AccountType.TEACHER_AUTHOR)
        learners = [self._get_user(email, name, User.AccountType.INDIVIDUAL) for email, name in LEARNERS]
        org_admin = self._get_user(ORG_ADMIN[0], ORG_ADMIN[1], User.AccountType.ORGANIZATION_ADMIN)
        staff = self._get_user("demo.staff@bibliogabon.ga", "Démo Staff", User.AccountType.PLATFORM_STAFF, is_staff=True)

        # --- Organisations ---
        orgs: dict[str, Organization] = {}
        for name, slug, org_type, requires in ORGANIZATIONS:
            orgs[slug], _ = Organization.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "organization_type": org_type,
                    "status": Organization.Status.ACTIVE,
                    "requires_identity_verification": requires,
                },
            )

        uob = orgs["uob"]
        # Un membre vérifié, un membre non vérifié (pour démontrer la barrière), un admin d'organisation.
        OrganizationMembership.objects.get_or_create(
            organization=uob, user=learners[0],
            defaults={
                "role": OrganizationMembership.Role.MEMBER,
                "status": OrganizationMembership.Status.ACTIVE,
                "verification_status": OrganizationMembership.VerificationStatus.VERIFIED,
                "verification_method": OrganizationMembership.VerificationMethod.STUDENT_CARD,
                "verified_by": staff,
                "verified_at": now,
                "proof_reference": "CARTE-ETU-UOB-0001",
            },
        )
        OrganizationMembership.objects.get_or_create(
            organization=uob, user=learners[1],
            defaults={
                "role": OrganizationMembership.Role.MEMBER,
                "status": OrganizationMembership.Status.ACTIVE,
                "verification_status": OrganizationMembership.VerificationStatus.UNVERIFIED,
            },
        )
        OrganizationMembership.objects.get_or_create(
            organization=uob, user=org_admin,
            defaults={
                "role": OrganizationMembership.Role.ADMIN,
                "status": OrganizationMembership.Status.ACTIVE,
                "verification_status": OrganizationMembership.VerificationStatus.VERIFIED,
                "verification_method": OrganizationMembership.VerificationMethod.STAFF_ID,
                "verified_by": staff,
                "verified_at": now,
            },
        )

        # --- Domaines & types ---
        domains: dict[str, AcademicDomain] = {}
        for name, slug in DOMAINS:
            domains[slug], _ = AcademicDomain.objects.get_or_create(
                slug=slug, defaults={"name": name, "is_active": True}
            )
        types: dict[str, DocumentType] = {}
        for name, slug, icon, color, order in TYPES:
            types[slug], _ = DocumentType.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "icon": icon, "color": color, "display_order": order, "is_active": True},
            )

        # --- Auteurs (rattachés aux comptes enseignants) ---
        authors: dict[str, Author] = {}
        for email, name in TEACHERS:
            authors[email], _ = Author.objects.get_or_create(
                display_name=name,
                defaults={
                    "normalized_name": name.lower(),
                    "author_type": Author.AuthorType.PERSON,
                    "linked_user": teachers[email],
                    "affiliation": "Université Omar Bongo",
                },
            )

        # --- Documents ---
        documents: dict[str, Document] = {}
        for (title, slug, type_slug, domain_slug, category, access_model, year,
             author_emails, npages, keywords) in DOCUMENTS:
            document, created = Document.objects.get_or_create(
                slug=slug,
                defaults={
                    "title": title,
                    "abstract": f"Document de démonstration : {title}.",
                    "language_code": "fr",
                    "publication_year": year,
                    "document_type": types[type_slug],
                    "academic_domain": domains[domain_slug],
                    "category": category,
                    "access_model": access_model,
                    "publication_status": Document.PublicationStatus.PUBLISHED,
                    "published_at": now,
                },
            )
            documents[slug] = document

            for position, email in enumerate(author_emails, start=1):
                DocumentAuthor.objects.get_or_create(
                    document=document, author=authors[email],
                    defaults={"role": DocumentAuthor.Role.AUTHOR, "position": position},
                )

            holder = dict(TEACHERS).get(author_emails[0], "BiblioGabon")
            RightsAgreement.objects.get_or_create(
                document=document,
                defaults={
                    "rights_holder_name": holder,
                    "agreement_type": AGREEMENT_BY_CATEGORY[category],
                    "authorization_status": RightsAgreement.AuthorizationStatus.APPROVED,
                    "authorization_date": now.date(),
                    "access_model": access_model,
                    "withdrawal_rule": RightsAgreement.WithdrawalRule.AUTHOR_REQUEST,
                    "reviewer_decision": "Approuvé pour publication (démonstration).",
                    "audit_reference": f"BG-DEMO-{slug}",
                },
            )

            self._seed_pages(document, npages, keywords, now)
            rebuild_document_search_index(document)

        # --- Une collection thématique ---
        collection, _ = Collection.objects.get_or_create(
            slug="fondamentaux-uob",
            defaults={
                "name": "Fondamentaux — UOB",
                "description": "Sélection de documents fondamentaux pour les étudiants de l'UOB.",
                "academic_domain": domains["droit"],
                "owner_organization": uob,
                "status": Collection.Status.PUBLISHED,
            },
        )
        for position, slug in enumerate(
            ["intro-droit-public-gabonais", "algorithmes-structures-donnees", "examen-droit-constitutionnel-2024"],
            start=1,
        ):
            CollectionItem.objects.get_or_create(
                collection=collection, document=documents[slug], defaults={"position": position}
            )

        # --- Offre commerciale + droits d'accès de test ---
        CommercialOffer.objects.get_or_create(
            slug="abonnement-mensuel-individuel",
            defaults={
                "name": "Abonnement mensuel individuel",
                "offer_type": CommercialOffer.OfferType.INDIVIDUAL,
                "billing_period": CommercialOffer.BillingPeriod.MONTHLY,
                "price_xaf": 2000,
                "duration_days": 30,
                "access_right": Entitlement.AccessRight.READ,
                "scope_type": Entitlement.ScopeType.GLOBAL,
            },
        )
        # Droit individuel accordé au premier apprenant (accède à tout, y compris payant).
        Entitlement.objects.get_or_create(
            user=learners[0],
            source=Entitlement.Source.ADMIN_GRANT,
            access_right=Entitlement.AccessRight.READ,
            scope_type=Entitlement.ScopeType.GLOBAL,
            defaults={"starts_at": now, "note": "Accès de démonstration."},
        )
        # Quota d'organisation : les membres UOB *vérifiés* accèdent aux documents restreints.
        Entitlement.objects.get_or_create(
            organization=uob,
            source=Entitlement.Source.ORGANIZATION_QUOTA,
            access_right=Entitlement.AccessRight.READ,
            scope_type=Entitlement.ScopeType.GLOBAL,
            defaults={"starts_at": now, "note": "Quota UOB de démonstration."},
        )

        self.stdout.write(self.style.SUCCESS(
            "Seed terminé : "
            f"{User.objects.count()} utilisateurs, "
            f"{Organization.objects.count()} organisations, "
            f"{DocumentType.objects.count()} types, "
            f"{AcademicDomain.objects.count()} domaines, "
            f"{Document.objects.count()} documents, "
            f"{Collection.objects.count()} collection(s)."
        ))
        self.stdout.write("Comptes de démo (mot de passe : demo1234) :")
        self.stdout.write("  - Enseignants : levis.andongui@bibliogabon.ga, mpiga.jess@bibliogabon.ga, elvis.oyono@bibliogabon.ga, ulrich.essone@bibliogabon.ga …")
        self.stdout.write("  - Apprenants  : sarah.moussavou@example.ga (UOB vérifié + accès global), yannick.boulingui@example.ga (UOB non vérifié)")

    # ------------------------------------------------------------------ helpers

    def _get_user(self, email: str, display_name: str, account_type: str, is_staff: bool = False) -> User:
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"display_name": display_name, "account_type": account_type, "is_staff": is_staff},
        )
        if created:
            user.set_password(PASSWORD)
            user.save(update_fields=["password"])
        return user

    def _seed_pages(self, document: Document, npages: int, keywords: list[str], now) -> DocumentVersion:
        version, created = DocumentVersion.objects.get_or_create(
            document=document,
            version_label="v1",
            defaults={
                "status": DocumentVersion.Status.PROCESSED,
                "is_current": True,
                "page_count": npages,
                "detected_format": "pdf",
                "processed_at": now,
                "processing_summary": "Contenu de démonstration.",
            },
        )
        if not created:
            return version
        for i in range(1, npages + 1):
            page = DocumentPage.objects.create(
                version=version, page_number=i, status=DocumentPage.Status.PROCESSED
            )
            text = (
                f"{document.title} — page {i}.\n"
                f"Domaine : {document.academic_domain.name}.\n"
                f"Mots-clés : {', '.join(keywords)}.\n\n"
                "Ceci est un contenu de démonstration destiné à tester le lecteur "
                "sécurisé et la recherche plein-texte de BiblioGabon. "
                "Le texte réel sera produit par le pipeline d'ingestion à partir du PDF d'origine."
            )
            ExtractedText.objects.create(page=page, text=text, language_code="fr")
        return version