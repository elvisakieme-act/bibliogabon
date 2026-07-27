Les 5 Piliers du Backend
Pour concevoir BiblioGabon, votre backend devra orchestrer les services suivants :

1. Le Pipeline d'Ingestion (Traitement Asynchrone)
Quand un éditeur ou un administrateur upload un livre (PDF ou EPUB), le fichier brut ne doit jamais être exposé.

Stockage brut : Le fichier est stocké de manière sécurisée (sur Amazon S3, MinIO, etc.).

File d'attente (Message Broker) : Un système comme RabbitMQ ou Redis prend le relais pour éviter de bloquer le serveur web. Des processus en arrière-plan (workers) s'occupent de traiter le fichier.

Découpage : Le backend découpe le document page par page et les convertit (souvent en images compressées, en WebP ou en SVG) pour un affichage rapide sur mobile.

Extraction (OCR) : Le texte brut de chaque page est extrait pour alimenter la base de recherche.

2. Le Serveur de Streaming et la Protection (DRM)
L'objectif est d'empêcher un utilisateur de récupérer le livre complet avec un simple script.

API de Pagination : L'interface de lecture ne demande pas "le livre", elle demande GET /api/documents/{id}/pages/12.

Tokens Éphémères : Chaque requête pour lire une page doit générer une URL signée avec une durée de vie très courte (ex: 5 minutes).

Contrôle des Sessions : Le backend doit vérifier à chaque requête si l'abonnement est actif et limiter le nombre d'appareils simultanés pour empêcher le partage abusif de comptes.

3. Le Moteur de Recherche (Full-Text)
Pour des documents universitaires, les étudiants chercheront des concepts à l'intérieur des livres. Une base de données relationnelle classique montre vite ses limites sur ce point.

Indexation : Le texte extrait lors de l'ingestion est envoyé vers un moteur dédié (comme Elasticsearch ou Meilisearch).

Recherche profonde : Cela permet des recherches textuelles ultra-rapides, la tolérance aux fautes de frappe, et surtout la capacité de renvoyer l'utilisateur directement à la bonne page du document.

4. L'Orchestration des Paiements (Mobile Money)
C'est le cœur de la monétisation en Afrique francophone, mais les API des opérateurs (Airtel, Moov, etc.) sont souvent lentes et asynchrones.

États stricts : Votre base de données doit gérer des statuts de transaction précis (EN_ATTENTE, SUCCÈS, ÉCHEC, EXPIRÉ).

Webhooks : C'est l'opérateur (ou l'agrégateur de paiement) qui enverra une requête HTTP POST à votre backend pour lui confirmer que l'étudiant a bien validé le code USSD sur son téléphone. Le système doit être conçu pour écouter et traiter ces confirmations de manière sécurisée.