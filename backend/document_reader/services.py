from __future__ import annotations

import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import Entitlement
from accounts.services import active_organization_ids_for_user, user_has_entitlement
from catalog.models import Document, RightsAgreement
from document_ingestion.blob_storage import open_stream
from document_ingestion.models import DocumentAsset, DocumentVersion
from document_processing.models import DocumentPage, ExtractedText
from document_reader.exceptions import (
    ReaderAccessDenied,
    ReaderPageUnavailable,
    ReaderSessionInactive,
)
from document_reader.models import (
    FavoriteDocument,
    PageAccessLog,
    ReaderSession,
    ReadingProgress,
)

RESTRICTED_ACCESS_MODELS = {
    Document.AccessModel.SUBSCRIPTION,
    Document.AccessModel.INSTITUTION_ONLY,
    Document.AccessModel.SPONSORED,
    Document.AccessModel.RESTRICTED,
}


def document_requires_entitlement(document: Document) -> bool:
    return document.access_model in RESTRICTED_ACCESS_MODELS


def document_is_reader_accessible(document: Document) -> bool:
    return (
        document.publication_status == Document.PublicationStatus.PUBLISHED
        and document.access_model != Document.AccessModel.PRIVATE
    )


def _user_is_authenticated(user) -> bool:
    return bool(user and getattr(user, "is_authenticated", False))


def _user_has_document_read_entitlement(user, document: Document, at=None) -> bool:
    if user_has_entitlement(
        user=user,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.DOCUMENT,
        scope_id=document.entitlement_scope_id,
        at=at,
    ):
        return True
    if document.academic_domain_id:
        return user_has_entitlement(
            user=user,
            access_right=Entitlement.AccessRight.READ,
            scope_type=Entitlement.ScopeType.DOMAIN,
            scope_id=str(document.academic_domain_id),
            at=at,
        )
    return False


def user_can_read_document(user, document: Document, at=None) -> bool:
    if not document_is_reader_accessible(document):
        return False
    if not document_requires_entitlement(document):
        return document.access_model == Document.AccessModel.FREE
    if not _user_is_authenticated(user):
        return False
    return _user_has_document_read_entitlement(user, document, at=at)


def readable_document_ids_for_user(user, documents, at=None) -> set[int]:
    documents = list(documents)
    readable_ids = {
        document.pk
        for document in documents
        if document_is_reader_accessible(document)
        and not document_requires_entitlement(document)
        and document.access_model == Document.AccessModel.FREE
    }
    restricted_documents = [
        document
        for document in documents
        if document_is_reader_accessible(document) and document_requires_entitlement(document)
    ]
    if not restricted_documents or not _user_is_authenticated(user):
        return readable_ids

    at = at or timezone.now()
    organization_ids = active_organization_ids_for_user(user, at=at)
    entitlements = Entitlement.objects.filter(
        Q(user=user) | Q(user__isnull=True, organization_id__in=organization_ids),
        access_right=Entitlement.AccessRight.READ,
        scope_type__in=[
            Entitlement.ScopeType.GLOBAL,
            Entitlement.ScopeType.DOMAIN,
            Entitlement.ScopeType.DOCUMENT,
        ],
        starts_at__lte=at,
        revoked_at__isnull=True,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=at))

    has_global_access = False
    domain_scope_ids = set()
    document_scope_ids = set()
    for entitlement in entitlements:
        if entitlement.scope_type == Entitlement.ScopeType.GLOBAL:
            has_global_access = True
        elif entitlement.scope_type == Entitlement.ScopeType.DOMAIN:
            domain_scope_ids.add(entitlement.scope_id)
        elif entitlement.scope_type == Entitlement.ScopeType.DOCUMENT:
            document_scope_ids.add(entitlement.scope_id)

    for document in restricted_documents:
        if (
            has_global_access
            or document.entitlement_scope_id in document_scope_ids
            or (
                document.academic_domain_id
                and str(document.academic_domain_id) in domain_scope_ids
            )
        ):
            readable_ids.add(document.pk)
    return readable_ids


def get_current_processed_version(document: Document) -> DocumentVersion:
    versions = list(
        DocumentVersion.objects.filter(
            document=document,
            is_current=True,
            status=DocumentVersion.Status.PROCESSED,
            page_count__isnull=False,
            page_count__gt=0,
        ).order_by("-created_at")[:2]
    )
    if len(versions) != 1:
        raise ReaderAccessDenied("Document has no single readable current version")
    return versions[0]


def favorite_document(user, document: Document) -> tuple[FavoriteDocument, bool]:
    if not document_is_reader_accessible(document):
        raise ReaderAccessDenied("Document is not discoverable")
    return FavoriteDocument.objects.get_or_create(user=user, document=document)


def remove_favorite(user, document: Document) -> bool:
    deleted_count, _ = FavoriteDocument.objects.filter(user=user, document=document).delete()
    return deleted_count > 0


def record_reading_progress(user, document: Document, last_page_number: int) -> ReadingProgress:
    if last_page_number < 1:
        raise ReaderPageUnavailable("last_page_number must be positive")
    if not user_can_read_document(user, document):
        raise ReaderAccessDenied("User cannot record progress for this document")
    version = get_current_processed_version(document)
    if last_page_number > version.page_count:
        raise ReaderPageUnavailable("last_page_number is outside the readable document range")
    progress, _ = ReadingProgress.objects.update_or_create(
        user=user,
        document=document,
        defaults={"last_page_number": last_page_number},
    )
    return progress


def start_reader_session(
    *,
    user,
    document: Document,
    client_ip: str = "",
    user_agent: str = "",
    at=None,
) -> ReaderSession:
    at = at or timezone.now()
    if user is not None and not _user_is_authenticated(user):
        raise ReaderAccessDenied("Anonymous users must be represented as None")
    if not user_can_read_document(user, document, at=at):
        raise ReaderAccessDenied("User cannot read this document")

    version = get_current_processed_version(document)
    ttl_minutes = int(getattr(settings, "READER_SESSION_TTL_MINUTES", 120))
    with transaction.atomic():
        return ReaderSession.objects.create(
            user=user,
            document=document,
            version=version,
            started_at=at,
            expires_at=at + timezone.timedelta(minutes=ttl_minutes),
            client_ip=client_ip,
            user_agent=user_agent,
            last_seen_at=at,
        )


def end_reader_session(*, session: ReaderSession, at=None) -> ReaderSession:
    return session.end(at=at)


def _ensure_reader_session_can_read(session: ReaderSession, at=None):
    if not session.is_active_at(at=at):
        raise ReaderSessionInactive("Reader session is not active")
    if not user_can_read_document(session.user, session.document, at=at):
        raise ReaderAccessDenied("User can no longer read this document")
    if (
        not session.version.is_current
        or session.version.status != DocumentVersion.Status.PROCESSED
        or not session.version.page_count
    ):
        raise ReaderAccessDenied("Reader session version is no longer readable")


def get_reader_page(*, session: ReaderSession, page_number: int, at=None) -> dict:
    at = at or timezone.now()
    if page_number < 1:
        raise ReaderPageUnavailable("page_number must be positive")

    session.refresh_from_db()
    _ensure_reader_session_can_read(session, at=at)

    if page_number > session.version.page_count:
        raise ReaderPageUnavailable("Page is outside the readable document range")

    try:
        page = DocumentPage.objects.get(
            version=session.version,
            page_number=page_number,
            status=DocumentPage.Status.PROCESSED,
        )
    except DocumentPage.DoesNotExist as exc:
        raise ReaderPageUnavailable("Page is not available for reading") from exc

    try:
        extracted_text = ExtractedText.objects.get(page=page)
    except ExtractedText.DoesNotExist as exc:
        raise ReaderPageUnavailable("Page has no extracted text") from exc

    _record_page_access(session=session, page=page, at=at)
    policy = text_layer_policy(session.document)

    return {
        "session_key": str(session.session_key),
        "document_id": session.document_id,
        "version_id": session.version_id,
        "page_number": page.page_number,
        "page_count": session.version.page_count,
        "language_code": extracted_text.language_code,
        "text": extracted_text.text,
        # Un document sous clause de confidentialité ne reçoit aucune position :
        # empêcher la sélection dissuade, ne pas envoyer le texte protège.
        "words": []
        if policy == TextLayerPolicy.WITHHELD
        else list(extracted_text.word_boxes or []),
        "text_policy": policy,
    }


class TextLayerPolicy:
    """Ce qu'un lecteur peut faire du texte d'une page.

    La couche texte transparente rend la page sélectionnable, cherchable et
    lisible par un lecteur d'écran. Elle la rend aussi copiable — et une
    plateforme où l'on copie un mémoire entier ne tient pas ce qu'elle promet
    à ses déposants.

    La règle suit donc **l'accord de droits signé**, pas un réglage global :
    un réglage uniforme trahirait soit les auteurs, soit l'accès ouvert.

    Une honnêteté à garder en tête : `SELECTABLE` et `PROTECTED` envoient le
    même texte au navigateur. Empêcher la sélection dissuade, ne protège pas —
    qui ouvre les outils de développement récupère le texte. Seul `WITHHELD`
    protège vraiment, en n'envoyant rien, et c'est pour cela qu'il coûte le
    lecteur d'écran et qu'il est réservé aux documents qui l'exigent.
    """

    SELECTABLE = "selectable"
    PROTECTED = "protected"
    WITHHELD = "withheld"


