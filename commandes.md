# Pour les commandes d'analyse IaC avec Trivy

D'abord on extrait le fichier YAML du code IaC pour les fichiers VPC et S3:

```bash
cd IaC/
python vpc.py > ../yaml/vpc.yaml
python s3_bucket.py > ../yaml/s3_bucket.yaml
cd ..
```

Ensuite, on exécute Trivy pour analyser les fichiers YAML extraits:

```bash
trivy config --format json -o json/trivy_vpc.json yaml/vpc.yaml
trivy config --format json -o json/trivy_s3.json yaml/s3_bucket.yaml
```

Pour filtrer les vulnérabilités de haute sévérité, on utilise `jq` avec le script `filter.jq`:

```bash
jq -f filter.jq json/trivy_vpc.json > json/trivy_vpc_high_severity.json
jq -f filter.jq json/trivy_s3.json > json/trivy_s3_high_severity.json
```

Pour déployer l'architecture AWS, on utilise AWS CLI:
