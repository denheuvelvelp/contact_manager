#!/usr/bin/env bash
# ==============================================================================
# Setup script voor Google Cloud Platform (Cloud Run, Firestore & Artifact Registry)
# Voer dit script uit in Google Cloud Shell (in je browser) of een machine met gcloud.
# ==============================================================================

set -euo pipefail

echo "=========================================================="
echo " Google Cloud Setup voor Huismeester Contactmanager"
echo "=========================================================="

# 1. Bepaal of project is geselecteerd
PROJECT_ID=$(gcloud config get-value project 2>/dev/null || true)

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
    echo "Fout: Geen actief Google Cloud project geselecteerd."
    echo "Voer eerst uit: gcloud config set project JOUW-PROJECT-ID"
    exit 1
fi

echo "Actief Google Cloud Project: $PROJECT_ID"
REGION="europe-west4" # Eemshaven, Nederland (laagste latency + EU AVG/GDPR)

echo ""
echo "[1/5] Vereiste Google Cloud APIs inschakelen..."
gcloud services enable \
    run.googleapis.com \
    firestore.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    firebase.googleapis.com \
    --project="$PROJECT_ID"

echo ""
echo "[2/5] Artifact Registry repository aanmaken (Docker images)..."
if ! gcloud artifacts repositories describe contact-manager --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
    gcloud artifacts repositories create contact-manager \
        --repository-format=docker \
        --location="$REGION" \
        --description="Docker repository voor Contactmanager" \
        --project="$PROJECT_ID"
    echo "Artifact Registry repository 'contact-manager' aangemaakt."
else
    echo "Artifact Registry repository 'contact-manager' bestaat al."
fi

echo ""
echo "[3/5] Cloud Firestore database controleren..."
if ! gcloud firestore databases describe --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "Firestore database wordt aangemaakt in $REGION..."
    gcloud firestore databases create --location="$REGION" --type=firestore-native --project="$PROJECT_ID"
else
    echo "Firestore database is al actief."
fi

echo ""
echo "[4/5] GitHub Actions Service Account aanmaken..."
SA_NAME="github-deployer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$SA_NAME" \
        --display-name="GitHub Actions Deployer" \
        --project="$PROJECT_ID"
    echo "Service Account $SA_EMAIL aangemaakt."
else
    echo "Service Account $SA_EMAIL bestaat al."
fi

echo ""
echo "[5/5] Rechten toekennen aan Service Account..."
ROLES=(
    "roles/run.admin"
    "roles/artifactregistry.writer"
    "roles/iam.serviceAccountUser"
    "roles/datastore.user"
)

for role in "${ROLES[@]}"; do
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="$role" \
        --condition=None \
        --quiet >/dev/null
    echo "Rol toegekend: $role"
done

# Sleutel genereren voor GitHub Secrets
KEY_FILE="github-actions-sa-key.json"
echo ""
echo "Sleutel genereren voor GitHub Secrets ($KEY_FILE)..."
gcloud iam service-accounts keys create "$KEY_FILE" \
    --iam-account="$SA_EMAIL" \
    --project="$PROJECT_ID"

echo ""
echo "=========================================================="
echo " SETUP VOLTOOID!"
echo "=========================================================="
echo "Voeg nu de volgende 2 secrets toe in jouw GitHub repository:"
echo "(Ga naar: Settings -> Secrets and variables -> Actions -> New repository secret)"
echo ""
echo "1. GCP_PROJECT_ID:"
echo "   $PROJECT_ID"
echo ""
echo "2. GCP_SA_KEY:"
echo "   Kopieer de volledige inhoud van het bestand: $KEY_FILE"
echo ""
echo "Daarna zal elke push naar 'main' de applicatie automatisch deployen naar Cloud Run!"
echo "=========================================================="