def text_layer_policy(document: Document) -> str:
    """Politique applicable au texte de ce document.

    Sans accord de droits, la réponse est `PROTECTED` et non `SELECTABLE` :
    un document dont les droits ne sont pas déclarés ne doit pas être le plus
    permissif du catalogue.
    """
    agreement = getattr(document, "rights_agreement", None)

    if agreement is not None and agreement.confidentiality_terms.strip():
        return TextLayerPolicy.WITHHELD

    if document.category == Document.Category.OPEN_RESOURCE:
        return TextLayerPolicy.SELECTABLE
    if (
        agreement is not None
        and agreement.agreement_type == RightsAgreement.AgreementType.OPEN_LICENSE
    ):
        return TextLayerPolicy.SELECTABLE

    return TextLayerPolicy.PROTECTED


# Au-delà de ce délai, la session est rafraîchie ; en deçà, non. Une page
# affichée déclenche des dizaines de requêtes de tuiles en quelques
# millisecondes : les écrire toutes ferait autant d'écritures pour une
# information — « cette lecture est en cours » — qui ne change pas à cette
# échelle de temps.
SESSION_TOUCH_SECONDS = 30


def _page_already_logged(session: ReaderSession, page: DocumentPage) -> bool:
    """Cette page a-t-elle déjà été enregistrée pour cette session ?

    Fonction à part, et non une expression dans l'appelant : c'est la lecture
    qu'une requête concurrente voit périmée, et un test doit pouvoir la rendre
    périmée sans aveugler du même coup la validation du modèle — auquel cas il
    emprunterait un autre chemin d'erreur que celui observé en production.
    """
    return PageAccessLog.objects.filter(session=session, page=page).exists()


def _record_page_access(*, session: ReaderSession, page: DocumentPage, at) -> None:
    """Journalise l'accès à une page et rafraîchit la session.

    Appelée par **toutes** les représentations d'une page — texte, image
    entière, tuile. Une représentation qui ne journaliserait pas offrirait un
    chemin de lecture non tracé, et l'audit ne doit pas dépendre de ce que le
    client a demandé.

    **Une ligne par page et par session, pas une par requête.** Le tuilage a
    changé l'échelle du problème : afficher une page demande des dizaines de
    tuiles, servies en parallèle. Une écriture par requête a été observée
    comme « database is locked » sur SQLite — ce qui, sur PostgreSQL, aurait
    été une tempête d'écritures concurrentes plutôt qu'une panne visible.
    L'invariant tenu est donc : *toute page dont le contenu est remis est
    enregistrée, une fois par session de lecture*, et une contrainte d'unicité
    le garantit en base plutôt qu'à la faveur du code.

    Les deux écritures sont évitées quand elles n'apprendraient rien : la
    ligne existe déjà, ou la session a été vue il y a moins de
    `SESSION_TOUCH_SECONDS`.
    """
    already_logged = _page_already_logged(session, page)
    stale = (
        session.last_seen_at is None
        or (at - session.last_seen_at).total_seconds() >= SESSION_TOUCH_SECONDS
    )
    if already_logged and not stale:
        return

    with transaction.atomic():
        if not already_logged:
            # Deux tuiles d'une page jamais lue arrivent en même temps : les
            # deux lisent « aucune ligne », les deux écrivent. La contrainte
            # d'unicité refuse la seconde, et c'est exactement ce qu'on veut —
            # mais `full_clean()` la refuse en `ValidationError`, que
            # `get_or_create` ne rattrape pas. Sans ce garde, le lecteur
            # recevait une erreur serveur sur une tuile pour une ligne qui
            # venait d'être écrite correctement.
            #
            # Observé sur PostgreSQL, invisible sur SQLite, où le verrou global
            # sérialisait les écritures et masquait la course.
            try:
                with transaction.atomic():
                    PageAccessLog.objects.create(
                        session=session,
                        page=page,
                        user=session.user,
                        document=session.document,
                        page_number=page.page_number,
                        client_ip=session.client_ip,
                        user_agent=session.user_agent,
                    )
            except (IntegrityError, ValidationError):
                pass
        if stale:
            session.last_seen_at = at
            session.save(update_fields=["last_seen_at", "updated_at"])


def _authorized_page(session: ReaderSession, page_number: int, at) -> DocumentPage:
    """Page lisible d'une session vivante, ou l'exception qui dit pourquoi.

    Extrait pour que le texte, l'image et les tuiles passent **exactement** par
    la même vérification. Le jour où la règle d'accès change, elle change une
    fois : trois copies finiraient par diverger, et c'est l'image — le contenu
    lui-même — qui serait du mauvais côté.
    """
    if page_number < 1:
        raise ReaderPageUnavailable("page_number must be positive")

    session.refresh_from_db()
    _ensure_reader_session_can_read(session, at=at)

    if page_number > session.version.page_count:
        raise ReaderPageUnavailable("Page is outside the readable document range")

    try:
        return DocumentPage.objects.get(
            version=session.version,
            page_number=page_number,
            status=DocumentPage.Status.PROCESSED,
        )
    except DocumentPage.DoesNotExist as exc:
        raise ReaderPageUnavailable("Page is not available for reading") from exc


def get_reader_manifest(*, session: ReaderSession, base_url: str, at=None) -> dict:
    """Manifeste IIIF Presentation 3.0 de la session de lecture.

    Une seule requête donne au visualiseur tout ce dont il a besoin pour
    ouvrir le document : le nombre de pages, les dimensions de chacune et la
    description complète de son service d'images.

    C'est ce qui rend l'architecture tenable. Sans manifeste, un visualiseur
    qui met 157 pages en page doit lire 157 `info.json` à l'ouverture — donc
    demander 157 fois l'autorisation, et **journaliser le document entier
    comme lu** avant que le lecteur ait tourné une page.

    Le manifeste ne livre aucun contenu : des dimensions et des adresses. Les
    tuiles, elles, restent derrière l'autorisation, page par page.
    """
    at = at or timezone.now()
    session.refresh_from_db()
    _ensure_reader_session_can_read(session, at=at)

    document = session.document
    canvases = []
    for page in (
        DocumentPage.objects.filter(
            version=session.version, status=DocumentPage.Status.PROCESSED
        )
        .order_by("page_number")
        .iterator()
    ):
        info = _page_image_info(page)
        if info is None:
            # Une page traitée mais pas encore tuilée : elle n'entre pas au
            # manifeste plutôt que d'y figurer avec des dimensions inventées,
            # qui décaleraient la mise en page de tout le document.
            continue
        width, height = info["width"], info["height"]
        service_id = f"{base_url}/pages/{page.page_number}/iiif"
        # Le service est **décrit en entier** ici, pas seulement adressé : un
        # visualiseur qui recalculerait les facteurs d'échelle en tiendrait
        # une seconde écriture, et demanderait un jour des tuiles que
        # l'ingestion n'a pas produites.
        service = {**info, "id": service_id}
        canvases.append(
            {
                "id": f"{base_url}/canvas/{page.page_number}",
                "type": "Canvas",
                "label": {"fr": [f"Page {page.page_number}"]},
                "width": width,
                "height": height,
                "items": [
                    {
                        "id": f"{base_url}/canvas/{page.page_number}/page",
                        "type": "AnnotationPage",
                        "items": [
                            {
                                "id": f"{base_url}/canvas/{page.page_number}/annotation",
                                "type": "Annotation",
                                "motivation": "painting",
                                "target": f"{base_url}/canvas/{page.page_number}",
                                "body": {
                                    "id": f"{service_id}/full/max/0/default.webp",
                                    "type": "Image",
                                    "format": "image/webp",
                                    "width": width,
                                    "height": height,
                                    "service": [service],
                                },
                            }
                        ],
                    }
                ],
            }
        )

    return {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "id": f"{base_url}/manifest",
        "type": "Manifest",
        "label": {"fr": [document.title]},
        "viewingDirection": "left-to-right",
        "behavior": ["paged"],
        "items": canvases,
    }


def _page_image_info(page: DocumentPage) -> dict | None:
    """`info.json` d'une page, ou `None` si elle n'est pas tuilée."""
    from document_ingestion.iiif import tiles_root

    try:
        with open_stream(f"{tiles_root(page)}/info.json") as handle:
            return json.loads(handle.read())
    except Exception:
        return None


def get_reader_page_tile_key(
    *,
    session: ReaderSession,
    page_number: int,
    region: str,
    size: str,
    rotation: str,
    quality: str,
    image_format: str,
    at=None,
) -> str:
    """Clé de stockage d'une tuile, sous les mêmes conditions que le texte.

    La clé n'est pas fabriquée à partir de ce que le client envoie : elle est
    reconstruite par `tile_storage_key`, qui n'accepte que les quatre
    composantes de l'Image API. Concaténer un chemin reçu permettrait à un
    `../` de sortir de l'arborescence de la page.

    Seules la rotation `0` et la qualité `default` existent au niveau 0 : les
    annoncer autrement ferait chercher au visualiseur un objet qui n'a jamais
    été produit.
    """
    from document_ingestion.iiif import UnknownTile, tile_storage_key, tiles_root

    at = at or timezone.now()
    page = _authorized_page(session, page_number, at)

    if rotation != "0" or quality != "default" or image_format != "webp":
        raise ReaderPageUnavailable("Only 0/default.webp exists at level 0")

    try:
        storage_key = tile_storage_key(tiles_root(page), region, size)
    except UnknownTile as exc:
        raise ReaderPageUnavailable(str(exc)) from exc
    _record_page_access(session=session, page=page, at=at)
    return storage_key


def get_reader_page_image_info(
    *, session: ReaderSession, page_number: int, identifier: str, at=None
) -> dict:
    """`info.json` de la page, avec l'identifiant que le client doit utiliser.

    L'identifiant est passé par la couche API : c'est elle qui connaît l'URL
    publique, et le service en sert deux — la surface JWT et celle à session
    Django — dont les espaces d'adresses diffèrent.
    """
    from document_ingestion.iiif import tiles_root

    at = at or timezone.now()
    page = _authorized_page(session, page_number, at)

    try:
        with open_stream(f"{tiles_root(page)}/info.json") as handle:
            info = json.loads(handle.read())
    except Exception as exc:
        # Une page traitée avant le tuilage, ou dont le rendu a échoué : pas
        # d'information, et surtout pas d'erreur serveur — le lecteur doit
        # pouvoir retomber sur le texte.
        raise ReaderPageUnavailable("Page has no tiled image") from exc

    info["id"] = identifier
    _record_page_access(session=session, page=page, at=at)
    return info


def get_reader_page_thumbnail(*, session: ReaderSession, page_number: int, at=None):
    """La vignette d'une page : pour se repérer, pas pour lire.

    Même autorisation que l'image — `_authorized_page`, donc session vivante et
    droit de lecture valide au moment de la demande. Mais **aucune écriture au
    journal d'accès**, et c'est délibéré.

    Ouvrir un volet de miniatures sur un cours de 157 pages y inscrirait sinon
    157 pages lues : les rapports d'usage institutionnels compteraient des pages
    que personne n'a lues, et l'historique du lecteur dirait qu'il a parcouru un
    document qu'il a seulement ouvert. Une vignette de 120 px de large est de la
    navigation ; la lecture, c'est la page.

    L'arbitrage appartient au produit, pas au code : il a été posé le
    02/10/2026, parce qu'il touche à ce que la plateforme promet aux
    établissements et aux déposants. La porte reste gardée — ce qui n'est pas
    enregistré est la *trace*, jamais le droit.
    """
    at = at or timezone.now()
    page = _authorized_page(session, page_number, at)

    asset = (
        DocumentAsset.objects.filter(page=page, asset_type=DocumentAsset.AssetType.COVER)
        .order_by("id")
        .first()
    )
    if asset is None:
        # Une page sans vignette : le volet affiche son numéro, et le lecteur
        # garde toutes ses autres façons d'y aller.
        raise ReaderPageUnavailable("Page has no thumbnail")

    return asset


def get_reader_page_image(*, session: ReaderSession, page_number: int, at=None):
    """Image fidèle d'une page, sous les mêmes conditions que son texte.

    L'image est produite à chaque ingestion et n'était jamais servie : le
    lecteur rendait du texte à plat, et un mémoire y perdait ses titres, ses
    tableaux, ses figures et ses formules.

    L'autorisation n'est pas réécrite ici. C'est `_ensure_reader_session_can_read`,
    la même fonction que pour le texte : une session vivante et un droit de
    lecture valide au moment de la demande. Une seconde écriture de cette règle
    finirait par diverger, et c'est l'image — le contenu lui-même — qui serait
    du mauvais côté.
    """
    at = at or timezone.now()
    page = _authorized_page(session, page_number, at)

    asset = (
        DocumentAsset.objects.filter(page=page, asset_type=DocumentAsset.AssetType.PAGE_IMAGE)
        .order_by("id")
        .first()
    )
    if asset is None:
        # Une page traitée dont le rendu manque : pas d'image, et surtout pas
        # d'erreur serveur. Le lecteur retombe sur le texte.
        raise ReaderPageUnavailable("Page has no rendered image")

    _record_page_access(session=session, page=page, at=at)
    return asset
